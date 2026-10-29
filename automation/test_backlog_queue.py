import unittest
import json
from pathlib import Path
from backlog_queue import (
    build_report, parse_backlog, validate_evidence, owner_for, EXTERNAL_GATES
)

def sample(checked=()):
    return "\n".join(
        f"{n}. [{'x' if n in checked else ' '}] Task {n}"
        for n in range(1, 161)
    )

def verified(status="code_verified", **extra):
    return {
        "status": status,
        "commit": "a" * 40,
        "ci_url": "https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/12345",
        "ci_result": "success",
        **extra,
    }

class BacklogQueueTests(unittest.TestCase):
    def test_checked_in_evidence_is_code_only_not_final_completion(self):
        ledger = json.loads((Path(__file__).parent / "task-evidence.json").read_text(encoding="utf-8"))
        report = build_report(sample(), ledger)
        self.assertEqual(report["counts"]["complete"], 0)
        verified_numbers = {int(n) for n, record in ledger.items()
                            if record["status"] == "code_verified"}
        blocked_numbers = {int(n) for n, record in ledger.items()
                           if record["status"] == "blocked"}
        self.assertEqual(report["counts"]["code_verified"], len(verified_numbers))
        self.assertEqual(report["counts"]["blocked"], len(blocked_numbers))
        self.assertEqual({x["number"] for x in report["review_queue"]}, verified_numbers)
        queue_numbers = {x["number"] for x in report["next_queue"]}
        self.assertFalse((verified_numbers | blocked_numbers) & queue_numbers)

    def test_review_queue_is_not_limited_by_dispatch_batch_size(self):
        # Regression for CI 40824705443: a 13th verified item was hidden.
        ledger = {str(n): verified() for n in range(1, 16)}
        report = build_report(sample(), ledger, limit=3)
        self.assertEqual(report["counts"]["code_verified"], 15)
        self.assertEqual(len(report["next_queue"]), 3)
        self.assertEqual({x["number"] for x in report["review_queue"]},
                         set(range(1, 16)))
        self.assertFalse({x["number"] for x in report["next_queue"]} &
                         {x["number"] for x in report["review_queue"]})

    def test_exactly_160_and_unique(self):
        self.assertEqual(len(parse_backlog(sample())), 160)
        with self.assertRaises(ValueError):
            parse_backlog(sample() + "\n160. [ ] Duplicate")
        with self.assertRaises(ValueError):
            parse_backlog(sample().replace("42. [ ]", "44. [ ]"))

    def test_all_unverified_not_falsely_completed(self):
        report = build_report(sample(), timestamp="2026-10-29T00:00:00Z")
        self.assertEqual(report["counts"]["complete"], 0)
        self.assertEqual(report["counts"]["unverified"], 160)
        self.assertEqual(report["next_queue"][0]["number"], 11)
        self.assertFalse(any(t["external_gate"] for t in report["next_queue"]))
        self.assertEqual(report["safety"]["production_deploy"], False)

    def test_unchecked_master_never_complete(self):
        with self.assertRaisesRegex(ValueError, "master backlog"):
            build_report(sample(), {"11": verified("complete")})

    def test_ci_failure_or_missing_evidence_rejected(self):
        for record in (
            {"status": "code_verified"},
            verified(ci_result="failure"),
            verified(ci_url="https://evil.invalid/runs/1"),
            verified(commit="bad"),
        ):
            with self.subTest(record=record):
                with self.assertRaises(ValueError):
                    build_report(sample(), {"11": record})

    def test_checked_with_ci_can_complete_nonexternal(self):
        report = build_report(sample({11}), {"11": verified("complete")})
        self.assertEqual(report["counts"]["complete"], 1)
        self.assertNotIn(11, [x["number"] for x in report["next_queue"]])

    def test_external_and_approval_gate(self):
        self.assertIn(154, EXTERNAL_GATES)
        with self.assertRaisesRegex(ValueError, "real-world"):
            build_report(sample({154}), {"154": verified("complete")})
        with self.assertRaisesRegex(ValueError, "approval"):
            build_report(sample({154}), {"154": verified("complete", external_evidence="staging report")})
        report = build_report(sample({154}), {"154": verified(
            "complete", external_evidence="staging report", approval_evidence="signed approval"
        )})
        self.assertEqual(report["counts"]["complete"], 1)

    def test_owner_ranges_and_limit(self):
        self.assertEqual(owner_for(51), "12+15")
        self.assertEqual(owner_for(160), "15+16")
        self.assertEqual(len(build_report(sample(), limit=3)["next_queue"]), 3)
        with self.assertRaises(ValueError):
            build_report(sample(), limit=0)

    def test_blocked_excluded_and_code_verified_not_complete(self):
        report = build_report(sample(), {
            "11": {"status": "blocked"},
            "12": verified("code_verified"),
        })
        self.assertEqual(report["counts"]["blocked"], 1)
        self.assertEqual(report["counts"]["code_verified"], 1)
        self.assertEqual(report["counts"]["complete"], 0)
        self.assertNotIn(11, [x["number"] for x in report["next_queue"]])
        self.assertEqual([x["number"] for x in report["review_queue"]], [12])

    def test_verified_work_moves_to_review_without_duplicate_development(self):
        report = build_report(sample(), {
            "11": verified("code_verified"),
            "12": {"status": "in_progress"},
            "13": {"status": "blocked"},
            "14": verified("code_verified"),
        }, limit=5)
        build = [x["number"] for x in report["next_queue"]]
        review = [x["number"] for x in report["review_queue"]]
        self.assertNotIn(11, build)
        self.assertNotIn(14, build)
        self.assertNotIn(13, build)
        self.assertIn(12, build)
        self.assertEqual(review, [11, 14])
        self.assertEqual(report["counts"]["complete"], 0)

    def test_started_work_before_unverified_in_same_safety_tier(self):
        report = build_report(sample(), {
            "22": {"status": "in_progress"},
            "24": {"status": "in_progress"},
            "51": {"status": "in_progress"},
        }, limit=4)
        self.assertEqual([x["number"] for x in report["next_queue"]][:2], [22, 51])
        self.assertNotIn(24, [x["number"] for x in report["next_queue"]])

if __name__ == "__main__":
    unittest.main()
