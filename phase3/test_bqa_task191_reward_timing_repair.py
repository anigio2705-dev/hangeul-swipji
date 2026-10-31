"""Independent B/15 QA for #191 exact product SHA; no money or network."""
import json
import unittest
from pathlib import Path
from team14_reward_timing_sim import simulate_reward_timing

ROOT = Path(__file__).resolve().parent
DAY = 86400

def preview(**kw):
    args = dict(payment_at=0, completion_at=2*DAY, as_of=9*DAY,
                refund_window_seconds=7*DAY, policy="after_refund_window")
    args.update(kw)
    return simulate_reward_timing(**args)

class BQA191Repair(unittest.TestCase):
    def test_future_refund_cannot_confirm_for_any_policy(self):
        for policy in ("on_payment", "on_completion", "after_refund_window"):
            with self.subTest(policy=policy):
                r=preview(policy=policy, refund_at=10*DAY)
                self.assertFalse(r["safe_to_confirm_simulated"])
                self.assertNotEqual("SIMULATED_WINDOW_CLOSED", r["state"])
    def test_refund_at_boundary_voids_candidate(self):
        for refund_at in (0, 2*DAY, 9*DAY):
            with self.subTest(refund_at=refund_at):
                r=preview(refund_at=refund_at)
                self.assertEqual("VOID_REFUND", r["state"])
                self.assertFalse(r["candidate_triggered"])
    def test_future_refund_after_window_still_blocks_confirmation(self):
        self.assertFalse(preview(as_of=365*DAY, refund_at=366*DAY)["safe_to_confirm_simulated"])
    def test_no_payment_or_no_completion_fails_closed(self):
        for key in ("payment_at","completion_at"):
            with self.subTest(key=key):
                r=preview(**{key:None})
                self.assertFalse(r["safe_to_confirm_simulated"])
    def test_policy_rejects_untrusted_types(self):
        for bad in (None, True, False, 1, [], {}, "ON_PAYMENT", "on_payment;pay"):
            with self.subTest(value=repr(bad)), self.assertRaises(ValueError):
                preview(policy=bad)
    def test_timestamp_and_window_reject_non_integer_types(self):
        for field in ("payment_at", "completion_at", "refund_at", "as_of", "refund_window_seconds"):
            for bad in (True, 1.5, -1, "0"):
                with self.subTest(field=field,bad=bad), self.assertRaises(ValueError):
                    preview(**{field:bad})
    def test_all_candidate_policies_never_authorize_money(self):
        for policy in ("on_payment", "on_completion", "after_refund_window"):
            r=preview(policy=policy)
            for key in ("real_money", "policy_approved", "payment_enabled"):
                self.assertIs(r[key], False)
    def test_review_ui_has_no_active_network_or_payment_surface(self):
        html=(ROOT/"reward-timing-review.html").read_text(encoding="utf-8").lower()
        for forbidden in ("<script", "<form", "<iframe", "fetch(", "xmlhttprequest", "paymentrequest"):
            self.assertNotIn(forbidden, html)
        self.assertIn("default-src 'none'", html)
        self.assertIn("form-action 'none'", html)
    def test_review_ui_lists_three_candidates_and_unapproved_gate(self):
        html=(ROOT/"reward-timing-review.html").read_text(encoding="utf-8")
        for value in ("on_payment","on_completion","after_refund_window","정책 미승인","INTERNAL_READY=HOLD"):
            self.assertIn(value, html)
    def test_public_allowlist_and_shell_route(self):
        allowed=json.loads((ROOT/"free-public-files.json").read_text(encoding="utf-8"))
        self.assertEqual(1,allowed.count("phase3/reward-timing-review.html"))
        self.assertIn('href="/phase3/reward-timing-review.html"',
                      (ROOT/"shell.html").read_text(encoding="utf-8"))

if __name__ == "__main__":
    unittest.main()
