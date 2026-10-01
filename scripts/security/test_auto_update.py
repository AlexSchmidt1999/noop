import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

import auto_update


class AutoUpdateSafetyTests(unittest.TestCase):
    def test_only_version_changes_can_refresh_the_source_baseline(self):
        before = '  MARKETING_VERSION: "11.8.0"\n  CURRENT_PROJECT_VERSION: "415"\n  CODE_SIGNING_ALLOWED: NO\n'
        version = '  MARKETING_VERSION: "11.9.0"\n  CURRENT_PROJECT_VERSION: "416"\n  CODE_SIGNING_ALLOWED: NO\n'
        changed_setting = version.replace('CODE_SIGNING_ALLOWED: NO', 'CODE_SIGNING_ALLOWED: YES')
        self.assertTrue(auto_update.policy_allows_auto(["scripts: changed: project.yml"], before, version))
        self.assertFalse(auto_update.policy_allows_auto(["scripts: changed: project.yml"], before, changed_setting))
        self.assertFalse(auto_update.policy_allows_auto(["scripts: changed: project.yml", "capabilities: added: HealthKit"], before, version))

    def test_only_the_exact_candidate_run_can_be_promoted(self):
        runs = [
            {"id": 8, "head_sha": "right", "head_branch": "main", "event": "workflow_dispatch"},
            {"id": 9, "head_sha": "wrong", "head_branch": "codex/auto-upstream-release", "event": "workflow_dispatch"},
            {"id": 10, "head_sha": "right", "head_branch": "codex/auto-upstream-release", "event": "push"},
            {"id": 7, "head_sha": "right", "head_branch": "codex/auto-upstream-release", "event": "workflow_dispatch"},
        ]
        self.assertEqual(auto_update.matching_run(runs, "codex/auto-upstream-release", "right")["id"], 7)
        self.assertIsNone(auto_update.matching_run(runs, "codex/auto-upstream-release", "missing"))

    def test_scheduled_check_never_promotes_a_green_candidate(self):
        green = {"id": 7, "status": "completed", "conclusion": "success"}
        with patch.object(auto_update, "workflow_run", return_value=green), \
             patch.object(auto_update, "promote_candidate") as promote:
            auto_update.inspect_pending_candidate("candidate-sha")
        promote.assert_not_called()

    def test_scheduled_check_does_not_scan_unchanged_main(self):
        with patch.object(auto_update, "prepare_candidate") as prepare, \
             patch.object(auto_update, "dispatch") as dispatch:
            auto_update.prepare_if_new_release("v11.8.0", "v11.8.0")
        prepare.assert_not_called()
        dispatch.assert_not_called()

    def test_manual_promotion_rejects_a_different_run(self):
        run = {
            "id": 7, "head_sha": "candidate-sha", "head_branch": auto_update.BRANCH,
            "event": "workflow_dispatch", "repository": {"full_name": auto_update.REPO},
            "path": f".github/workflows/{auto_update.WORKFLOW}@candidate-sha",
            "status": "completed", "conclusion": "success",
        }
        auto_update.verify_candidate_run("candidate-sha", run)
        for field, value in (("head_sha", "other-sha"), ("head_branch", "main"),
                             ("event", "push"), ("path", ".github/workflows/other.yml"),
                             ("status", "in_progress"), ("conclusion", "failure")):
            with self.subTest(field=field):
                changed = {**run, field: value}
                with self.assertRaises(RuntimeError):
                    auto_update.verify_candidate_run("candidate-sha", changed)

    def test_pinned_current_waits_for_its_exact_green_run(self):
        sha = "a" * 40
        run = {
            "head_sha": sha, "head_branch": "main", "event": "workflow_dispatch",
            "repository": {"full_name": auto_update.REPO},
            "path": f".github/workflows/{auto_update.WORKFLOW}@{sha}",
            "status": "in_progress", "conclusion": None,
        }
        with tempfile.TemporaryDirectory() as temp:
            pin = Path(temp) / "pending.json"
            pin.write_text(json.dumps({"run_id": 123, "commit": sha}))
            calls = []

            def fake_command(*args, **_):
                calls.append(args)
                return SimpleNamespace(stdout=json.dumps(run) if args[0] == "gh" else "")

            with patch.object(auto_update, "PENDING_CURRENT", pin), patch.object(auto_update, "command", side_effect=fake_command):
                auto_update.cache_approved_current()
                self.assertTrue(pin.exists())
                self.assertEqual(len(calls), 1)
                run["status"], run["conclusion"] = "completed", "success"
                run["head_sha"] = "b" * 40
                with self.assertRaises(RuntimeError):
                    auto_update.cache_approved_current()
                self.assertTrue(pin.exists())
                run["head_sha"] = sha
                auto_update.cache_approved_current()
                self.assertFalse(pin.exists())
                self.assertEqual(calls[-1][:3], ("python3", "scripts/security/install-analyzed-ios.py", "--approve-run"))


if __name__ == "__main__":
    unittest.main()
