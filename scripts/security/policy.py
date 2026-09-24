#!/usr/bin/env python3
"""Reviewable source capabilities and executable-surface policy for NOOP."""
import argparse
import hashlib
import json
import os
import plistlib
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "scripts/security/baselines/source.json"
RUNTIME_DIRS = ("Strand/", "StrandiOS/", "StrandiOSShared/", "StrandiOSWidgets/", "NOOPWatch/", "NOOPWatchComplications/", "Packages/")
SCRIPT_EXTS = {".sh", ".py", ".rb", ".js", ".mjs", ".cjs", ".command", ".xcconfig"}
URL = re.compile(r"\b(?:https?|wss?)://[^\s\"'<>\\)]+", re.I)
DOMAIN = re.compile(r"(?<![\w.-])(?:[a-z0-9-]+\.)+[a-z]{2,}(?![\w.-])", re.I)
IP = re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])")
NETWORK_CONTEXT = re.compile(r"url|endpoint|host|server|socket|domain|request|session|network", re.I)
SCRIPT_RISK = re.compile(r"\b(curl|wget|eval|base64|security|codesign|xcodebuild|ssh|scp|nc|osascript)\b|\$\{|\$\(|/\.ssh|/\.aws|keychain|secret|token|password|http[s]?://", re.I)


def run(*args):
    return subprocess.check_output(args, cwd=ROOT, text=True)


def files():
    names = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=ROOT).decode().split("\0")
    return sorted(p for p in names if p and (ROOT / p).is_file())


