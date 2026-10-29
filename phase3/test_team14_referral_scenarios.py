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
 def test_large_graph_and_cycle_fail_closed(self):
  # Regression for the 10,000-edge contract: unrelated ancestry must not
  # trigger quadratic scans, and cycles remain rejected even off the payout path.
  import time
  edges=[('node'+str(i),'node'+str(i+1)) for i in range(9000)]
  started=time.monotonic()
  result=simulate_referral(10000,edges)
  self.assertLess(time.monotonic()-started,1.0,'referral validation regressed to quadratic scanning')
  self.assertEqual(result['gross'],10000)
  self.assertFalse(result['real_money'])
  self.assertFalse(result['payment_enabled'])
  self.assertFalse(result['policy_approved'])
  with self.assertRaises(SimError) as ctx:
   simulate_referral(10000,edges+[('node9000','node0')])
  self.assertEqual(ctx.exception.code,'CONFLICT')
 def test_rounding_conservation(self):
  x=simulate_referral(1,[],(300,100))
  self.assertEqual(x['gross'],x['teacher']+x['platform']+sum(x['rewards']))
 def test_all_four_introduction_directions_are_distinct_and_mock_only(self):
  from team14_referral_scenarios import simulate_introduction
  seen=set()
  for introducer in ('teacher','student'):
   for introduced in ('teacher','student'):
    with self.subTest(introducer=introducer,introduced=introduced):
     scenario=simulate_introduction(introducer,introduced)
     self.assertEqual(scenario['introducer_role'],introducer)
     self.assertEqual(scenario['introduced_role'],introduced)
     self.assertEqual(scenario['status'],'simulation_only')
     self.assertFalse(scenario['real_money'])
     self.assertFalse(scenario['payment_enabled'])
     self.assertFalse(scenario['policy_approved'])
     seen.add(scenario['scenario_id'])
  self.assertEqual(len(seen),4)
 def test_introduction_roles_fail_closed_for_invalid_inputs(self):
  from team14_referral_scenarios import simulate_introduction
  for invalid in (None,True,0,'admin','partner','Teacher','',[],{}):
   with self.subTest(invalid=invalid):
    with self.assertRaises(SimError) as ctx:
     simulate_introduction(invalid,'student')
    self.assertEqual(ctx.exception.code,'VALIDATION_ERROR')
    with self.assertRaises(SimError):
     simulate_introduction('teacher',invalid)
if __name__=='__main__':unittest.main()
