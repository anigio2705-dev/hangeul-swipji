import unittest
from hq_pilot import decide, route_failure

class HQPilotTests(unittest.TestCase):
    def test_missing_never_approves(self):
        self.assertEqual(decide({}).state, "waiting")
    def test_failed_contract_blocks(self):
        result = decide({"team13":"success","team14":"success","cross_contract":"failure"})
        self.assertEqual((result.state,result.owner), ("blocked","13+14"))
    def test_pass_requires_staging(self):
        checks = dict.fromkeys(("team13","team14","cross_contract"),"success")
        result = decide(checks)
        self.assertEqual(result.state,"code_passed")
        self.assertTrue(result.approval_required)
        self.assertEqual(decide(checks,True).state,"ready_for_review")
    def test_pending_never_approves(self):
        self.assertEqual(decide({"team13":"success","team14":"queued"}).state,"waiting")
    def test_routes_known_contract_failure(self):
        self.assertEqual(route_failure("sqlite3: no such table: booking_product_snapshots"),"13+14")
    def test_unknown_failure_to_qa(self):
        self.assertEqual(route_failure("unexpected test error"),"15")

if __name__ == "__main__":
    unittest.main()
