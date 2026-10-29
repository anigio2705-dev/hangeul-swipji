import unittest
from hq_team_consensus import TEAMS, review
class ConsensusTests(unittest.TestCase):
    def valid(self):
        return {t: dict(team=t,decision="ACCEPT",deliverables=["work"],dependencies=["interface"],risks=["risk"],evidence={"run_id":f"run-{t}"},acknowledges=[x for x in TEAMS if x!=t]) for t in TEAMS}
    def test_empty_blocks(self):
        self.assertEqual(review({})["status"],"BLOCKED")
    def test_partial_blocks(self):
        self.assertEqual(review({"11":{"team":"11","decision":"ACCEPT"}})["status"],"BLOCKED")
    def test_missing_evidence_blocks(self):
        d=self.valid();d["12"]["evidence"]={}
        self.assertEqual(review(d)["status"],"BLOCKED")
    def test_missing_cross_ack_blocks(self):
        d=self.valid();d["12"]["acknowledges"].remove("13")
        self.assertEqual(review(d)["status"],"BLOCKED")
    def test_valid_passes(self):
        self.assertEqual(review(self.valid())["status"],"PASS")
if __name__=="__main__": unittest.main()
