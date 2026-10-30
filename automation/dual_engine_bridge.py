"""Fail-closed GitHub Issue #34 discussion ingestion and work routing.
This adapter parses trusted, structured comments; it never calls AI or mutates GitHub.
"""
import json
from automation.dual_engine import TEAMS, speak, queue_work, next_team

FIELDS = ("agreement", "challenge", "hypothesis", "experiment", "evidence", "handoff")

def ingest_turn(state, comment, trusted_authors):
    if comment.get("author") not in trusted_authors:
        raise ValueError("untrusted author")
    if comment.get("issue_number") != 34:
        raise ValueError("wrong issue")
    if not str(comment.get("url", "")).startswith(
        "https://github.com/anigio2705-dev/hangeul-swipji/issues/34#issuecomment-"
    ):
        raise ValueError("missing canonical comment URL")
    data = json.loads(comment["body"])
    if data.get("type") != "TEAM_TURN" or data.get("task") != state["task"]:
        raise ValueError("invalid turn type/task")
    if data.get("round") != state["round"] or data.get("team") != next_team(state):
        raise ValueError("out of order")
    if data.get("team") != comment.get("team_identity"):
        raise ValueError("team identity mismatch")
    if any(not str(data.get(field, "")).strip() for field in FIELDS):
        raise ValueError("incomplete contribution")
    if any(x.get("source_url") == comment["url"] for x in state["discussion"]):
        raise ValueError("replayed comment")
    entry = {field: data[field] for field in FIELDS}
    entry["read_previous"] = data.get("read_previous")
    record = speak(state, data["team"], entry)
    record["source_url"] = comment["url"]
    return record

def dispatch_approved(state, assignments):
    """Return work intents; actual execution requires a separate trusted runner."""
    # The caller controls assignment dictionaries. A boolean such as
    # approved_by_central=True is NOT a signed/verified Issue #34 command.
    # Keep this bridge read-only until a trusted receiver binds actor, comment
    # id, owner, SHA and replay state. Local queue_work remains a test-only
    # intent builder; it must not be treated as actual AI dispatch.
    if assignments:
        raise ValueError("trusted central command provenance not verified; dispatch blocked")
    return []

def progress(state):
    discussion_done = state["turn"] == len(TEAMS)
    development_done = bool(state["work"]) and all(
        job["status"] == "verified" for job in state["work"]
    )
    return {"discussion_complete": discussion_done,
            "development_complete": development_done,
            # Mutable JSON flags are not independent GitHub/CI attestation.
            # Only an external authenticated verifier may issue READY.
            "ready_complete": False,
            "next_team": next_team(state),
            "queued_jobs": sum(job["status"] == "queued" for job in state["work"])}
