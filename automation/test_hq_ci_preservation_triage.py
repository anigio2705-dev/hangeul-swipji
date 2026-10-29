"""Negative and positive cases for immutable source preservation diagnostics."""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import hq_ci_preservation_triage as gate


class SourcePreservationTriageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = "intro.html"

    def show(self, _args, cwd):
        self.assertEqual(Path(cwd), self.root)
        return b"approved baseline bytes"

    def test_preserved_source(self):
        (self.root / self.path).write_bytes(b"approved baseline bytes")
        result = gate.inspect(self.root, paths=[self.path], git_show=self.show)
        self.assertTrue(result["all_preserved"])
        self.assertEqual("PRESERVED", result["files"][0]["status"])

    def test_modified_source_fails_closed_without_writing(self):
        file = self.root / self.path
        file.write_bytes(b"unexpected modified bytes")
        before = file.read_bytes()
        result = gate.inspect(self.root, paths=[self.path], git_show=self.show)
        self.assertFalse(result["all_preserved"])
        self.assertEqual("MODIFIED", result["files"][0]["status"])
        self.assertNotEqual(result["files"][0]["baseline_sha256"],
                            result["files"][0]["current_sha256"])
        self.assertEqual(before, file.read_bytes())

    def test_missing_source_fails_closed(self):
        result = gate.inspect(self.root, paths=[self.path], git_show=self.show)
        self.assertFalse(result["all_preserved"])
        self.assertEqual("MISSING", result["files"][0]["status"])

    def test_unavailable_baseline_is_not_success(self):
        def unavailable(_args, cwd):
            raise FileNotFoundError("history unavailable")
        result = gate.inspect(self.root, paths=[self.path], git_show=unavailable)
        self.assertFalse(result["all_preserved"])
        self.assertEqual("BASE_UNAVAILABLE", result["files"][0]["status"])

    def test_invalid_ref_and_unapproved_path_rejected(self):
        with self.assertRaises(ValueError):
            gate.inspect(self.root, base="main; rm -rf", paths=[self.path], git_show=self.show)
        with self.assertRaises(ValueError):
            gate.inspect(self.root, paths=[".env"], git_show=self.show)

    def test_strict_cli_exit_code_is_two_on_drift(self):
        (self.root / self.path).write_bytes(b"modified")
        with mock.patch.object(gate, "ORIGINAL_PATHS", (self.path,)), \
             mock.patch.object(gate.subprocess, "check_output", side_effect=self.show), \
             contextlib.redirect_stdout(io.StringIO()) as captured:
            rc = gate.main(["--root", str(self.root), "--strict"])
        self.assertEqual(2, rc)
        self.assertIn('"all_preserved": false', captured.getvalue())


if __name__ == "__main__":
    unittest.main()
