"""Immutable HQ semantic gate for backlog #49.

An AI patch must not erase all recommendations when a learner has weak skills.
The checker is run outside the AI-owned team checkout.
"""
import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

def verify(candidate_root):
    sys.path.insert(0, str(candidate_root / "phase3"))
    import learning
    curriculum = {
        "unitMapping": {"u1": {"stage": 1, "nextUnitId": "u2"},
                        "u2": {"stage": 1}},
        "stages": [{"id": 1, "lessons": [
            {"unitId": "u1", "status": "authored"},
            {"unitId": "u2", "status": "authored"}]}],
    }
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("CREATE TABLE learning_placements (user_id TEXT, stage INTEGER, groups_json TEXT)")
    db.execute("CREATE TABLE learning_checks (user_id TEXT, unit_id TEXT, phase TEXT, score INTEGER, max_score INTEGER, kind TEXT, skills_json TEXT, created_at REAL)")
    try:
        with patch.object(learning, "plan", return_value=curriculum):
            db.execute("INSERT INTO learning_checks VALUES (?,?,?,?,?,?,?,?)", (
                "student", "u1", "post", 0, 2, "text-check",
                json.dumps({"reading": {"earned": 0, "possible": 2}}), 1.0))
            weak = learning.summary(db, "student")
            if weak["weakSkills"] != ["reading"]:
                raise AssertionError("Failed to detect the learner's weak reading skill")
            if not weak["recommendations"] or weak["recommendations"][0]["unitId"] != "u1":
                raise AssertionError("Weak learner must receive a relevant retry recommendation")
            if "not certified" not in weak["recommendationBasis"]:
                raise AssertionError("Recommendation must not be presented as certified placement")
            db.execute("DELETE FROM learning_checks")
            db.execute("INSERT INTO learning_checks VALUES (?,?,?,?,?,?,?,?)", (
                "student", "u1", "post", 2, 2, "text-check",
                json.dumps({"reading": {"earned": 2, "possible": 2}}), 2.0))
            strong = learning.summary(db, "student")
            if strong["weakSkills"] or not strong["recommendations"]:
                raise AssertionError("Strong learner should receive next-unit guidance")
            if strong["recommendations"][0]["unitId"] != "u2":
                raise AssertionError("Completed unit should not be recommended again without weakness")
    finally:
        db.close()
    return True

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: verify_task49.py <candidate_checkout>")
    verify(Path(sys.argv[1]).resolve())
    print("PASS task #49 weak-skill retry, next-unit guidance and non-certification")
