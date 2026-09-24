#!/usr/bin/env python3
"""Fail closed on new serious findings in the full MobSF iOS binary report."""

import argparse
import hashlib
import json
from pathlib import Path
import plistlib


REVIEWED_ATS_FINDING = "Insecure local networking is allowed"


def check(report, bundle_id, ipa=None):
    failures = []
    if report.get("version") != "v4.5.2":
        failures.append("Unexpected MobSF scanner version")
    if report.get("bundle_id") != bundle_id or report.get("file_name") != "NOOP-unsigned.ipa":
        failures.append("Wrong app identity in MobSF report")
    if ipa and report.get("sha256") != hashlib.sha256(ipa.read_bytes()).hexdigest():
        failures.append("MobSF report does not describe the scanned IPA")

    try:
        info = plistlib.loads(report["info_plist"].encode())
        local_networking = info["NSAppTransportSecurity"]["NSAllowsLocalNetworking"] is True
        appsec = report["appsec"]
        ats = report["ats_analysis"]["ats_findings"]
        binary = report["binary_analysis"]["findings"]
        code = report["code_analysis"]["findings"]
        macho = report["macho_analysis"]
        domains = report["domains"]
        trackers = report["trackers"]
        secrets = report["secrets"]
        if not isinstance(appsec["high"], list) or not isinstance(ats, list):
            raise ValueError("Malformed high findings")
        if not isinstance(binary, dict) or not isinstance(code, dict) or not isinstance(macho, dict) or not isinstance(domains, dict):
            raise ValueError("Malformed scan findings")
        if not isinstance(secrets, list) or not isinstance(trackers["trackers"], list):
            raise ValueError("Malformed secret or tracker findings")
    except (KeyError, TypeError, ValueError, plistlib.InvalidFileException) as error:
        failures.append(f"Incomplete MobSF report: {error}")
        return failures

    allowed = (
        local_networking
        and len(ats) == 1
        and isinstance(ats[0], dict)
        and ats[0].get("issue") == REVIEWED_ATS_FINDING
        and ats[0].get("severity") == "high"
        and len(appsec["high"]) == 1
        and isinstance(appsec["high"][0], dict)
        and appsec["high"][0].get("title") == REVIEWED_ATS_FINDING
    )
    if not allowed:
        failures.append("Unexpected high MobSF finding or changed local-network exception")
    for section, findings in (("binary", binary), ("code", code), ("Mach-O", macho)):
        for title, finding in findings.items():
            if isinstance(finding, dict) and finding.get("severity", "").lower() in {"high", "critical"}:
                failures.append(f"Serious {section} finding: {title}")
    if any(not isinstance(result, dict) or result.get("bad") != "no" for result in domains.values()):
        failures.append("Unknown or malicious domain in MobSF report")
    if trackers.get("detected_trackers") != 0 or trackers["trackers"]:
        failures.append("Tracker detected in MobSF report")
    if secrets:
        failures.append("Potential secret detected in MobSF report")
    return failures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--bundle-id", required=True)
    parser.add_argument("--ipa", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    failures = check(json.loads(args.report.read_text()), args.bundle_id, args.ipa)
    result = {"status": "FAIL" if failures else "PASS", "failures": failures}
    if args.output:
        args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
