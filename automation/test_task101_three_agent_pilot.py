"""Offline security regressions for the bounded #101 three-role API pilot."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import task101_three_agent_pilot as pilot


class HandoffTests(unittest.TestCase):
    def fixture(self, path, team="11", run_id="123", sha="a" * 40):
        record = {
            "schema": 1, "task_id": 101, "team": team, "run_id": run_id,
            "job": "team11", "workflow_sha": sha, "product_sha": pilot.PRODUCT_SHA,
            "model": pilot.MODEL, "api_response_id": "chatcmpl-fake-fixture",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            "previous_handoff_id": "",
            "analysis": {"consumed_handoff_id": "", "hypothesis": "H",
                         "challenge": "C", "next_experiment": "X",
                         "evidence_boundary": "NOT ACTUALLY EXECUTED"},
            "ready_approval": False,
        }
        record["handoff_id"] = hashlib.sha256(pilot.canonical(record)).hexdigest()
        Path(path).write_text(json.dumps(record))
        return record

    def test_accepts_exact_handoff_for_next_role(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "11.json"
            a = self.fixture(p)
            self.assertEqual(a["handoff_id"],
                             pilot.validate_prior(p, "14", "123", "a" * 40)["handoff_id"])

    def test_rejects_tampered_handoff(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "11.json"
            a = self.fixture(p)
            a["analysis"]["hypothesis"] = "tampered"
            p.write_text(json.dumps(a))
            with self.assertRaises(ValueError):
                pilot.validate_prior(p, "14", "123", "a" * 40)

    def test_rejects_wrong_team_or_run(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "11.json"
            self.fixture(p)
            with self.assertRaises(ValueError):
                pilot.validate_prior(p, "15", "123", "a" * 40)
            with self.assertRaises(ValueError):
                pilot.validate_prior(p, "14", "456", "a" * 40)

    def test_missing_api_key_makes_zero_calls(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}, clear=False):
            with patch("sys.argv", ["pilot", "--team", "11", "--output", "/tmp/never-written-task101.json"]):
                with self.assertRaisesRegex(RuntimeError, "MISSING_API_KEY"):
                    pilot.main()


if __name__ == "__main__":
    unittest.main()
