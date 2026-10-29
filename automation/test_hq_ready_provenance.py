"""Fail-closed pre-OpenAI READY provenance regressions (no network or model calls)."""
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from hq_six_developers import verify_ready_provenance, shell


class ReadyProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / "feature.py").write_text("def f(): return True\n")
        (self.root / "test_feature.py").write_text(
            "import unittest\nclass T(unittest.TestCase):\n"
            " def test_f(self): self.assertTrue(True)\n")
        self.sha = "a" * 40
        self.item = {"number": 101, "path": "feature.py", "dynamic": True}
        self.registry = {"items": {"101": {
            "state": "READY", "independent_team15": "PASS",
            "independent_ci_sha": self.sha,
            "independent_ci_url":
                "https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/123",
            "source_paths": ["feature.py"], "test_paths": ["test_feature.py"],
        }}}

    def run_json(self, **overrides):
        result = {"head_sha": self.sha, "status": "completed",
                  "conclusion": "success",
                  "repository": {"full_name": "anigio2705-dev/hangeul-swipji"}}
        result.update(overrides)
        return io.BytesIO(json.dumps(result).encode())

    def git(self, *args, **kwargs):
        if args[:2] == ("git", "fetch"):
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if args[:2] in (("git", "rev-parse"), ("git", "hash-object")):
            return SimpleNamespace(returncode=0, stdout="b" * 40 + "\n", stderr="")
        raise AssertionError("Unexpected git command: " + repr(args))

    def test_no_token_means_no_network_and_no_model_spend(self):
        with patch.dict(os.environ, {"GITHUB_TOKEN": ""}), \
             patch("hq_six_developers.urlopen") as request, \
             patch("hq_six_developers.shell") as git:
            with self.assertRaisesRegex(ValueError, "READY_PROVENANCE_MISSING"):
                verify_ready_provenance(self.item, self.registry, self.root)
            request.assert_not_called()
            git.assert_not_called()

    def test_fake_ci_success_from_different_sha_is_rejected(self):
        with patch.dict(os.environ, {"GITHUB_TOKEN": "fake-token"}), \
             patch("hq_six_developers.urlopen",
                   return_value=self.run_json(head_sha="c" * 40)), \
             patch("hq_six_developers.shell") as git:
            with self.assertRaisesRegex(ValueError, "READY_CI_SHA_OR_STATUS_MISMATCH"):
                verify_ready_provenance(self.item, self.registry, self.root)
            git.assert_not_called()

    def test_wrong_repository_ci_is_rejected(self):
        with patch.dict(os.environ, {"GITHUB_TOKEN": "fake-token"}), \
             patch("hq_six_developers.urlopen",
                   return_value=self.run_json(
                       repository={"full_name": "someone/other"})), \
             patch("hq_six_developers.shell") as git:
            with self.assertRaisesRegex(ValueError, "READY_CI_SHA_OR_STATUS_MISMATCH"):
                verify_ready_provenance(self.item, self.registry, self.root)
            git.assert_not_called()

    def test_stale_team_branch_file_rejected_even_with_green_ci(self):
        def stale_git(*args, **kwargs):
            result = self.git(*args, **kwargs)
            if args[:2] == ("git", "hash-object"):
                result.stdout = "c" * 40 + "\n"
            return result
        with patch.dict(os.environ, {"GITHUB_TOKEN": "fake-token"}), \
             patch("hq_six_developers.urlopen", return_value=self.run_json()), \
             patch("hq_six_developers.shell", side_effect=stale_git):
            with self.assertRaisesRegex(ValueError, "READY_BASELINE_BLOB_MISMATCH"):
                verify_ready_provenance(self.item, self.registry, self.root)

    def test_exact_ci_and_source_test_blobs_pass_without_model_call(self):
        with patch.dict(os.environ, {"GITHUB_TOKEN": "fake-token"}), \
             patch("hq_six_developers.urlopen", return_value=self.run_json()) as request, \
             patch("hq_six_developers.shell", side_effect=self.git) as git:
            self.assertTrue(verify_ready_provenance(self.item, self.registry, self.root))
            request.assert_called_once()
            self.assertEqual(git.call_count, 5)  # fetch + two files x two hashes

    def test_missing_test_file_blocks_before_model(self):
        (self.root / "test_feature.py").unlink()
        with patch.dict(os.environ, {"GITHUB_TOKEN": "fake-token"}), \
             patch("hq_six_developers.urlopen", return_value=self.run_json()), \
             patch("hq_six_developers.shell", side_effect=self.git):
            with self.assertRaisesRegex(ValueError, "READY_FILE_MISSING"):
                verify_ready_provenance(self.item, self.registry, self.root)


    def test_candidate_subprocess_never_receives_api_or_github_tokens(self):
        with patch.dict(os.environ, {"GITHUB_TOKEN": "secret-gh",
                                     "OPENAI_API_KEY": "secret-ai",
                                     "SAFE_FLAG": "allowed"}), \
             patch("hq_six_developers.subprocess.run") as process:
            shell("python", "--version")
            sent = process.call_args.kwargs["env"]
            self.assertNotIn("GITHUB_TOKEN", sent)
            self.assertNotIn("OPENAI_API_KEY", sent)
            self.assertEqual(sent["SAFE_FLAG"], "allowed")


if __name__ == "__main__":
    unittest.main()
