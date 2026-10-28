"""Regression tests for honest physical human-recording inventory (no decoder needed)."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from team12_audio_inventory import inspect


class AudioInventoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "assets/hangul-audio").mkdir(parents=True)
        self.records = {}

    def tearDown(self):
        self.tmp.cleanup()

    def add(self, word, filename, raw=b"unique recording", **overrides):
        (self.root / "assets/hangul-audio" / filename).write_bytes(raw)
        entry = {
            "src": "./assets/hangul-audio/" + filename,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "kind": "human",
            "sourceUrl": "https://example.org/recording",
            "author": "Speaker",
            "license": "CC BY 4.0",
        }
        entry.update(overrides)
        self.records[word] = entry

    def audit(self, *, decoder_status=0):
        (self.root / "hangul-audio-manifest.json").write_text(
            json.dumps({"recordings": self.records}, ensure_ascii=False), encoding="utf-8"
        )
        with patch("team12_audio_inventory.subprocess.run", return_value=SimpleNamespace(
                returncode=decoder_status, stderr="decoder failure")):
            return inspect(self.root)

    def test_clean_recording_is_unapproved_not_approved(self):
        self.add("가", "ac00.mp3")
        report = self.audit()
        self.assertEqual({"ready_unapproved": 1, "held": 0, "missing": 398}, report["counts"])
        self.assertEqual([], report["file_issues"])
        self.assertEqual("NOT_APPROVED", report["human_listening"])
        self.assertEqual("NOT_TESTED", report["browser_playback"])

    def test_missing_hash_and_bad_provenance_are_quarantined(self):
        self.add("가", "ac00.mp3", sha256="", sourceUrl="http://unsafe.example")
        report = self.audit()
        self.assertEqual({"ready_unapproved": 0, "held": 1, "missing": 398}, report["counts"])
        self.assertEqual({"missing_or_invalid_sha256", "missing_provenance"},
                         {x["issue"] for x in report["file_issues"]})

    def test_duplicate_path_and_duplicate_audio_bytes(self):
        self.add("가", "ac00.mp3", b"same recording")
        self.add("나", "b098.mp3", b"same recording")
        self.records["다"] = dict(self.records["가"])
        report = self.audit()
        issues = {x["issue"] for x in report["file_issues"]}
        self.assertIn("duplicate_audio_bytes", issues)
        self.assertIn("duplicate_source_path", issues)
        self.assertEqual({"ready_unapproved": 1, "held": 2, "missing": 396}, report["counts"])

    def test_corrupt_file_and_decode_failure_not_ready(self):
        self.add("가", "ac00.mp3", sha256="0" * 64)
        report = self.audit(decoder_status=1)
        self.assertEqual({"hash_mismatch", "decode_failed"},
                         {x["issue"] for x in report["file_issues"]})
        self.assertEqual(1, report["counts"]["held"])

    def test_malformed_entry_and_path_traversal(self):
        self.records["가"] = None
        self.records["나"] = {"src": "./assets/hangul-audio/../escape.mp3"}
        report = self.audit()
        self.assertEqual({"invalid_recording_entry", "invalid_source_path"},
                         {x["issue"] for x in report["file_issues"]})
        self.assertEqual(2, report["counts"]["held"])

    def test_disabled_recording_remains_held(self):
        self.add("가", "ac00.mp3", disabled=True)
        report = self.audit()
        self.assertEqual(1, report["counts"]["held"])
        self.assertEqual(0, report["counts"]["ready_unapproved"])


if __name__ == "__main__":
    unittest.main()
