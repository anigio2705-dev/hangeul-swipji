"""Staging deployment identity must not invent a Git commit SHA."""
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from staging_server import deployment_commit


class StagingDeploymentIdentityTests(unittest.TestCase):
    def test_render_full_commit_is_exposed(self):
        sha = "A" * 40
        self.assertEqual(deployment_commit({"RENDER_GIT_COMMIT": sha}), sha.lower())

    def test_invalid_or_missing_sha_is_not_reported(self):
        for env in ({}, {"RENDER_GIT_COMMIT": "ad5757d"},
                    {"RENDER_GIT_COMMIT": "unknown"},
                    {"RENDER_GIT_COMMIT": "x" * 40}):
            with self.subTest(env=env):
                self.assertIsNone(deployment_commit(env))

    def test_explicit_staging_build_sha_fallback(self):
        sha = "0123456789abcdef" * 2 + "01234567"
        self.assertEqual(deployment_commit({"HS_STAGING_BUILD_SHA": sha}), sha)

    def test_provider_commit_takes_precedence(self):
        self.assertEqual(deployment_commit({"RENDER_GIT_COMMIT": "a"*40,
                                            "HS_STAGING_BUILD_SHA": "b"*40}), "a"*40)


if __name__ == "__main__":
    unittest.main()
