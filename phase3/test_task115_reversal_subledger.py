"""#115 isolated reversal tests; all records and money are simulated."""
import os
import sqlite3
import tempfile
import unittest

from team14_reversal_subledger import SimulatedReversalLedger


def transaction(**overrides):
    p = dict(tx_id="tx1", evidence_id="evt1", gross_krw=1000,
             teacher_krw=700, platform_krw=200, referral_krw=30,
             benefit_krw=70)
    p.update(overrides)
    return p


def reversal(**overrides):
    p = dict(reversal_id="rev1", tx_id="tx1", evidence_id="refund1",
             event_kind="partial_refund", refund_krw=250)
    p.update(overrides)
    return p


class Task115ReversalTests(unittest.TestCase):
    def setUp(self):
        self.ledger = SimulatedReversalLedger()
        self.ledger.record(**transaction())

    def tearDown(self):
        self.ledger.close()

    def test_partial_then_full_conserves_all_four_buckets(self):
        a = self.ledger.reverse(**reversal())
        b = self.ledger.reverse(**reversal(
            reversal_id="rev2", evidence_id="refund2",
            event_kind="full_refund", refund_krw=750))
        self.assertEqual((250, 750), (a["refund_krw"], b["refund_krw"]))
        self.assertEqual(0, b["remaining_krw"])
        combined = {}
        for result in (a, b):
            for entry in result["reversed_entries"]:
                combined[entry["bucket"]] = combined.get(
                    entry["bucket"], 0) + entry["amount_krw"]
        self.assertEqual(dict(teacher=700, platform=200, referral=30,
                              benefit=70), combined)
        self.assertEqual(1000, self.ledger.read("tx1")["gross_krw"])

    def test_cancel_reverses_full_unrefunded_balance(self):
        result = self.ledger.reverse(**reversal(
            event_kind="cancel", refund_krw=1000))
        self.assertEqual(0, result["remaining_krw"])
        self.assertEqual(1000, sum(e["amount_krw"]
                                   for e in result["reversed_entries"]))

    def test_cancel_after_partial_reverses_remainder(self):
        self.ledger.reverse(**reversal())
        result = self.ledger.reverse(**reversal(
            reversal_id="rev2", evidence_id="refund2",
            event_kind="cancel", refund_krw=750))
        self.assertEqual(0, result["remaining_krw"])

    def test_same_reversal_id_replay_is_idempotent(self):
        a = self.ledger.reverse(**reversal())
        b = self.ledger.reverse(**reversal())
        self.assertEqual(a, b)
        self.assertEqual(1, self.ledger.db.execute(
            "SELECT count(*) FROM sim_reversal").fetchone()[0])
        self.assertEqual(4, self.ledger.db.execute(
            "SELECT count(*) FROM sim_reversal_entry").fetchone()[0])

    def test_conflicting_replay_rejected_without_write(self):
        self.ledger.reverse(**reversal())
        with self.assertRaisesRegex(ValueError, "idempotency conflict"):
            self.ledger.reverse(**reversal(refund_krw=251))
        self.assertEqual(250, self.ledger.read_reversal(
            "rev1")["cumulative_refunded_krw"])

    def test_over_refund_rejected(self):
        self.ledger.reverse(**reversal())
        with self.assertRaisesRegex(ValueError, "exceeds"):
            self.ledger.reverse(**reversal(
                reversal_id="rev2", evidence_id="refund2",
                refund_krw=800))
        self.assertEqual(1, self.ledger.db.execute(
            "SELECT count(*) FROM sim_reversal").fetchone()[0])

    def test_partial_must_not_consume_full_balance(self):
        with self.assertRaisesRegex(ValueError, "partial refund"):
            self.ledger.reverse(**reversal(refund_krw=1000))

    def test_full_and_cancel_must_match_remaining(self):
        for kind in ("full_refund", "cancel"):
            with self.subTest(kind=kind), self.assertRaisesRegex(
                    ValueError, "full reversal"):
                self.ledger.reverse(**reversal(
                    event_kind=kind, refund_krw=250))

    def test_invalid_amount_types_and_event_kinds(self):
        for amount in (0, -1, True, "250", 1.25, 10**12 + 1):
            with self.subTest(amount=amount), self.assertRaises(ValueError):
                self.ledger.reverse(**reversal(refund_krw=amount))
        for kind in ("chargeback", "pay", None, 1):
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                self.ledger.reverse(**reversal(event_kind=kind))

    def test_invalid_ids_and_missing_original_rejected(self):
        for field in ("reversal_id", "tx_id", "evidence_id"):
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.ledger.reverse(**reversal(**{field: "../invalid"}))
        with self.assertRaises(KeyError):
            self.ledger.reverse(**reversal(tx_id="missing"))

    def test_original_and_reversal_tables_immutable(self):
        self.ledger.reverse(**reversal())
        for sql in (
            "UPDATE sim_reversal SET refund_krw=1 WHERE reversal_id='rev1'",
            "DELETE FROM sim_reversal WHERE reversal_id='rev1'",
            "UPDATE sim_reversal_entry SET reversed_krw=1 WHERE reversal_id='rev1'",
            "DELETE FROM sim_reversal_entry WHERE reversal_id='rev1'",
        ):
            with self.subTest(sql=sql), self.assertRaises(sqlite3.IntegrityError):
                self.ledger.db.execute(sql)

    def test_atomic_rollback_on_entry_failure(self):
        self.ledger.db.execute("""
CREATE TRIGGER test_reversal_insert_failure BEFORE INSERT ON sim_reversal_entry
WHEN NEW.bucket='benefit'
BEGIN SELECT RAISE(ABORT,'forced reversal insert failure'); END
""")
        with self.assertRaises(sqlite3.IntegrityError):
            self.ledger.reverse(**reversal())
        self.assertEqual(0, self.ledger.db.execute(
            "SELECT count(*) FROM sim_reversal").fetchone()[0])
        self.assertEqual(0, self.ledger.db.execute(
            "SELECT count(*) FROM sim_reversal_entry").fetchone()[0])

    def test_separate_transactions_do_not_cross_reverse(self):
        self.ledger.record(**transaction(
            tx_id="tx2", evidence_id="evt2", gross_krw=100,
            teacher_krw=100, platform_krw=0, referral_krw=0, benefit_krw=0))
        self.ledger.reverse(**reversal())
        second = self.ledger.reverse(**reversal(
            reversal_id="rev2", tx_id="tx2", evidence_id="refund2",
            event_kind="full_refund", refund_krw=100))
        self.assertEqual(0, second["remaining_krw"])
        self.assertEqual(750, self.ledger.read_reversal("rev1")["remaining_krw"])

    def test_reversal_id_cannot_be_reused_across_transactions(self):
        self.ledger.record(**transaction(
            tx_id="tx2", evidence_id="evt2", gross_krw=100,
            teacher_krw=100, platform_krw=0, referral_krw=0, benefit_krw=0))
        self.ledger.reverse(**reversal())
        with self.assertRaisesRegex(ValueError, "idempotency conflict"):
            self.ledger.reverse(**reversal(
                tx_id="tx2", event_kind="full_refund", refund_krw=100))

    def test_rounding_repeated_small_refunds_reaches_exact_full_amount(self):
        self.ledger.record(**transaction(
            tx_id="tiny", evidence_id="tiny_evt", gross_krw=3,
            teacher_krw=1, platform_krw=1, referral_krw=1, benefit_krw=0))
        reversed_buckets = dict(teacher=0, platform=0, referral=0, benefit=0)
        for i in range(3):
            r = self.ledger.reverse(
                reversal_id="tinyrev" + str(i), tx_id="tiny",
                evidence_id="tinyrefund" + str(i),
                event_kind="partial_refund" if i < 2 else "full_refund",
                refund_krw=1)
            for e in r["reversed_entries"]:
                reversed_buckets[e["bucket"]] += e["amount_krw"]
        self.assertEqual(dict(teacher=1, platform=1, referral=1,
                              benefit=0), reversed_buckets)

    def test_independent_qa_counterexample_nonnegative_incremental_buckets(self):
        # B/15: gross 7, [0,1,3,3], refund 3 then 1. Rounding two
        # cumulative targets previously produced a forbidden -1 delta.
        self.ledger.record(**transaction(
            tx_id="qa7", evidence_id="qa_evt", gross_krw=7,
            teacher_krw=0, platform_krw=1, referral_krw=3, benefit_krw=3))
        results = []
        for i, amount in enumerate((3, 1, 3)):
            result = self.ledger.reverse(
                reversal_id="qa_rev" + str(i), tx_id="qa7",
                evidence_id="qa_evidence" + str(i),
                event_kind="partial_refund" if i < 2 else "full_refund",
                refund_krw=amount)
            results.append(result)
            self.assertTrue(all(e["amount_krw"] >= 0
                                for e in result["reversed_entries"]))
            self.assertEqual(amount, sum(e["amount_krw"]
                                         for e in result["reversed_entries"]))
        total = dict(teacher=0, platform=0, referral=0, benefit=0)
        for result in results:
            for e in result["reversed_entries"]:
                total[e["bucket"]] += e["amount_krw"]
        self.assertEqual(dict(teacher=0, platform=1, referral=3, benefit=3),
                         total)
        self.assertEqual(0, results[-1]["remaining_krw"])

    def test_simulation_never_authorizes_money(self):
        r = self.ledger.reverse(**reversal())
        for key in ("real_money", "policy_approved", "payment_enabled",
                    "refund_executed", "payout_authorized",
                    "operating_db_connected"):
            self.assertIs(r[key], False)

    def test_file_persistence_only_in_isolated_test_db(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "isolated.sqlite")
            a = SimulatedReversalLedger(path)
            try:
                a.record(**transaction(tx_id="persistent"))
                a.reverse(**reversal(
                    reversal_id="persistrev", tx_id="persistent"))
            finally:
                a.close()
            b = SimulatedReversalLedger(path)
            try:
                self.assertEqual(750, b.read_reversal("persistrev")[
                    "remaining_krw"])
                self.assertEqual(1000, b.read("persistent")["gross_krw"])
            finally:
                b.close()


if __name__ == "__main__":
    unittest.main()
