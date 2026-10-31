"""#127 payout candidate rule matrix; no approved business policy or live money."""
import copy
import unittest
from team14_payout_policy_candidates import review_payout_candidate


def candidate(**kw):
    value = dict(
        candidate_id="draft_1", cycle="WEEKLY", minimum_target_minor=100,
        fee_bps=1000, fx_numerator=1, fx_denominator=1,
        hold_days=0, max_retries=3, retry_delay_hours=24,
    )
    value.update(kw)
    return value


def context(**kw):
    value = dict(
        gross_source_minor=1000, settled_at_utc="2026-10-01T00:00:00Z",
        as_of_utc="2026-11-01T00:00:00Z", failed_attempts=0,
        last_failed_at_utc=None, disputed=False, refund_pending=False,
    )
    value.update(kw)
    return value


def review(c=None, x=None):
    return review_payout_candidate(c if c is not None else candidate(),
                                   x if x is not None else context())


class Task127PayoutCandidateTests(unittest.TestCase):
    def assert_never_live(self, value):
        for key in ("policy_approved", "fx_quote_verified", "recipient_verified",
                    "can_payout", "can_retry_payment",
                    "can_modify_operating_db", "can_activate_real_money"):
            self.assertIs(value[key], False, key)

    def test_hypothetical_math_and_no_real_payout(self):
        r = review()
        self.assertEqual(100, r["hypothetical_fee_minor"])
        self.assertEqual(900, r["hypothetical_net_source_minor"])
        self.assertEqual(900, r["hypothetical_target_minor"])
        self.assertEqual("REVIEW_ONLY", r["review_status"])
        self.assert_never_live(r)

    def test_rounding_half_up_for_fee(self):
        r = review(candidate(fee_bps=5000), context(gross_source_minor=1))
        self.assertEqual(1, r["hypothetical_fee_minor"])
        self.assertEqual(0, r["hypothetical_target_minor"])

    def test_fx_integer_rounding_half_up(self):
        r = review(candidate(fee_bps=0, fx_numerator=1, fx_denominator=2,
                             minimum_target_minor=0),
                   context(gross_source_minor=1))
        self.assertEqual(1, r["hypothetical_target_minor"])

    def test_fx_nonhalf_floor(self):
        r = review(candidate(fee_bps=0, fx_numerator=1, fx_denominator=3,
                             minimum_target_minor=0),
                   context(gross_source_minor=1))
        self.assertEqual(0, r["hypothetical_target_minor"])

    def test_minimum_holds(self):
        r = review(candidate(minimum_target_minor=901))
        self.assertIn("BELOW_MINIMUM", r["review_reasons"])
        self.assertEqual("HOLD", r["review_status"])

    def test_hold_period_holds(self):
        r = review(candidate(hold_days=60))
        self.assertIn("HOLD_PERIOD_ACTIVE", r["review_reasons"])

    def test_dispute_holds(self):
        r = review(x=context(disputed=True))
        self.assertIn("DISPUTE_OPEN", r["review_reasons"])

    def test_refund_holds(self):
        r = review(x=context(refund_pending=True))
        self.assertIn("REFUND_PENDING", r["review_reasons"])

    def test_retry_limit_holds(self):
        r = review(x=context(failed_attempts=3,
            last_failed_at_utc="2026-10-01T01:00:00Z"))
        self.assertIn("RETRY_LIMIT_REACHED", r["review_reasons"])

    def test_retry_cooldown_holds(self):
        r = review(x=context(failed_attempts=1,
            last_failed_at_utc="2026-10-31T23:00:00Z"))
        self.assertIn("RETRY_COOLDOWN_ACTIVE", r["review_reasons"])

    def test_retry_cooldown_expired_is_only_review(self):
        r = review(x=context(failed_attempts=1,
            last_failed_at_utc="2026-10-02T00:00:00Z"))
        self.assertEqual("REVIEW_ONLY", r["review_status"])
        self.assert_never_live(r)

    def test_cycle_next_review_weekly(self):
        r = review()
        self.assertEqual("2026-11-02T00:00:00Z", r["next_cycle_review_at_utc"])

    def test_cycle_next_review_monthly(self):
        r = review(candidate(cycle="MONTHLY"))
        self.assertEqual("2026-12-01T00:00:00Z", r["next_cycle_review_at_utc"])

    def test_cycle_next_review_biweekly(self):
        r = review(candidate(cycle="BIWEEKLY"))
        self.assertEqual("2026-11-09T00:00:00Z", r["next_cycle_review_at_utc"])

    def test_invalid_cycle_and_id(self):
        for change in (dict(cycle="DAILY"), dict(cycle=1),
                       dict(candidate_id="../forged"), dict(candidate_id="")):
            with self.subTest(change=change), self.assertRaises(ValueError):
                review(candidate(**change))

    def test_bool_numeric_spoof_rejected(self):
        for key in ("fee_bps", "fx_numerator", "fx_denominator", "hold_days",
                    "max_retries", "retry_delay_hours", "minimum_target_minor"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                review(candidate(**{key: True}))
        with self.assertRaises(ValueError):
            review(x=context(gross_source_minor=True))

    def test_invalid_bounds_rejected(self):
        for change in (dict(fee_bps=10001), dict(fee_bps=-1),
                       dict(fx_denominator=0), dict(fx_numerator=0),
                       dict(hold_days=366), dict(max_retries=21),
                       dict(retry_delay_hours=0)):
            with self.subTest(change=change), self.assertRaises(ValueError):
                review(candidate(**change))

    def test_invalid_schema_and_pii_fields_rejected(self):
        with self.assertRaises(ValueError):
            review(candidate(bank_account="1234"))
        with self.assertRaises(ValueError):
            review(x=context(tax_id="private"))
        with self.assertRaises(ValueError):
            review(c={"candidate_id": "only"})

    def test_invalid_context_types_rejected(self):
        for change in (dict(disputed=1), dict(refund_pending="false"),
                       dict(failed_attempts=-1), dict(gross_source_minor=-1)):
            with self.subTest(change=change), self.assertRaises(ValueError):
                review(x=context(**change))

    def test_failure_chronology_and_missing_timestamp_rejected(self):
        for change in (dict(failed_attempts=1),
                       dict(last_failed_at_utc="2026-10-31T00:00:00Z"),
                       dict(failed_attempts=1, last_failed_at_utc="2026-09-30T00:00:00Z"),
                       dict(failed_attempts=1, last_failed_at_utc="2026-11-02T00:00:00Z")):
            with self.subTest(change=change), self.assertRaises(ValueError):
                review(x=context(**change))

    def test_future_settlement_and_non_utc_rejected(self):
        for change in (dict(settled_at_utc="2026-11-02T00:00:00Z"),
                       dict(as_of_utc="2026-11-01T09:00:00+09:00"),
                       dict(as_of_utc="2026-11-01")):
            with self.subTest(change=change), self.assertRaises(ValueError):
                review(x=context(**change))

    def test_inputs_immutable_and_no_secrets_echo(self):
        c = candidate()
        x = context()
        before = copy.deepcopy((c, x))
        r = review(c, x)
        self.assertEqual(before, (c, x))
        self.assertNotIn("tax_id", str(r))
        self.assert_never_live(r)

    def test_multiple_blockers_are_all_reported(self):
        r = review(candidate(minimum_target_minor=99999, hold_days=60),
                   context(disputed=True, refund_pending=True))
        self.assertEqual(["BELOW_MINIMUM", "DISPUTE_OPEN", "HOLD_PERIOD_ACTIVE",
                          "REFUND_PENDING"], r["review_reasons"])

    def test_zero_amount_never_authorizes_payout(self):
        r = review(candidate(minimum_target_minor=0),
                   context(gross_source_minor=0))
        self.assertEqual(0, r["hypothetical_target_minor"])
        self.assert_never_live(r)


if __name__ == "__main__":
    unittest.main()
