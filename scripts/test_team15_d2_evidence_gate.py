import unittest
from scripts.team15_d2_evidence_gate import validate

def row(**updates):
    item = dict(team="15", feature="99-login", code_sha="", ci_run_url="",
                render_sha="", http_evidence="", browser_evidence="",
                state="not_started", blockers=["Render access"])
    item.update(updates)
    return item

class EvidenceGateTests(unittest.TestCase):
    def test_unverified_is_valid_and_not_pass(self):
        self.assertEqual(validate([row()]), [])
    def test_ci_cannot_be_server_pass(self):
        r = row(state="server_verified", code_sha="a"*40,
                ci_run_url="https://github.com/a/b/actions/runs/123")
        self.assertTrue(any("Render SHA" in e for e in validate([r])))
    def test_valid_server_evidence(self):
        r = row(state="server_verified", code_sha="a"*40, render_sha="b"*40,
                ci_run_url="https://github.com/a/b/actions/runs/123",
                http_evidence="https://example.test/log/123",
                browser_evidence="https://example.test/browser/123",
                verification_time="2026-10-28T14:00:00Z")
        self.assertEqual(validate([r]), [])
    def test_duplicate_detection(self):
        self.assertTrue(any("duplicate" in e for e in validate([row(),row()])))
    def test_invalid_ci_url(self):
        self.assertTrue(any("invalid CI" in e for e in validate([row(ci_run_url="made-up")])))

if __name__ == "__main__":
    unittest.main()
