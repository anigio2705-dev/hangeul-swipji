"""Independent B/15 QA-only adversarial regression for #104 exact product SHA.

Base: PR #166 148b074f60b91c3bb13ec4a0d6f4e0f0f44a3075.
No product edits, no DB/network/payment calls, no real settlement approval.
"""
import itertools
import unittest

from team14_reward_timing_sim import simulate_reward_timing, POLICIES, MAX_WINDOW_SECONDS

DAY = 86400
LOCKED = ("real_money", "payment_enabled", "policy_approved")


def run(**changes):
    data = dict(payment_at=100, completion_at=200, refund_at=None,
                as_of=200, policy="after_refund_window",
                refund_window_seconds=DAY)
    data.update(changes)
    return simulate_reward_timing(**data)


class IndependentBTask104QA(unittest.TestCase):
    def locked(self, result):
        for key in LOCKED:
            self.assertIs(result[key], False, key)

    def test_01_every_policy_never_enables_real_money_across_matrix(self):
        for policy, payment, completed, now, window in itertools.product(
                sorted(POLICIES), (None, 0, 100, 300),
                (None, 0, 200, 400), (0, 100, 200, 300, 500),
                (0, 1, DAY)):
            with self.subTest(policy=policy, payment=payment, completed=completed,
                              now=now, window=window):
                r = run(policy=policy, payment_at=payment, completion_at=completed,
                        as_of=now, refund_window_seconds=window)
                self.locked(r)
                if payment is None or payment > now:
                    self.assertFalse(r["candidate_triggered"])
                    self.assertFalse(r["safe_to_confirm_simulated"])

    def test_02_refund_at_and_before_observation_voids_every_policy(self):
        for policy in sorted(POLICIES):
            for refund, now in ((100, 100), (101, 101), (200, 200),
                                (201, 201), (201, 300), (DAY + 200, DAY + 200)):
                with self.subTest(policy=policy, refund=refund, now=now):
                    r = run(policy=policy, refund_at=refund, as_of=now)
                    self.assertEqual("VOID_REFUND", r["state"])
                    self.assertFalse(r["candidate_triggered"])
                    self.assertFalse(r["safe_to_confirm_simulated"])
                    self.locked(r)

    def test_03_known_future_refund_never_marked_safe(self):
        for policy in sorted(POLICIES):
            for future in (200 + DAY + 1, 200 + DAY * 3):
                r = run(policy=policy, refund_at=future, as_of=200 + DAY)
                self.assertFalse(r["safe_to_confirm_simulated"])
                self.locked(r)

    def test_04_window_exact_boundary_and_reversed_event_order(self):
        for paid, done, window in ((100, 200, 0), (100, 200, 1),
                                   (300, 200, DAY), (0, 0, 1),
                                   (300, 100, MAX_WINDOW_SECONDS)):
            deadline = max(paid, done) + window
            at = run(payment_at=paid, completion_at=done,
                     as_of=deadline, refund_window_seconds=window)
            self.assertEqual(deadline, at["candidate_trigger_at"])
            self.assertTrue(at["candidate_triggered"])
            self.assertTrue(at["safe_to_confirm_simulated"])
            self.locked(at)
            if deadline > 0:
                before = run(payment_at=paid, completion_at=done,
                             as_of=deadline - 1, refund_window_seconds=window)
                self.assertFalse(before["safe_to_confirm_simulated"])

    def test_05_completion_policy_requires_both_events(self):
        for payment, completion, now in ((None, 1, 200), (1, None, 200),
                                         (300, 1, 200), (1, 300, 200)):
            r = run(policy="on_completion", payment_at=payment,
                    completion_at=completion, as_of=now)
            self.assertFalse(r["candidate_triggered"])
            self.assertFalse(r["safe_to_confirm_simulated"])
            self.locked(r)

    def test_06_future_refund_after_candidate_trigger_stays_provisional(self):
        for policy in sorted(POLICIES):
            r = run(policy=policy, as_of=200 + DAY + 1,
                    refund_at=200 + DAY + 2)
            self.assertEqual("PROVISIONAL_REFUND_RISK", r["state"])
            self.assertFalse(r["safe_to_confirm_simulated"])
            self.locked(r)

    def test_07_invalid_unhashable_and_boolean_policy_rejected(self):
        for invalid in (None, True, 1, [], {}, set(), (), "cash_out", ""):
            with self.subTest(value=repr(invalid)), self.assertRaises(ValueError):
                run(policy=invalid)

    def test_08_invalid_time_and_window_types_rejected(self):
        for key, invalid in (
            ("payment_at", True), ("completion_at", 1.0),
            ("refund_at", False), ("as_of", "200"), ("as_of", -1),
            ("refund_window_seconds", True), ("refund_window_seconds", -1),
            ("refund_window_seconds", MAX_WINDOW_SECONDS + 1)):
            with self.subTest(key=key, invalid=invalid), self.assertRaises(ValueError):
                run(**{key: invalid})

    def test_09_refund_cannot_precede_payment(self):
        with self.assertRaises(ValueError):
            run(payment_at=200, refund_at=199, as_of=300)
        with self.assertRaises(ValueError):
            run(payment_at=None, refund_at=201, as_of=300)

    def test_10_no_future_events_are_treated_as_completed(self):
        for policy in sorted(POLICIES):
            r = run(payment_at=300, completion_at=400, as_of=200, policy=policy)
            self.assertEqual("WAIT_PAYMENT", r["state"])
            self.assertFalse(r["candidate_triggered"])
            self.assertFalse(r["safe_to_confirm_simulated"])
            self.locked(r)


if __name__ == "__main__":
    unittest.main()
