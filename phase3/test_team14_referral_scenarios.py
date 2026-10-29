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
 def test_mock_review_all_four_roles_both_outcomes_without_authorization(self):
  from team14_referral_scenarios import simulate_introduction_review
  seen=set()
  for from_role in ('teacher','student'):
   for to_role in ('teacher','student'):
    for decision in ('accept','reject'):
     with self.subTest(from_role=from_role,to_role=to_role,decision=decision):
      result=simulate_introduction_review('user_a',from_role,'user_b',to_role,decision)
      self.assertEqual(result['review_decision'],decision)
      self.assertEqual(result['scenario_id'],from_role+'_introduces_'+to_role)
      self.assertEqual(result['status'],'simulation_only')
      self.assertEqual(result['review_mode'],'mock_only')
      for flag in ('identity_verified','role_verified','authorization_granted',
                   'reward_eligible','real_money','payment_enabled','policy_approved'):
       self.assertIs(result[flag],False)
      seen.add((result['scenario_id'],decision))
  self.assertEqual(len(seen),8)
 def test_mock_review_rejects_self_spoofed_ids_and_unapproved_decisions(self):
  from team14_referral_scenarios import simulate_introduction_review
  for bad_id in (None,True,0,'', 'bad space', [], {},'a'*129):
   with self.subTest(bad_id=bad_id),self.assertRaises(SimError):
    simulate_introduction_review(bad_id,'teacher','user_b','student','accept')
   with self.subTest(bad_id=bad_id),self.assertRaises(SimError):
    simulate_introduction_review('user_a','teacher',bad_id,'student','reject')
  with self.assertRaises(SimError) as ctx:
   simulate_introduction_review('same','teacher','same','student','accept')
  self.assertEqual(ctx.exception.code,'CONFLICT')
  for bad_decision in ('approve','accepted','paid','',None,True,0,[],{}):
   with self.subTest(decision=bad_decision),self.assertRaises(SimError) as ctx:
    simulate_introduction_review('user_a','teacher','user_b','student',bad_decision)
   self.assertEqual(ctx.exception.code,'VALIDATION_ERROR')
  for bad_role in ('admin','partner','Teacher',None,True):
   with self.subTest(role=bad_role),self.assertRaises(SimError):
    simulate_introduction_review('user_a',bad_role,'user_b','student','accept')
   with self.subTest(role=bad_role),self.assertRaises(SimError):
    simulate_introduction_review('user_a','teacher','user_b',bad_role,'reject')
 def test_mock_review_detects_duplicate_and_cycles_without_writing(self):
  from team14_referral_scenarios import simulate_introduction_review
  def review(edges):
   return simulate_introduction_review('alice','teacher','bob','student',
                                       'accept',existing_edges=edges)
  with self.assertRaises(SimError) as ctx:
   review([('alice','bob')])
  self.assertEqual(ctx.exception.code,'CONFLICT')
  for edges in ([('bob','alice')], [('bob','carol'),('carol','alice')],
                [('x','y'),('y','x')], [('x','z'),('y','z')],
                [('charlie','bob')]):
   with self.subTest(edges=edges),self.assertRaises(SimError) as ctx:
    review(edges)
   self.assertEqual(ctx.exception.code,'CONFLICT')
  result=review([('bob','carol'),('x','y')])
  self.assertEqual(result['review_decision'],'accept')
  self.assertFalse(result['authorization_granted'])
  self.assertFalse(result['reward_eligible'])
  self.assertFalse(result['payment_enabled'])
  self.assertFalse(result['identity_verified'])
 def test_one_introducer_can_refer_multiple_people_but_introduced_person_is_unique(self):
  from team14_referral_scenarios import simulate_introduction_review
  # One legitimate introducer may introduce many distinct people.
  # Each introduced person can have only one direct introducer.
  accepted=simulate_introduction_review(
   'alice','teacher','bob','student','accept',
   existing_edges=[('alice','carol'),('alice','dave'),('x','y')])
  self.assertEqual(accepted['review_decision'],'accept')
  self.assertFalse(accepted['authorization_granted'])
  self.assertFalse(accepted['reward_eligible'])
  self.assertFalse(accepted['payment_enabled'])
  for edges in ([('charlie','bob')], [('alice','bob')]):
   with self.subTest(edges=edges), self.assertRaises(SimError) as ctx:
    simulate_introduction_review('alice','teacher','bob','student','accept',
                                  existing_edges=edges)
   self.assertEqual(ctx.exception.code,'CONFLICT')
  # An unrelated existing graph with multiple children per introducer is valid.
  accepted=simulate_introduction_review(
   'alice','student','bob','teacher','accept',
   existing_edges=[('x','y'),('x','z')])
  self.assertEqual(accepted['scenario_id'],'student_introduces_teacher')
  self.assertFalse(accepted['policy_approved'])
 def test_mock_review_rejects_malformed_existing_edges(self):
  from team14_referral_scenarios import simulate_introduction_review
  def review(edges):
   return simulate_introduction_review('alice','teacher','bob','student',
                                       'reject',existing_edges=edges)
  for bad in (None, 'abc', {}, [('a',)], [('a','b','c')],
              [[None,'b']], [('a',True)], [('x','x')],
              [('x','y')]*2, [('a','b')]*10001):
   with self.subTest(bad=str(bad)[:50]),self.assertRaises(SimError):
    review(bad)
  result=review([])
  self.assertEqual(result['review_mode'],'mock_only')
  self.assertFalse(result['policy_approved'])
 def test_mock_rejection_never_adds_proposed_edge(self):
  from team14_referral_scenarios import simulate_introduction_review
  # A declined introduction must not be added to the existing graph:
  # it can be declined even when acceptance would form a cycle or duplicate.
  for edges in ([('bob','alice')], [('alice','carol')], [('alice','bob')]):
   with self.subTest(edges=edges):
    result=simulate_introduction_review('alice','teacher','bob','student',
                                         'reject',existing_edges=edges)
    self.assertEqual(result['review_decision'],'reject')
    self.assertEqual(result['review_mode'],'mock_only')
    for flag in ('identity_verified','authorization_granted',
                 'reward_eligible','payment_enabled','policy_approved'):
     self.assertIs(result[flag],False)
if __name__=='__main__':unittest.main()
