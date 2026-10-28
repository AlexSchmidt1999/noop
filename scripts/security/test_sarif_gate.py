import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

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
