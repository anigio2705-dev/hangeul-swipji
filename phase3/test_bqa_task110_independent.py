"""B/15 independent QA-only #110; exact product SHA aecbdee3c97d8836ecc8892bc42d6fe93ad9d0f4."""
import hashlib
import hmac
import unittest

from team14_referral_policy_preview import canonical_policy_bytes, simulate_versioned_reward

KEY = b"B-independent-fixture-only-key-0123456789"


def record(**changes):
    r = dict(version="qa-v1", rate_bps=300, cap_krw=20000,
             effective_from=100, expires_at=1000000,
             refund_window_seconds=604800,
             approved_by="qa-fixture-only", scope="referral_simulation_only")
    r.update(changes)
    return r


def signed(r):
    return hmac.new(KEY, canonical_policy_bytes(r), hashlib.sha256).hexdigest()


def simulate(**changes):
    p = record()
    args = dict(policy_version=p["version"], policy_record=p,
                approval_signature=signed(p), trusted_verification_key=KEY,
                gross_krw=100000, payment_verified=True,
                lesson_completed=True, attendance_verified=True,
                refunded=False, referrer_eligible=True,
                risk_flags=[], paid_at=100, completed_at=200, as_of=700000)
    args.update(changes)
    return simulate_versioned_reward(**args)


class BIndependentTask110Tests(unittest.TestCase):
    def assert_safe(self, result):
        for key in ("real_money", "payment_enabled", "points_credited",
                    "payout_authorized", "production_policy_activated"):
            self.assertIs(result[key], False)
        self.assertEqual({"learner", "teacher", "referrer", "platform"},
                         set(result["participants"]))

    def test_unsigned_or_wrong_key_fails_closed(self):
        for changes in ({"policy_record": None}, {"approval_signature": None},
                        {"approval_signature": "0"*64},
                        {"trusted_verification_key": None},
                        {"trusted_verification_key": b"short"},
                        {"trusted_verification_key": b"Z"*40},
                        {"policy_version": "qa-v2"}):
            with self.subTest(changes=changes):
                result = simulate(**changes)
                self.assertEqual("POLICY_UNVERIFIED", result["state"])
                self.assertEqual(0, result["hypothetical_referral_candidate_krw"])
                self.assert_safe(result)

    def test_signed_record_mutation_invalidates_signature(self):
        for changes in ({"rate_bps": 9999}, {"cap_krw": 99999},
                        {"expires_at": 999999}, {"approved_by": "someone"}):
            r = simulate(policy_record=record(**changes))
            self.assertEqual("POLICY_UNVERIFIED", r["state"])
            self.assert_safe(r)

    def test_exact_refund_window_boundary(self):
        self.assertEqual("WAIT_REFUND_WINDOW", simulate(as_of=604999)["state"])
        self.assertEqual("SIMULATED_CANDIDATE", simulate(as_of=605000)["state"])

    def test_expiry_and_effective_boundaries(self):
        changes = dict(payment_verified=False, lesson_completed=False,
                       paid_at=None, completed_at=None)
        self.assertEqual("POLICY_NOT_EFFECTIVE",
                         simulate(as_of=99, **changes)["state"])
        self.assertEqual("WAIT_PAYMENT", simulate(as_of=100, **changes)["state"])
        self.assertEqual("POLICY_NOT_EFFECTIVE",
                         simulate(as_of=1000000, **changes)["state"])

    def test_refund_risk_and_ineligible_override_candidate(self):
        for changes, expected in (({"refunded": True}, "REFUND_VOID"),
                                  ({"risk_flags": ["SELF_REFERRAL"]}, "RISK_REVIEW"),
                                  ({"referrer_eligible": False}, "REFERRER_INELIGIBLE")):
            result = simulate(**changes)
            self.assertEqual(expected, result["state"])
            self.assertEqual(0, result["hypothetical_referral_candidate_krw"])
            self.assert_safe(result)

    def test_false_evidence_blocks_even_signed_policy(self):
        for changes, expected in (
            ({"payment_verified": False, "paid_at": None}, "WAIT_PAYMENT"),
            ({"lesson_completed": False, "completed_at": None}, "WAIT_LESSON"),
            ({"attendance_verified": False}, "WAIT_LESSON"),
        ):
            result = simulate(**changes)
            self.assertEqual(expected, result["state"])
            self.assert_safe(result)

    def test_forged_truthy_flags_and_timestamps_rejected(self):
        for changes in ({"payment_verified": 1}, {"lesson_completed": "yes"},
                        {"attendance_verified": 1}, {"refunded": 0},
                        {"referrer_eligible": None}, {"gross_krw": True},
                        {"as_of": True}, {"paid_at": 700001},
                        {"completed_at": 700001}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                simulate(**changes)

    def test_invalid_risk_flags_and_schema_rejected(self):
        for changes in ({"risk_flags": "SELF_REFERRAL"},
                        {"risk_flags": ["lowercase"]},
                        {"risk_flags": ["A"]*101},
                        {"policy_record": record(scope="live")},
                        {"policy_record": record(rate_bps=10001)},
                        {"policy_record": {**record(), "extra": "field"}}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                simulate(**changes)

    def test_signed_fixture_never_authorizes_live_payout(self):
        r = simulate()
        self.assertEqual("SIMULATED_CANDIDATE", r["state"])
        self.assertEqual(3000, r["hypothetical_referral_candidate_krw"])
        self.assertTrue(r["approval_evidence_verified"])
        self.assert_safe(r)

    def test_cap_and_zero_gross_only_change_hypothetical_candidate(self):
        p = record(rate_bps=10000, cap_krw=1)
        result = simulate(policy_record=p, approval_signature=signed(p))
        self.assertEqual(1, result["hypothetical_referral_candidate_krw"])
        self.assert_safe(result)
        result = simulate(gross_krw=0)
        self.assertEqual(0, result["hypothetical_referral_candidate_krw"])
        self.assert_safe(result)


if __name__ == "__main__":
    unittest.main()
