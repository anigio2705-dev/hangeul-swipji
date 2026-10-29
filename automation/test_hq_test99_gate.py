"""Independent negative controls for the test99 acceptance gate."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hq_test99_gate import TEST99, PRODUCTION, acceptance_gate, static_evidence


class Test99Acceptance(unittest.TestCase):
    def setUp(self):
        self.base = static_evidence()
        self.good = dict(self.base, health_status=200, health_mode="test",
                         health_scope="isolated-staging",
                         hosted_source_sha256=self.base["local_staging_source_sha256"],
                         verified_deploy_sha="a" * 40,
                         health_origin_matches=True,
                         unauthenticated_home_status=401,
                         hosting_configuration_verified_live=True,
                         authenticated_browser_pass=True,
                         mobile_browser_pass=True, owner_approval=True)

    def test_historical_url_is_real_record_but_not_current_proof(self):
        self.assertEqual(self.base["url"], TEST99)
        self.assertNotEqual(TEST99, PRODUCTION.rstrip("/"))
        self.assertTrue(self.base["historical_only"])
        self.assertTrue(self.base["static_isolation_configuration_pass"])

    def test_historical_evidence_cannot_approve(self):
        self.assertEqual(acceptance_gate(self.base, "a" * 40)["status"], "BLOCKED")

    def test_full_synthetic_fixture_is_only_gate_unit_test(self):
        self.assertEqual(acceptance_gate(self.good, "a" * 40)["status"], "ACCEPTED")

    def test_wrong_deploy_sha_is_blocked(self):
        self.assertIn("DEPLOY_SHA_UNVERIFIED", acceptance_gate(self.good, "b" * 40)["reasons"])

    def test_wrong_server_source_is_blocked(self):
        self.good["hosted_source_sha256"] = "wrong"
        self.assertIn("HOSTED_SOURCE_MISMATCH_OR_UNKNOWN", acceptance_gate(self.good, "a" * 40)["reasons"])

    def test_production_or_unknown_mode_is_blocked(self):
        self.good["health_mode"] = "production"
        self.assertIn("HOSTED_HEALTH_UNVERIFIED", acceptance_gate(self.good, "a" * 40)["reasons"])

    def test_missing_browser_or_mobile_blocks(self):
        self.good["authenticated_browser_pass"] = False
        self.good["mobile_browser_pass"] = False
        errors = acceptance_gate(self.good, "a" * 40)["reasons"]
        self.assertIn("AUTHENTICATED_BROWSER_UNVERIFIED", errors)
        self.assertIn("MOBILE_BROWSER_UNVERIFIED", errors)

    def test_hosted_origin_must_match(self):
        self.good["health_origin_matches"] = False
        self.assertIn("HOSTED_ORIGIN_UNVERIFIED", acceptance_gate(self.good, "a" * 40)["reasons"])

    def test_private_home_must_not_be_public(self):
        self.good["unauthenticated_home_status"] = 200
        self.assertIn("PRIVATE_GATE_UNVERIFIED", acceptance_gate(self.good, "a" * 40)["reasons"])

    def test_live_isolation_not_inferred_from_yaml(self):
        self.good["hosting_configuration_verified_live"] = False
        self.assertIn("HOSTING_ISOLATION_UNVERIFIED", acceptance_gate(self.good, "a" * 40)["reasons"])

    def test_owner_approval_not_inferred_from_ci(self):
        self.good["owner_approval"] = False
        self.assertIn("OWNER_APPROVAL_PENDING", acceptance_gate(self.good, "a" * 40)["reasons"])


if __name__ == "__main__":
    unittest.main()
