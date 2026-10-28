"""Bounded referral graph validation; simulated money only."""
import unittest
from team14_persistent import SimError
from team14_referral_eligibility import eligible_referral
class ReferralEligibilityTests(unittest.TestCase):
    def test_rewards_conserve_gross(self):
        x=eligible_referral(10000,'student',[('student','p1'),('p1','p2')],(300,100))
        self.assertEqual([300,100],[a['amount_krw'] for a in x['recipients']])
        self.assertEqual(10000,x['teacher_krw']+x['platform_krw']+sum(a['amount_krw'] for a in x['recipients']))
        self.assertFalse(x['payment_enabled'])
    def test_invalid_and_oversized_graph(self):
        for edges in (None,'bad',[('a',)],[('a','a')],[('a','b'),('a','c')]):
            with self.subTest(edges=edges),self.assertRaises(SimError):eligible_referral(10000,'a',edges)
        with self.assertRaises(SimError) as e:
            eligible_referral(10000,'u0',[('u'+str(i),'u'+str(i+1)) for i in range(10001)])
        self.assertEqual('VALIDATION_ERROR',e.exception.code)
    def test_10000_edges_and_cycle(self):
        edges=[('u'+str(i),'u'+str(i+1)) for i in range(10000)]
        x=eligible_referral(10000,'u0',edges)
        self.assertEqual('u1',x['recipients'][0]['user_id'])
        edges[-1]=('u9999','u0')
        with self.assertRaises(SimError) as e:eligible_referral(10000,'u0',edges)
        self.assertEqual('CONFLICT',e.exception.code)
if __name__=='__main__':unittest.main()
