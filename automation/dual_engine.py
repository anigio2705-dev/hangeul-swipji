"""Dual-engine pilot: ordered discussion + independently dispatchable work.
No AI API calls or GitHub mutations occur here. State is JSON for audit.
"""
import argparse
import json
from pathlib import Path

TEAMS = ("11", "12", "13", "14", "15", "16")
REQUIRED = ("agreement", "challenge", "hypothesis", "experiment", "evidence", "handoff")
STATES = ("queued", "running", "verified", "failed")

def new_state(task="101"):
    return {"task": str(task), "round": 1, "turn": 0, "discussion": [],
            "work": [], "ready": False, "independent_approval": False}

def next_team(state):
    return TEAMS[state["turn"]] if state["turn"] < len(TEAMS) else None

def speak(state, team, entry):
    if next_team(state) != team:
        raise ValueError("out-of-order discussion turn")
    if any(not str(entry.get(k, "")).strip() for k in REQUIRED):
        raise ValueError("missing discussion evidence or reasoning")
    if state["discussion"] and entry.get("read_previous") != state["discussion"][-1]["id"]:
        raise ValueError("previous turn not acknowledged")
    if not state["discussion"] and entry.get("read_previous") not in (None, ""):
        raise ValueError("unexpected predecessor")
    if any(x["hypothesis"] == entry["hypothesis"] for x in state["discussion"]):
        raise ValueError("duplicate hypothesis")
    record = {**{k: entry[k] for k in REQUIRED}, "team": team,
              "round": state["round"], "id": f'R{state["round"]}-T{state["turn"]+1}'}
    if state["discussion"]:
        record["read_previous"] = entry["read_previous"]
    state["discussion"].append(record)
    state["turn"] += 1
    return record

def advance_round(state):
    if state["turn"] != len(TEAMS):
        raise ValueError("six turns required")
    state["round"] += 1
    state["turn"] = 0

def queue_work(state, job):
    for key in ("id", "owner", "hypothesis", "test", "branch"):
        if not str(job.get(key, "")).strip():
            raise ValueError("missing job " + key)
    if job["owner"] not in TEAMS or any(x["id"] == job["id"] for x in state["work"]):
        raise ValueError("invalid owner or duplicate job")
    if job["branch"] == "main":
        raise ValueError("main modifications forbidden")
    record = dict(job, status="queued", evidence=None)
    state["work"].append(record)
    return record

def work_result(state, job_id, status, evidence):
    if status not in STATES[1:] or not evidence:
        raise ValueError("invalid work status or missing evidence")
    job = next((j for j in state["work"] if j["id"] == job_id), None)
    if job is None:
        raise ValueError("unknown job")
    if job["status"] == "verified":
        raise ValueError("verified job is immutable")
    job["status"], job["evidence"] = status, evidence

def approve(state, approver, evidence):
    # Never trust CLI-supplied team identity or arbitrary evidence strings.
    # READY requires an external verifier to check GitHub author identity,
    # exact commit SHA, successful CI, task ownership and HQ2 approval.
    raise PermissionError("READY blocked: trusted independent GitHub attestation verifier not connected")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=["init", "speak", "next", "queue", "result", "approve"])
    p.add_argument("--state", default="automation/dual_engine_state.json")
    p.add_argument("--team")
    p.add_argument("--job")
    p.add_argument("--status")
    p.add_argument("--evidence")
    p.add_argument("--data", default="{}")
    args = p.parse_args()
    path = Path(args.state)
    state = new_state() if args.command == "init" else json.loads(path.read_text())
    data = json.loads(args.data)
    if args.command == "speak":
        speak(state, args.team, data)
    elif args.command == "next":
        advance_round(state)
    elif args.command == "queue":
        queue_work(state, data)
    elif args.command == "result":
        work_result(state, args.job, args.status, args.evidence)
    elif args.command == "approve":
        approve(state, args.team, args.evidence)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"round": state["round"], "next_team": next_team(state),
                      "jobs": len(state["work"]), "ready": state["ready"]}))

if __name__ == "__main__":
    main()
