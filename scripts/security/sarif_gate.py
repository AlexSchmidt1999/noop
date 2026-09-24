#!/usr/bin/env python3
"""Fail on serious CodeQL SARIF findings; parse scanner output locally."""
import argparse
import json
import sys
from pathlib import Path


def severity(result, rules):
    rule = rules.get(result.get("ruleId"), {})
    props = rule.get("properties", {})
    score = props.get("security-severity")
    if score is not None:
        return float(score) >= 7.0
    return result.get("level") == "error"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("directory", type=Path)
    ap.add_argument("--report", type=Path, required=True)
    args = ap.parse_args()
    paths = sorted(args.directory.rglob("*.sarif"))
    if not paths:
        raise SystemExit("CodeQL produced no SARIF")
    hits = []
    for path in paths:
        data = json.loads(path.read_text())
        for run in data.get("runs", []):
            rules = {r.get("id"): r for r in run.get("tool", {}).get("driver", {}).get("rules", [])}
            for result in run.get("results", []):
                if severity(result, rules):
                    loc = result.get("locations", [{}])[0].get("physicalLocation", {})
                    hits.append({"rule": result.get("ruleId"), "file": loc.get("artifactLocation", {}).get("uri"), "line": loc.get("region", {}).get("startLine")})
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps({"status": "FAIL" if hits else "PASS", "serious_findings": hits}, indent=2) + "\n")
    print(f"CodeQL: {len(hits)} HIGH/CRITICAL or error findings")
    if hits:
        raise SystemExit(1)

if __name__ == "__main__":
    main()
