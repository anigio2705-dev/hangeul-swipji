"""Regression: historical Render success must not unlock staging99 redeploy."""
import json
import tempfile
import unittest
from pathlib import Path

from automation.staging99_redeploy_guard import ROOT, inspect, SERVICE_ID


class Staging99RedeployGuardTests(unittest.TestCase):
    def test_actual_repository_fails_closed(self):
        r = inspect(ROOT)
        self.assertFalse(r["safeToRedeploy"])
        self.assertFalse(r["historicalDeployIsCurrent"])
        self.assertIn("EPHEMERAL_SQLITE_DATA_LOSS", r["blockers"])
        self.assertIn("FREE_PLAN_NO_PERSISTENT_DISK", r["blockers"])
        self.assertIn("BACKUP_AND_RESTORE_UNVERIFIED", r["blockers"])
        self.assertEqual(SERVICE_ID, r["serviceId"])

    def fixture(self, yaml, service_id=SERVICE_ID):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        (root / "deploy").mkdir()
        (root / "audit").mkdir()
        (root / "deploy/render-staging.yaml").write_text(yaml, encoding="utf-8")
        (root / "audit/staging99-deployment.json").write_text(json.dumps({
            "serviceId": service_id,
            "deployedCommit": "a" * 40,
            "statusObserved": "Live",
        }), encoding="utf-8")
        self.addCleanup(temp.cleanup)
        return root

    def test_even_historical_live_sha_is_not_current_proof(self):
        root = self.fixture("plan: free\nautoDeployTrigger: 'off'\nvalue: /tmp/db.sqlite3\n")
        r = inspect(root)
        self.assertEqual("a" * 40, r["historicalDeploySHA"])
        self.assertFalse(r["historicalDeployIsCurrent"])
        self.assertFalse(r["safeToRedeploy"])

    def test_even_proposed_persistent_disk_does_not_prove_real_mount(self):
        root = self.fixture("plan: starter\nautoDeployTrigger: 'off'\nvalue: /var/data/hangeul-swipji-staging/platform.sqlite3\n")
        r = inspect(root)
        self.assertNotIn("EPHEMERAL_SQLITE_DATA_LOSS", r["blockers"])
        self.assertNotIn("FREE_PLAN_NO_PERSISTENT_DISK", r["blockers"])
        self.assertIn("PERSISTENT_MOUNT_UNVERIFIED", r["blockers"])
        self.assertFalse(r["safeToRedeploy"])

    def test_autodeploy_enabled_is_blocked(self):
        root = self.fixture("plan: starter\nautoDeployTrigger: on\nvalue: /var/data/hangeul-swipji-staging/platform.sqlite3\n")
        self.assertIn("AUTODEPLOY_NOT_DISABLED", inspect(root)["blockers"])

    def test_wrong_service_id_is_blocked(self):
        root = self.fixture("plan: starter\nautoDeployTrigger: 'off'\nvalue: /var/data/hangeul-swipji-staging/platform.sqlite3\n", "wrong")
        self.assertIn("SERVICE_ID_NOT_CONFIRMED", inspect(root)["blockers"])

    def test_missing_database_path_is_blocked(self):
        root = self.fixture("plan: free\nautoDeployTrigger: 'off'\n")
        self.assertIn("SQLITE_PATH_NOT_PROVEN", inspect(root)["blockers"])


if __name__ == "__main__":
    unittest.main()
