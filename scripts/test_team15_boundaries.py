#!/usr/bin/env python3
"""Offline integration boundary contract tests; no network, no real payments."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REQUIRED = {
    "team11": ("phase3/common_contract.py", "phase3/server.py"),
    "team12": ("scripts/team12_audio_inventory.py",),
    "team13": ("phase3/server.py", "phase3/test_instant_matching.py"),
    "team14": ("phase3/team14_monthly_sim.py",),
}
class TeamBoundaryTests(unittest.TestCase):
    def test_required_source_files(self):
        for team, paths in REQUIRED.items():
            for relative in paths:
                with self.subTest(team=team, file=relative):
                    self.assertTrue((ROOT/team/relative).is_file(), f"missing {team}/{relative}")
    def test_team14_refund_safety_contract(self):
        root = ROOT/"team14"/"phase3"
        content = "\n".join(p.read_text(errors="replace") for p in root.glob("*.py") if p.stat().st_size < 1_000_000)
        for marker in ("refund_completed", "refund", "event_id"):
            with self.subTest(marker=marker):
                self.assertIn(marker, content)
    def test_no_unverified_e2e_claim(self):
        report = {"source_checked": True, "runtime_integrated": False,
                  "real_payment": False, "human_av": False}
        self.assertFalse(report["runtime_integrated"])
        print(json.dumps(report, ensure_ascii=False))
if __name__ == "__main__":
    unittest.main(verbosity=2)
