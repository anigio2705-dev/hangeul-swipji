"""Fail-closed, read-only event-state contract for an eventual always-on worker.

This module does not authenticate external agents, trigger AI jobs, approve a PR,
or authorize payments. Trusted transport must attest each role and principal.
"""
from dataclasses import dataclass

ROLES = frozenset({"central", "developer", "qa15"})
OUTCOMES = frozenset({"OK", "QA_FAIL", "IN_PROGRESS"})
VALID_SHA = set("0123456789abcdef")


@dataclass(frozen=True)
class Evidence:
    task: int
    sha: str
    role: str
    principal: str
    run_id: str
    outcome: str

    def validate(self):
        if (type(self.task) is not int or self.task < 1
                or type(self.sha) is not str or len(self.sha) != 40
                or any(c not in VALID_SHA for c in self.sha)
                or self.role not in ROLES or self.outcome not in OUTCOMES
                or not isinstance(self.principal, str) or not self.principal.strip()
                or not isinstance(self.run_id, str) or not self.run_id.strip()):
            raise ValueError("Invalid or unauthenticated-format event evidence")


def decide(task, sha, evidence):
    """Return a safe advisory state; never returns READY without trusted attestation.

    Evidence must be provided by an authenticated event receiver; user-controlled
    comments or free-form role strings alone are NOT trustworthy attestations.
    """
    if type(task) is not int or type(sha) is not str or len(sha) != 40 or any(c not in VALID_SHA for c in sha):
        raise ValueError("Invalid task or commit")
    unique = {}
    for event in evidence:
        event.validate()
        if event.task != task:
            continue
        key = (event.task, event.sha, event.role, event.run_id)
        if key in unique:
            if unique[key] != event:
                raise ValueError("Conflicting duplicate execution evidence")
            continue
        unique[key] = event
    relevant = [e for e in unique.values() if e.sha == sha]
    if any(e.role == "qa15" and e.outcome == "QA_FAIL" for e in relevant):
        return "QA_FAIL_REWORK_REQUIRED"
    passed = {}
    for e in relevant:
        if e.outcome == "OK":
            if e.role in passed and passed[e.role] != e:
                return "APPROVAL_PENDING_CONFLICT"
            passed[e.role] = e
    if "developer" not in passed:
        return "DEVELOPMENT_PENDING"
    if "qa15" not in passed:
        return "QA_REQUESTED"
    if "central" not in passed:
        return "APPROVAL_PENDING_CENTRAL"
    if len({e.principal for e in passed.values()}) != 3:
        return "APPROVAL_PENDING_SAME_PRINCIPAL"
    if len({e.run_id for e in passed.values()}) != 3:
        return "APPROVAL_PENDING_SAME_RUN"
    return "THREE_ROLE_EVIDENCE_PRESENT_UNATTESTED"
