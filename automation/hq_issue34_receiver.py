"""Fail-closed Issue #34 command intake. It NEVER dispatches AI, edits READY or code."""
import argparse
import json
import os
import re
from pathlib import Path
from urllib.request import Request, urlopen

API = "https://api.github.com/repos/anigio2705-dev/hangeul-swipji/issues/34/comments"
OWNER = "anigio2705-dev"
BOT = "github-actions[bot]"
COMMAND = "HQ_COMMAND_V1"
RECEIPT = "HQ_RECEIPT_V1"
TEAMS = {"11", "12", "13", "14", "15", "16"}
NONCE = re.compile(r"[0-9a-f]{24,64}\Z")


def parse_message(body, marker):
    if not isinstance(body, str) or len(body) > 900:
        return None
    lines = body.strip().splitlines()
    if len(lines) != 2 or lines[0] != marker:
        return None
    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Ambiguous duplicate JSON key")
            result[key] = value
        return result
    try:
        value = json.loads(lines[1], object_pairs_hook=unique_keys)
    except (ValueError, TypeError):
        return None
    return value if isinstance(value, dict) else None


def trusted_command(comment, catalog, registry):
    """Only repo owner's exact, read-only command for a canonical owned task."""
    user = comment.get("user") or {}
    if user.get("login") != OWNER or comment.get("author_association") != "OWNER":
        return None
    # Edited comments are not immutable commands. Reject them even if a prior
    # ACK exists, rather than treating an edited payload as a fresh request.
    created, updated = comment.get("created_at"), comment.get("updated_at")
    if created and updated and created != updated:
        return None
    value = parse_message(comment.get("body"), COMMAND)
    if value is None or set(value) != {"v", "task_id", "team", "operation", "nonce"}:
        return None
    task_id, team, nonce = value["task_id"], value["team"], value["nonce"]
    if type(value["v"]) is not int or value["v"] != 1:
        return None
    if type(task_id) is not int or not 1 <= task_id <= 160:
        return None
    if not isinstance(team, str) or team not in TEAMS:
        return None
    if value["operation"] != "AUDIT_READY_ONLY":
        return None
    if not isinstance(nonce, str) or not NONCE.fullmatch(nonce):
        return None
    contract = catalog.get(task_id)
    entry = registry.get("items", {}).get(str(task_id), {})
    if not contract or contract.get("owner") != team or entry.get("owner") != team:
        return None
    return value


def trusted_receipt(comment):
    if (comment.get("user") or {}).get("login") != BOT:
        return None
    value = parse_message(comment.get("body"), RECEIPT)
    if value is None or set(value) != {"comment_id", "nonce", "task_id", "team", "result"}:
        return None
    if type(value["comment_id"]) is not int or value["comment_id"] <= 0:
        return None
    if not isinstance(value["nonce"], str) or not NONCE.fullmatch(value["nonce"]):
        return None
    if value["result"] != "READ_ONLY_ACK_NO_DISPATCH":
        return None
    return value


def inspect(comments, catalog, registry):
    """Replays are rejected using prior bot receipts and first-seen nonce."""
    ordered = sorted(comments, key=lambda c: c["id"])
    commands = {comment["id"]: cmd for comment in ordered
                if (cmd := trusted_command(comment, catalog, registry)) is not None}
    acknowledged_ids, acknowledged_nonces = set(), set()
    for comment in ordered:
        receipt = trusted_receipt(comment)
        if not receipt:
            continue
        cmd = commands.get(receipt["comment_id"])
        # An authentic bot identity is necessary but insufficient: receipts
        # must bind to a preceding, valid owner command with identical fields.
        # Unrelated/malformed bot comments must never suppress owner commands.
        if (cmd is None or comment["id"] <= receipt["comment_id"]
                or any(receipt[key] != cmd[key] for key in
                       ("nonce", "task_id", "team"))):
            continue
        acknowledged_ids.add(receipt["comment_id"])
        acknowledged_nonces.add(receipt["nonce"])
    seen_nonces = set(acknowledged_nonces)
    accepted = []
    for comment in ordered:
        cmd = commands.get(comment["id"])
        if cmd is None:
            continue
        if comment["id"] in acknowledged_ids or cmd["nonce"] in seen_nonces:
            continue
        seen_nonces.add(cmd["nonce"])
        accepted.append({"comment_id": comment["id"], **cmd,
                         "result": "READ_ONLY_ACK_NO_DISPATCH",
                         "ready_state": registry["items"][str(cmd["task_id"])]["state"]})
    return accepted


def api_request(url, token, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    request = Request(url, data=data, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json"}, method="POST" if data else "GET")
    with urlopen(request, timeout=20) as response:
        return json.load(response)


def read_all_comments(token):
    comments = []
    # Never silently accept a truncated command stream.
    for page in range(1, 21):
        batch = api_request(API + "?per_page=100&page=" + str(page), token)
        if not isinstance(batch, list):
            raise RuntimeError("GitHub issue comments response malformed")
        comments.extend(batch)
        if len(batch) < 100:
            return comments
    raise RuntimeError("Comment pagination limit reached; fail closed")


def main():
    from hq_160_task_cycle import load_catalog
    parser = argparse.ArgumentParser()
    parser.add_argument("--ack", action="store_true", help="Post read-only receipt; never dispatch")
    parser.add_argument("--output", default="/tmp/hq-issue34-receiver.json")
    args = parser.parse_args()
    token = os.environ.get("GH_TOKEN", "")
    if not token:
        raise RuntimeError("GH_TOKEN required")
    catalog = load_catalog("automation/hq_backlog_160.md")
    registry = json.loads(Path("automation/hq_semantic_contract_paths.json").read_text())
    if registry.get("schema") != 1:
        raise RuntimeError("Untrusted registry schema")
    comments = read_all_comments(token)
    accepted = inspect(comments, catalog, registry)
    report = {"schema": 1, "comments_checked": len(comments),
              "read_only_commands": accepted, "ai_api_calls": 0,
              "ready_promotions": 0, "source_changes": 0,
              "ack_requested": args.ack, "ack_posted": []}
    if args.ack:
        for item in accepted:
            receipt = {k: item[k] for k in ("comment_id", "nonce", "task_id", "team", "result")}
            # No user text is interpolated into code, shell, workflows or runner.
            response = api_request(API, token, {"body": RECEIPT + "\n" +
                                               json.dumps(receipt, separators=(",", ":"))})
            report["ack_posted"].append(response["id"])
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"comments_checked": len(comments),
                      "accepted": len(accepted), "ack_posted": len(report["ack_posted"]),
                      "ai_api_calls": 0, "ready_promotions": 0}))


if __name__ == "__main__":
    main()
