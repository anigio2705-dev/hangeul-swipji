"""#102 product regression: comparison is hypothetical and cannot pay."""
import copy
import unittest
from team14_referral_comparison import compare_referral_options


def candidate(**overrides):
    result = dict(candidate_id="direct", max_depth=1, duration_days=30,
                  eligible_events=["LESSON_COMPLETED"])
    result.update(overrides)
    return result


def scenario(**overrides):
    result = dict(referral_chain=["student", "teacher", "partner"],
                  referred_at_utc="2026-10-01T00:00:00Z",
                  transaction_at_utc="2026-10-15T00:00:00Z",
                  as_of_utc="2026-11-01T00:00:00Z",
                  event="LESSON_COMPLETED", refund_pending=False,
                  fixture_payment_evidence_present=True)
    result.update(overrides)
    return result


def compare(candidates=None, context=None):
    return compare_referral_options(
        [candidate()] if candidates is None else candidates,
        scenario() if context is None else context)


class Task102ComparisonTests(unittest.TestCase):
    def assert_never_live(self, output):
        self.assertIs(output["policy_approved"], False)
        self.assertIs(output["can_activate_real_money"], False)
        for item in output["results"]:
            for key in ("identity_verified", "transaction_verified",
                        "policy_approved", "legal_tax_approved",
                        "can_create_reward", "can_payout",
                        "can_modify_operating_db"):
                self.assertIs(item[key], False, key)

    def test_direct_depth_only(self):
        r = compare()
        self.assertEqual([1], r["results"][0]["hypothetical_depths"])
        self.assertEqual("DIRECT_ONLY", r["results"][0]["model"])
        self.assert_never_live(r)

    def test_two_levels_and_depth_cap(self):
        r = compare([candidate(candidate_id="two", max_depth=2)])
        self.assertEqual([1, 2], r["results"][0]["hypothetical_depths"])
        self.assertEqual("MULTILEVEL", r["results"][0]["model"])
        self.assert_never_live(r)

    def test_ten_levels_with_only_two_ancestors(self):
        r = compare([candidate(max_depth=10)])
        self.assertEqual([1, 2], r["results"][0]["hypothetical_depths"])

    def test_compare_multiple_policies_without_selection(self):
        r = compare([candidate(), candidate(candidate_id="multi", max_depth=2)])
        self.assertEqual(2, r["comparison_count"])
        self.assertEqual([1, 2], r["results"][1]["hypothetical_depths"])
        self.assert_never_live(r)

    def test_eligible_booking_vs_lesson(self):
        r = compare([candidate(eligible_events=["BOOKING_PAID"])])
        self.assertEqual([], r["results"][0]["hypothetical_depths"])
        self.assertIn("EVENT_NOT_IN_CANDIDATE", r["results"][0]["review_reasons"])

    def test_monthly_renewal_option(self):
        r = compare([candidate(eligible_events=["MONTH_RENEWED"])],
                    scenario(event="MONTH_RENEWED"))
        self.assertEqual([1], r["results"][0]["hypothetical_depths"])

    def test_duration_inclusive_boundary(self):
        r = compare([candidate(duration_days=14)])
        self.assertEqual([1], r["results"][0]["hypothetical_depths"])

    def test_duration_exceeded_by_microsecond(self):
        r = compare([candidate(duration_days=14)],
                    scenario(transaction_at_utc="2026-10-15T00:00:00.000001Z"))
        self.assertIn("CANDIDATE_PERIOD_EXPIRED", r["results"][0]["review_reasons"])

    def test_zero_duration_same_instant_only(self):
        r = compare([candidate(duration_days=0)],
                    scenario(transaction_at_utc="2026-10-01T00:00:00Z"))
        self.assertEqual([1], r["results"][0]["hypothetical_depths"])

    def test_refund_and_missing_evidence_fail_closed(self):
        r = compare(context=scenario(refund_pending=True,
                                     fixture_payment_evidence_present=False))
        self.assertEqual(0, r["results"][0]["hypothetical_referrer_count"])
        self.assertEqual(["NO_FIXTURE_PAYMENT_EVIDENCE", "REFUND_PENDING"],
                         r["results"][0]["review_reasons"])
        self.assert_never_live(r)

    def test_reject_self_and_cycles(self):
        for chain in (["a", "a"], ["a", "b", "a"]):
            with self.subTest(chain=chain), self.assertRaises(ValueError):
                compare(context=scenario(referral_chain=chain))

    def test_reject_oversized_chain_and_candidates(self):
        with self.assertRaises(ValueError):
            compare(context=scenario(referral_chain=[str(i) for i in range(12)]))
        with self.assertRaises(ValueError):
            compare([candidate(candidate_id=str(i)) for i in range(17)])

    def test_reject_duplicate_candidates(self):
        with self.assertRaises(ValueError):
            compare([candidate(), candidate()])

    def test_reject_invalid_numeric_types(self):
        for change in (dict(max_depth=True), dict(max_depth=0),
                       dict(max_depth=11), dict(duration_days=-1),
                       dict(duration_days=3651), dict(duration_days=1.0)):
            with self.subTest(change=change), self.assertRaises(ValueError):
                compare([candidate(**change)])

    def test_reject_unsafe_ids_and_extra_fields(self):
        for change in (dict(candidate_id="../forged"), dict(candidate_id=""),
                       dict(bank_account="123")):
            with self.subTest(change=change), self.assertRaises(ValueError):
                compare([candidate(**change)])
        with self.assertRaises(ValueError):
            compare(context=scenario(referral_chain=["a", "../b"]))

    def test_reject_duplicate_unknown_or_invalid_events(self):
        for events in ([], ["LESSON_COMPLETED"] * 2, ["PAYOUT"],
                       "LESSON_COMPLETED", [True], [None]):
            with self.subTest(events=events), self.assertRaises(ValueError):
                compare([candidate(eligible_events=events)])

    def test_reject_untrusted_boolean_spoofing(self):
        for change in (dict(refund_pending=0),
                       dict(fixture_payment_evidence_present="true")):
            with self.subTest(change=change), self.assertRaises(ValueError):
                compare(context=scenario(**change))

    def test_reject_invalid_chronology(self):
        for change in (dict(transaction_at_utc="2026-09-30T00:00:00Z"),
                       dict(as_of_utc="2026-10-14T00:00:00Z"),
                       dict(referred_at_utc="2026-11-02T00:00:00Z")):
            with self.subTest(change=change), self.assertRaises(ValueError):
                compare(context=scenario(**change))

    def test_reject_non_utc_and_invalid_calendar(self):
        for stamp in ("2026-10-15T09:00:00+09:00",
                      "2026-02-30T00:00:00Z", "2026-10-15",
                      "2026-10-15T00:00:00.1234567Z"):
            with self.subTest(stamp=stamp), self.assertRaises(ValueError):
                compare(context=scenario(transaction_at_utc=stamp))

    def test_no_mutation_or_secret_echo(self):
        c = [candidate(candidate_id="x", eligible_events=["LESSON_COMPLETED"])]
        x = scenario()
        old = copy.deepcopy((c, x))
        r = compare(c, x)
        self.assertEqual((c, x), old)
        self.assertNotIn("student", str(r))
        self.assertNotIn("teacher", str(r))
        self.assert_never_live(r)

    def test_max_year_candidate_expiry_overflow_rejected(self):
        with self.assertRaises(ValueError):
            compare([candidate(duration_days=3650)],
                    scenario(referred_at_utc="9999-12-30T00:00:00Z",
                             transaction_at_utc="9999-12-30T00:00:00Z",
                             as_of_utc="9999-12-30T00:00:00Z"))

    def test_reject_schema_extras_and_empty_inputs(self):
        for policies in ([], "bad"):
            with self.subTest(policies=policies), self.assertRaises(ValueError):
                compare(policies)
        with self.assertRaises(ValueError):
            compare_referral_options(None, scenario())
        with self.assertRaises(ValueError):
            compare(context=scenario(password="secret"))


if __name__ == "__main__":
    unittest.main()
