"""B/15 independent negative regression against C PR #168 exact SHA
cc7ebee316479f13a7a7ccc16d6e49d1347bdc39a.

No GitHub requests, no real SQLite file, no credentials, no production writes.
An apparent /var/lib/hangeul-swipji/ prefix must not authorize a normalized
path outside the trusted durable directory.
"""
import unittest
from unittest.mock import patch

import ci_poll_fallback as poller
import qa_handoff_dispatcher as dispatcher


class DurablePathContainmentIndependentTests(unittest.TestCase):
    def test_01_polling_rejects_parent_traversal_before_any_fetch(self):
        outside = "/var/lib/hangeul-swipji/../attacker-owned/ci.sqlite"
        with patch.object(poller, "_persist_ci_qa_event",
                          side_effect=AssertionError("unexpected DB write")):
            with self.assertRaises(ValueError):
                poller.poll_once(
                    outside, token="fake-token",
                    fetch=lambda path, token: {"workflow_runs": []})

    def test_02_dispatcher_rejects_parent_traversal_before_sqlite_open(self):
        outside = "/var/lib/hangeul-swipji/../../tmp/attacker-ci.sqlite"
        with patch.object(dispatcher.sqlite3, "connect",
                          side_effect=AssertionError("out-of-root DB opened")) as connect:
            with self.assertRaises(ValueError):
                dispatcher.dispatch_once(
                    outside, token="fake-token",
                    repo="anigio2705-dev/hangeul-swipji", now=1)
            connect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
