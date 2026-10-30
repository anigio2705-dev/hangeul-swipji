"""No-network security and sequencing regressions for Issue #34 discussion cursor."""
import json
import unittest

from hq_round_robin import CENTRAL_ID, REPO, inspect, TEAM_BY_TURN


def message(cid, marker, payload, user="anigio2705-dev",
            association="OWNER", edited=False):
    return {"id": cid, "user": {"login": user},
            "author_association": association,
            "created_at": "2026-10-30T12:00:00Z",
            "updated_at": "2026-10-30T12:01:00Z" if edited else
                          "2026-10-30T12:00:00Z",
            "body": marker + "\n" + json.dumps(payload, sort_keys=True)}


def turn(round_no=1, turn_no=1, prev=CENTRAL_ID, hypothesis=None):
    return {"round": round_no, "turn": turn_no,
            "team": TEAM_BY_TURN[turn_no],
            "read_previous": REPO + "/issues/34#issuecomment-" + str(prev),
            "agreement": "Accept existing fail-closed READY=0 gate",
            "challenge": "Current CI success does not prove deployment",
            "new_hypothesis": hypothesis or "H101-NEW-HYPOTHESIS-" + str(turn_no),
            "experiment": "Run a bounded isolated regression against exact SHA",
            "evidence": {"sha": "a" * 40, "pr": REPO + "/pull/147",
                         "ci": REPO + "/actions/runs/41050189657"},
            "handoff_to": "Ask the next team to verify the CI contract"}


def accept(cid, round_no=1, turn_no=1, turn_comment=6522211000):
    return message(cid, "HQ_TURN_ACCEPT_V1",
                   {"round": round_no, "turn": turn_no,
                    "comment_id": turn_comment, "sha": "a" * 40,
                    "reason": "Central discussion acceptance only"})


class RoundRobinTests(unittest.TestCase):
    def test_empty_requires_first_team(self):
        r = inspect([])
        self.assertEqual((r["round"], r["turn"], r["team"]),
                         (1, 1, "11"))
        self.assertEqual(r["status"], "AWAIT_TEAM_COMMENT")
        self.assertEqual(r["actual_ai_calls_verified"], 0)
        self.assertEqual(r["ready_promotions"], 0)

    def test_unaccepted_team_comment_does_not_advance(self):
        r = inspect([message(6522211000, "HQ_TURN_V1", turn())])
        self.assertEqual(r["status"], "AWAIT_HQ_ACCEPTANCE")
        self.assertEqual(r["turn"], 1)

    def test_accepted_discussion_advances_without_ready_claim(self):
        r = inspect([message(6522211000, "HQ_TURN_V1", turn()), accept(6522211001)])
        self.assertEqual((r["round"], r["turn"]), (1, 2))
        self.assertEqual(r["history"][0]["decision"], "ACK_DISCUSSION_ONLY")
        self.assertFalse(r["team_identity_independently_verified"])

    def test_out_of_order_or_wrong_team_is_ignored(self):
        data = turn(turn_no=2)
        r = inspect([message(6522211000, "HQ_TURN_V1", data)])
        self.assertEqual(r["status"], "AWAIT_TEAM_COMMENT")

    def test_untrusted_or_edited_is_ignored(self):
        for bad in ({"user": "attacker"}, {"edited": True},
                    {"association": "COLLABORATOR"}):
            with self.subTest(bad=bad):
                r = inspect([message(6522211000, "HQ_TURN_V1", turn(), **bad)])
                self.assertEqual(r["status"], "AWAIT_TEAM_COMMENT")

    def test_mismatched_ack_does_not_advance(self):
        a = accept(6522211001)
        a["body"] = a["body"].replace("a" * 40, "b" * 40)
        r = inspect([message(6522211000, "HQ_TURN_V1", turn()), a])
        self.assertEqual(r["status"], "AWAIT_HQ_ACCEPTANCE")

    def test_duplicate_json_key_is_rejected(self):
        c = message(6522211000, "HQ_TURN_V1", turn())
        c["body"] = 'HQ_TURN_V1\n{"round":1,"round":2}'
        self.assertEqual(inspect([c])["status"], "AWAIT_TEAM_COMMENT")

    def test_weak_evidence_rejected(self):
        t = turn()
        t["evidence"]["ci"] = "https://example.com/fake"
        self.assertEqual(inspect([message(6522211000, "HQ_TURN_V1", t)])["status"],
                         "AWAIT_TEAM_COMMENT")

    def test_previous_comment_binding_enforced(self):
        cs = [message(6522211000, "HQ_TURN_V1", turn()), accept(6522211001),
              message(6522211002, "HQ_TURN_V1", turn(turn_no=2, prev=CENTRAL_ID))]
        self.assertEqual(inspect(cs)["status"], "AWAIT_TEAM_COMMENT")
        self.assertEqual(inspect(cs)["turn"], 2)

    def test_six_turns_require_central_summary(self):
        cs, prev = [], CENTRAL_ID
        for i in range(1, 7):
            cid = 6522211000 + (i - 1) * 2
            cs.append(message(cid, "HQ_TURN_V1", turn(turn_no=i, prev=prev)))
            cs.append(accept(cid + 1, turn_no=i, turn_comment=cid))
            prev = cid
        r = inspect(cs)
        self.assertEqual(r["status"], "AWAIT_CENTRAL_SUMMARY")
        self.assertEqual(len(r["history"]), 6)
        cs.append(message(6522211012, "HQ_ROUND_SUMMARY_V1",
                          {"round": 1, "last_comment_id": prev,
                           "summary": "Central review: independent READY remains blocked"}))
        r = inspect(cs)
        self.assertEqual((r["round"], r["turn"]), (2, 1))
        self.assertEqual(r["status"], "AWAIT_TEAM_COMMENT")

    def test_replayed_hypothesis_not_accepted(self):
        cs = [message(6522211000, "HQ_TURN_V1", turn()), accept(6522211001),
              message(6522211002, "HQ_TURN_V1",
                      turn(turn_no=2, prev=6522211000, hypothesis="H101-NEW-HYPOTHESIS-1"))]
        self.assertEqual(inspect(cs)["status"], "AWAIT_TEAM_COMMENT")

    def test_central_deadline_skip_is_not_team_agreement(self):
        skip = {"round": 1, "turn": 1,
                "read_previous": REPO + "/issues/34#issuecomment-" + str(CENTRAL_ID),
                "reason": "deadline_passed: team11 did not provide evidence"}
        c = message(6522211100, "HQ_TURN_SKIP_V1", skip)
        r = inspect([c])
        self.assertEqual((r["turn"], r["team"]), (2, "12"))
        self.assertEqual(r["history"][0]["decision"], "NO_RESPONSE_SKIP")
        self.assertEqual(r["history"][0]["evidence_status"], "NO_TEAM_EVIDENCE")

    def test_no_automatic_skip_without_central_deadline_reason(self):
        skip = {"round": 1, "turn": 1,
                "read_previous": REPO + "/issues/34#issuecomment-" + str(CENTRAL_ID),
                "reason": "no"}
        r = inspect([message(6522211100, "HQ_TURN_SKIP_V1", skip)])
        self.assertEqual(r["status"], "AWAIT_TEAM_COMMENT")


if __name__ == "__main__":
    unittest.main()
