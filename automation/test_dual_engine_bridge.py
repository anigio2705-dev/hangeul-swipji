import json
import unittest
from automation.dual_engine import new_state, work_result
from automation.dual_engine_bridge import ingest_turn, dispatch_approved, progress

class BridgeTests(unittest.TestCase):
    def comment(self, author="trusted", team="11"):
        body = dict(type="TEAM_TURN", task="101", round=1, team=team,
                    agreement="yes", challenge="no", hypothesis="H1",
                    experiment="test", evidence="sha-and-ci", handoff="next")
        return dict(author=author, issue_number=34, team_identity=team,
                    url="https://github.com/anigio2705-dev/hangeul-swipji/issues/34#issuecomment-123",
                    body=json.dumps(body))

    def test_trusted_turn(self):
        s = new_state()
        ingest_turn(s, self.comment(), {"trusted"})
        self.assertEqual(progress(s)["next_team"], "12")

    def test_untrusted_rejected(self):
        with self.assertRaises(ValueError):
            ingest_turn(new_state(), self.comment(author="attacker"), {"trusted"})

    def test_team_spoof_rejected(self):
        with self.assertRaises(ValueError):
            ingest_turn(new_state(), self.comment(team="14"), {"trusted"})

    def test_wrong_issue_rejected(self):
        c = self.comment()
        c["issue_number"] = 35
        with self.assertRaises(ValueError):
            ingest_turn(new_state(), c, {"trusted"})

    def test_work_requires_central_approval(self):
        s = new_state()
        job = dict(id="W1", owner="14", hypothesis="H", test="pytest",
                   branch="isolated/101")
        with self.assertRaises(ValueError):
            dispatch_approved(s, [job])
        self.assertEqual(len(s["work"]), 0)
        dispatch_approved(s, [{**job, "approved_by_central": True}])
        self.assertEqual(progress(s)["queued_jobs"], 1)
        work_result(s, "W1", "verified", "sha-ci")
        self.assertTrue(progress(s)["development_complete"])
        self.assertFalse(progress(s)["ready_complete"])

    def test_no_ready_from_discussion_or_code_alone(self):
        s = new_state()
        self.assertEqual(progress(s)["ready_complete"], False)
        self.assertEqual(progress(s)["discussion_complete"], False)

if __name__ == "__main__":
    unittest.main()
