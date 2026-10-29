"""D1 regression for explicit 75/25 simulated products; no real PG."""
import os
import sqlite3
import tempfile
import unittest
from team14_persistent import MonthlyStore, SimError
from team14_initial_products import (validate_product,create_simulated_package,
                                     expected_split,verify_server_product_contract)

class InitialProductTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=os.path.join(self.tmp.name,'settlements.db')
        self.store=MonthlyStore(self.path)
    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()
    def test_15_minute_75_25_and_referral_inside_platform(self):
        result=create_simulated_package(self.store,'m15',['b15'],15,10000,300)
        self.assertFalse(result['product']['prices_approved'])
        self.store.event('m15','lesson_b15','b15','tx15','evt15','complete')
        t=self.store.totals('m15')
        self.assertEqual((t['teacher'],t['referral'],t['platform']), (7500,300,2200))
        self.assertEqual(t['teacher']+t['referral']+t['platform'],10000)
        self.assertFalse(t['real_money'])
        self.assertFalse(t['rates_approved'])
    def test_four_25_minute_sessions_settle_only_when_completed(self):
        bookings=['b1','b2','b3','b4']
        p=create_simulated_package(self.store,'m25',bookings,25,12000)
        self.assertEqual(p['product']['total_price_krw'],48000)
        self.store.event('m25','lesson_b1','b1','tx1','ev1','complete')
        t=self.store.totals('m25')
        self.assertEqual((t['teacher'],t['platform'],t['pending']), (9000,3000,36000))
        self.store.event('m25','lesson_b1','b1','refund1','refund1','refund_completed',6000)
        self.assertEqual(self.store.totals('m25')['refunded'],6000)
        self.store.close()
        self.store=MonthlyStore(self.path)
        self.assertEqual(self.store.totals('m25')['refunded'],6000)
        self.store.event('m25','lesson_b1','b1','refund1','refund1','refund_completed',6000)
        self.assertEqual(self.store.totals('m25')['refunded'],6000)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM ledger WHERE kind='teacher_accrual'").fetchone()[0],1)
    def test_invalid_duration_package_and_prices_rejected(self):
        for args in [(10,1,10000,0),(15,2,10000,0),(15,1,0,0),
                     (25,4,10000,2501),(25,1,True,0)]:
            with self.subTest(args=args),self.assertRaises(SimError):
                validate_product(*args)
        with self.assertRaises(SimError):
            create_simulated_package(self.store,'mdup',['b','b','c','d'],25,10000)
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM months').fetchone()[0],0)
    def test_server_product_contract_rejects_unverified_and_wrong_role(self):
        db=sqlite3.connect(':memory:')
        db.row_factory=sqlite3.Row
        db.executescript("""
          CREATE TABLE users(id TEXT PRIMARY KEY,role TEXT,approved INTEGER);
          CREATE TABLE bookings(id TEXT PRIMARY KEY,teacher_id TEXT,price INTEGER);
          CREATE TABLE booking_product_snapshots(
            booking_id TEXT PRIMARY KEY,product_code TEXT,
            duration_minutes INTEGER,price_krw INTEGER,currency TEXT);
          INSERT INTO users VALUES('t','partner',1);
          INSERT INTO bookings VALUES('b','t',10000);
          INSERT INTO booking_product_snapshots VALUES('b','partner_25',25,10000,'KRW');
        """)
        verified=dict(verifiedByServer=True,type='lesson.completed',status='completed',
                      bookingId='b',amount=10000,productCode='partner_25',
                      durationMinutes=25,priceKrw=10000,currency='KRW')
        self.assertEqual('partner_25',verify_server_product_contract(db,'b',verified)['product_code'])
        for event in ('forged-event', dict(verified,verifiedByServer=False),
                      dict(verified,type='lesson.started'),
                      dict(verified,status='cancelled'),
                      dict(verified,amount=20000),
                      dict(verified,productCode='professional_25'),
                      dict(verified,durationMinutes=15),
                      dict(verified,priceKrw=6000),
                      dict(verified,currency='USD')):
            with self.subTest(event=event),self.assertRaises(SimError):
                verify_server_product_contract(db,'b',event)
        db.execute("UPDATE booking_product_snapshots SET product_code='professional_25',price_krw=15000 WHERE booking_id='b'")
        db.execute("UPDATE bookings SET price=15000 WHERE id='b'")
        with self.assertRaises(SimError):
            verify_server_product_contract(db,'b',dict(verified,amount=15000))
        db.close()

    def test_integer_split_conservation(self):
        for total in (1,3,101,10000,99999):
            for bps in (0,300,2500):
                x=expected_split(total,bps)
                self.assertEqual(x['gross'],x['teacher']+x['platform']+x['referral'])
                self.assertEqual(x['platform_including_referral'],x['gross']-x['teacher'])
                self.assertFalse(x['payout_eligible'])

if __name__=='__main__':unittest.main()
