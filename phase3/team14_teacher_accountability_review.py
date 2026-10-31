"""#117 teacher accountability criteria and appeal review, ISOLATED / NONBINDING.

Consumes the #118 two-party manual-review snapshot as an untrusted fixture.
No identity verification, policy approval, live booking adapter, financial action,
search-rank change, suspension, or operating database integration is provided.
"""
import sqlite3
from team14_fair_dispute_review import _id, _text

OUTCOMES = ("uphold_review", "reopen_investigation", "withdraw_proposal")
ACTIONS = ("warning", "exposure_adjustment", "settlement_hold", "activity_limit")


def review_teacher_accountability(dispute, *, prior_confirmed_cases=0,
                                  financial_risk_verified=False):
    """Return reviewable criteria; NEVER authorize or execute a sanction."""
    if type(dispute) is not dict:
        raise ValueError("invalid dispute")
    _id(dispute.get("case_id"), "case id")
    if type(prior_confirmed_cases) is not int or not 0 <= prior_confirmed_cases <= 1000:
        raise ValueError("invalid prior confirmed cases")
    if type(financial_risk_verified) is not bool:
        raise ValueError("invalid financial risk flag")
    decision = dispute.get("operator_review")
    statements = dispute.get("statements")
    if type(statements) is not list:
        raise ValueError("invalid statements")
    if len(statements) != 2 or {p.get("role") for p in statements if type(p) is dict} != {"student", "teacher"}:
        raise ValueError("two party statements required")
    parties = {p["role"]: _id(p.get("participant_id"), "party id") for p in statements}
    if parties["student"] == parties["teacher"]:
        raise ValueError("parties must be distinct")
    confirmed = (type(decision) is dict
                 and decision.get("verdict") == "teacher_fault"
                 and type(decision.get("rationale")) is str
                 and bool(decision["rationale"].strip())
                 and type(decision.get("evidence_ref")) is str
                 and bool(decision["evidence_ref"].strip())
                 and decision.get("operator_id") not in parties.values()
                 and type(decision.get("operator_id")) is str)
    if type(decision) is dict and decision.get("verdict") == "teacher_fault" and not confirmed:
        raise ValueError("invalid teacher-fault confirmation")
    criteria = (
        ("warning", confirmed, "independent manual teacher-fault finding"),
        ("exposure_adjustment", confirmed and prior_confirmed_cases >= 2,
         "at least two previous verified findings; no ranking change authorized"),
        ("settlement_hold", confirmed and financial_risk_verified,
         "verified financial risk; policy and separate payment approval required"),
        ("activity_limit", confirmed and prior_confirmed_cases >= 3,
         "at least three previous verified findings; appeal review required"),
    )
    return {
        "case_id": dispute["case_id"],
        "teacher_id_fixture": parties["teacher"],
        "original_operator_id_fixture": decision.get("operator_id") if confirmed else None,
        "finding": "MANUAL_TEACHER_FAULT_RECORDED" if confirmed else "NO_CONFIRMED_TEACHER_FAULT",
        "criteria": [{"action": action, "candidate": bool(candidate),
                      "rationale": rationale, "authorized": False, "executed": False}
                     for action, candidate, rationale in criteria],
        "appeal_available_for_review": confirmed,
        "policy_approved": False, "identity_verified": False,
        "evidence_provenance_verified": False, "live_booking_verified": False,
        "automatic_sanction": False, "warning_sent": False,
        "exposure_changed": False, "settlement_blocked": False,
        "account_restricted": False, "real_money": False,
        "simulation_only": True,
    }


class TeacherAppealReview:
    """Append-only appeal/independent reviewer audit; NOT a sanctions engine."""

    def __init__(self, path=":memory:"):
        self.db = sqlite3.connect(path, isolation_level=None, timeout=10)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
