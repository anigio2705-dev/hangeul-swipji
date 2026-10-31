"""Negative cases for the persistent GitHub issue queue watchdog."""
import io
import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from urllib.error import HTTPError

from continuous_dispatcher import (
    MARKER, QueueIntegrityError, list_open_issues, pending, plan, request,
    valid_repo,
)


def issue(number=1, **changes):
    item = {"number": number, "title": MARKER + " work", "state": "open",
            "created_at": "2026-10-31T10:30:00Z"}
    item.update(changes)
    return item


NOW = datetime(2026, 10, 31, 11, 0, tzinfo=timezone.utc)


class QueueTests(unittest.TestCase):
    def test_empty_creates_request(self):
        self.assertEqual(plan([])["action"], "create")

    def test_open_request_deduplicates(self):
        self.assertEqual(plan([issue()], now=NOW)["action"], "wait")

    def test_closed_request_allows_next(self):
        self.assertEqual(plan([issue(state="closed")])["action"], "create")

    def test_pull_request_not_work_request(self):
        self.assertEqual(pending([issue(pull_request={})]), [])

    def test_unrelated_issue_not_blocking(self):
        self.assertEqual(plan([issue(title="Other")])["action"], "create")

    def test_no_approval_claim(self):
        self.assertIn("NOT evidence", plan([])["body"])

    def test_duplicate_open_requests_fail_closed(self):
        result = plan([issue(1), issue(2)], now=NOW)
        self.assertEqual(result["action"], "blocked")
        self.assertEqual(result["numbers"], [1, 2])

    def test_stale_request_not_silently_replaced(self):
        old = issue(created_at="2026-10-31T09:59:00Z")
        self.assertEqual(plan([old], now=NOW)["action"], "stale")

    def test_fresh_request_stays_waiting(self):
        self.assertEqual(plan([issue()], now=NOW)["action"], "wait")

    def test_bad_timestamp_blocks(self):
        self.assertEqual(plan([issue(created_at="nonsense")])["action"], "blocked")

    def test_no_timestamp_waits_instead_of_creating(self):
        self.assertEqual(plan([issue(created_at=None)])["action"], "wait")

    def test_repo_validation(self):
        self.assertTrue(valid_repo("anigio2705-dev/hangeul-swipji"))
        for name in ("", "owner", "owner/repo/extra", "owner/repo?x=1"):
            self.assertFalse(valid_repo(name))

    def test_more_than_100_issues_pages_and_deduplicates(self):
        calls = []
        def fetch(path, token):
            calls.append(path)
            if path.endswith("&page=1"):
                return [issue(n, title="Other") for n in range(1, 101)]
            if path.endswith("&page=2"):
                return [issue(101)]
            raise AssertionError("unexpected page")
        found = list_open_issues("owner/repo", "token", fetch=fetch)
        self.assertEqual(len(found), 101)
        self.assertEqual(plan(found, now=NOW)["action"], "wait")
        self.assertEqual(len(calls), 2)

    def test_exactly_100_requires_next_page(self):
        def fetch(path, token):
            return [issue(n, title="Other") for n in range(100)] if path.endswith("&page=1") else []
        self.assertEqual(len(list_open_issues("o/r", "token", fetch=fetch)), 100)

    def test_pagination_failure_fails_closed(self):
        def fetch(path, token):
            return [issue(n, title="Other") for n in range(100)]
        with self.assertRaises(QueueIntegrityError):
            list_open_issues("o/r", "token", fetch=fetch, max_pages=2)

    def test_non_list_response_fails_closed(self):
        with self.assertRaises(QueueIntegrityError):
            list_open_issues("o/r", "token", fetch=lambda p, t: {"message": "denied"})

    def test_permission_denied_is_not_retried(self):
        attempts = []
        def denied(req, timeout):
            attempts.append(1)
            raise HTTPError(req.full_url, 403, "Forbidden", {}, None)
        with self.assertRaises(HTTPError):
            request("/repos/o/r/issues", "token", opener=denied, sleeper=lambda s: None)
        self.assertEqual(len(attempts), 1)

    def test_transient_503_is_retried(self):
        attempts, waits = [], []
        def flaky(req, timeout):
            attempts.append(1)
            if len(attempts) < 3:
                raise HTTPError(req.full_url, 503, "busy", {}, None)
            return io.BytesIO(b'[]')
        result = request("/repos/o/r/issues", "token", opener=flaky,
                         sleeper=waits.append)
        self.assertEqual(result, [])
        self.assertEqual(len(attempts), 3)
        self.assertEqual(waits, [1, 2])

    def test_rate_limit_403_is_retried(self):
        attempts = []
        def flaky(req, timeout):
            attempts.append(1)
            if len(attempts) == 1:
                raise HTTPError(req.full_url, 403, "rate limited",
                                {"X-RateLimit-Remaining": "0"}, None)
            return io.BytesIO(b'[]')
        self.assertEqual(request("/repos/o/r/issues", "token", opener=flaky,
                                 sleeper=lambda s: None), [])
        self.assertEqual(len(attempts), 2)

    def test_invalid_token_or_path_rejected(self):
        for path, token in (("https://evil.test", "t"), ("/repos/o/r", ""),
                            ("/other/path", "t")):
            with self.assertRaises(ValueError):
                request(path, token, opener=lambda *a, **kw: None)

    def test_main_aborts_create_on_second_read_race(self):
        import continuous_dispatcher as dispatcher
        with patch.dict("os.environ", {"GITHUB_REPOSITORY": "o/r",
                                        "GH_TOKEN": "secret",
                                        "APPLY_QUEUE": "true"}):
            with patch.object(dispatcher, "list_open_issues",
                              side_effect=[[], [issue()]]):
                with patch.object(dispatcher, "request") as write:
                    dispatcher.main()
                    write.assert_not_called()

    def test_main_fails_closed_on_duplicate(self):
        import continuous_dispatcher as dispatcher
        with patch.dict("os.environ", {"GITHUB_REPOSITORY": "o/r",
                                        "GH_TOKEN": "secret",
                                        "APPLY_QUEUE": "true"}):
            with patch.object(dispatcher, "list_open_issues",
                              return_value=[issue(1), issue(2)]):
                with patch.object(dispatcher, "request") as write:
                    with self.assertRaises(QueueIntegrityError):
                        dispatcher.main()
                    write.assert_not_called()


    def test_qa15_ambiguous_post_503_must_not_replay_without_idempotency(self):
        """A POST may have committed before a 503; replay creates a second issue."""
        calls = []
        def ambiguous(req, timeout):
            calls.append(req.get_method())
            if len(calls) == 1:
                raise HTTPError(req.full_url, 503, "response lost after commit", {}, None)
            return io.BytesIO(b'{"number": 999}')
        # GET retries are fine; POST must not be blindly replayed without a
        # server-enforced idempotency key or a transactional uniqueness guard.
        with self.assertRaises(HTTPError):
            request("/repos/o/r/issues", "token", "POST",
                    {"title": MARKER + " work"}, opener=ambiguous,
                    sleeper=lambda _: None)
        self.assertEqual(calls, ["POST"])


if __name__ == "__main__":
    unittest.main()
