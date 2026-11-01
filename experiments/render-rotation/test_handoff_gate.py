"""Render rotation QA planning safety tests; no API credentials needed."""
import datetime as dt
import unittest
from handoff_gate import plan_tick

START=dt.datetime(2026,11,1,tzinfo=dt.timezone.utc).timestamp()
def sample(status="CI_PASS", retries=0):
    return dict(REQUEST_ID="HUB-20261101-C-001",TASK_ID="C-AUTO-1",
                SOURCE_ROLE="C",TARGET_ROLE="B",PR_NUMBER=168,
                PRODUCT_SHA="a"*40,QA_SHA="",CI_RUN_URL="https://example.invalid/ci",
                QA_STATUS=status,FAILURE_EVIDENCE="",RETRY_COUNT=retries,
                NEXT_ACTION="",UPDATED_AT="2026-11-01T00:00:00Z")
class GateTests(unittest.TestCase):
    def test_b_requests_only_after_ci(self):
        self.assertEqual(plan_tick(START+240*3,sample())["action"],"REQUEST_B_QA_VIA_TRUSTED_OUTBOX")
        self.assertEqual(plan_tick(START+240*3,sample("CODE_READY"))["action"],"NOOP")
    def test_c_failure_needs_verified_repair(self):
        self.assertEqual(plan_tick(START,sample("QA_FAIL"))["action"],"FETCH_VERIFIED_FAILURE_AND_REPAIR")
        self.assertEqual(plan_tick(START,sample("QA_FAIL",3))["action"],"ESCALATE_245")
    def test_c_pass_never_changes_qa(self):
        self.assertEqual(plan_tick(START,sample("QA_PASS"))["action"],"NO_C_FIX_A_REVIEW_ONLY")
    def test_invalid_sha_or_contract_holds(self):
        self.assertEqual(plan_tick(START,sample()|{"PRODUCT_SHA":"wrong"})["action"],"HOLD_INVALID_CONTRACT")
        self.assertEqual(plan_tick(START,{"PR_NUMBER":168})["action"],"HOLD_INVALID_CONTRACT")
if __name__=="__main__":
    unittest.main()
