"""B/15 independent #126 teacher payout procedure QA on exact product SHA.

Mock checklist only; no real identity, bank data, tax, payout or external review.
"""
from copy import deepcopy
from unittest.mock import patch
import unittest

from team14_teacher_payout_review_procedure import review_teacher_payout_procedure

STAGES = ("identity_verification", "recipient_ownership", "tax_requirements",
          "country_eligibility", "provider_payout_capability")
NO_LIVE = ("collect_raw_bank_or_identity_data", "tax_decision_made",
           "country_payout_supported", "recipient_verified", "can_payout",
           "can_activate_real_money", "operating_db_connected")
TRUST = {"COUNTRY_AND_CURRENCY_PROVIDER_CONFIRMATION_REQUIRED",
         "TRUSTED_KYC_TAX_PROVIDER_AND_REVIEWER_NOT_CONNECTED",
         "REPRESENTATIVE_PAYOUT_APPROVAL_NOT_VERIFIED"}


def proof(stage, **changes):
    x = dict(stage=stage, evidence_ref="proof_" + stage,
             reviewer_ref="external_reviewer",
             checked_at="2026-10-15T00:00:00Z",
             expires_at="2026-12-15T00:00:00Z",
             claimed_pass=True)
    x.update(changes)
    return x


def review(**changes):
    args = dict(teacher_ref="teacher_X", country_code="KR",
                evidence=[proof(s) for s in STAGES],
                as_of_utc="2026-11-01T00:00:00Z")
    args.update(changes)
    return review_teacher_payout_procedure(**args)


