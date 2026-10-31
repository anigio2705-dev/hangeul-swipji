"""#105 isolated comparison regression tests; no real payment or DB writes."""
import unittest

from team14_referral_continuation_sim import simulate_referral_continuation as sim


def candidate(**overrides):
    kwargs = dict(
        policy="first_only", lesson_kind="first", same_tutor=True,
        days_since_first=0, previous_rewarded_count=0,
        payment_confirmed=True, lesson_completed=True,
        refunded=False, referrer_eligible=True,
    )
    kwargs.update(overrides)
    return sim(**kwargs)


class ReferralContinuationTests(unittest.TestCase):
    def assert_simulation_only(self, value):
        self.assertIs(value["real_money"], False)
        self.assertIs(value["payment_enabled"], False)
        self.assertIs(value["policy_approved"], False)
        self.assertIs(value["payout_authorized"], False)

    def test_first_only_allows_first_completed_paid_lesson(self):
        value = candidate()
        self.assertTrue(value["candidate_eligible"])
        self.assertEqual(value["reason"], "SIMULATED_CANDIDATE")
        self.assert_simulation_only(value)

    def test_first_only_blocks_repeat_and_monthly(self):
        for kind in ("repeat", "monthly_renewal"):
            with self.subTest(kind=kind):
                value = candidate(lesson_kind=kind, previous_rewarded_count=1)
                self.assertEqual(value["reason"], "OUT_OF_SCOPE")
                self.assert_simulation_only(value)

    def test_same_tutor_30d_repeat_and_renewal(self):
        for kind in ("repeat", "monthly_renewal"):
            value = candidate(policy="same_tutor_30d", lesson_kind=kind,
                              previous_rewarded_count=1, days_since_first=30)
            self.assertTrue(value["candidate_eligible"])
            self.assert_simulation_only(value)

    def test_same_tutor_30d_rejects_other_tutor(self):
        value = candidate(policy="same_tutor_30d", lesson_kind="other_tutor",
                          same_tutor=False, days_since_first=10)
        self.assertEqual(value["reason"], "OUT_OF_SCOPE")

    def test_platform_90d_other_tutor_and_monthly(self):
        for kind, same in (("other_tutor", False), ("monthly_renewal", True)):
            value = candidate(policy="platform_90d", lesson_kind=kind,
                              same_tutor=same, days_since_first=90)
            self.assertTrue(value["candidate_eligible"])
            self.assert_simulation_only(value)

    def test_time_window_boundary(self):
        for policy, day in (("same_tutor_30d", 31), ("platform_90d", 91)):
            value = candidate(policy=policy, lesson_kind="repeat",
                              days_since_first=day)
            self.assertEqual(value["reason"], "WINDOW_EXPIRED")
            self.assertFalse(value["candidate_eligible"])

    def test_reward_count_cap_boundary(self):
        for policy, count in (("same_tutor_30d", 3), ("platform_90d", 10)):
            value = candidate(policy=policy, lesson_kind="repeat",
                              previous_rewarded_count=count)
            self.assertEqual(value["reason"], "COUNT_CAP_REACHED")

    def test_refund_voids_even_candidate(self):
        value = candidate(policy="platform_90d", lesson_kind="repeat",
                          refunded=True)
        self.assertEqual(value["reason"], "REFUND_VOID")
        self.assertFalse(value["candidate_eligible"])
        self.assert_simulation_only(value)

    def test_ineligible_referrer_blocks_new_reward_not_lesson(self):
        value = candidate(referrer_eligible=False)
        self.assertEqual(value["reason"], "REFERRER_INELIGIBLE")
        self.assertFalse(value["candidate_eligible"])
        self.assert_simulation_only(value)

    def test_missing_payment_and_completion(self):
        self.assertEqual(candidate(payment_confirmed=False)["reason"],
                         "WAIT_PAYMENT")
        self.assertEqual(candidate(lesson_completed=False)["reason"],
                         "WAIT_COMPLETION")

    def test_reject_inconsistent_other_tutor(self):
        with self.assertRaises(ValueError):
            candidate(lesson_kind="other_tutor", same_tutor=True)

    def test_reject_first_lesson_with_prior_reward(self):
        with self.assertRaises(ValueError):
            candidate(previous_rewarded_count=1)

    def test_reject_invalid_policy_kind_and_counts(self):
        for kwargs in (
                {"policy": "auto_payout"},
                {"policy": []},
                {"lesson_kind": "fake_booking"},
                {"days_since_first": -1},
                {"days_since_first": True},
                {"previous_rewarded_count": -1},
                {"previous_rewarded_count": 1000001}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                candidate(**kwargs)

    def test_reject_non_boolean_state_flags(self):
        for key in ("same_tutor", "payment_confirmed", "lesson_completed",
                    "refunded", "referrer_eligible"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                candidate(**{key: 1})

    def test_no_candidate_can_authorize_payout(self):
        for policy in ("first_only", "same_tutor_30d", "platform_90d"):
            value = candidate(policy=policy)
            self.assert_simulation_only(value)


if __name__ == "__main__":
    unittest.main()