def sha(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def normalize(value):
    if isinstance(value, dict):
        return {str(k): normalize(v) for k, v in sorted(value.items())}
    if isinstance(value, list):
        return [normalize(v) for v in value]
    if isinstance(value, (bytes, bytearray)):
        return value.hex()
    return value


def project():
    # Ruby's bundled Psych parses XcodeGen YAML; safe_load never constructs arbitrary objects.
    code = 'require "yaml"; require "json"; p=YAML.safe_load(File.read("project.yml"), aliases: true); puts JSON.generate(p.fetch("targets"))'
    return json.loads(run("ruby", "-e", code))


def source_capabilities(targets):
    result = {}
    for name, target in sorted(targets.items()):
        entry = {}
        for kind in ("entitlements", "info"):
            config = target.get(kind) or {}
            path = config.get("path")
            content = plistlib.loads((ROOT / path).read_bytes()) if path else {}
            content.update(config.get("properties") or {})
            entry[kind] = {"path": path, "values": normalize(content)}
        entry["bundle_id"] = (target.get("settings") or {}).get("base", {}).get("PRODUCT_BUNDLE_IDENTIFIER")
        result[name] = entry
    return result


def endpoints(paths):
    result = {"runtime": {}, "build": {}}
    for path in paths:
        runtime = path.startswith(RUNTIME_DIRS) and (path.endswith(".swift") or path.endswith(".plist"))
        build = path == "project.yml" or path.startswith(".github/workflows/") or Path(path).suffix in SCRIPT_EXTS
        if not runtime and not build:
            continue
        kind = "runtime" if runtime else "build"
        try:
            content = (ROOT / path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line_number, line in enumerate(content.splitlines(), 1):
            hosts = set()
            for match in URL.finditer(line):
                host = urlsplit(match.group(0).rstrip(".,;)")).hostname
                if host:
                    hosts.add(host.lower())
            if NETWORK_CONTEXT.search(line):
                # Bare host literals must be quoted; otherwise Python/Swift member names
                # such as urls.items and URLSession.shared become false endpoints.
                for literal in re.findall(r"['\"]([^'\"\n]+)['\"]", line):
                    literal = re.sub(r"\\\([^)]*\)", "*", literal)  # Ignore Swift interpolation expressions.
                    hosts.update(h.lower() for h in DOMAIN.findall(literal))
                    hosts.update(IP.findall(literal))
            for host in hosts:
                # Include origins in reports, not in the approved set: moving a URL still reports via git diff.
                result[kind].setdefault(host, []).append(f"{path}:{line_number}")
    return {kind: {host: sorted(set(origins)) for host, origins in sorted(items.items())} for kind, items in result.items()}


def script_inventory(paths):
    result = {}
    for path in paths:
        p = Path(path)
        if path in {"project.yml", ".gitleaksignore", ".github/CODEOWNERS", ".github/dependabot.yml"} or path.startswith(".github/workflows/") or p.suffix in SCRIPT_EXTS or os.access(ROOT / path, os.X_OK) and p.suffix not in {".swift", ".kt"}:
            result[path] = sha(path)
    return result


def snapshot():
    paths = files()
    locks = {p: sha(p) for p in paths if p.endswith("Package.resolved") or p.endswith("Package.swift")}
    executable = sorted(p for p in paths if os.access(ROOT / p, os.X_OK) and not p.startswith(".git/"))
    return {"capabilities": source_capabilities(project()), "endpoints": endpoints(paths), "scripts": script_inventory(paths), "dependencies": locks, "executables": executable}


def changes(old, new):
    output = {}
    for category in ("capabilities", "scripts", "dependencies"):
        a, b = old[category], new[category]
        output[category] = {"added": sorted(b.keys() - a.keys()), "removed": sorted(a.keys() - b.keys()), "changed": sorted(k for k in a.keys() & b.keys() if a[k] != b[k])}
    a, b = set(old["executables"]), set(new["executables"])
    output["executables"] = {"added": sorted(b-a), "removed": sorted(a-b)}
    output["endpoints"] = {}
    for kind in ("runtime", "build"):
        a, b = old["endpoints"][kind], new["endpoints"][kind]
        output["endpoints"][kind] = {"added": {k: b[k] for k in sorted(b.keys()-a.keys())}, "removed": sorted(a.keys()-b.keys())}
    output["capability_keys"] = {}
    for target in sorted(old["capabilities"].keys() & new["capabilities"].keys()):
        details = {}
        for kind in ("entitlements", "info"):
            a = old["capabilities"][target][kind]["values"]
            b = new["capabilities"][target][kind]["values"]
            diff = {"added": sorted(b.keys() - a.keys()), "removed": sorted(a.keys() - b.keys()), "changed": sorted(k for k in a.keys() & b.keys() if a[k] != b[k])}
            if any(diff.values()):
                details[kind] = diff
        if old["capabilities"][target]["bundle_id"] != new["capabilities"][target]["bundle_id"]:
            details["bundle_id_changed"] = True
        if details:
            output["capability_keys"][target] = details
    return output


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=("check", "snapshot"))
    ap.add_argument("--report", type=Path)
    ap.add_argument("--base-ref")
    args = ap.parse_args()
    current = snapshot()
    if args.command == "snapshot":
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
        print(f"Wrote review baseline: {BASELINE}")
        return
    old = json.loads(BASELINE.read_text())
    delta = changes(old, current)
    failures = []
    for category in ("capabilities", "scripts", "dependencies"):
        for disposition in ("added", "removed", "changed"):
            failures += [f"{category}: {disposition}: {x}" for x in delta[category][disposition]]
    failures += [f"executable: added: {x}" for x in delta["executables"]["added"]]
    for kind in ("runtime", "build"):
        failures += [f"{kind} endpoint: added: {host} ({', '.join(origins[:5])})" for host, origins in delta["endpoints"][kind]["added"].items()]
    if args.base_ref:
        changed = run("git", "diff", "--name-status", f"{args.base_ref}...HEAD", "--", "Packages", "Strand", "StrandiOS", "StrandiOSShared", "StrandiOSWidgets", "NOOPWatch", "NOOPWatchComplications", "project.yml", ".github", "scripts/security")
        delta["upstream_diff"] = changed.splitlines()
        delta["sensitive_swift_files"] = [line for line in changed.splitlines() if line.endswith(".swift") and re.search(r"BLE|Health|Network|Keychain|Bluetooth|Export|Telemetry|Sync|Session", line, re.I)]
    risk = {}
    for path in delta["scripts"]["added"] + delta["scripts"]["changed"]:
        matches = []
        for n, line in enumerate((ROOT / path).read_text(errors="replace").splitlines(), 1):
            if SCRIPT_RISK.search(line):
                matches.append(f"{path}:{n}: sensitive build-script pattern")
        risk[path] = matches[:30]
    delta["script_risk_lines"] = risk
    delta["status"] = "FAIL" if failures else "PASS"
    delta["failures"] = failures
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(delta, indent=2, sort_keys=True) + "\n")
    for item in failures:
        print(item)
    if not failures:
        print("Source policy PASS: capabilities, endpoints, scripts, dependencies, executables")
    else:
        print("Update the tracked baseline only after reviewing the diff; see docs/SECURITY_PIPELINE.md", file=sys.stderr)
        raise SystemExit(1)

if __name__ == "__main__":
    main()
