"""Read-only, fail-closed Issue #34 round-robin discussion cursor.

A team name in a shared GitHub account comment is NOT proof of an AI call.
A central acceptance is a discussion acknowledgment, never READY approval.
No code, READY, deployment, payment or GitHub issue writes occur here.
"""
import argparse
import json
import os
import re
from pathlib import Path

from hq_issue34_receiver import OWNER, read_all_comments

CENTRAL_ID = 6522210538
REPO = "https://github.com/anigio2705-dev/hangeul-swipji"
TEAM_BY_TURN = {1: "11", 2: "12", 3: "13", 4: "14", 5: "15", 6: "16"}
SHA = re.compile(r"[a-f0-9]{40}\Z")
MARKERS = {"HQ_TURN_V1", "HQ_TURN_ACCEPT_V1", "HQ_TURN_SKIP_V1",
           "HQ_ROUND_SUMMARY_V1"}
TURN_FIELDS = {"round", "turn", "team", "read_previous", "agreement",
               "challenge", "new_hypothesis", "experiment", "evidence",
               "handoff_to"}
EVIDENCE_FIELDS = {"sha", "pr", "ci"}


def unique_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("duplicate JSON key")
        obj[key] = value
    return obj


def trusted_message(comment):
    if not isinstance(comment, dict) or type(comment.get("id")) is not int:
        return None
    if comment["id"] <= CENTRAL_ID:
        return None
    user = comment.get("user") or {}
    if user.get("login") != OWNER or comment.get("author_association") != "OWNER":
        return None
    created, updated = comment.get("created_at"), comment.get("updated_at")
    if not created or not updated or created != updated:
        return None
    body = comment.get("body")
    if not isinstance(body, str) or len(body) > 6000:
        return None
    lines = body.strip().splitlines()
    if len(lines) != 2 or lines[0] not in MARKERS:
        return None
    try:
        data = json.loads(lines[1], object_pairs_hook=unique_object)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    return lines[0], data


def positive_int(value):
    return type(value) is int and value > 0


def valid_turn(data, round_no, turn_no, previous_id, seen_hypotheses):
    if set(data) != TURN_FIELDS:
        return False
    if data.get("round") != round_no or data.get("turn") != turn_no:
        return False
    if type(data["round"]) is not int or type(data["turn"]) is not int:
        return False
    if data.get("team") != TEAM_BY_TURN[turn_no]:
        return False
    if data.get("read_previous") != (
            REPO + "/issues/34#issuecomment-" + str(previous_id)):
        return False
    for field in ("agreement", "challenge", "new_hypothesis",
                  "experiment", "handoff_to"):
        if not isinstance(data.get(field), str) or len(data[field].strip()) < 12:
            return False
    if data["new_hypothesis"] in seen_hypotheses:
        return False
    evidence = data.get("evidence")
    if not isinstance(evidence, dict) or set(evidence) != EVIDENCE_FIELDS:
        return False
    if not isinstance(evidence["sha"], str) or not SHA.fullmatch(evidence["sha"]):
        return False
    if not isinstance(evidence["pr"], str) or not re.fullmatch(
            re.escape(REPO) + r"/pull/[1-9][0-9]*", evidence["pr"]):
        return False
    if not isinstance(evidence["ci"], str) or not re.fullmatch(
            re.escape(REPO) + r"/actions/runs/[1-9][0-9]*", evidence["ci"]):
        return False
    return True


def inspect(comments):
    ordered = sorted(comments, key=lambda c: c.get("id", -1))
    parsed = [(c["id"], *msg) for c in ordered
              if (msg := trusted_message(c)) is not None]
    round_no, turn_no, previous_id = 1, 1, CENTRAL_ID
    seen_hypotheses, history = set(), []
    consumed = set()
    for _ in range(600):  # bounded 100 rounds; never loop forever
        candidate = next(((cid, data) for cid, marker, data in parsed
                          if cid not in consumed and cid > previous_id
                          and marker == "HQ_TURN_V1"
                          and valid_turn(data, round_no, turn_no, previous_id,
                                         seen_hypotheses)), None)
        if candidate is None:
            return report(round_no, turn_no, "AWAIT_TEAM_COMMENT",
                          previous_id, history, len(comments))
        cid, data = candidate
        consumed.add(cid)
        acceptance = next(((aid, marker, value) for aid, marker, value in parsed
                           if aid > cid and aid not in consumed
                           and marker in ("HQ_TURN_ACCEPT_V1", "HQ_TURN_SKIP_V1")
                           and set(value) == {"round", "turn", "comment_id",
                                              "sha", "reason"}
                           and value["round"] == round_no
                           and value["turn"] == turn_no
                           and value["comment_id"] == cid
                           and value["sha"] == data["evidence"]["sha"]
                           and isinstance(value["reason"], str)
                           and len(value["reason"].strip()) >= 12), None)
        if acceptance is None:
            return report(round_no, turn_no, "AWAIT_HQ_ACCEPTANCE",
                          previous_id, history, len(comments),
                          proposed_comment_id=cid)
        aid, marker, value = acceptance
        consumed.add(aid)
        history.append({"round": round_no, "turn": turn_no,
                        "team": data["team"], "comment_id": cid,
                        "decision_id": aid,
                        "decision": "ACK_DISCUSSION_ONLY" if
                        marker == "HQ_TURN_ACCEPT_V1" else "SKIPPED_NO_CONSENSUS",
                        "evidence_status": "REFERENCES_NOT_INDEPENDENTLY_VERIFIED"})
        seen_hypotheses.add(data["new_hypothesis"])
        previous_id = cid
        if turn_no < 6:
            turn_no += 1
            continue
        summary = next(((sid, value) for sid, mark, value in parsed
                        if sid > aid and mark == "HQ_ROUND_SUMMARY_V1"
                        and set(value) == {"round", "last_comment_id", "summary"}
                        and value["round"] == round_no
                        and value["last_comment_id"] == cid
                        and isinstance(value["summary"], str)
                        and len(value["summary"].strip()) >= 12), None)
        if summary is None:
            return report(round_no, turn_no, "AWAIT_CENTRAL_SUMMARY",
                          previous_id, history, len(comments))
        previous_id = summary[0]
        consumed.add(previous_id)
        round_no, turn_no = round_no + 1, 1
    raise RuntimeError("bounded discussion rounds exceeded")


def report(round_no, turn_no, status, previous_id, history, count, **extra):
    return {"schema": 1, "issue": 34, "task": 101,
            "round": round_no, "turn": turn_no,
            "team": TEAM_BY_TURN[turn_no], "status": status,
            "read_previous": REPO + "/issues/34#issuecomment-" + str(previous_id),
            "comments_checked": count, "history": history,
            "actual_ai_calls_verified": 0,
            "ready_promotions": 0,
            "team_identity_independently_verified": False,
            "auto_posting_enabled": False, **extra}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="/tmp/hq-round-robin.json")
    args = parser.parse_args()
    token = os.environ.get("GH_TOKEN")
    if not token:
        raise RuntimeError("GH_TOKEN required for read-only polling")
    result = inspect(read_all_comments(token))
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False,
                                           indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
