"""Team 15 independent #102 negative-case audit. QA-only, no product changes or payments.
Candidate PR #156 exact SHA c042cf00064d0ac0e875121895a4d55c9443ddff.
Run by existing phase3-isolated-tests.yml push workflow, not central #157 CI.
"""
import pathlib
import subprocess
import unittest

from team14_persistent import SimError
from team14_referral_eligibility import eligible_referral
from team14_referral_scenarios import simulate_referral
from team14_referral_store import ReferralStore

CANDIDATE = "c042cf00064d0ac0e875121895a4d55c9443ddff"
PRODUCT = "d8c6a625ad72334f467e33c173996b79c120081c"
QA_PATH = "phase3/test_qa15_task102_policy_negative.py"
ROOT = pathlib.Path(__file__).resolve().parent.parent


class Team15Task102IndependentCases(unittest.TestCase):
    def test_00_exact_candidate_base_and_qa_only_delta(self):
        def git(*args):
            return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()
        self.assertEqual(git("rev-parse", "HEAD^"), CANDIDATE)
        self.assertEqual(git("rev-parse", "HEAD^:phase3/team14_referral_eligibility.py"),
                         git("rev-parse", "HEAD:phase3/team14_referral_eligibility.py"))
        self.assertEqual(git("rev-parse", "HEAD^:phase3/team14_referral_scenarios.py"),
                         git("rev-parse", "HEAD:phase3/team14_referral_scenarios.py"))
        self.assertEqual(git("rev-parse", "HEAD^:docs/TASK102_REFERRAL_POLICY_COMPARISON_20261031.md"),
                         git("rev-parse", "HEAD:docs/TASK102_REFERRAL_POLICY_COMPARISON_20261031.md"))
        self.assertEqual(git("diff", "--name-only", "HEAD^", "HEAD"), QA_PATH)
        print("QA15_EXACT_CANDIDATE_BASE=" + CANDIDATE)
        print("QA15_ONLY_DELTA=" + QA_PATH)

    def test_01_doc_correction_and_policy_unapproved(self):
        text = (ROOT / "docs/TASK102_REFERRAL_POLICY_COMPARISON_20261031.md").read_text(encoding="utf-8")
        for phrase in ("eligible_referral", "simulate_referral", "21,000원",
                       "20,000원", "정책", "READY=0", PRODUCT,
                       "실지급", "payment_enabled=False"):
            self.assertIn(phrase, text)
        self.assertIn("실제 조상 존재 여부를 지급률 계산에 반영하지 않는", text)

    def test_02_missing_ancestor_and_abstract_simulator_difference(self):
        real = eligible_referral(100000, "student", [("student", "alice")], (300, 100), 2000)
        abstract = simulate_referral(100000, [("student", "alice")], (300, 100), 2000)
        self.assertEqual(real["recipients"], [{"user_id": "alice", "amount_krw": 3000}])
        self.assertEqual((real["teacher_krw"], real["platform_krw"]), (76000, 21000))
        self.assertEqual((abstract["teacher"], abstract["rewards"], abstract["platform"]),
                         (76000, [3000, 1000], 20000))

    def test_03_empty_graph_does_not_create_phantom_reward(self):
        real = eligible_referral(100000, "student", [], (300, 100), 2000)
        abstract = simulate_referral(100000, [], (300, 100), 2000)
        self.assertEqual(real["recipients"], [])
        self.assertEqual((real["teacher_krw"], real["platform_krw"]), (76000, 24000))
        self.assertEqual(abstract["rewards"], [3000, 1000])
        self.assertEqual(abstract["platform"], 20000)

    def test_04_full_two_ancestors_and_conservation(self):
        real = eligible_referral(100000, "student",
                                 [("student", "alice"), ("alice", "bob")], (300, 100), 2000)
        self.assertEqual(real["recipients"], [
            {"user_id": "alice", "amount_krw": 3000},
            {"user_id": "bob", "amount_krw": 1000}])
        self.assertEqual(real["teacher_krw"], 76000)
        self.assertEqual(real["platform_krw"], 20000)
        self.assertEqual(real["teacher_krw"] + real["platform_krw"]
                         + sum(x["amount_krw"] for x in real["recipients"]), 100000)

    def test_05_cycle_rejected_in_both_modules(self):
        edges = [("a", "b"), ("b", "c"), ("c", "a")]
        with self.assertRaises(SimError):
            eligible_referral(100000, "a", edges, (300, 100), 2000)
        with self.assertRaises(SimError):
            simulate_referral(100000, edges, (300, 100), 2000)

    def test_06_duplicate_and_self_parent_rejected(self):
        for edges in ([("student", "student")],
                      [("student", "alice"), ("student", "bob")]):
            with self.subTest(edges=edges):
                with self.assertRaises(SimError):
                    eligible_referral(100000, "student", edges, (300, 100), 2000)
                with self.assertRaises(SimError):
                    simulate_referral(100000, edges, (300, 100), 2000)

    def test_07_budget_overrun_and_11_depth_fail_closed(self):
        for rates in ((9000, 2000), tuple([100] * 11)):
            with self.subTest(rates=rates):
                with self.assertRaises(SimError):
                    eligible_referral(100000, "student", [], rates, 2000)
                with self.assertRaises(SimError):
                    simulate_referral(100000, [], rates, 2000)

    def test_08_rounding_conserves_every_won(self):
        for gross in (1, 2, 3, 7, 99, 101, 100001):
            with self.subTest(gross=gross):
                x = eligible_referral(gross, "student",
                      [("student", "alice"), ("alice", "bob")], (3333, 3333), 1000)
                self.assertEqual(gross, x["teacher_krw"] + x["platform_krw"]
                     + sum(row["amount_krw"] for row in x["recipients"]))
                y = simulate_referral(gross, [], (3333, 3333), 1000)
                self.assertEqual(gross, y["teacher"] + y["platform"] + sum(y["rewards"]))

    def test_09_boolean_rate_rejected(self):
        for rate in (True, False, -1, 10001, "300"):
            with self.subTest(rate=rate):
                with self.assertRaises(SimError):
                    eligible_referral(100000, "student", [], (rate,), 2000)
                with self.assertRaises(SimError):
                    simulate_referral(100000, [], (rate,), 2000)

    def test_10_all_mock_payout_safety_flags_false(self):
        x = eligible_referral(100000, "student", [("student", "alice")], (300, 100), 2000)
        y = simulate_referral(100000, [("student", "alice")], (300, 100), 2000)
        for z in (x, y):
            for flag in ("real_money", "policy_approved", "payment_enabled"):
                self.assertIs(z[flag], False)

    def test_11_store_missing_parent_and_no_retroactive_reward(self):
        store = ReferralStore(":memory:")
        try:
            store.link("student", "alice")
            first = store.award("event1", "student", "lesson1", 100000, (300, 100), 2000)
            self.assertEqual(first["platform_krw"], 21000)
            store.link("alice", "bob")
            self.assertEqual(first, store.award("event1", "student", "lesson1",
                                               100000, (300, 100), 2000))
            second = store.award("event2", "student", "lesson2", 100000, (300, 100), 2000)
            self.assertEqual(second["platform_krw"], 20000)
            self.assertEqual(len(second["recipients"]), 2)
        finally:
            store.close()

    def test_12_store_cycle_and_duplicate_lesson_fail_closed(self):
        store = ReferralStore(":memory:")
        try:
            store.link("student", "alice")
            with self.assertRaises(SimError):
                store.link("alice", "student")
            store.award("event1", "student", "lesson1", 100000)
            with self.assertRaises(SimError):
                store.award("event2", "student", "lesson1", 100000)
            self.assertEqual(store.db.execute("SELECT COUNT(*) FROM referral_awards").fetchone()[0], 1)
        finally:
            store.close()

    def test_13_product_commit_unchanged_in_document_candidate(self):
        p = subprocess.check_output(["git", "rev-parse", CANDIDATE + ":phase3/server.py"],
                                    cwd=ROOT, text=True).strip()
        q = subprocess.check_output(["git", "rev-parse", PRODUCT + ":phase3/server.py"],
                                    cwd=ROOT, text=True).strip()
        self.assertEqual(p, q)
        print("QA15_PRODUCT_SERVER_UNCHANGED=" + PRODUCT)


if __name__ == "__main__":
    unittest.main(verbosity=2)
