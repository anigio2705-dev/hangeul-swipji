"""Independent B/15 #127 candidate payout-policy adversarial QA.
Exact A product SHA: 7be9fd4c27b17b3133d7141e5deb3db6ce867882.
No actual policy, payout, FX execution, provider, or operating database.
"""
import copy
import unittest
from unittest.mock import patch
from team14_payout_policy_candidates import review_payout_candidate

NO_LIVE = ("policy_approved", "fx_quote_verified", "recipient_verified",
           "can_payout", "can_retry_payment", "can_modify_operating_db",
           "can_activate_real_money")

def policy(**changes):
    v = dict(candidate_id="bqa_127", cycle="BIWEEKLY",
             minimum_target_minor=0, fee_bps=0,
             fx_numerator=1, fx_denominator=1,
             hold_days=0, max_retries=3, retry_delay_hours=24)
    v.update(changes)
    return v

def context(**changes):
    v = dict(gross_source_minor=100, settled_at_utc="2026-01-01T00:00:00Z",
             as_of_utc="2026-11-01T00:00:00Z",
             failed_attempts=0, last_failed_at_utc=None,
             disputed=False, refund_pending=False)
    v.update(changes)
    return v

def run(p=None, c=None):
    return review_payout_candidate(p if p is not None else policy(),
                                   c if c is not None else context())

