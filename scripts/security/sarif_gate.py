#!/usr/bin/env python3
"""Fail on serious SARIF findings; parse scanner output locally."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def severity(result, rules):
    rule = rules.get(result.get("ruleId"), {})
    props = rule.get("properties", {})
    score = props.get("security-severity")
    level = result.get("level", rule.get("defaultConfiguration", {}).get("level"))
    return (score is not None and float(score) >= 7.0) or level == "error"


def finding_locations(result):
    locations = set()
    def visit(value):
        if isinstance(value, dict):
            loc = value.get("physicalLocation", {})
            uri = loc.get("artifactLocation", {}).get("uri")
            if uri:
                region = loc.get("region", {})
                locations.add((uri, region.get("startLine", 0), region.get("startColumn", 0)))
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    visit(result)
    return sorted(locations)


def finding_fingerprint(result, rules):
    rule = rules.get(result.get("ruleId"), {})
    identity = {
        "rule": result.get("ruleId"),
        "level": result.get("level", rule.get("defaultConfiguration", {}).get("level")),
        "security_severity": rule.get("properties", {}).get("security-severity"),
        "locations": finding_locations({"locations": result.get("locations", []),
                                        "relatedLocations": result.get("relatedLocations", [])}),
    }
    return hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()


def source_hashes(result, root):
    hashes = {}
    for uri, _, _ in finding_locations(result):
        path = (root / uri).resolve()
        try:
            path.relative_to(root.resolve())
            hashes[uri] = hashlib.sha256(path.read_bytes()).hexdigest()
        except (OSError, ValueError):
            return {}
    return hashes


def reviewed_finding(result, rules, reviews, root):
    fingerprint = finding_fingerprint(result, rules)
    for review in reviews:
        if review["fingerprint"] == fingerprint:
            hashes = source_hashes(result, root)
            if hashes and hashes == review["source_sha256"]:
                return review
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("directory", type=Path)
    ap.add_argument("--report", type=Path, required=True)
    ap.add_argument("--reviewed-findings", type=Path)
    args = ap.parse_args()
    reviews = []
    if args.reviewed_findings:
        policy = json.loads(args.reviewed_findings.read_text())
        if policy["schema_version"] != 1:
            raise ValueError("Unsupported reviewed-finding schema")
        reviews = policy["findings"]
    paths = sorted(args.directory.rglob("*.sarif"))
    if not paths:
        raise SystemExit("CodeQL produced no SARIF")
    hits = []
    reviewed = []
    for path in paths:
        data = json.loads(path.read_text())
        for run in data.get("runs", []):
            tool = run.get("tool", {})
            components = [tool.get("driver", {}), *tool.get("extensions", [])]
            rules = {r.get("id"): r for component in components for r in component.get("rules", [])}
            for result in run.get("results", []):
                if severity(result, rules):
                    loc = result.get("locations", [{}])[0].get("physicalLocation", {})
                    finding = {"rule": result.get("ruleId"), "file": loc.get("artifactLocation", {}).get("uri"), "line": loc.get("region", {}).get("startLine")}
                    review = reviewed_finding(result, rules, reviews, ROOT)
                    if review:
                        reviewed.append({**finding, "review": review["id"], "reason": review["reason"]})
                    else:
                        hits.append(finding)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps({"status": "FAIL" if hits else "PASS", "serious_findings": hits, "reviewed_findings": reviewed}, indent=2) + "\n")
    print(f"SARIF: {len(hits)} unreviewed HIGH/CRITICAL or error findings; {len(reviewed)} reviewed")
    if hits:
        raise SystemExit(1)

if __name__ == "__main__":
    main()
