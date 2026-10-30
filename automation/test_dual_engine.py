import unittest
from automation.dual_engine import new_state, speak, next_team, advance_round, queue_work, work_result, approve

class DualEngineTests(unittest.TestCase):
    def entry(self, i, previous=None):
        return dict(agreement="agree", challenge="counterexample",
                    hypothesis="hypothesis-" + str(i), experiment="test-" + str(i),
                    evidence="https://github.com/example/evidence/" + str(i),
                    handoff="question", read_previous=previous)

    def test_six_ordered_turns_and_round(self):
        s = new_state()
        previous = None
        for i, team in enumerate(("11","12","13","14","15","16")):
            record = speak(s, team, self.entry(i, previous))
            previous = record["id"]
        self.assertIsNone(next_team(s))
        advance_round(s)
        self.assertEqual(next_team(s), "11")
        self.assertEqual(s["round"], 2)

    def test_out_of_order_and_missing_predecessor(self):
        s = new_state()
        with self.assertRaises(ValueError):
            speak(s, "14", self.entry(1))
        speak(s, "11", self.entry(1))
        with self.assertRaises(ValueError):
            speak(s, "12", self.entry(2))
        self.assertEqual(s["turn"], 1)

    def test_no_duplicate_hypotheses(self):
        s = new_state()
        speak(s, "11", self.entry(1))
        with self.assertRaises(ValueError):
            speak(s, "12", self.entry(1, "R1-T1"))

    def test_parallel_work_does_not_wait_for_discussion(self):
        s = new_state()
        queue_work(s, dict(id="W1", owner="14", hypothesis="new", test="pytest",
                           branch="isolated/101"))
        self.assertEqual(next_team(s), "11")
        work_result(s, "W1", "verified", "sha:abc-ci:green")
        self.assertEqual(s["work"][0]["status"], "verified")

    def test_ready_fail_closed(self):
        s = new_state()
        with self.assertRaises(ValueError):
            approve(s, "15", "ci")
        queue_work(s, dict(id="W1", owner="14", hypothesis="new", test="pytest",
                           branch="isolated/101"))
        with self.assertRaises(ValueError):
            approve(s, "11", "ci")
        with self.assertRaises(ValueError):
            approve(s, "15", "ci")
        work_result(s, "W1", "verified", "sha:abc")
        result = approve(s, "15", "independent-ci:abc")
        self.assertEqual(result, "PENDING_TRUSTED_INDEPENDENT_REVIEW")
        self.assertFalse(s["ready"])
        self.assertFalse(s["independent_approval"])
        self.assertEqual(s["review_request"]["claimed_team"], "15")

    def test_forged_local_approval_never_sets_ready(self):
        s = new_state()
        queue_work(s, dict(id="W1", owner="14", hypothesis="H", test="pytest",
                           branch="isolated/101"))
        work_result(s, "W1", "verified", "sha:abc")
        for forged_evidence in ("ci:success", "https://github.com/example/actions/runs/1"):
            approve(s, "15", forged_evidence)
            self.assertFalse(s["ready"])
            self.assertFalse(s["independent_approval"])

    def test_protect_main_and_duplicate_jobs(self):
        s = new_state()
        with self.assertRaises(ValueError):
            queue_work(s, dict(id="W1", owner="14", hypothesis="new", test="pytest",
                               branch="main"))
        job = dict(id="W1", owner="14", hypothesis="new", test="pytest", branch="isolated")
        queue_work(s, job)
        with self.assertRaises(ValueError):
            queue_work(s, job)

if __name__ == "__main__":
    unittest.main()
