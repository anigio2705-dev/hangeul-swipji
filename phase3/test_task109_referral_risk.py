"""#109 isolated server-side risk signals; no real payment or account surveillance."""
import unittest
from team14_persistent import SimError
from team14_referral_risk import screen_referral_risk


def booking(**changes):
    result = dict(student_id="child", teacher_id="teacher",
                  payment_verified=True, lesson_completed=True,
                  attendance_verified=True)
    result.update(changes)
    return result


class Task109ReferralRiskTests(unittest.TestCase):
    def screen(self, **changes):
        args = dict(referred_id="child", inviter_id="parent",
                    stored_edges=[], booking=booking())
        args.update(changes)
        return screen_referral_risk(**args)

    def test_normal_trusted_snapshot_is_review_clean_but_never_payout_authorized(self):
        result = self.screen()
        self.assertEqual([], result["flags"])
        self.assertFalse(result["review_required"])
        for field in ("real_money", "payment_enabled", "reward_authorized", "policy_approved"):
            self.assertIs(result[field], False)

    def test_self_referral(self):
        result = self.screen(inviter_id="child")
        self.assertIn("SELF_REFERRAL", result["flags"])
        self.assertIn("CYCLE_OR_RECIPROCAL", result["flags"])

    def test_reciprocal_and_longer_cycles(self):
        self.assertIn("CYCLE_OR_RECIPROCAL", self.screen(
            stored_edges=[("parent", "child")])["flags"])
        self.assertIn("CYCLE_OR_RECIPROCAL", self.screen(
            stored_edges=[("parent", "middle"), ("middle", "child")])["flags"])

    def test_existing_parent_cannot_change_but_replay_is_not_fraud(self):
        old = [("child", "parent")]
        self.assertEqual([], self.screen(stored_edges=old)["flags"])
        result = self.screen(stored_edges=old, inviter_id="other")
        self.assertIn("IMMUTABLE_PARENT_CONFLICT", result["flags"])

    def test_duplicate_and_corrupt_historical_edges(self):
        result = self.screen(stored_edges=[("x", "y"), ("x", "z")])
        self.assertIn("DUPLICATE_OR_CHANGED_PARENT", result["flags"])
        result = self.screen(stored_edges=[("x", "y"), ("y", "x")])
        self.assertIn("CYCLE_OR_RECIPROCAL", result["flags"])

    def test_trusted_duplicate_account_cluster_is_only_a_review_signal(self):
        result = self.screen(verified_account_clusters=[("child", "parent")])
        self.assertIn("POSSIBLE_MULTI_ACCOUNT", result["flags"])
        self.assertTrue(result["account_identity_assessed"])
        self.assertIs(result["reward_authorized"], False)
        self.assertNotIn("POSSIBLE_MULTI_ACCOUNT", self.screen(
            verified_account_clusters=[("child", "other")])["flags"])
        self.assertFalse(self.screen()["account_identity_assessed"])

    def test_unverified_or_fake_transaction_evidence_is_flagged(self):
        for change in (
            {"payment_verified": False},
            {"lesson_completed": False},
            {"attendance_verified": False},
            {"payment_verified": "true"},
        ):
            with self.subTest(change=change):
                self.assertIn("TRANSACTION_EVIDENCE_MISSING",
                              self.screen(booking=booking(**change))["flags"])
        self.assertIn("TRANSACTION_NOT_ASSESSED", self.screen(booking=None)["flags"])

    def test_self_trade_and_booking_owner_mismatch(self):
        self.assertIn("SELF_TRADE", self.screen(
            booking=booking(teacher_id="child"))["flags"])
        self.assertIn("BOOKING_OWNER_MISMATCH", self.screen(
            booking=booking(student_id="someone-else"))["flags"])

    def test_reject_malformed_untrusted_data(self):
        for change in (
            {"stored_edges": "child,parent"},
            {"stored_edges": [("x",)]},
            {"stored_edges": [("x", None)]},
            {"verified_account_clusters": "child,parent"},
            {"verified_account_clusters": [["child", None]]},
            {"booking": {"student_id": "child"}},
        ):
            with self.subTest(change=change), self.assertRaises(SimError):
                self.screen(**change)

    def test_bounded_inputs_and_no_side_effects(self):
        with self.assertRaises(SimError):
            self.screen(stored_edges=[("x", "y")] * 10001)
        with self.assertRaises(SimError):
            self.screen(verified_account_clusters=[()] * 1001)
        result = self.screen(stored_edges=[("ancestor", "top")])
        self.assertFalse(result["review_required"])
        self.assertFalse(result["reward_authorized"])


if __name__ == "__main__":
    unittest.main()