class BQA127Independent(unittest.TestCase):
    def assert_not_live(self, r):
        for field in NO_LIVE:
            self.assertIs(r[field], False, field)

    def test_01_review_only_never_becomes_approved_payout(self):
        r = run()
        self.assertEqual(r["review_status"], "REVIEW_ONLY")
        self.assert_not_live(r)

    def test_02_biweekly_anchor_prior_day_must_not_skip_first_review(self):
        # Jan 5 2026 is the documented internal biweekly anchor. The next
        # cycle after Jan 4 must be Jan 5, NOT Jan 19.
        c = context(settled_at_utc="2025-12-01T00:00:00Z",
                    as_of_utc="2026-01-04T23:59:59Z")
        r = run(c=c)
        self.assertEqual(r["next_cycle_review_at_utc"],
                         "2026-01-05T00:00:00Z")
        self.assert_not_live(r)

    def test_03_biweekly_exact_anchor_advances_one_period(self):
        c = context(settled_at_utc="2025-12-01T00:00:00Z",
                    as_of_utc="2026-01-05T00:00:00Z")
        self.assertEqual(run(c=c)["next_cycle_review_at_utc"],
                         "2026-01-19T00:00:00Z")

    def test_04_biweekly_later_anchor_boundary(self):
        c = context(as_of_utc="2026-11-09T00:00:00Z")
        self.assertEqual(run(c=c)["next_cycle_review_at_utc"],
                         "2026-11-23T00:00:00Z")

    def test_05_fee_rounding_half_up_then_fx_rounding_half_up(self):
        p = policy(fee_bps=5000, fx_numerator=3, fx_denominator=2)
        r = run(p=p, c=context(gross_source_minor=3))
        self.assertEqual(r["hypothetical_fee_minor"], 2)
        self.assertEqual(r["hypothetical_net_source_minor"], 1)
        self.assertEqual(r["hypothetical_target_minor"], 2)
        self.assert_not_live(r)

    def test_06_fee_100_percent_zero_net_no_transfer(self):
        r = run(p=policy(fee_bps=10000), c=context(gross_source_minor=999))
        self.assertEqual(r["hypothetical_net_source_minor"], 0)
        self.assertEqual(r["hypothetical_target_minor"], 0)
        self.assert_not_live(r)

    def test_07_fee_and_fx_max_bounds_no_float_or_negative(self):
        r = run(p=policy(fee_bps=9999, fx_numerator=10**9,
                         fx_denominator=1), c=context(gross_source_minor=10**12))
        self.assertIsInstance(r["hypothetical_target_minor"], int)
        self.assertGreaterEqual(r["hypothetical_target_minor"], 0)
        self.assert_not_live(r)

    def test_08_minimum_is_applied_to_target_minor_after_conversion(self):
        p = policy(fx_numerator=1, fx_denominator=2,
                   minimum_target_minor=51)
        r = run(p=p)
        self.assertEqual(r["hypothetical_target_minor"], 50)
        self.assertIn("BELOW_MINIMUM", r["review_reasons"])
        self.assertEqual(r["review_status"], "HOLD")

    def test_09_hold_boundary_is_exclusive(self):
        c = context(settled_at_utc="2026-10-30T00:00:00Z",
                    as_of_utc="2026-11-01T00:00:00Z")
        self.assertNotIn("HOLD_PERIOD_ACTIVE",
                         run(p=policy(hold_days=2), c=c)["review_reasons"])

    def test_10_retry_limit_and_cooldown_both_hold(self):
        c = context(failed_attempts=3,
                    last_failed_at_utc="2026-10-31T23:00:00Z")
        r = run(c=c)
        self.assertIn("RETRY_LIMIT_REACHED", r["review_reasons"])
        self.assertIn("RETRY_COOLDOWN_ACTIVE", r["review_reasons"])
        self.assert_not_live(r)

    def test_11_dispute_refund_and_minimum_all_preserved(self):
        r = run(p=policy(minimum_target_minor=1000),
                c=context(disputed=True, refund_pending=True))
        self.assertEqual(r["review_reasons"],
                         ["BELOW_MINIMUM", "DISPUTE_OPEN", "REFUND_PENDING"])
        self.assert_not_live(r)

    def test_12_spoofed_bool_and_numeric_types_fail_closed(self):
        for key in ("fee_bps", "minimum_target_minor", "fx_numerator",
                    "fx_denominator", "hold_days", "max_retries",
                    "retry_delay_hours"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                run(p=policy(**{key: True}))
        for key in ("disputed", "refund_pending"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                run(c=context(**{key: 1}))

    def test_13_bad_timestamp_and_future_settlement_rejected(self):
        for bad in ("2026-11-01", "2026-11-01T09:00:00+09:00",
                    "2026-02-30T00:00:00Z", None, True):
            with self.subTest(bad=repr(bad)), self.assertRaises(ValueError):
                run(c=context(as_of_utc=bad))
        with self.assertRaises(ValueError):
            run(c=context(settled_at_utc="2026-12-01T00:00:00Z"))

    def test_14_bad_failure_chronology_rejected(self):
        for change in (dict(failed_attempts=1),
                       dict(last_failed_at_utc="2026-10-31T00:00:00Z"),
                       dict(failed_attempts=1,
                            last_failed_at_utc="2025-12-31T00:00:00Z"),
                       dict(failed_attempts=1,
                            last_failed_at_utc="2026-11-02T00:00:00Z")):
            with self.subTest(change=change), self.assertRaises(ValueError):
                run(c=context(**change))

    def test_15_sensitive_fields_and_fake_approvals_denied(self):
        for key in ("bank_account", "tax_id", "policy_approved",
                    "can_payout", "fx_quote_verified"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                run(p=policy(**{key: True}))
            with self.subTest(key=key), self.assertRaises(ValueError):
                run(c=context(**{key: True}))

    def test_16_inputs_not_mutated_or_echoed(self):
        p, c = policy(), context()
        before = copy.deepcopy((p, c))
        r = run(p, c)
        self.assertEqual((p, c), before)
        self.assertNotIn("bank_account", str(r))
        self.assert_not_live(r)

    def test_17_no_network_or_operating_db_access(self):
        with patch("sqlite3.connect", side_effect=AssertionError("DB forbidden")), \
             patch("urllib.request.urlopen", side_effect=AssertionError("HTTP forbidden")):
            self.assert_not_live(run())

    def test_18_weekly_and_monthly_cycle_boundaries(self):
        c = context(as_of_utc="2026-11-02T00:00:00Z")
        self.assertEqual(run(p=policy(cycle="WEEKLY"), c=c)
                         ["next_cycle_review_at_utc"], "2026-11-09T00:00:00Z")
        self.assertEqual(run(p=policy(cycle="MONTHLY"), c=c)
                         ["next_cycle_review_at_utc"], "2026-12-01T00:00:00Z")

if __name__ == "__main__":
    unittest.main()
