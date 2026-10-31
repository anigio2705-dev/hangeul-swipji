"""#118: isolated, nonbinding two-party dispute review audit ledger.

Never connect to an operating database or use to authorize sanctions, refunds,
settlement holds, or forfeitures. A future server adapter must authenticate
participant identities, operator authorization, and trusted evidence.
"""
import hashlib
import json
import re
import sqlite3

_ID = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")
_ALLOWED = {"unresolved", "no_fault", "student_fault", "teacher_fault", "more_evidence"}


def _id(value, label):
    if type(value) is not str or not _ID.fullmatch(value):
        raise ValueError("invalid " + label)
    return value


def _text(value, label, maximum=2000):
    if type(value) is not str or not value.strip() or len(value) > maximum:
        raise ValueError("invalid " + label)
    return value.strip()


class FairDisputeReview:
    """Append-only SQLite review records; no automated guilt or money actions."""

    def __init__(self, path=":memory:"):
        self.db = sqlite3.connect(path, isolation_level=None, timeout=10)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
CREATE TABLE IF NOT EXISTS fair_case (
  case_id TEXT PRIMARY KEY, booking_ref TEXT NOT NULL,
  complaint_evidence TEXT NOT NULL, category TEXT NOT NULL
    CHECK(category IN ('nonperformance','connectivity','quality'))
);
CREATE TABLE IF NOT EXISTS fair_statement (
  case_id TEXT NOT NULL REFERENCES fair_case(case_id),
  role TEXT NOT NULL CHECK(role IN ('student','teacher')),
  participant_id TEXT NOT NULL, evidence_ref TEXT NOT NULL,
  statement TEXT NOT NULL, statement_hash TEXT NOT NULL,
  PRIMARY KEY(case_id,role)
);
CREATE TABLE IF NOT EXISTS fair_decision (
  case_id TEXT PRIMARY KEY REFERENCES fair_case(case_id),
  operator_id TEXT NOT NULL, verdict TEXT NOT NULL,
  rationale TEXT NOT NULL, evidence_ref TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS fair_case_immutable_u BEFORE UPDATE ON fair_case
BEGIN SELECT RAISE(ABORT,'immutable case'); END;
CREATE TRIGGER IF NOT EXISTS fair_case_immutable_d BEFORE DELETE ON fair_case
BEGIN SELECT RAISE(ABORT,'immutable case'); END;
CREATE TRIGGER IF NOT EXISTS fair_statement_immutable_u BEFORE UPDATE ON fair_statement
BEGIN SELECT RAISE(ABORT,'immutable statement'); END;
CREATE TRIGGER IF NOT EXISTS fair_statement_immutable_d BEFORE DELETE ON fair_statement
BEGIN SELECT RAISE(ABORT,'immutable statement'); END;
CREATE TRIGGER IF NOT EXISTS fair_decision_immutable_u BEFORE UPDATE ON fair_decision
BEGIN SELECT RAISE(ABORT,'immutable decision'); END;
CREATE TRIGGER IF NOT EXISTS fair_decision_immutable_d BEFORE DELETE ON fair_decision
BEGIN SELECT RAISE(ABORT,'immutable decision'); END;
""")

    def close(self):
        self.db.close()

    def open_case(self, *, case_id, booking_ref, complaint_evidence, category):
        _id(case_id, "case id")
        _id(booking_ref, "booking reference")
        _id(complaint_evidence, "complaint evidence")
        if category not in ("nonperformance", "connectivity", "quality"):
            raise ValueError("invalid dispute category")
        self.db.execute("INSERT INTO fair_case VALUES(?,?,?,?)",
                        (case_id, booking_ref, complaint_evidence, category))
        return self.read(case_id)

    def add_statement(self, *, case_id, role, participant_id, evidence_ref, statement):
        _id(case_id, "case id")
        if role not in ("student", "teacher"):
            raise ValueError("invalid party role")
        _id(participant_id, "participant id")
        _id(evidence_ref, "evidence reference")
        statement = _text(statement, "statement")
        digest = hashlib.sha256(json.dumps(
            [case_id, role, participant_id, evidence_ref, statement],
            ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()
        self.db.execute("BEGIN IMMEDIATE")
        try:
            if self.db.execute("SELECT 1 FROM fair_decision WHERE case_id=?",
                               (case_id,)).fetchone():
                raise ValueError("case already decided")
            previous = self.db.execute(
                "SELECT statement_hash FROM fair_statement WHERE case_id=? AND role=?",
                (case_id, role)).fetchone()
            if previous is not None:
                if previous["statement_hash"] != digest:
                    raise ValueError("conflicting party statement")
            else:
                self.db.execute("INSERT INTO fair_statement VALUES(?,?,?,?,?,?)",
                                (case_id, role, participant_id, evidence_ref,
                                 statement, digest))
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise
        return self.read(case_id)

    def record_operator_review(self, *, case_id, operator_id, verdict,
                               rationale, evidence_ref):
        _id(case_id, "case id")
        _id(operator_id, "operator id")
        _id(evidence_ref, "decision evidence")
        rationale = _text(rationale, "decision rationale")
        if verdict not in _ALLOWED:
            raise ValueError("invalid manual verdict")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            if self.db.execute("SELECT 1 FROM fair_decision WHERE case_id=?",
                               (case_id,)).fetchone():
                raise ValueError("decision already recorded")
            parties = self.db.execute(
                "SELECT role,participant_id FROM fair_statement WHERE case_id=?",
                (case_id,)).fetchall()
            if {p["role"] for p in parties} != {"student", "teacher"}:
                raise ValueError("both party statements required")
            if len({p["participant_id"] for p in parties}) != 2:
                raise ValueError("same participant cannot represent both parties")
            if operator_id in {p["participant_id"] for p in parties}:
                raise ValueError("operator must be independent of both parties")
            self.db.execute("INSERT INTO fair_decision VALUES(?,?,?,?,?)",
                            (case_id, operator_id, verdict, rationale, evidence_ref))
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise
        return self.read(case_id)

    def read(self, case_id):
        _id(case_id, "case id")
        row = self.db.execute("SELECT * FROM fair_case WHERE case_id=?",
                              (case_id,)).fetchone()
        if row is None:
            raise KeyError("dispute not found")
        parties = [dict(p) for p in self.db.execute(
            "SELECT role,participant_id,evidence_ref,statement FROM fair_statement "
            "WHERE case_id=? ORDER BY role", (case_id,))]
        decision = self.db.execute(
            "SELECT operator_id,verdict,rationale,evidence_ref FROM fair_decision "
            "WHERE case_id=?", (case_id,)).fetchone()
        return {
            "case_id": row["case_id"], "booking_ref": row["booking_ref"],
            "complaint_evidence": row["complaint_evidence"],
            "category": row["category"], "statements": parties,
            "status": ("MANUAL_REVIEW_RECORDED" if decision else
                       "AWAIT_BOTH_PARTIES"),
            "operator_review": dict(decision) if decision else None,
            "automatic_fault": False, "automatic_forfeiture": False,
            "refund_executed": False, "payout_blocked": False,
            "operating_db_connected": False, "operator_auth_verified": False,
            "real_money": False,
        }
