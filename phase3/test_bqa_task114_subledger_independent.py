"""Independent B/15 adversarial tests for #114 exact product SHA."""
import sqlite3
import unittest
from team14_transaction_subledger import SimulatedTransactionLedger, BUCKETS, MAX_KRW

def entry(**changes):
    args=dict(tx_id="qa_tx",evidence_id="qa_evt",gross_krw=101,
              teacher_krw=67,platform_krw=22,referral_krw=5,benefit_krw=7)
    args.update(changes)
    return args

class BQA114Subledger(unittest.TestCase):
    def setUp(self):
        self.store=SimulatedTransactionLedger()
    def tearDown(self):
        self.store.close()
    def test_bucket_order_and_conservation_with_unequal_krw(self):
        r=self.store.record(**entry())
        self.assertEqual(list(BUCKETS),[e["bucket"] for e in r["separate_ledger_entries"]])
        self.assertEqual(101,sum(e["amount_krw"] for e in r["separate_ledger_entries"]))
    def test_zero_value_buckets_still_present(self):
        r=self.store.record(**entry(gross_krw=1,teacher_krw=1,platform_krw=0,
                                    referral_krw=0,benefit_krw=0))
        self.assertEqual([1,0,0,0],[e["amount_krw"] for e in r["separate_ledger_entries"]])
    def test_max_bound_and_overflow_fail_closed(self):
        r=self.store.record(**entry(gross_krw=MAX_KRW,teacher_krw=MAX_KRW,
                                    platform_krw=0,referral_krw=0,benefit_krw=0))
        self.assertEqual(MAX_KRW,r["gross_krw"])
        with self.assertRaises(ValueError):
            self.store.record(**entry(tx_id="too_large",gross_krw=MAX_KRW+1))
    def test_evidence_swap_same_transaction_is_conflict(self):
        self.store.record(**entry())
        with self.assertRaisesRegex(ValueError,"idempotency conflict"):
            self.store.record(**entry(evidence_id="another_event"))
        self.assertEqual("qa_evt",self.store.read("qa_tx")["evidence_id"])
    def test_invalid_types_do_not_write(self):
        for bad in (True,False,None,1.2,"1",-1):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                self.store.record(**entry(tx_id="bad",benefit_krw=bad))
        self.assertEqual(0,self.store.db.execute("SELECT count(*) FROM sim_tx").fetchone()[0])
    def test_invalid_id_and_sql_injection_fail_closed(self):
        for bad in ("../bad","x';DROP TABLE sim_tx;--","",None,"a"*129):
            with self.subTest(bad=repr(bad)),self.assertRaises(ValueError):
                self.store.record(**entry(tx_id=bad))
        self.assertEqual(0,self.store.db.execute("SELECT count(*) FROM sim_tx").fetchone()[0])
    def test_atomic_rollback_even_after_partial_entries(self):
        self.store.db.execute("""CREATE TRIGGER qa_fail_platform BEFORE INSERT ON sim_entry
             WHEN NEW.bucket='platform' BEGIN SELECT RAISE(ABORT,'qa forced rollback'); END""")
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.record(**entry())
        self.assertEqual(0,self.store.db.execute("SELECT count(*) FROM sim_tx").fetchone()[0])
        self.assertEqual(0,self.store.db.execute("SELECT count(*) FROM sim_entry").fetchone()[0])
    def test_original_records_are_immutable(self):
        self.store.record(**entry())
        for sql in ("UPDATE sim_tx SET evidence_id='evil'",
                    "DELETE FROM sim_tx",
                    "UPDATE sim_entry SET amount_krw=0",
                    "DELETE FROM sim_entry"):
            with self.subTest(sql=sql),self.assertRaises(sqlite3.IntegrityError):
                self.store.db.execute(sql)
        self.assertEqual(101,self.store.read("qa_tx")["gross_krw"])
    def test_cross_transaction_replay_does_not_mix_balances(self):
        self.store.record(**entry())
        self.store.record(**entry(tx_id="qa_tx2",evidence_id="qa_evt2",
                                  gross_krw=1,teacher_krw=0,platform_krw=1,
                                  referral_krw=0,benefit_krw=0))
        self.assertEqual(101,self.store.read("qa_tx")["gross_krw"])
        self.assertEqual(1,self.store.read("qa_tx2")["gross_krw"])
        self.assertEqual(8,self.store.db.execute("SELECT count(*) FROM sim_entry").fetchone()[0])
    def test_no_money_or_operating_db_authorization(self):
        r=self.store.record(**entry())
        for flag in ("real_money","policy_approved","payment_enabled",
                     "payout_authorized","operating_db_connected"):
            self.assertIs(r[flag],False)
    def test_missing_transaction_fails_closed(self):
        with self.assertRaises(KeyError):
            self.store.read("missing")
    def test_replay_does_not_duplicate_rows(self):
        for _ in range(4):
            self.store.record(**entry())
        self.assertEqual(1,self.store.db.execute("SELECT count(*) FROM sim_tx").fetchone()[0])
        self.assertEqual(4,self.store.db.execute("SELECT count(*) FROM sim_entry").fetchone()[0])

if __name__ == "__main__":
    unittest.main()
