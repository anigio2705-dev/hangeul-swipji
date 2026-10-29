"""Regression: a green CI or checked backlog is not representative approval.

This is a synthetic gate test. It never approves a real task or deploys code.
"""
import unittest
from hq_160_task_cycle import make_report


def sample(*checked):
    return "\n".join(
        f"{n}. [{'x' if n in checked else ' '}] Acceptance for #{n}"
        for n in range(1, 161)
    )


def proof():
    return {
        "status": "complete",
        "commit": "a" * 40,
        "ci_conclusion": "success",
        "independent_review": "pass",
        "ci_url": "https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/123",
    }


class RepresentativeApprovalGateTests(unittest.TestCase):
    def test_checked_and_green_ci_cannot_self_approve(self):
        self.assertEqual(make_report(sample(9), {"9": proof()})["final_complete"], 0)

    def test_approval_flag_without_evidence_is_not_final(self):
        record = proof()
        record["representative_approval"] = True
        self.assertEqual(make_report(sample(9), {"9": record})["final_complete"], 0)

    def test_approval_evidence_without_explicit_confirmation_is_not_final(self):
        record = proof()
        record["representative_approval_evidence"] = "representative review reference"
        self.assertEqual(make_report(sample(9), {"9": record})["final_complete"], 0)

    def test_synthetic_non_external_item_needs_both_owner_signals(self):
        record = proof()
        record.update(representative_approval=True,
                      representative_approval_evidence="representative review reference")
        self.assertEqual(make_report(sample(9), {"9": record})["final_complete"], 1)

    def test_external_gate_remains_required(self):
        record = proof()
        record.update(representative_approval=True,
                      representative_approval_evidence="representative review reference")
        self.assertEqual(make_report(sample(16), {"16": record})["final_complete"], 0)
        record["external_evidence"] = "read-only browser verification"
        self.assertEqual(make_report(sample(16), {"16": record})["final_complete"], 1)


if __name__ == "__main__":
    unittest.main()
