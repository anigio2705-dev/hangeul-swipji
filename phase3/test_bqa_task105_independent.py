"""B/15 independent QA-only #105; exact product SHA 97d3aa8e8a707363657e86b7b643b653df1e285e."""
import itertools
import unittest

from team14_referral_continuation_sim import simulate_referral_continuation


def sim(**changes):
    args = dict(policy="platform_90d", lesson_kind="repeat", same_tutor=True,
                days_since_first=5, previous_rewarded_count=1,
                payment_confirmed=True, lesson_completed=True,
                refunded=False, referrer_eligible=True)
    args.update(changes)
    return simulate_referral_continuation(**args)


class BIndependentTask105Tests(unittest.TestCase):
    def assert_no_payout(self, result):
        for key in ("real_money", "payment_enabled", "policy_approved",
                    "payout_authorized"):
            self.assertIs(result[key], False)

    def test_all_valid_policy_kind_combinations_never_enable_payout(self):
        for policy, kind in itertools.product(
            ("first_only", "same_tutor_30d", "platform_90d"),
            ("first", "repeat", "other_tutor", "monthly_renewal")
        ):
            result = sim(policy=policy, lesson_kind=kind,
                         same_tutor=(kind != "other_tutor"),
                         previous_rewarded_count=0)
            self.assert_no_payout(result)

    def test_forged_truthy_flags_are_not_boolean_evidence(self):
        for flag in ("payment_confirmed", "lesson_completed", "refunded",
                     "referrer_eligible", "same_tutor"):
            for forged in (1, "true", [], None):
                with self.subTest(flag=flag, forged=repr(forged)):
                    with self.assertRaises(ValueError):
                        sim(**{flag: forged})

    def test_refund_and_ineligibility_override_other_candidate_states(self):
        for policy in ("first_only", "same_tutor_30d", "platform_90d"):
            args = dict(policy=policy, lesson_kind="first",
                        previous_rewarded_count=0)
            self.assertEqual("REFUND_VOID", sim(**args, refunded=True)["reason"])
            self.assertEqual("REFERRER_INELIGIBLE",
                             sim(**args, referrer_eligible=False)["reason"])

    def test_payment_and_completion_missing_block_all_candidates(self):
        for policy in ("first_only", "same_tutor_30d", "platform_90d"):
            args = dict(policy=policy, lesson_kind="first",
                        previous_rewarded_count=0)
            self.assertEqual("WAIT_PAYMENT",
                             sim(**args, payment_confirmed=False)["reason"])
            self.assertEqual("WAIT_COMPLETION",
                             sim(**args, lesson_completed=False)["reason"])

    def test_windows_and_count_caps_are_exact_boundaries(self):
        for policy, window, cap in (("same_tutor_30d", 30, 3),
                                    ("platform_90d", 90, 10)):
            self.assertTrue(sim(policy=policy, days_since_first=window,
                                previous_rewarded_count=cap-1)["candidate_eligible"])
            self.assertEqual("WINDOW_EXPIRED",
                             sim(policy=policy, days_since_first=window+1,
                                 previous_rewarded_count=cap-1)["reason"])
            self.assertEqual("COUNT_CAP_REACHED",
                             sim(policy=policy, days_since_first=window,
                                 previous_rewarded_count=cap)["reason"])

    def test_first_only_never_rewards_repeat_or_renewal(self):
        for kind in ("repeat", "other_tutor", "monthly_renewal"):
            result = sim(policy="first_only", lesson_kind=kind,
                         same_tutor=(kind != "other_tutor"))
            self.assertEqual("OUT_OF_SCOPE", result["reason"])
            self.assert_no_payout(result)

    def test_same_tutor_scope_does_not_expand_to_other_tutor(self):
        for day in (0, 1, 29, 30):
            result = sim(policy="same_tutor_30d", lesson_kind="other_tutor",
                         same_tutor=False, days_since_first=day)
            self.assertEqual("OUT_OF_SCOPE", result["reason"])

    def test_bounded_counts_and_inconsistent_history_rejected(self):
        for changes in (
            {"days_since_first": True}, {"days_since_first": -1},
            {"days_since_first": 1000001},
            {"previous_rewarded_count": 1000001},
            {"previous_rewarded_count": 1.0},
            {"lesson_kind": "first", "previous_rewarded_count": 1},
            {"lesson_kind": "other_tutor", "same_tutor": True},
            {"policy": "live"}, {"lesson_kind": "payout"},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                sim(**changes)


if __name__ == "__main__":
    unittest.main()
