"""Fail-closed regressions for legacy curated task fallback.

An old curated ID cannot substitute for the independent 15-team READY gate.
The canonical registry is intentionally consulted; no temporary approval is made.
"""
import unittest
from hq_160_task_cycle import _semantic_dispatch_gate, contracts, next_assignment


class CuratedFailClosedTests(unittest.TestCase):
    def test_unmapped_ids_cannot_dispatch(self):
        self.assertFalse(_semantic_dispatch_gate(8, "scripts/team15_independent_gate.py"))
        self.assertFalse(_semantic_dispatch_gate(115, "phase3/team14_refund_workflow.py"))

    def test_candidate_blocked_and_code_verified_are_not_fresh_ready(self):
        for number, path in (
            (22, "phase3/instant_matching.py"),
            (51, "scripts/audit-hangul-audio.py"),
            (55, "scripts/render-audio-credits.py"),
            (56, "scripts/find-human-audio-sources.py"),
            (41, "scripts/team12_content_regression.py"),
            (151, "scripts/team15_cross_team_smoke.py"),
        ):
            with self.subTest(number=number):
                self.assertFalse(_semantic_dispatch_gate(number, path))

    def test_empty_evidence_does_not_reopen_unreviewed_work(self):
        sample = "\n".join(f"{n}. [ ] Item {n}" for n in range(1, 161))
        catalog = contracts(sample)
        for team in ("11", "12", "13", "14", "15", "16"):
            with self.subTest(team=team):
                self.assertIsNone(next_assignment(team, catalog, evidence={}),
                                  "No independently READY contract exists on this branch")


if __name__ == "__main__":
    unittest.main()