class BQA126Independent(unittest.TestCase):
    def no_live(self, r):
        for key in NO_LIVE:
            self.assertIs(r[key], False, key)
        self.assertTrue(r["evidence_untrusted"])
        self.assertTrue(TRUST.issubset(r["reasons"]))
        self.assertIn(r["review_status"], ("REVIEW_ONLY", "HOLD"))

    def test_01_complete_untrusted_claims_remain_review_only(self):
        r = review()
        self.assertEqual("REVIEW_ONLY", r["review_status"])
        self.assertEqual([], r["missing_stages"])
        self.assertEqual(list(STAGES), r["procedure_steps"])
        self.no_live(r)

    def test_02_empty_evidence_holds_all_five(self):
        r = review(evidence=[])
        self.assertEqual("HOLD", r["review_status"])
        self.assertEqual(list(STAGES), r["missing_stages"])
        self.no_live(r)

    def test_03_each_missing_stage_forces_hold(self):
        for absent in STAGES:
            with self.subTest(absent=absent):
                r = review(evidence=[proof(s) for s in STAGES if s != absent])
                self.assertEqual([absent], r["missing_stages"])
                self.assertEqual("HOLD", r["review_status"])
                self.no_live(r)

    def test_04_false_claim_must_not_complete_a_stage(self):
        records = [proof(s, claimed_pass=(s != "tax_requirements")) for s in STAGES]
        r = review(evidence=records)
        self.assertIn("tax_requirements", r["missing_stages"])
        self.assertIn("REVIEW_NOT_PASSED", r["reasons"])
        self.no_live(r)

    def test_05_bool_impersonation_rejected(self):
        for bad in (1, 0, "true", "false", None, [], {}):
            with self.subTest(bad=repr(bad)), self.assertRaises(ValueError):
                review(evidence=[proof(STAGES[0], claimed_pass=bad)])

    def test_06_duplicate_stage_does_not_complete_review(self):
        r = review(evidence=[proof(s) for s in STAGES] +
                   [proof(STAGES[0], evidence_ref="duplicate_stage")])
        self.assertEqual("HOLD", r["review_status"])
        self.assertIn("DUPLICATE_REVIEW_STAGE", r["reasons"])
        self.no_live(r)

    def test_07_expired_exactly_at_review_time_is_invalid(self):
        rows = [proof(s) for s in STAGES]
        rows[0]["expires_at"] = "2026-11-01T00:00:00Z"
        r = review(evidence=rows)
        self.assertIn(STAGES[0], r["missing_stages"])
        self.assertIn("STALE_OR_INVALID_REVIEW", r["reasons"])
        self.no_live(r)

    def test_08_future_dated_review_is_invalid(self):
        rows = [proof(s) for s in STAGES]
        rows[2]["checked_at"] = "2026-11-01T00:00:01Z"
        r = review(evidence=rows)
        self.assertIn("tax_requirements", r["missing_stages"])
        self.assertIn("FUTURE_DATED_REVIEW", r["reasons"])
        self.no_live(r)

    def test_09_expiry_before_issue_date_forces_hold(self):
        rows = [proof(s) for s in STAGES]
        rows[3]["expires_at"] = rows[3]["checked_at"]
        r = review(evidence=rows)
        self.assertIn("STALE_OR_INVALID_REVIEW", r["reasons"])
        self.no_live(r)

    def test_10_invalid_teacher_and_evidence_refs_rejected(self):
        for bad in ("", "../other", "x/y", "x"*65, True, None, 3):
            with self.subTest(teacher=repr(bad)), self.assertRaises(ValueError):
                review(teacher_ref=bad)
            for key in ("evidence_ref", "reviewer_ref"):
                with self.subTest(key=key, bad=repr(bad)), self.assertRaises(ValueError):
                    review(evidence=[proof(STAGES[0], **{key: bad})])

    def test_11_country_code_format_does_not_claim_support(self):
        for code in ("KR", "US", "ZZ"):
            r = review(country_code=code)
            self.assertEqual(code, r["country_code_unverified"])
            self.no_live(r)
        for bad in ("kr", "KOR", "K", "K1", "../KR", True, None):
            with self.subTest(code=repr(bad)), self.assertRaises(ValueError):
                review(country_code=bad)

    def test_12_raw_pii_and_fake_approval_fields_rejected(self):
        for field in ("bank_account", "tax_id", "identity_document",
                      "signed_owner_approval", "real_payout_enabled"):
            with self.subTest(field=field), self.assertRaises(ValueError):
                review(evidence=[proof(STAGES[0], **{field: "sensitive"})])

    def test_13_malformed_review_schema_rejected(self):
        for bad in (None, "passed", {}, {"stage": STAGES[0]}, []):
            with self.subTest(bad=repr(bad)), self.assertRaises(ValueError):
                review(evidence=[bad])
        with self.assertRaises(ValueError):
            review(evidence=[proof("unknown_review")])

    def test_14_timestamp_inputs_strict_utc(self):
        for bad in (None, "", "2026-11-01", "2026-02-30T00:00:00Z",
                    "2026-11-01T09:00:00+09:00", True):
            with self.subTest(now=repr(bad)), self.assertRaises(ValueError):
                review(as_of_utc=bad)
            with self.subTest(checked=repr(bad)), self.assertRaises(ValueError):
                review(evidence=[proof(STAGES[0], checked_at=bad)])
            with self.subTest(expiry=repr(bad)), self.assertRaises(ValueError):
                review(evidence=[proof(STAGES[0], expires_at=bad)])

    def test_15_evidence_list_size_and_type_rejected(self):
        for bad in (None, {}, (), "complete", [proof(STAGES[0])]*11):
            with self.subTest(bad=type(bad).__name__), self.assertRaises(ValueError):
                review(evidence=bad)

    def test_16_caller_records_not_mutated_or_echoed(self):
        records = [proof(s) for s in STAGES]
        records[0]["reviewer_ref"] = "private_reviewer_token"
        original = deepcopy(records)
        r = review(evidence=records)
        self.assertEqual(original, records)
        self.assertNotIn("private_reviewer_token", repr(r))
        self.no_live(r)

    def test_17_order_independent_and_deterministic(self):
        records = [proof(s) for s in STAGES]
        self.assertEqual(review(evidence=records),
                         review(evidence=list(reversed(records))))

    def test_18_no_network_or_sqlite_during_offline_review(self):
        with patch("sqlite3.connect", side_effect=AssertionError("DB forbidden")), \
             patch("urllib.request.urlopen", side_effect=AssertionError("HTTP forbidden")):
            self.no_live(review())

    def test_19_valid_country_format_is_not_a_tax_or_payout_decision(self):
        r = review(country_code="US")
        self.assertIs(r["country_payout_supported"], False)
        self.assertIs(r["tax_decision_made"], False)
        self.assertIs(r["recipient_verified"], False)
        self.assertIs(r["can_payout"], False)
        self.no_live(r)


if __name__ == "__main__":
    unittest.main()
