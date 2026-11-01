"""B/15 additional #127 adversarial fractional UTC hold-boundary contract tests.
Product SHA 8c44e47e01c89480829ad3fdc3c0cc9a69c8d793.
No product edits; a displayed hold-until must not precede the actual hold cutoff.
"""
import unittest
from team14_payout_policy_candidates import review_payout_candidate

def review(now):
    candidate = dict(candidate_id="bqa_fractional", cycle="WEEKLY",
                     minimum_target_minor=0, fee_bps=0, fx_numerator=1,
                     fx_denominator=1, hold_days=1, max_retries=1,
                     retry_delay_hours=24)
    context = dict(gross_source_minor=100,
                   settled_at_utc="2026-10-31T00:00:00.500000Z",
                   as_of_utc=now, failed_attempts=0,
                   last_failed_at_utc=None, disputed=False,
                   refund_pending=False)
    return review_payout_candidate(candidate, context)

class BQA127FractionalBoundary(unittest.TestCase):
    def test_01_hold_until_must_not_round_down_to_earlier_second(self):
        r = review("2026-11-01T00:00:00Z")
        self.assertIn("HOLD_PERIOD_ACTIVE", r["review_reasons"])
        # Exact cutoff is .500000; returning .000000 incorrectly tells
        # consumers the hold has already ended at the as_of timestamp.
        self.assertEqual("2026-11-01T00:00:00.500000Z",
                         r["hold_until_utc"])
        self.assertFalse(r["can_payout"])

    def test_02_fractional_cutoff_exactly_releases_hypothetical_hold(self):
        r = review("2026-11-01T00:00:00.500000Z")
        self.assertNotIn("HOLD_PERIOD_ACTIVE", r["review_reasons"])
        self.assertEqual("REVIEW_ONLY", r["review_status"])
        self.assertFalse(r["can_payout"])

    def test_03_fractional_cutoff_one_microsecond_early_stays_held(self):
        r = review("2026-11-01T00:00:00.499999Z")
        self.assertIn("HOLD_PERIOD_ACTIVE", r["review_reasons"])
        self.assertEqual("HOLD", r["review_status"])
        self.assertFalse(r["can_payout"])


    def test_04_fractional_one_microsecond_not_rounded_down(self):
        candidate = dict(candidate_id="bqa_microsecond", cycle="WEEKLY",
                         minimum_target_minor=0, fee_bps=0, fx_numerator=1,
                         fx_denominator=1, hold_days=1, max_retries=1,
                         retry_delay_hours=24)
        context = dict(gross_source_minor=100,
                       settled_at_utc="2026-10-31T00:00:00.000001Z",
                       as_of_utc="2026-11-01T00:00:00Z",
                       failed_attempts=0, last_failed_at_utc=None,
                       disputed=False, refund_pending=False)
        r = review_payout_candidate(candidate, context)
        self.assertEqual(r["hold_until_utc"], "2026-11-01T00:00:00.000001Z")
        self.assertIn("HOLD_PERIOD_ACTIVE", r["review_reasons"])
        self.assertFalse(r["can_payout"])

    def test_05_second_only_cutoff_keeps_backward_compatible_format(self):
        candidate = dict(candidate_id="bqa_seconds", cycle="WEEKLY",
                         minimum_target_minor=0, fee_bps=0, fx_numerator=1,
                         fx_denominator=1, hold_days=1, max_retries=1,
                         retry_delay_hours=24)
        context = dict(gross_source_minor=100,
                       settled_at_utc="2026-10-31T00:00:00Z",
                       as_of_utc="2026-10-31T23:59:59Z",
                       failed_attempts=0, last_failed_at_utc=None,
                       disputed=False, refund_pending=False)
        r = review_payout_candidate(candidate, context)
        self.assertEqual(r["hold_until_utc"], "2026-11-01T00:00:00Z")
        self.assertIn("HOLD_PERIOD_ACTIVE", r["review_reasons"])
        self.assertFalse(r["can_payout"])

if __name__ == "__main__":
    unittest.main()
