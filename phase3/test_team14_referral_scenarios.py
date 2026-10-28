import unittest
from team14_referral_scenarios import simulate_referral
from team14_persistent import SimError
class ReferralScenariosTests(unittest.TestCase):
 def test_single_depth(self):
  x=simulate_referral(10000,[('student','teacher')])
  self.assertEqual(x['rewards'],[300]);self.assertEqual(x['teacher'],7700);self.assertEqual(x['platform'],2000)
  self.assertFalse(x['payment_enabled'])
 def test_two_depth(self):
  x=simulate_referral(10000,[('student','teacher'),('teacher','partner')],(300,100))
  self.assertEqual(x['rewards'],[300,100])
  self.assertEqual(sum(x['rewards'])+x['teacher']+x['platform'],10000)
 def test_self_referral(self):
  with self.assertRaises(SimError):simulate_referral(10000,[('a','a')])
 def test_cycle(self):
  with self.assertRaises(SimError):simulate_referral(10000,[('a','b'),('b','a')])
 def test_duplicate_edge(self):
  with self.assertRaises(SimError):simulate_referral(10000,[('a','b'),('a','c')])
 def test_excess_budget(self):
  with self.assertRaises(SimError):simulate_referral(10000,[],(9000,3000))
 def test_zero_and_overflow(self):
  for n in (0,-1,10**15+1,True):
   with self.assertRaises(SimError):simulate_referral(n,[])
 def test_malformed_graph_rejected_without_unhandled_exception(self):
  for edges in (None,'ab',[('a',)],[('a','b','c')],[123],[[None,'a']]):
   with self.subTest(edges=edges),self.assertRaises(SimError):
    simulate_referral(10000,edges)
  with self.assertRaises(SimError):simulate_referral(10000,[('a','b')]*10001)
 def test_rounding_conservation(self):
  x=simulate_referral(1,[],(300,100))
  self.assertEqual(x['gross'],x['teacher']+x['platform']+sum(x['rewards']))
if __name__=='__main__':unittest.main()
