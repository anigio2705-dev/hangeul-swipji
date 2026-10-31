"""B/15 independent exact-SHA #130 offline activation evidence adversarial QA.

Tests are independent of product-authored test_task130. No live approval, DB,
network, charge, payout or deployment is exercised.
"""
from copy import deepcopy
from unittest.mock import patch
import unittest

from team14_live_activation_preflight import review_activation_evidence

KINDS = ("owner_approval", "provider_review", "legal_tax_review",
         "payout_compliance", "security_qa", "reconciliation_qa")
LIVE_FLAGS = ("can_enable_real_charge", "can_enable_real_payout",
              "can_enable_real_settlement", "can_change_operating_db",
              "can_deploy_to_production", "live_activation_performed")
TRUST_BLOCKERS = {"TRUSTED_ATTESTATION_VERIFIER_NOT_CONNECTED",
                  "LIVE_PROVIDER_AND_LEDGER_ADAPTER_NOT_CONNECTED",
                  "EXPLICIT_OWNER_LIVE_RELEASE_NOT_VERIFIED"}


def row(kind, **overrides):
    data = dict(kind=kind, evidence_id="proof_" + kind,
                scope="swipji2026", issuer="reviewer_" + kind,
                issued_at="2026-10-31T00:00:00Z",
                expires_at="2026-11-30T00:00:00Z",
                claimed_approved=True)
    data.update(overrides)
    return data


def run(**overrides):
    kwargs = dict(environment="production", scope="swipji2026",
                  evidence=[row(kind) for kind in KINDS],
                  now_utc="2026-11-01T00:00:00Z")
    kwargs.update(overrides)
    return review_activation_evidence(**kwargs)


