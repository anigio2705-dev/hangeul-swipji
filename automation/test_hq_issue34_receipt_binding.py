"""Independent 15-team red/green security tests for Issue #34 receipt binding."""
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from hq_issue34_receiver import inspect, trusted_command
from test_hq_issue34_receiver import CATALOG, REGISTRY, NONCE, comment

def bot_receipt(cid, command_id, *, nonce=NONCE, task_id=11, team="11"):
    body = {"comment_id": command_id, "nonce": nonce, "task_id": task_id,
            "team": team, "result": "READ_ONLY_ACK_NO_DISPATCH"}
    return {"id": cid, "user": {"login": "github-actions[bot]"},
            "body": "HQ_RECEIPT_V1\n" + json.dumps(body)}

class ReceiptBindingTests(unittest.TestCase):
    def test_bot_receipt_wrong_nonce_cannot_suppress_valid_owner_command(self):
        self.assertEqual(len(inspect([
            comment(10), bot_receipt(11, 10, nonce="f" * 24)
        ], CATALOG, REGISTRY)), 1)

    def test_bot_receipt_wrong_task_or_team_cannot_suppress_valid_command(self):
        for task, team in ((22, "13"), (11, "12")):
            with self.subTest(task=task, team=team):
                self.assertEqual(len(inspect([
                    comment(10), bot_receipt(11, 10, task_id=task, team=team)
                ], CATALOG, REGISTRY)), 1)

    def test_receipt_earlier_than_command_is_not_acknowledgment(self):
        self.assertEqual(len(inspect([
            bot_receipt(9, 10), comment(10)
        ], CATALOG, REGISTRY)), 1)

    def test_duplicate_json_keys_in_owner_command_fail_closed(self):
        raw = ('HQ_COMMAND_V1\n{"v":1,"task_id":11,"team":"11",'
               '"operation":"AUDIT_READY_ONLY","nonce":"' + NONCE +
               '","task_id":11}')
        self.assertIsNone(trusted_command(comment(10, body=raw), CATALOG, REGISTRY))

    def test_edited_owner_comment_is_not_a_fresh_command(self):
        changed = comment(10)
        changed["created_at"] = "2026-10-30T08:00:00Z"
        changed["updated_at"] = "2026-10-30T08:01:00Z"
        self.assertEqual(inspect([changed], CATALOG, REGISTRY), [])

    def test_genuine_matching_receipt_still_prevents_replay(self):
        self.assertEqual(inspect([
            comment(10), bot_receipt(11, 10)
        ], CATALOG, REGISTRY), [])

if __name__ == "__main__":
    unittest.main()
