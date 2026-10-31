"""#130 isolated activation preflight: no path may enable live money."""
from copy import deepcopy
import unittest

from team14_live_activation_preflight import review_activation_evidence

KINDS = (
    "owner_approval", "provider_review", "legal_tax_review",
    "payout_compliance", "security_qa", "reconciliation_qa",
)


def approval(kind, **changes):
    result = {
        "kind": kind,
        "evidence_id": "approval_" + kind,
        "scope": "product2026",
        "issuer": "issuer_" + kind,
        "issued_at": "2026-10-01T00:00:00Z",
        "expires_at": "2026-12-01T00:00:00Z",
        "claimed_approved": True,
    }
    result.update(changes)
    return result


def review(**changes):
    args = dict(
        environment="production", scope="product2026",
        evidence=[approval(kind) for kind in KINDS],
        now_utc="2026-11-01T00:00:00Z",
    )
    args.update(changes)
    return review_activation_evidence(**args)


class Task130ActivationPreflightTests(unittest.TestCase):
    def assert_no_live_action(self, result):
        for key in (
            "can_enable_real_charge", "can_enable_real_payout",
            "can_enable_real_settlement", "can_change_operating_db",
            "can_deploy_to_production", "live_activation_performed",
        ):
            self.assertIs(result[key], False, key)

    def test_all_claims_present_still_never_authorize_live_money(self):
        result = review()
        self.assertEqual("REVIEW_ONLY", result["decision"])
        self.assertEqual([], result["missing_approval_kinds"])
        self.assertIn("TRUSTED_ATTESTATION_VERIFIER_NOT_CONNECTED", result["blockers"])
        self.assertIn("EXPLICIT_OWNER_LIVE_RELEASE_NOT_VERIFIED", result["blockers"])
        self.assert_no_live_action(result)

    def test_sandbox_claims_cannot_authorize_production(self):
        result = review(environment="sandbox")
        self.assert_no_live_action(result)
        self.assertEqual("sandbox", result["environment"])

    def test_empty_evidence_holds(self):
        result = review(evidence=[])
        self.assertEqual("HOLD", result["decision"])
        self.assertEqual(len(KINDS), len(result["missing_approval_kinds"]))
        self.assert_no_live_action(result)

    def test_each_missing_kind_holds(self):
        for missing in KINDS:
            with self.subTest(missing=missing):
                result = review(evidence=[approval(x) for x in KINDS if x != missing])
                self.assertIn(missing, result["missing_approval_kinds"])
                self.assertEqual("HOLD", result["decision"])

    def test_expired_approval_holds(self):
        rows = [approval(x) for x in KINDS]
        rows[0]["expires_at"] = "2026-10-30T00:00:00Z"
        result = review(evidence=rows)
        self.assertIn("EXPIRED_OR_INVALID_EVIDENCE", result["blockers"])
        self.assert_no_live_action(result)

    def test_future_dated_approval_holds(self):
        rows = [approval(x) for x in KINDS]
        rows[0]["issued_at"] = "2026-11-03T00:00:00Z"
        result = review(evidence=rows)
        self.assertIn("FUTURE_DATED_EVIDENCE", result["blockers"])

    def test_expiration_before_issuance_holds(self):
        rows = [approval(x) for x in KINDS]
        rows[0]["expires_at"] = "2026-09-30T00:00:00Z"
        result = review(evidence=rows)
        self.assertIn("EXPIRED_OR_INVALID_EVIDENCE", result["blockers"])

    def test_scope_mismatch_holds(self):
        rows = [approval(x) for x in KINDS]
        rows[0]["scope"] = "otherproduct"
        result = review(evidence=rows)
        self.assertIn("SCOPE_MISMATCH", result["blockers"])

    def test_duplicate_approval_kind_holds(self):
        rows = [approval(x) for x in KINDS] + [approval(KINDS[0], evidence_id="extra")]
        result = review(evidence=rows)
        self.assertIn("DUPLICATE_APPROVAL_KIND", result["blockers"])

    def test_duplicate_evidence_id_holds(self):
        rows = [approval(x) for x in KINDS]
        rows[1]["evidence_id"] = rows[0]["evidence_id"]
        result = review(evidence=rows)
        self.assertIn("DUPLICATE_EVIDENCE_ID", result["blockers"])

    def test_false_claim_does_not_count(self):
        rows = [approval(x) for x in KINDS]
        rows[0]["claimed_approved"] = False
        result = review(evidence=rows)
        self.assertIn("UNAPPROVED_EVIDENCE", result["blockers"])
        self.assertIn(KINDS[0], result["missing_approval_kinds"])

    def test_bool_like_values_rejected(self):
        for value in (1, 0, "true", None, {}, []):
            with self.subTest(value=value), self.assertRaises(ValueError):
                review(evidence=[approval(KINDS[0], claimed_approved=value)])

    def test_unknown_approval_kind_rejected(self):
        with self.assertRaises(ValueError):
            review(evidence=[approval("fake_external_review")])

    def test_invalid_schema_rejected(self):
        with self.assertRaises(ValueError):
            review(evidence=[{"kind": KINDS[0]}])
        with self.assertRaises(ValueError):
            review(evidence=[approval(KINDS[0], fake_signature=True)])

    def test_invalid_identifiers_rejected(self):
        for value in ("../secret", "", "x" * 65, None, 3):
            with self.subTest(value=value), self.assertRaises(ValueError):
                review(scope=value)
            with self.subTest(value=value), self.assertRaises(ValueError):
                review(evidence=[approval(KINDS[0], issuer=value)])

    def test_invalid_environment_rejected(self):
        for value in ("live", "test", "", True, None, 1):
            with self.subTest(value=value), self.assertRaises(ValueError):
                review(environment=value)

    def test_bad_timestamp_rejected(self):
        for value in ("2026-11-01", "2026-11-01T00:00:00+09:00",
                      "not-a-date", "", None, "2026-02-30T00:00:00Z"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                review(now_utc=value)

    def test_too_many_evidence_records_rejected(self):
        with self.assertRaises(ValueError):
            review(evidence=[approval(KINDS[0]) for _ in range(33)])

    def test_non_list_evidence_rejected(self):
        for value in ((), {}, None, "approval"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                review(evidence=value)

    def test_inputs_unchanged_and_no_secret_echo(self):
        rows = [approval(x) for x in KINDS]
        before = deepcopy(rows)
        result = review(evidence=rows)
        self.assertEqual(before, rows)
        self.assertNotIn("issuer_owner_approval", str(result))
        self.assert_no_live_action(result)


if __name__ == "__main__":
    unittest.main()
