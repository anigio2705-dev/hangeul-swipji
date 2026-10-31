"""B/15 independent adversarial QA for product #109 exact 8e04ee874b1b6b3649080d833d5f813308c07a66.

QA-only; no production DB, HTTP, payment, payout or identity service.
These tests are independent of product's test_task109_referral_risk.py.
"""
import copy
import unittest

from team14_persistent import SimError
from team14_referral_risk import screen_referral_risk


def trusted_booking(**changes):
    data = dict(student_id="child", teacher_id="tutor", payment_verified=True,
                lesson_completed=True, attendance_verified=True)
    data.update(changes)
    return data


def check(**changes):
    args = dict(referred_id="child", inviter_id="parent",
                stored_edges=(), verified_account_clusters=(),
                booking=trusted_booking())
    args.update(changes)
    return screen_referral_risk(**args)


class BIndependentTask109Tests(unittest.TestCase):
    def assert_no_money(self, result):
        for key in ("real_money", "payment_enabled", "reward_authorized",
                    "policy_approved"):
            self.assertIs(result[key], False)

    def test_baseline_is_review_only_never_authorization(self):
        result = check()
        self.assertEqual([], result["flags"])
        self.assertIs(result["review_required"], False)
        self.assert_no_money(result)

    def test_injected_booking_evidence_never_turns_on_payout(self):
        for key in ("payment_verified", "lesson_completed", "attendance_verified"):
            for bad in (False, None, 1, "true", [], {}):
                with self.subTest(key=key, bad=repr(bad)):
                    result = check(booking=trusted_booking(**{key: bad}))
                    self.assertIn("TRANSACTION_EVIDENCE_MISSING", result["flags"])
                    self.assert_no_money(result)

    def test_historical_graph_cycles_not_just_new_edge(self):
        for edges in (
            [("a", "b"), ("b", "a")],
            [("a", "b"), ("b", "c"), ("c", "a")],
            [("a", "a")],
        ):
            with self.subTest(edges=edges):
                result = check(stored_edges=edges)
                self.assertIn("CYCLE_OR_RECIPROCAL", result["flags"])
                self.assert_no_money(result)

    def test_new_edge_closes_cycle_and_reciprocal(self):
        for edges in ([("parent", "child")],
                      [("parent", "grandparent"), ("grandparent", "child")]):
            result = check(stored_edges=edges)
            self.assertIn("CYCLE_OR_RECIPROCAL", result["flags"])
            self.assertTrue(result["review_required"])

    def test_existing_parent_immutability_and_idempotent_replay(self):
        self.assertNotIn("IMMUTABLE_PARENT_CONFLICT",
                         check(stored_edges=[("child", "parent")])["flags"])
        conflict = check(stored_edges=[("child", "original")])
        self.assertIn("IMMUTABLE_PARENT_CONFLICT", conflict["flags"])
        self.assert_no_money(conflict)

    def test_duplicate_historical_parent_is_not_silently_clean(self):
        result = check(stored_edges=[("a", "b"), ("a", "c")])
        self.assertIn("DUPLICATE_OR_CHANGED_PARENT", result["flags"])
        self.assertTrue(result["review_required"])

    def test_cluster_signal_requires_explicit_trusted_group(self):
        self.assertNotIn("POSSIBLE_MULTI_ACCOUNT", check()["flags"])
        flagged = check(verified_account_clusters=[("child", "parent", "other")])
        self.assertIn("POSSIBLE_MULTI_ACCOUNT", flagged["flags"])
        self.assertTrue(flagged["account_identity_assessed"])
        self.assert_no_money(flagged)
        not_flagged = check(verified_account_clusters=[("child", "other")])
        self.assertNotIn("POSSIBLE_MULTI_ACCOUNT", not_flagged["flags"])

    def test_booking_mismatch_self_trade_and_missing_snapshot(self):
        cases = (
            (trusted_booking(student_id="outsider"), "BOOKING_OWNER_MISMATCH"),
            (trusted_booking(teacher_id="child"), "SELF_TRADE"),
            (None, "TRANSACTION_NOT_ASSESSED"),
        )
        for snapshot, flag in cases:
            with self.subTest(flag=flag):
                result = check(booking=snapshot)
                self.assertIn(flag, result["flags"])
                self.assert_no_money(result)

    def test_malformed_trusted_inputs_rejected(self):
        for changes in (
            {"referred_id": None}, {"inviter_id": 0},
            {"stored_edges": "a,b"}, {"stored_edges": [("a",)]},
            {"stored_edges": [("a", None)]},
            {"verified_account_clusters": "a,b"},
            {"verified_account_clusters": [("child", None)]},
            {"verified_account_clusters": [("x",) * 101]},
            {"booking": {"student_id": "child", "teacher_id": None}},
            {"booking": []},
        ):
            with self.subTest(changes=repr(changes)), self.assertRaises(SimError):
                check(**changes)

    def test_bounded_inputs_and_sorted_deterministic_flags(self):
        with self.assertRaises(SimError):
            check(stored_edges=[("a", "b")] * 10001)
        with self.assertRaises(SimError):
            check(verified_account_clusters=[()] * 1001)
        edges = [("parent", "child"), ("x", "y"), ("x", "z")]
        clusters = [("parent", "child")]
        booking = trusted_booking(teacher_id="child", payment_verified=False)
        before = copy.deepcopy((edges, clusters, booking))
        result = check(stored_edges=edges, verified_account_clusters=clusters,
                       booking=booking)
        self.assertEqual(result["flags"], sorted(set(result["flags"])))
        self.assertEqual((edges, clusters, booking), before)
        self.assert_no_money(result)


if __name__ == "__main__":
    unittest.main()
