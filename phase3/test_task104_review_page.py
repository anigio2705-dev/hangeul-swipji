"""#104 safe read-only comparison UI; does not approve or pay rewards."""
import json
import unittest
from pathlib import Path
from team14_reward_timing_sim import simulate_reward_timing

ROOT = Path(__file__).resolve().parent

class Task104ReviewPageTests(unittest.TestCase):
    def setUp(self):
        self.html = (ROOT / "reward-timing-review.html").read_text(encoding="utf-8")

    def test_page_exposes_all_three_unapproved_candidates(self):
        for token in ("on_payment", "on_completion", "after_refund_window",
                      "정책 미승인", "INTERNAL_READY=HOLD", "D0", "D2", "D9"):
            self.assertIn(token, self.html)

    def test_no_external_network_scripts_or_live_actions(self):
        self.assertIn("default-src 'none'", self.html)
        self.assertIn("form-action 'none'", self.html)
        self.assertNotIn("<script", self.html.lower())
        self.assertNotIn("<form", self.html.lower())
        self.assertNotIn("<button", self.html.lower())
        self.assertNotIn("fetch(", self.html)

    def test_static_page_is_publicly_allowlisted_and_linked(self):
        files = json.loads((ROOT / "free-public-files.json").read_text(encoding="utf-8"))
        self.assertIn("phase3/reward-timing-review.html", files)
        shell = (ROOT / "shell.html").read_text(encoding="utf-8")
        self.assertIn('href="/phase3/reward-timing-review.html"', shell)

    def test_example_matches_pure_simulator_without_payout(self):
        day = 86400
        for policy, trigger in (("on_payment", 0), ("on_completion", 2 * day),
                                ("after_refund_window", 9 * day)):
            result = simulate_reward_timing(
                payment_at=0, completion_at=2 * day, as_of=9 * day,
                policy=policy, refund_window_seconds=7 * day)
            self.assertEqual(trigger, result["candidate_trigger_at"])
            self.assertFalse(result["real_money"])
            self.assertFalse(result["payment_enabled"])
            self.assertFalse(result["policy_approved"])

    def test_scheduled_future_refund_never_confirms(self):
        day = 86400
        result = simulate_reward_timing(payment_at=0, completion_at=2 * day,
                                       refund_at=10 * day, as_of=9 * day,
                                       policy="after_refund_window",
                                       refund_window_seconds=7 * day)
        self.assertFalse(result["safe_to_confirm_simulated"])
        self.assertFalse(result["payment_enabled"])

if __name__ == "__main__":
    unittest.main()
