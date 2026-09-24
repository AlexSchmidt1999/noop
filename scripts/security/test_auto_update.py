import unittest

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


if __name__ == "__main__":
    unittest.main()
