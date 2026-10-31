import unittest
from continuous_dispatcher import MARKER, pending, plan

class QueueTests(unittest.TestCase):
    def test_empty_creates_request(self):
        self.assertEqual(plan([])["action"], "create")
    def test_open_request_deduplicates(self):
        self.assertEqual(plan([{"title": MARKER + " a", "state": "open"}])["action"], "wait")
    def test_closed_request_allows_next(self):
        self.assertEqual(plan([{"title": MARKER + " a", "state": "closed"}])["action"], "create")
    def test_pull_request_not_work_request(self):
        self.assertEqual(pending([{"title": MARKER, "state": "open", "pull_request": {}}]), [])
    def test_unrelated_issue_not_blocking(self):
        self.assertEqual(plan([{"title": "Other", "state": "open"}])["action"], "create")
    def test_no_approval_claim(self):
        self.assertIn("NOT evidence", plan([])["body"])
if __name__ == "__main__":
    unittest.main()
