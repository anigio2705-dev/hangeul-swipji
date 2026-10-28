"""Read-only, evidence-gated HQ queue for the 160-item master backlog.

Never changes the original backlog, production, or GitHub state. Only a
record with CI success AND review evidence can be labelled complete.
"""
import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ITEM = re.compile(r"^(\d{1,3})\. \[([ xX])\] (.+)$", re.MULTILINE)
PRIORITY = tuple(range(11, 31)) + tuple(range(51, 61)) + tuple(range(1, 11)) + tuple(range(31, 51)) + tuple(range(61, 161))
OWNER_RANGES = (
    (1, 10, "HQ"), (11, 20, "11+15"), (21, 30, "13+15"),
    (31, 40, "11+13"), (41, 50, "12+13"), (51, 60, "12+15"),
    (61, 70, "12"), (71, 80, "14"), (81, 100, "13+14"),
    (101, 120, "14"), (121, 130, "11+14"), (131, 140, "11+15"),
    (141, 150, "13+16"), (151, 160, "15+16"),
)
# These tasks require evidence from a real environment, an external party,
# legal review, or explicit release authorization; CI cannot approve them.
EXTERNAL_GATES = frozenset({
    13, 14, 15, 16, 17, 18, 20, 23, 24, 25, 26, 27, 29, 30,
    55, 56, 57, 58, 60, 69, 70, 107, 121, 126, 130, 136,
    146, 150, 151, 152, 154, 155,
})
REVIEW_REQUIRED = frozenset({6, 14, 15, 26, 60, 70, 91, 107, 130, 150, 152, 154, 155})
ALLOWED_STATUSES = frozenset({"unverified", "in_progress", "blocked", "code_verified", "complete"})

def parse_backlog(text):
    matches = [(int(n), mark.lower() == "x", title.strip()) for n, mark, title in ITEM.findall(text)]
    numbers = [n for n, _, _ in matches]
    if numbers != list(range(1, 161)):
        raise ValueError("Backlog must have exactly 160 ordered unique numbered tasks")
    return matches

def owner_for(number):
    for start, end, owner in OWNER_RANGES:
        if start <= number <= end:
            return owner
    raise ValueError("Unknown backlog task")

def validate_evidence(number, record, checked):
    if not isinstance(record, dict):
        raise ValueError(f"Invalid evidence for task {number}")
    status = record.get("status", "unverified")
    if status not in ALLOWED_STATUSES:
        raise ValueError(f"Unknown task {number} status")
    if status in ("code_verified", "complete"):
        sha = record.get("commit", "")
        ci = record.get("ci_url", "")
        if not re.fullmatch(r"[0-9a-f]{40}", sha):
            raise ValueError(f"Task {number}: valid commit required")
        if not re.fullmatch(r"https://github\.com/anigio2705-dev/hangeul-swipji/actions/runs/[0-9]+", ci):
            raise ValueError(f"Task {number}: GitHub Actions evidence required")
        if record.get("ci_result") != "success":
            raise ValueError(f"Task {number}: successful CI evidence required")
    if status == "complete":
        if not checked:
            raise ValueError(f"Task {number}: master backlog is not checked")
        if number in EXTERNAL_GATES and not record.get("external_evidence"):
            raise ValueError(f"Task {number}: real-world evidence required")
        if number in REVIEW_REQUIRED and not record.get("approval_evidence"):
            raise ValueError(f"Task {number}: representative approval required")
    return status

def build_report(backlog_text, evidence=None, branch_heads=None, timestamp=None, limit=12):
    if not isinstance(limit, int) or limit < 1 or limit > 160:
        raise ValueError("Invalid queue limit")
    if evidence is None:
        evidence = {}
    if not isinstance(evidence, dict):
        raise ValueError("Evidence must be a task-keyed object")
    entries = []
    for number, checked, title in parse_backlog(backlog_text):
        record = evidence.get(str(number), {})
        status = validate_evidence(number, record, checked)
        entries.append({
            "number": number, "title": title, "owner": owner_for(number),
            "status": status, "master_checked": checked,
            "external_gate": number in EXTERNAL_GATES,
        })
    pending = {entry["number"]: entry for entry in entries if entry["status"] not in ("complete", "blocked")}
    ordered = [pending[n] for n in PRIORITY if n in pending]
    # Prefer tasks that can advance in an isolated branch without live-system changes.
    queue = sorted(ordered, key=lambda e: (e["external_gate"], PRIORITY.index(e["number"])))[:limit]
    counts = {s: sum(e["status"] == s for e in entries) for s in sorted(ALLOWED_STATUSES)}
    return {
        "schema_version": 1,
        "generated_at_utc": timestamp or datetime.now(timezone.utc).isoformat(),
        "backlog_sha256": hashlib.sha256(backlog_text.encode("utf-8")).hexdigest(),
        "source": "docs/platform-execution-backlog-20261027:docs/PLATFORM_EXECUTION_BACKLOG.md",
        "counts": counts,
        "branch_heads": branch_heads or {},
        "next_queue": queue,
        "tasks": entries,
        "safety": {
            "write_scope": "isolated branches only",
            "production_deploy": False,
            "real_payments": False,
            "completion_requires_ci_and_master_check": True,
            "note": "A successful test is not proof of public deployment, real video, audio quality, or legal review.",
        },
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--backlog", required=True)
    parser.add_argument("--evidence")
    parser.add_argument("--branch-heads")
    parser.add_argument("--output", required=True)
    parser.add_argument("--limit", type=int, default=12)
    args = parser.parse_args()
    evidence = json.loads(Path(args.evidence).read_text()) if args.evidence else {}
    heads = json.loads(Path(args.branch_heads).read_text()) if args.branch_heads else {}
    report = build_report(Path(args.backlog).read_text(encoding="utf-8"), evidence, heads, limit=args.limit)
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Verified completion: {report['counts']['complete']}/160; queue: " +
          ", ".join(str(t["number"]) for t in report["next_queue"]))

if __name__ == "__main__":
    main()
