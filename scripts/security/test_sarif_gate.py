import copy
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import policy
import sarif_gate


class SarifGateTests(unittest.TestCase):
    def test_default_error_level_blocks_without_result_level(self):
        rules = {"logging": {"defaultConfiguration": {"level": "error"}}}
        self.assertTrue(sarif_gate.severity({"ruleId": "logging"}, rules))
        self.assertFalse(sarif_gate.severity({"ruleId": "logging", "level": "note"}, rules))

    def test_error_level_blocks_even_below_high_security_score(self):
        rules = {"storage": {"properties": {"security-severity": "6.5"}}}
        self.assertTrue(sarif_gate.severity({"ruleId": "storage", "level": "error"}, rules))
        self.assertFalse(sarif_gate.severity({"ruleId": "storage", "level": "warning"}, rules))

    def test_codeql_extension_metadata_blocks_high_and_default_error_findings(self):
        report = {"runs": [{"tool": {
            "driver": {"rules": []},
            "extensions": [{"rules": [
                {"id": "storage", "properties": {"security-severity": "7.5"}},
                {"id": "logging", "defaultConfiguration": {"level": "error"}},
                {"id": "note", "defaultConfiguration": {"level": "note"}},
            ]}],
        }, "results": [{"ruleId": rule} for rule in ["storage", "logging", "note"]]}]}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "codeql.sarif").write_text(json.dumps(report))
            output = root / "gate.json"
            result = subprocess.run(
                [sys.executable, sarif_gate.__file__, str(root), "--report", str(output)],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 1, result.stderr)
            findings = json.loads(output.read_text())
            self.assertEqual(findings["status"], "FAIL")
            self.assertEqual([r["rule"] for r in findings["serious_findings"]], ["storage", "logging"])


class ReviewedFindingTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        (self.root / "Strand").mkdir()
        (self.root / "Strand/Store.swift").write_text("let stored = sample\n")
        (self.root / "Strand/Source.swift").write_text("let sample = 10\n")
        self.rules = {"storage": {"properties": {"security-severity": "7.5"}}}
        self.result = {
            "ruleId": "storage",
            "locations": [self.location("Strand/Store.swift", 1)],
            "relatedLocations": [self.location("Strand/Source.swift", 1)],
        }
        self.review = {
            "id": "reviewed-storage", "reason": "Explicitly accepted local storage.",
            "fingerprint": sarif_gate.finding_fingerprint(self.result, self.rules),
            "source_sha256": sarif_gate.source_hashes(self.result, self.root),
        }

    @staticmethod
    def location(path, line):
        return {"physicalLocation": {"artifactLocation": {"uri": path}, "region": {"startLine": line}}}

    def test_exact_review_is_reported_separately_from_new_findings(self):
        (self.root / "input.sarif").write_text(json.dumps({"runs": [{
            "tool": {"driver": {"rules": [dict(id=key, **rule) for key, rule in self.rules.items()]}},
            "results": [self.result],
        }]}))
        reviewed = self.root / "reviewed.json"
        reviewed.write_text(json.dumps({"schema_version": 1, "findings": [self.review]}))
        output = self.root / "gate.json"
        argv = ["sarif_gate.py", str(self.root), "--report", str(output), "--reviewed-findings", str(reviewed)]
        with patch.object(sarif_gate, "ROOT", self.root), patch.object(sys, "argv", argv), patch("sys.stdout", new=io.StringIO()):
            sarif_gate.main()
        report = json.loads(output.read_text())
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["serious_findings"], [])
        self.assertEqual(report["reviewed_findings"][0]["review"], "reviewed-storage")

    def test_changed_rule_location_or_severity_requires_review(self):
        variants = []
        result = copy.deepcopy(self.result)
        result["ruleId"] = "new-storage"
        variants.append((result, self.rules))
        result = copy.deepcopy(self.result)
        result["locations"][0]["physicalLocation"]["region"]["startLine"] = 2
        variants.append((result, self.rules))
        rules = copy.deepcopy(self.rules)
        rules["storage"]["properties"]["security-severity"] = "9.0"
        variants.append((self.result, rules))
        for result, rules in variants:
            with self.subTest(result=result, rules=rules):
                self.assertIsNone(sarif_gate.reviewed_finding(result, rules, [self.review], self.root))

    def test_changed_source_requires_review(self):
        (self.root / "Strand/Source.swift").write_text("let sample = healthData\n")
        self.assertIsNone(sarif_gate.reviewed_finding(self.result, self.rules, [self.review], self.root))

    def test_new_flow_source_requires_review(self):
        result = copy.deepcopy(self.result)
        result["codeFlows"] = [{"threadFlows": [{"locations": [{
            "location": self.location("Strand/NewSource.swift", 1),
        }]}]}]
        self.assertIsNone(sarif_gate.reviewed_finding(result, self.rules, [self.review], self.root))

    def test_missing_source_pin_cannot_approve_a_finding(self):
        review = copy.deepcopy(self.review)
        del review["source_sha256"]["Strand/Source.swift"]
        self.assertIsNone(sarif_gate.reviewed_finding(self.result, self.rules, [review], self.root))

    def test_outside_source_root_cannot_be_reviewed(self):
        result = {"ruleId": "storage", "locations": [self.location("../outside.swift", 1)]}
        review = {**self.review, "fingerprint": sarif_gate.finding_fingerprint(result, self.rules), "source_sha256": {}}
        self.assertIsNone(sarif_gate.reviewed_finding(result, self.rules, [review], self.root))

    def test_review_policy_is_pinned_by_source_policy(self):
        path = "scripts/security/baselines/codeql-reviewed.json"
        self.assertIn(path, policy.script_inventory([path]))
