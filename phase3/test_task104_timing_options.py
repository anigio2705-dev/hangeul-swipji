"""#104 virtual timing cases only. No payment, DB, or deployment."""
import unittest

from team14_reward_timing_sim import simulate_reward_timing


DAY = 86400


def sim(**kwargs):
    args = dict(payment_at=100, completion_at=200, as_of=200,
                policy="after_refund_window", refund_window_seconds=7 * DAY)
    args.update(kwargs)
    return simulate_reward_timing(**args)


class RewardTimingOptionsTest(unittest.TestCase):
    def assert_sandbox(self, result):
        self.assertIs(result["real_money"], False)
        self.assertIs(result["policy_approved"], False)
        self.assertIs(result["payment_enabled"], False)

    def test_payment_first_candidate_is_provisional(self):
        result = sim(policy="on_payment", completion_at=None, as_of=101)
        self.assertTrue(result["candidate_triggered"])
        self.assertFalse(result["safe_to_confirm_simulated"])
        self.assertEqual(result["state"], "PROVISIONAL_REFUND_RISK")
        self.assert_sandbox(result)

    def test_completion_candidate_waits_for_lesson(self):
        result = sim(policy="on_completion", completion_at=None, as_of=101)
        self.assertEqual(result["state"], "WAIT_LESSON")
        self.assertFalse(result["candidate_triggered"])

    def test_completion_candidate_triggered_only_after_both(self):
        self.assertFalse(sim(policy="on_completion", as_of=199)["candidate_triggered"])
        result = sim(policy="on_completion", as_of=200)
        self.assertEqual(result["candidate_trigger_at"], 200)
        self.assertTrue(result["candidate_triggered"])
        self.assertFalse(result["safe_to_confirm_simulated"])

    def test_window_candidate_boundary(self):
        self.assertFalse(sim(as_of=200 + 7 * DAY - 1)["candidate_triggered"])
        result = sim(as_of=200 + 7 * DAY)
        self.assertEqual(result["state"], "SIMULATED_WINDOW_CLOSED")
        self.assertTrue(result["safe_to_confirm_simulated"])
        self.assert_sandbox(result)

    def test_later_payment_controls_window_start(self):
        self.assertFalse(sim(payment_at=300, completion_at=200,
                             as_of=300 + 7 * DAY - 1)["candidate_triggered"])
        self.assertTrue(sim(payment_at=300, completion_at=200,
                            as_of=300 + 7 * DAY)["candidate_triggered"])

    def test_refund_during_window_voids_candidate(self):
        result = sim(policy="on_payment", refund_at=201, as_of=202)
        self.assertEqual(result["state"], "VOID_REFUND")
        self.assertFalse(result["candidate_triggered"])
        self.assertFalse(result["safe_to_confirm_simulated"])

    def test_late_refund_never_authorizes_payment(self):
        result = sim(refund_at=200 + 8 * DAY, as_of=200 + 9 * DAY)
        self.assertEqual(result["state"], "VOID_REFUND")
        self.assertFalse(result["payment_enabled"])

    def test_future_refund_not_applied_prematurely(self):
        result = sim(refund_at=200 + 8 * DAY, as_of=200 + 7 * DAY)
        self.assertTrue(result["candidate_triggered"])
        self.assertFalse(result["payment_enabled"])

    def test_no_payment_never_triggers(self):
        for policy in ("on_payment", "on_completion", "after_refund_window"):
            result = sim(policy=policy, payment_at=None)
            self.assertEqual(result["state"], "WAIT_PAYMENT")
            self.assertFalse(result["candidate_triggered"])

    def test_future_payment_not_yet_captured(self):
        result = sim(payment_at=500, as_of=200, policy="on_payment")
        self.assertEqual(result["state"], "WAIT_PAYMENT")

    def test_zero_window_only_after_both(self):
        result = sim(refund_window_seconds=0, as_of=200)
        self.assertTrue(result["safe_to_confirm_simulated"])

    def test_reject_invalid_policy_and_window(self):
        for kwargs in ({"policy": "live_payout"}, {"refund_window_seconds": -1},
                       {"refund_window_seconds": 91 * DAY},
                       {"refund_window_seconds": True}):
            with self.assertRaises(ValueError):
                sim(**kwargs)

    def test_reject_invalid_timestamps(self):
        for kwargs in ({"as_of": True}, {"payment_at": -1},
                       {"completion_at": "200"}, {"refund_at": False},
                       {"refund_at": 99}, {"payment_at": None, "refund_at": 300}):
            with self.assertRaises(ValueError):
                sim(**kwargs)


if __name__ == "__main__":
    unittest.main()