class BQA130Independent(unittest.TestCase):
    def no_live(self, result):
        self.assertIn(result["decision"], ("HOLD", "REVIEW_ONLY"))
        for flag in LIVE_FLAGS:
            self.assertIs(result[flag], False, flag)
        self.assertTrue(result["evidence_untrusted"])
        self.assertTrue(TRUST_BLOCKERS.issubset(result["blockers"]))

    def test_01_all_six_self_claimed_reviews_are_not_live_authority(self):
        result = run()
        self.assertEqual("REVIEW_ONLY", result["decision"])
        self.assertEqual([], result["missing_approval_kinds"])
        self.assertEqual(6, result["evidence_count"])
        self.no_live(result)

    def test_02_sandbox_is_not_an_escape_hatch_to_live_payment(self):
        result = run(environment="sandbox")
        self.assertEqual("sandbox", result["environment"])
        self.no_live(result)

    def test_03_empty_list_holds_all_six_categories(self):
        result = run(evidence=[])
        self.assertEqual("HOLD", result["decision"])
        self.assertEqual(sorted(KINDS), result["missing_approval_kinds"])
        self.no_live(result)

    def test_04_each_required_category_is_individually_mandatory(self):
        for omitted in KINDS:
            with self.subTest(omitted=omitted):
                result = run(evidence=[row(k) for k in KINDS if k != omitted])
                self.assertEqual([omitted], result["missing_approval_kinds"])
                self.assertEqual("HOLD", result["decision"])
                self.no_live(result)

    def test_05_false_claim_is_not_approved_evidence(self):
        rows = [row(k, claimed_approved=(k != "security_qa")) for k in KINDS]
        result = run(evidence=rows)
        self.assertIn("security_qa", result["missing_approval_kinds"])
        self.assertIn("UNAPPROVED_EVIDENCE", result["blockers"])
        self.no_live(result)

    def test_06_boolean_spoofing_is_rejected_instead_of_coerced(self):
        for bad in (1, 0, "true", "False", None, [], {}):
            with self.subTest(bad=repr(bad)), self.assertRaises(ValueError):
                run(evidence=[row("owner_approval", claimed_approved=bad)])

    def test_07_duplicate_kind_even_with_distinct_ids_forces_hold(self):
        records = [row(k) for k in KINDS]
        records.append(row("owner_approval", evidence_id="another_proof"))
        result = run(evidence=records)
        self.assertIn("DUPLICATE_APPROVAL_KIND", result["blockers"])
        self.assertEqual("HOLD", result["decision"])
        self.no_live(result)

    def test_08_duplicate_evidence_id_across_kinds_forces_hold(self):
        records = [row(k) for k in KINDS]
        records[-1]["evidence_id"] = records[0]["evidence_id"]
        result = run(evidence=records)
        self.assertIn("DUPLICATE_EVIDENCE_ID", result["blockers"])
        self.assertEqual("HOLD", result["decision"])
        self.no_live(result)

    def test_09_cross_scope_claim_cannot_count_as_approval(self):
        records = [row(k) for k in KINDS]
        records[2]["scope"] = "other_app"
        result = run(evidence=records)
        self.assertIn("legal_tax_review", result["missing_approval_kinds"])
        self.assertIn("SCOPE_MISMATCH", result["blockers"])
        self.no_live(result)

    def test_10_approval_expiring_exactly_at_now_is_invalid(self):
        records = [row(k) for k in KINDS]
        records[1]["expires_at"] = "2026-11-01T00:00:00Z"
        result = run(evidence=records)
        self.assertIn("EXPIRED_OR_INVALID_EVIDENCE", result["blockers"])
        self.assertIn("provider_review", result["missing_approval_kinds"])
        self.no_live(result)

    def test_11_approval_issued_after_now_is_invalid(self):
        records = [row(k) for k in KINDS]
        records[0]["issued_at"] = "2026-11-01T00:00:01Z"
        result = run(evidence=records)
        self.assertIn("FUTURE_DATED_EVIDENCE", result["blockers"])
        self.assertIn("owner_approval", result["missing_approval_kinds"])
        self.no_live(result)

    def test_12_reversed_issue_expiry_window_holds(self):
        records = [row(k) for k in KINDS]
        records[3]["expires_at"] = records[3]["issued_at"]
        result = run(evidence=records)
        self.assertIn("EXPIRED_OR_INVALID_EVIDENCE", result["blockers"])
        self.no_live(result)

    def test_13_invalid_evidence_id_issuer_scope_and_environment(self):
        for field in ("evidence_id", "issuer", "scope"):
            for bad in ("", "../escape", "bad/id", "x"*65, 0, True, None):
                with self.subTest(field=field, bad=repr(bad)), self.assertRaises(ValueError):
                    run(evidence=[row("owner_approval", **{field: bad})])
        for bad in ("live", "PRODUCTION", "", None, True, 1):
            with self.subTest(env=repr(bad)), self.assertRaises(ValueError):
                run(environment=bad)

    def test_14_malformed_schema_and_claimed_signature_injection_rejected(self):
        cases = [None, {}, {"kind": "owner_approval"},
                 row("owner_approval", signed_by_owner=True),
                 row("owner_approval", fake_signature="trusted")]
        for bad in cases:
            with self.subTest(bad=repr(bad)), self.assertRaises(ValueError):
                run(evidence=[bad])

    def test_15_unknown_approval_kind_rejected(self):
        with self.assertRaises(ValueError):
            run(evidence=[row("owner_release_v2")])

    def test_16_malformed_timestamps_in_any_position_rejected(self):
        bads = ("", "yesterday", "2026-11-01", "2026-02-30T00:00:00Z",
                "2026-11-01T00:00:00+09:00", None, True)
        for bad in bads:
            with self.subTest(bad=repr(bad)), self.assertRaises(ValueError):
                run(now_utc=bad)
            with self.subTest(issued=repr(bad)), self.assertRaises(ValueError):
                run(evidence=[row("owner_approval", issued_at=bad)])
            with self.subTest(expires=repr(bad)), self.assertRaises(ValueError):
                run(evidence=[row("owner_approval", expires_at=bad)])

    def test_17_evidence_list_type_and_capacity_limits(self):
        for bad in (None, {}, (), "approved", [row("owner_approval")]*33):
            with self.subTest(bad=type(bad).__name__), self.assertRaises(ValueError):
                run(evidence=bad)

    def test_18_no_mutation_or_sensitive_issuer_echo(self):
        records = [row(k) for k in KINDS]
        records[0]["issuer"] = "private_issuer_token"
        original = deepcopy(records)
        result = run(evidence=records)
        self.assertEqual(original, records)
        self.assertNotIn("private_issuer_token", repr(result))
        self.no_live(result)

    def test_19_permuting_records_cannot_change_decision(self):
        records = [row(k) for k in KINDS]
        left = run(evidence=records)
        right = run(evidence=list(reversed(records)))
        self.assertEqual(left, right)
        self.no_live(right)

    def test_20_no_sqlite_or_network_in_read_only_preflight(self):
        with patch("sqlite3.connect", side_effect=AssertionError("DB forbidden")), \
             patch("urllib.request.urlopen", side_effect=AssertionError("network forbidden")):
            self.no_live(run())

    def test_21_all_present_but_one_expired_must_not_be_review_only(self):
        records = [row(k) for k in KINDS]
        records[-1]["expires_at"] = "2026-10-31T23:59:59Z"
        result = run(evidence=records)
        self.assertEqual("HOLD", result["decision"])
        self.assertIn("reconciliation_qa", result["missing_approval_kinds"])
        self.no_live(result)


if __name__ == "__main__":
    unittest.main()
