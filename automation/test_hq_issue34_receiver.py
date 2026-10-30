"""Security and canonical ownership regressions for Issue #34 receiver."""
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from hq_issue34_receiver import inspect, trusted_command, trusted_receipt

CATALOG = {11: {"owner": "11"}, 22: {"owner": "13"}, 47: {"owner": "12"}}
REGISTRY = {"items": {"11": {"owner": "11", "state": "CANDIDATE"},
                      "22": {"owner": "13", "state": "BLOCKED"},
                      "47": {"owner": "12", "state": "BLOCKED"}}}
NONCE = "0123456789abcdef01234567"


def comment(cid=1, *, user="anigio2705-dev", assoc="OWNER", team="11",
            task=11, operation="AUDIT_READY_ONLY", nonce=NONCE, body=None):
    value = {"v": 1, "task_id": task, "team": team, "operation": operation, "nonce": nonce}
    return {"id": cid, "user": {"login": user}, "author_association": assoc,
            "body": body if body is not None else "HQ_COMMAND_V1\n" + json.dumps(value)}


class ReceiverSecurityTests(unittest.TestCase):
    def test_owner_command_is_read_only_and_does_not_promote_ready(self):
        self.assertEqual(inspect([comment()], CATALOG, REGISTRY)[0]["ready_state"], "CANDIDATE")
        self.assertEqual(REGISTRY["items"]["11"]["state"], "CANDIDATE")

    def test_untrusted_user_rejected(self):
        self.assertEqual(inspect([comment(user="attacker")], CATALOG, REGISTRY), [])

    def test_author_association_must_be_owner(self):
        self.assertEqual(inspect([comment(assoc="NONE")], CATALOG, REGISTRY), [])

    def test_wrong_team_and_missing_registry_rejected(self):
        self.assertEqual(inspect([comment(team="13"), comment(2, task=13)], CATALOG, REGISTRY), [])

    def test_arbitrary_action_and_injection_rejected(self):
        self.assertEqual(inspect([comment(operation="DISPATCH_AI")], CATALOG, REGISTRY), [])
        self.assertEqual(inspect([comment(body="HQ_COMMAND_V1\n{}\nextra")], CATALOG, REGISTRY), [])

    def test_nonce_must_be_strong_hex(self):
        self.assertEqual(inspect([comment(nonce="short")], CATALOG, REGISTRY), [])

    def test_duplicate_nonce_in_same_poll_rejected(self):
        self.assertEqual(len(inspect([comment(1), comment(2)], CATALOG, REGISTRY)), 1)

    def test_receipt_prevents_cross_run_replay(self):
        receipt = {"comment_id": 1, "nonce": NONCE, "task_id": 11,
                   "team": "11", "result": "READ_ONLY_ACK_NO_DISPATCH"}
        bot = {"id": 2, "user": {"login": "github-actions[bot]"},
               "body": "HQ_RECEIPT_V1\n" + json.dumps(receipt)}
        self.assertEqual(inspect([comment(1), bot], CATALOG, REGISTRY), [])

    def test_fake_receipt_cannot_suppress_command(self):
        fake = {"id": 2, "user": {"login": "attacker"},
                "body": "HQ_RECEIPT_V1\n" + json.dumps({
                    "comment_id": 1, "nonce": NONCE, "task_id": 11,
                    "team": "11", "result": "READ_ONLY_ACK_NO_DISPATCH"})}
        self.assertEqual(len(inspect([comment(1), fake], CATALOG, REGISTRY)), 1)

    def test_boolean_task_id_rejected(self):
        body = "HQ_COMMAND_V1\n" + json.dumps({
            "v": 1, "task_id": True, "team": "11",
            "operation": "AUDIT_READY_ONLY", "nonce": NONCE})
        self.assertIsNone(trusted_command(comment(body=body), CATALOG, REGISTRY))

    def test_unexpected_schema_fields_rejected(self):
        body = "HQ_COMMAND_V1\\n" + json.dumps({
            "v": 1, "task_id": 11, "team": "11",
            "operation": "AUDIT_READY_ONLY", "nonce": NONCE,
            "unsafe_execute": True})
        self.assertEqual(inspect([comment(body=body)], CATALOG, REGISTRY), [])

    def test_blocked_task_may_be_audited_but_not_promoted(self):
        r = inspect([comment(team="13", task=22)], CATALOG, REGISTRY)
        self.assertEqual(r[0]["ready_state"], "BLOCKED")
        self.assertEqual(REGISTRY["items"]["22"]["state"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
