"""Deterministic fail-closed queue contract for isolated CI pilot.

This does not run AI workers, authenticate users, persist state, or mark READY.
A future trusted dispatcher must atomically store each transition.
"""
from dataclasses import dataclass, replace

HEX = frozenset("0123456789abcdef")
MAX_QA_FAILURES = 3


def valid_sha(sha):
    return type(sha) is str and len(sha) == 40 and all(c in HEX for c in sha)


@dataclass(frozen=True)
class QueueState:
    task: int
    sha: str
    phase: str = "DEVELOP"
    qa_failures: int = 0
    seen: tuple = ()

    def __post_init__(self):
        if type(self.task) is not int or self.task < 1 or not valid_sha(self.sha):
            raise ValueError("Invalid task/SHA")
        if self.phase not in {
            "DEVELOP", "QA_PENDING", "REWORK", "REVIEW_PENDING",
            "ATTESTATION_PENDING", "BLOCKED"
        }:
            raise ValueError("Invalid phase")
        if not (0 <= self.qa_failures <= MAX_QA_FAILURES):
            raise ValueError("Invalid retry count")


def advance(state, event_id, action, sha, *, new_sha=None):
    """Idempotent event transition; reject stale SHA and out-of-order events."""
    if not isinstance(state, QueueState):
        raise ValueError("Invalid state")
    if type(event_id) is not str or not event_id.strip():
        raise ValueError("Missing unique event ID")
    if not valid_sha(sha):
        raise ValueError("Invalid event SHA")
    fingerprint = (event_id, action, sha, new_sha)
    old = [entry for entry in state.seen if entry[0] == event_id]
    if old:
        if old[0] == fingerprint:
            return state
        raise ValueError("Conflicting replay of event ID")
    if sha != state.sha:
        raise ValueError("Stale SHA")
    if state.phase == "BLOCKED":
        raise ValueError("Blocked: authorized recovery required")
    if action == "SHA_CHANGED":
        if not valid_sha(new_sha) or new_sha == sha:
            raise ValueError("Distinct valid commit required")
        if state.phase not in {"DEVELOP", "REWORK", "REVIEW_PENDING", "QA_PENDING"}:
            raise ValueError("SHA change not allowed in this phase")
        result = replace(state, sha=new_sha, phase="DEVELOP")
    else:
        if new_sha is not None:
            raise ValueError("Unexpected new SHA")
        allowed = {
            ("DEVELOP", "DEV_PASS"): "QA_PENDING",
            ("QA_PENDING", "QA_PASS"): "REVIEW_PENDING",
            ("REVIEW_PENDING", "CENTRAL_PASS"): "ATTESTATION_PENDING",
            ("REWORK", "REWORK_STARTED"): "REWORK",
        }
        # A later independent QA failure must revoke an earlier PASS, even
        # after central review; otherwise an already-attested candidate
        # could proceed with known defects.
        if action == "QA_FAIL" and state.phase in {
            "QA_PENDING", "REVIEW_PENDING", "ATTESTATION_PENDING"
        }:
            failures = state.qa_failures + 1
            result = replace(state, qa_failures=failures,
                             phase="BLOCKED" if failures >= MAX_QA_FAILURES else "REWORK")
        elif (state.phase, action) in allowed:
            result = replace(state, phase=allowed[(state.phase, action)])
        else:
            raise ValueError("Out-of-order or unsupported action")
    return replace(result, seen=state.seen + (fingerprint,))