CREATE TABLE IF NOT EXISTS teacher_appeal(
 case_id TEXT PRIMARY KEY, teacher_id TEXT NOT NULL,
 student_id TEXT NOT NULL, original_operator_id TEXT NOT NULL,
 reason TEXT NOT NULL, evidence_ref TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS teacher_appeal_resolution(
 case_id TEXT PRIMARY KEY REFERENCES teacher_appeal(case_id),
 reviewer_id TEXT NOT NULL, outcome TEXT NOT NULL,
 rationale TEXT NOT NULL, evidence_ref TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS teacher_appeal_no_update BEFORE UPDATE ON teacher_appeal
 BEGIN SELECT RAISE(ABORT,'immutable appeal'); END;
CREATE TRIGGER IF NOT EXISTS teacher_appeal_no_delete BEFORE DELETE ON teacher_appeal
 BEGIN SELECT RAISE(ABORT,'immutable appeal'); END;
CREATE TRIGGER IF NOT EXISTS teacher_resolution_no_update BEFORE UPDATE ON teacher_appeal_resolution
 BEGIN SELECT RAISE(ABORT,'immutable resolution'); END;
CREATE TRIGGER IF NOT EXISTS teacher_resolution_no_delete BEFORE DELETE ON teacher_appeal_resolution
 BEGIN SELECT RAISE(ABORT,'immutable resolution'); END;
""")

    def close(self):
        self.db.close()

    def file_appeal(self, *, dispute, teacher_id, reason, evidence_ref):
        proposal = review_teacher_accountability(dispute)
        if not proposal["appeal_available_for_review"]:
            raise ValueError("teacher fault must be independently recorded")
        _id(teacher_id, "teacher id")
        _id(evidence_ref, "appeal evidence")
        reason = _text(reason, "appeal reason")
        parties = {p["role"]: p["participant_id"] for p in dispute["statements"]}
        if teacher_id != parties["teacher"]:
            raise ValueError("only case teacher can file a review fixture")
        self.db.execute(
            "INSERT INTO teacher_appeal VALUES(?,?,?,?,?,?)",
            (proposal["case_id"], teacher_id, parties["student"],
             proposal["original_operator_id_fixture"], reason, evidence_ref))
        return self.read(proposal["case_id"])

    def decide_appeal(self, *, case_id, reviewer_id, outcome, rationale, evidence_ref):
        _id(case_id, "case id")
        _id(reviewer_id, "reviewer id")
        _id(evidence_ref, "resolution evidence")
        rationale = _text(rationale, "resolution rationale")
        if type(outcome) is not str or outcome not in OUTCOMES:
            raise ValueError("invalid appeal outcome")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.db.execute(
                "SELECT * FROM teacher_appeal WHERE case_id=?", (case_id,)).fetchone()
            if row is None:
                raise KeyError("appeal not found")
            if reviewer_id in (row["teacher_id"], row["student_id"],
                               row["original_operator_id"]):
                raise ValueError("appeal reviewer must be independent")
            self.db.execute(
                "INSERT INTO teacher_appeal_resolution VALUES(?,?,?,?,?)",
                (case_id, reviewer_id, outcome, rationale, evidence_ref))
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise
        return self.read(case_id)

    def read(self, case_id):
        _id(case_id, "case id")
        row = self.db.execute(
            "SELECT * FROM teacher_appeal WHERE case_id=?", (case_id,)).fetchone()
        if row is None:
            raise KeyError("appeal not found")
        decision = self.db.execute(
            "SELECT reviewer_id,outcome,rationale,evidence_ref FROM teacher_appeal_resolution "
            "WHERE case_id=?", (case_id,)).fetchone()
        return {
            "case_id": case_id, "appeal_reason": row["reason"],
            "appeal_evidence_ref": row["evidence_ref"],
            "status": "NONBINDING_REVIEW_RECORDED" if decision else "AWAIT_INDEPENDENT_REVIEW",
            "independent_review": dict(decision) if decision else None,
            "identity_verified": False, "policy_approved": False,
            "sanction_executed": False, "settlement_blocked": False,
            "account_restricted": False, "real_money": False,
            "simulation_only": True,
        }
