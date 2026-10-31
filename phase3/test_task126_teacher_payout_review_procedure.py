"""#126 independent-of-provider review procedure regression tests."""
import copy
import unittest

from team14_teacher_payout_review_procedure import review_teacher_payout_procedure

STAGES = (
    "identity_verification", "recipient_ownership", "tax_requirements",
    "country_eligibility", "provider_payout_capability",
)


def row(stage, **changes):
    result = dict(
        stage=stage,
        evidence_ref="ref_" + stage,
        reviewer_ref="reviewer_1",
        checked_at="2026-10-01T00:00:00Z",
        expires_at="2026-12-01T00:00:00Z",
        claimed_pass=True,
    )
    result.update(changes)
    return result


def run(**changes):
    args = dict(
        teacher_ref="teacher_1",
        country_code="KR",
        evidence=[row(x) for x in STAGES],
        as_of_utc="2026-11-01T00:00:00Z",
    )
    args.update(changes)
    return review_teacher_payout_procedure(**args)


class Task126TeacherPayoutProcedureTests(unittest.TestCase):
    def assert_never_pays(self, result):
        for field in (
            "collect_raw_bank_or_identity_data", "tax_decision_made",
            "country_payout_supported", "recipient_verified",
            "can_payout", "can_activate_real_money", "operating_db_connected",
        ):
            self.assertIs(result[field], False, field)

    def test_complete_fixture_is_review_only_never_payout(self):
        result = run()
        self.assertEqual("REVIEW_ONLY", result["review_status"])
        self.assertEqual([], result["missing_stages"])
        self.assertIn("TRUSTED_KYC_TAX_PROVIDER_AND_REVIEWER_NOT_CONNECTED", result["reasons"])
        self.assert_never_pays(result)

    def test_no_evidence_holds_with_five_missing_stages(self):
        result = run(evidence=[])
        self.assertEqual("HOLD", result["review_status"])
        self.assertEqual(list(STAGES), result["missing_stages"])
        self.assert_never_pays(result)

    def test_each_missing_stage_holds(self):
        for missing in STAGES:
            with self.subTest(missing=missing):
                result = run(evidence=[row(x) for x in STAGES if x != missing])
                self.assertIn(missing, result["missing_stages"])
                self.assertEqual("HOLD", result["review_status"])

    def test_false_claim_cannot_count(self):
        rows = [row(x) for x in STAGES]
        rows[0]["claimed_pass"] = False
        result = run(evidence=rows)
        self.assertIn(STAGES[0], result["missing_stages"])
        self.assertIn("REVIEW_NOT_PASSED", result["reasons"])

    def test_expired_evidence_holds(self):
        rows = [row(x) for x in STAGES]
        rows[0]["expires_at"] = "2026-10-31T00:00:00Z"
        result = run(evidence=rows)
        self.assertIn("STALE_OR_INVALID_REVIEW", result["reasons"])

    def test_future_dated_review_holds(self):
        rows = [row(x) for x in STAGES]
        rows[0]["checked_at"] = "2026-11-03T00:00:00Z"
        result = run(evidence=rows)
        self.assertIn("FUTURE_DATED_REVIEW", result["reasons"])

    def test_duplicate_stage_holds(self):
        rows = [row(x) for x in STAGES] + [row(STAGES[0], evidence_ref="extra")]
        result = run(evidence=rows)
        self.assertIn("DUPLICATE_REVIEW_STAGE", result["reasons"])
        self.assertEqual("HOLD", result["review_status"])

    def test_raw_sensitive_bank_field_rejected(self):
        with self.assertRaises(ValueError):
            run(evidence=[row(STAGES[0], bank_account="123456789")])

    def test_raw_tax_id_field_rejected(self):
        with self.assertRaises(ValueError):
            run(evidence=[row(STAGES[0], tax_id="sensitive")])

    def test_unknown_stage_rejected(self):
        with self.assertRaises(ValueError):
            run(evidence=[row("made_up")])

    def test_bad_record_schema_rejected(self):
        for item in ({}, {"stage": STAGES[0]}, "approved", None):
            with self.subTest(item=item), self.assertRaises(ValueError):
                run(evidence=[item])

    def test_bool_impersonation_rejected(self):
        for value in (1, 0, "true", None, {}, []):
            with self.subTest(value=value), self.assertRaises(ValueError):
                run(evidence=[row(STAGES[0], claimed_pass=value)])

    def test_bad_teacher_ref_rejected(self):
        for value in ("../other", "", "x" * 65, True, None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                run(teacher_ref=value)

    def test_country_code_is_format_only_not_supported_country(self):
        for code in ("KR", "US", "ZZ"):
            result = run(country_code=code)
            self.assertFalse(result["country_payout_supported"])
            self.assert_never_pays(result)

    def test_bad_country_code_rejected(self):
        for code in ("kr", "KOR", "K", "../KR", True, None):
            with self.subTest(code=code), self.assertRaises(ValueError):
                run(country_code=code)

    def test_bad_timestamp_rejected(self):
        for value in ("", "2026-11-01", "2026-11-01T09:00:00+09:00", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                run(as_of_utc=value)

    def test_invalid_reviewer_ref_rejected(self):
        with self.assertRaises(ValueError):
            run(evidence=[row(STAGES[0], reviewer_ref="../fake")])

    def test_evidence_limit_enforced(self):
        with self.assertRaises(ValueError):
            run(evidence=[row(STAGES[0]) for _ in range(11)])

    def test_non_list_evidence_rejected(self):
        for value in (None, {}, (), "review"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                run(evidence=value)

    def test_inputs_unchanged_and_no_sensitive_ref_echo(self):
        rows = [row(x) for x in STAGES]
        before = copy.deepcopy(rows)
        result = run(evidence=rows)
        self.assertEqual(before, rows)
        self.assertNotIn("reviewer_1", str(result))
        self.assert_never_pays(result)


if __name__ == "__main__":
    unittest.main()
