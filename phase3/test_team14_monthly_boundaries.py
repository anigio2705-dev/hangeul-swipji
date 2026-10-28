"""Additional isolated boundary tests for the actual Team14 simulation."""
import unittest
from team14_monthly_sim import Month, ContractError

class MonthlyBoundaryTests(unittest.TestCase):
    def test_zero_and_maximum(self):
        with self.assertRaises(ContractError): Month((0,))
        m=Month((10**15,))
        m.complete(0,"max")
        self.assertEqual(m.totals()["gross"],10**15)
        self.assertEqual(m.totals()["pending"],0)
        self.assertEqual(m.totals()["teacher"]+m.totals()["referral"]+m.totals()["platform"],10**15)

    def test_currency_mismatch_rejected_by_interface(self):
        m=Month((10000,))
        with self.assertRaises(TypeError): m.refund(0,1000,"r",currency="USD")
        self.assertEqual(m.totals()["gross"],10000)

    def test_invalid_lesson_states_and_indices(self):
        m=Month((5000,5000))
        for index in (-1,2,1.0,True):
            with self.subTest(index=index),self.assertRaises(ContractError):m.complete(index,"bad")
        m.complete(0,"c0")
        with self.assertRaises(ContractError):m.refund(0,5000,"r0")
        m.refund(1,5000,"r1")
        with self.assertRaises(ContractError):m.complete(1,"c1")

    def test_replay_and_key_scope(self):
        m=Month((10000,10000))
        m.complete(0,"x")
        self.assertFalse(m.complete(0,"x"))
        with self.assertRaises(ContractError):m.complete(1,"x")
        m.refund(1,2000,"y")
        self.assertFalse(m.refund(1,2000,"y"))
        with self.assertRaises(ContractError):m.refund(1,3000,"y")
        self.assertEqual(m.totals()["refunded"],2000)

    def test_partial_refund_reversals(self):
        m=Month((10000,10000,10000))
        m.complete(0,"c0")
        m.refund(1,2500,"r1")
        m.refund(1,3500,"r2")
        self.assertEqual([e[2] for e in m.entries if e[1]=="refund_reversal"],[-2500,-3500])
        t=m.totals()
        self.assertEqual((t["gross"],t["teacher"],t["referral"],t["platform"],t["refunded"],t["pending"]),(30000,8000,300,1700,6000,14000))
        self.assertEqual(sum((t["teacher"],t["referral"],t["platform"],t["refunded"],t["pending"])),t["gross"])

    def test_failed_operation_does_not_consume_key(self):
        m=Month((10000,))
        with self.assertRaises(ContractError):m.refund(0,11000,"retry")
        self.assertTrue(m.refund(0,5000,"retry"))
        self.assertFalse(m.refund(0,5000,"retry"))

    def test_rounding_and_double_settlement(self):
        m=Month((1,1,1))
        for i in range(3):m.complete(i,"c"+str(i))
        t=m.totals()
        self.assertEqual((t["teacher"],t["referral"],t["platform"]),(0,0,3))
        with self.assertRaises(ContractError):m.complete(2,"new")
        self.assertEqual(len(m.entries),9)

    def test_month_is_not_persistent_or_cross_month_idempotent(self):
        a,b=Month((1000,)),Month((1000,))
        self.assertTrue(a.complete(0,"same"))
        self.assertTrue(b.complete(0,"same"))
        self.assertEqual(a.totals(),b.totals())

if __name__=="__main__":unittest.main()
