#!/usr/bin/env python3
"""Inspect an unsigned NOOP device app without executing any bundled content."""
import argparse
import hashlib
import json
import plistlib
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

SIGNABLE = {
    ".": "com.noopapp.noop",
    "PlugIns/NOOPWidgets.appex": "com.noopapp.noop.widgets",
    "Watch/NOOPWatch.app": "com.noopapp.noop.watch",
    "Watch/NOOPWatch.app/PlugIns/NOOPWatchComplications.appex": "com.noopapp.noop.watch.complications",
}
SENSITIVE = re.compile(r"^NS.*UsageDescription$|^UIBackgroundModes$|^NSAppTransportSecurity$|^CFBundleURLTypes$|^NSBonjourServices$|^WKCompanionAppBundleIdentifier$|^NSExtension$|^AppGroupIdentifier$|^BGTaskSchedulerPermittedIdentifiers$|^LSApplicationQueriesSchemes$|^NSSupportsLiveActivities$|^UIFileSharingEnabled$")
URL = re.compile(rb"(?:https?|wss?)://[a-zA-Z0-9._:/?&=%#@+~-]+")


def cmd(*args, check=True):
    p = subprocess.run(args, text=True, capture_output=True)
    if check and p.returncode:
        raise RuntimeError(f"{args[0]} failed: {p.stderr[:300]}")
    return p.stdout.strip()


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def norm(value):
    if isinstance(value, dict):
        return {str(k): norm(v) for k, v in sorted(value.items())}
    if isinstance(value, list):
        return [norm(v) for v in value]
    return value.hex() if isinstance(value, bytes) else value


def expand(value, replacements):
    if isinstance(value, dict):
        return {key: expand(item, replacements) for key, item in value.items()}
    if isinstance(value, list):
        return [expand(item, replacements) for item in value]
    if isinstance(value, str):
        for old, new in replacements.items():
            value = value.replace(old, new)
        if "$(" in value:
            raise ValueError(f"Unresolved sensitive Info.plist variable: {value}")
    return value


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("app", type=Path)
    ap.add_argument("--report", type=Path, required=True)
    ap.add_argument("--source-baseline", type=Path, default=Path("scripts/security/baselines/source.json"))
    args = ap.parse_args()
    app = args.app.resolve()
    if not app.is_dir() or app.name != "NOOP.app":
        raise SystemExit("Expected NOOP.app device build")
    baseline = json.loads(args.source_baseline.read_text())
    source = baseline["capabilities"]
    approved_hosts = set(baseline["endpoints"]["runtime"])
    target_for = {".": "NOOPiOS", "PlugIns/NOOPWidgets.appex": "NOOPiOSWidgets", "Watch/NOOPWatch.app": "NOOPWatch", "Watch/NOOPWatch.app/PlugIns/NOOPWatchComplications.appex": "NOOPWatchComplications"}
    failures = []
    bundles = {}
    expected_executables = set()
    for rel, default_id in SIGNABLE.items():
        bundle = app if rel == "." else app / rel
        if not bundle.is_dir():
            failures.append(f"Missing bundle: {rel}")
            continue
        plist_path = bundle / "Info.plist"
        if not plist_path.is_file():
            failures.append(f"Missing Info.plist: {rel}")
            continue
        info = plistlib.loads(plist_path.read_bytes())
        bundle_id = info.get("CFBundleIdentifier") or ""
        suffix = default_id.removeprefix("com.noopapp")
        if not bundle_id.endswith(suffix):
            failures.append(f"Unexpected bundle ID: {rel}: {bundle_id}")
        prefix = bundle_id.removesuffix(suffix)
        replacements = {"$(BUNDLE_ID_PREFIX)": prefix, "$(PRODUCT_BUNDLE_IDENTIFIER)": bundle_id, "$(APP_GROUP_ID)": f"group.{prefix}.noop.staging"}
        target = source[target_for[rel]]
        expected_info = target["info"]["values"]
        sensitive = {k: norm(v) for k, v in info.items() if SENSITIVE.search(k)}
        for key, value in sensitive.items():
            if key not in expected_info:
                failures.append(f"Unexpected runtime Info.plist key: {rel}: {key}")
            elif norm(expand(expected_info[key], replacements)) != value:
                failures.append(f"Runtime Info.plist differs: {rel}: {key}")
        for key in expected_info:
            if SENSITIVE.search(key) and key not in sensitive:
                failures.append(f"Missing runtime Info.plist key: {rel}: {key}")
        executable = info.get("CFBundleExecutable")
        if not executable or not (bundle / executable).is_file():
            failures.append(f"Missing executable: {rel}: {executable}")
            continue
        exe = bundle / executable
        expected_executables.add(exe.relative_to(app).as_posix())
        signing = subprocess.run(["codesign", "-d", "--entitlements", "-", str(bundle)], capture_output=True)
        if signing.returncode == 0:
            failures.append(f"Unexpected signed component in unsigned build: {rel}")
            effective_entitlements = norm(plistlib.loads(signing.stdout)) if signing.stdout else {}
            signing_state = "signed"
        elif b"code object is not signed at all" in signing.stderr:
            effective_entitlements = {}
            signing_state = "unsigned"
        else:
            failures.append(f"Could not inspect signing state: {rel}")
            effective_entitlements = {}
            signing_state = "unknown"
        bundles[rel] = {"bundle_id": bundle_id, "executable": executable, "executable_sha256": digest(exe), "info": sensitive, "linked_libraries": cmd("otool", "-L", str(exe)).splitlines()[1:], "effective_entitlements": effective_entitlements, "signing_state": signing_state}
    components = []
    macho = []
    urls = {}
    for path in sorted(app.rglob("*")):
        if path.is_symlink():
            target = path.resolve()
            if not target.is_relative_to(app):
                failures.append(f"Symlink escapes app: {path.relative_to(app)}")
            continue
        if path.is_dir():
            if path.suffix in {".appex", ".app", ".framework"}:
                rel = path.relative_to(app).as_posix()
                components.append(rel)
                if rel not in SIGNABLE:
                    failures.append(f"Unexpected signable component: {rel}")
            continue
        rel = path.relative_to(app).as_posix()
        kind = cmd("file", "-b", str(path))
        if "Mach-O" in kind:
            macho.append({"path": rel, "sha256": digest(path), "type": kind})
            if rel not in expected_executables:
                failures.append(f"Unexpected Mach-O executable: {rel}")
            # Supplementary only: strings cannot prove absence of network behaviour.
            for match in URL.findall(cmd("strings", "-a", str(path), check=False).encode(errors="replace")):
                host = urlsplit(match.decode(errors="replace")).hostname
                if host:
                    urls.setdefault(host.lower(), []).append(rel)
        if path.suffix == ".dylib":
            failures.append(f"Unexpected dylib: {rel}")
    for host in sorted(urls.keys() - approved_hosts):
        failures.append(f"Unreviewed binary URL host: {host}")
    manifest = {"bundles": bundles, "components": components, "macho": macho, "binary_urls": {k: sorted(set(v)) for k, v in sorted(urls.items())}, "failures": failures, "status": "FAIL" if failures else "PASS"}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    for failure in failures:
        print(failure, file=sys.stderr)
    print(f"Binary policy {manifest['status']}: {len(bundles)} bundles, {len(macho)} Mach-O files")
    if failures:
        raise SystemExit(1)

if __name__ == "__main__":
    main()
