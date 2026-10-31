"""#114 isolated ledger regressions: no production DB, payouts or refunds."""
import os
import sqlite3
import tempfile
import unittest

from team14_transaction_subledger import SimulatedTransactionLedger, BUCKETS


def payload(**changes):
    value = dict(tx_id="tx_001", evidence_id="verified_evt_001",
                 gross_krw=1000, teacher_krw=700, platform_krw=200,
                 referral_krw=30, benefit_krw=70)
    value.update(changes)
    return value


class Task114SubledgerTests(unittest.TestCase):
    def setUp(self):
        self.store = SimulatedTransactionLedger()

    def tearDown(self):
        self.store.close()

    def test_four_separate_ledger_buckets_conserve_gross(self):
        result = self.store.record(**payload())
        entries = result["separate_ledger_entries"]
        self.assertEqual(list(BUCKETS), [e["bucket"] for e in entries])
        self.assertEqual(1000, sum(e["amount_krw"] for e in entries))
        self.assertEqual([700, 200, 30, 70],
                         [e["amount_krw"] for e in entries])

    def test_no_live_money_or_policy_activation(self):
        result = self.store.record(**payload())
        for key in ("real_money", "policy_approved", "payment_enabled",
                    "payout_authorized", "operating_db_connected"):
            self.assertIs(result[key], False)

    def test_same_transaction_exact_replay_is_idempotent(self):
        a = self.store.record(**payload())
        b = self.store.record(**payload())
        self.assertEqual(a, b)
        self.assertEqual(4, self.store.db.execute(
            "SELECT count(*) FROM sim_entry").fetchone()[0])

    def test_replayed_transaction_with_new_allocation_rejected(self):
        self.store.record(**payload())
        with self.assertRaisesRegex(ValueError, "idempotency conflict"):
            self.store.record(**payload(teacher_krw=690, platform_krw=210))
        self.assertEqual(1000, self.store.read("tx_001")["gross_krw"])

    def test_separate_transactions_do_not_mix_entries(self):
        self.store.record(**payload())
        self.store.record(**payload(tx_id="tx_002", evidence_id="evt_002",
                                    gross_krw=100, teacher_krw=100,
                                    platform_krw=0, referral_krw=0,
                                    benefit_krw=0))
        self.assertEqual(8, self.store.db.execute(
            "SELECT count(*) FROM sim_entry").fetchone()[0])
        self.assertEqual(100, self.store.read("tx_002")["gross_krw"])

    def test_nonconserving_allocation_rejected_before_write(self):
        with self.assertRaises(ValueError):
            self.store.record(**payload(benefit_krw=71))
        self.assertEqual(0, self.store.db.execute(
            "SELECT count(*) FROM sim_tx").fetchone()[0])

    def test_invalid_money_types_and_limits(self):
        for bad in (True, -1, 1.5, "100", 10**12 + 1):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.store.record(**payload(teacher_krw=bad))
        with self.assertRaises(ValueError):
            self.store.record(**payload(gross_krw=0, teacher_krw=0,
                                        platform_krw=0, referral_krw=0,
                                        benefit_krw=0))

    def test_invalid_ids_and_injection_rejected(self):
        for tx in ("", "../tx", "x'; DROP TABLE sim_tx;--", "a" * 129, None):
            with self.subTest(tx=tx), self.assertRaises(ValueError):
                self.store.record(**payload(tx_id=tx))
        with self.assertRaises(ValueError):
            self.store.record(**payload(evidence_id="unverified/evt"))

    def test_immutable_header_and_entries(self):
        self.store.record(**payload())
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.db.execute(
                "UPDATE sim_entry SET amount_krw=1 WHERE tx_id='tx_001'")
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.db.execute("DELETE FROM sim_tx WHERE tx_id='tx_001'")
        self.assertEqual(1000, self.store.read("tx_001")["gross_krw"])

    def test_atomic_rollback_on_entry_failure(self):
        self.store.db.execute("""
            CREATE TRIGGER test_reject_benefit BEFORE INSERT ON sim_entry
            WHEN NEW.bucket='benefit'
            BEGIN SELECT RAISE(ABORT,'test failure'); END
        """)
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.record(**payload())
        self.assertEqual(0, self.store.db.execute(
            "SELECT count(*) FROM sim_tx").fetchone()[0])
        self.assertEqual(0, self.store.db.execute(
            "SELECT count(*) FROM sim_entry").fetchone()[0])

    def test_test_isolated_file_persists_without_production_integration(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "simulated_only.sqlite")
            first = SimulatedTransactionLedger(path)
            try:
                first.record(**payload())
            finally:
                first.close()
            second = SimulatedTransactionLedger(path)
            try:
                self.assertEqual(1000, second.read("tx_001")["gross_krw"])
                self.assertEqual(4, len(second.read("tx_001")[
                    "separate_ledger_entries"]))
            finally:
                second.close()

    def test_missing_transaction_fails_closed(self):
        with self.assertRaises(KeyError):
            self.store.read("not_found")


if __name__ == "__main__":
    unittest.main()
