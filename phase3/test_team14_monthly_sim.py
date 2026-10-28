"""Run: python -m unittest discover -s phase3 -p 'test_team14_monthly_sim.py' -v"""
import unittest
from team14_monthly_sim import Month, ContractError

class MonthlySimulationTests(unittest.TestCase):
    def test_partial_month_conservation(self):
        m = Month((20000, 20000, 20000, 20000))
        self.assertTrue(m.complete(0, "c0"))
        self.assertTrue(m.complete(1, "c1"))
        self.assertTrue(m.refund(2, 8000, "r2a"))
        self.assertTrue(m.refund(2, 12000, "r2b"))
        self.assertTrue(m.refund(3, 20000, "r3"))
        self.assertEqual(m.totals(), dict(gross=80000, teacher=32000, referral=1200, platform=6800, refunded=40000, pending=0, real_money=False, rates_approved=False))

    def test_duplicate_settlement_and_replay(self):
        m=Month((10001,))
        self.assertTrue(m.complete(0, "complete"))
        before=list(m.entries)
        self.assertFalse(m.complete(0, "complete"))
        self.assertEqual(before,m.entries)
        with self.assertRaises(ContractError): m.complete(0,"another")
        self.assertEqual(sum(e[2] for e in m.entries),10001)

    def test_duplicate_refund_and_over_refund(self):
        m=Month((10000,))
        self.assertTrue(m.refund(0,4000,"refund1"))
        self.assertFalse(m.refund(0,4000,"refund1"))
        with self.assertRaises(ContractError):m.refund(0,7000,"refund2")
        with self.assertRaises(ContractError):m.refund(0,5000,"refund1")
        self.assertEqual(m.totals()["refunded"],4000)
        self.assertEqual(len(m.entries),1)

    def test_refund_blocks_settlement(self):
        m=Month((10000,))
        m.refund(0,1000,"refund")
        with self.assertRaises(ContractError):m.complete(0,"complete")
        self.assertEqual(m.totals()["pending"],9000)

    def test_completed_refund_requires_dispute(self):
        m=Month((10000,))
        m.complete(0,"complete")
        with self.assertRaises(ContractError):m.refund(0,1000,"refund")
        self.assertEqual(m.totals()["refunded"],0)

    def test_validation_and_immutable_snapshot(self):
        for prices in ((),(0,),(-1,),(True,),("100",)):
            with self.subTest(prices=prices),self.assertRaises(ContractError):Month(prices)
        with self.assertRaises(ContractError):Month((100,),commission_bps=9800,referral_bps=300)
        m=Month((100,))
        with self.assertRaises(ContractError):m.refund(0,True,"bad")
        with self.assertRaises(ContractError):m.complete(3,"bad")
        with self.assertRaises(ContractError):m.complete(0,"")
        self.assertEqual(m.totals()["gross"],100)

if __name__=="__main__": unittest.main()
