import os,tempfile,unittest
from team14_persistent import SimError
from team14_referral_store import ReferralStore
class ReferralStoreTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.path=os.path.join(self.tmp.name,'referrals.sqlite')
  self.s=ReferralStore(self.path)
 def tearDown(self):self.s.close();self.tmp.cleanup()
 def test_link_and_replay(self):
  self.assertTrue(self.s.link('student','alice'))
  self.assertFalse(self.s.link('student','alice'))
 def test_conflicting_parent(self):
  self.s.link('student','alice')
  with self.assertRaises(SimError):self.s.link('student','bob')
 def test_cycle(self):
  self.s.link('a','b');self.s.link('b','c')
  with self.assertRaises(SimError):self.s.link('c','a')
 def test_self_link(self):
  with self.assertRaises(SimError):self.s.link('a','a')
 def test_reward_uses_real_links(self):
  self.s.link('student','alice')
  result=self.s.award('event1','student','lesson1',10000)
  self.assertEqual(result['recipients'],[dict(user_id='alice',amount_krw=300)])
 def test_no_ancestor_no_reward(self):
  self.assertEqual(self.s.award('event1','student','lesson1',10000)['recipients'],[])
 def test_idempotent_event(self):
  self.s.link('student','alice')
  first=self.s.award('event1','student','lesson1',10000)
  self.assertEqual(first,self.s.award('event1','student','lesson1',10000))
  self.assertEqual(self.s.db.execute('SELECT COUNT(*) FROM referral_awards').fetchone()[0],1)
 def test_changed_event_rejected(self):
  self.s.award('event1','student','lesson1',10000)
  with self.assertRaises(SimError):self.s.award('event1','student','lesson1',9000)
 def test_new_event_same_lesson_rejected(self):
  self.s.award('event1','student','lesson1',10000)
  with self.assertRaises(SimError):self.s.award('event2','student','lesson1',10000)
 def test_restart_recovers_relationships_and_awards(self):
  self.s.link('student','alice');expected=self.s.award('event1','student','lesson1',10000)
  self.s.close();self.s=ReferralStore(self.path)
  self.assertEqual(expected,self.s.awards_for_lesson('lesson1'))
  self.assertEqual(expected,self.s.award('event1','student','lesson1',10000))
 def test_invalid_amount(self):
  with self.assertRaises(SimError):self.s.award('event1','student','lesson1',True)
 def test_invalid_policy_does_not_create_award(self):
  for rates in (None,'300',range(11),[100]*11):
   with self.subTest(rates=rates),self.assertRaises(SimError):
    self.s.award('bad-event','student','lesson1',10000,rates)
  self.assertEqual(self.s.db.execute('SELECT COUNT(*) FROM referral_awards').fetchone()[0],0)
  self.assertEqual(self.s.award('good-event','student','lesson1',10000)['gross_krw'],10000)
 def test_corrupt_award_read_and_idempotent_replay_fail_closed(self):
  import json
  self.s.link('student','alice')
  good=self.s.award('event1','student','lesson1',10000)
  tampered=[
   'not-json',
   '{}',
   json.dumps({**good,'teacher_krw':good['teacher_krw']+1}),
   json.dumps({**good,'real_money':True}),
   json.dumps({**good,'recipients':[{'user_id':'student','amount_krw':300}]}),
   json.dumps({**good,'recipients':[{'user_id':'alice','amount_krw':300},
                                    {'user_id':'alice','amount_krw':0}]}),
  ]
  for payload in tampered:
   with self.subTest(payload=payload):
    self.s.db.execute('UPDATE referral_awards SET result=? WHERE event_id=?',(payload,'event1'))
    with self.assertRaises(SimError) as error:self.s.awards_for_lesson('lesson1')
    self.assertEqual('CONFLICT',error.exception.code)
    with self.assertRaises(SimError) as error:self.s.award('event1','student','lesson1',10000)
    self.assertEqual('CONFLICT',error.exception.code)
  self.s.db.execute('UPDATE referral_awards SET result=? WHERE event_id=?',(json.dumps(good),'event1'))
  self.assertEqual(good,self.s.award('event1','student','lesson1',10000))
 def test_tampered_recipient_or_policy_is_rejected(self):
  import json
  self.s.link('student','alice');self.s.link('alice','bob')
  good=self.s.award('event1','student','lesson1',10000,(300,100))
  invalid=[
   {**good,'recipients':[{'user_id':'alice','amount_krw':250},{'user_id':'bob','amount_krw':100}],'platform_krw':good['platform_krw']+50},
   {**good,'recipients':[{'user_id':'mallory','amount_krw':300},{'user_id':'bob','amount_krw':100}]},
   {**good,'teacher_krw':good['teacher_krw']+100,'platform_krw':good['platform_krw']-100},
  ]
  for item in invalid:
   with self.subTest(item=item):
    self.s.db.execute('UPDATE referral_awards SET result=? WHERE event_id=?',(json.dumps(item),'event1'))
    with self.assertRaises(SimError) as ctx:self.s.awards_for_lesson('lesson1')
    self.assertEqual(ctx.exception.code,'CONFLICT')
    with self.assertRaises(SimError):self.s.award('event1','student','lesson1',10000,(300,100))
  self.s.db.execute('UPDATE referral_awards SET result=? WHERE event_id=?',(json.dumps(good),'event1'))
  self.s.db.execute('UPDATE referral_awards SET signature=? WHERE event_id=?',(json.dumps(['student','wrong',10000,[300,100],2000]),'event1'))
  with self.assertRaises(SimError):self.s.awards_for_lesson('lesson1')
  self.s.db.execute('UPDATE referral_awards SET signature=? WHERE event_id=?',(json.dumps(['student','lesson1',10000,[300,100],2000],separators=(',',':')),'event1'))
  self.assertEqual(good,self.s.awards_for_lesson('lesson1'))
 def test_new_ancestor_does_not_retroactively_change_previous_award(self):
  self.s.link('student','alice')
  good=self.s.award('event1','student','lesson1',10000,(300,100))
  self.s.link('alice','bob')
  self.assertEqual(good,self.s.award('event1','student','lesson1',10000,(300,100)))
 def test_second_lesson_is_distinct(self):
  self.s.link('student','alice')
  self.s.award('event1','student','lesson1',10000)
  self.s.award('event2','student','lesson2',10000)
  self.assertEqual(self.s.db.execute('SELECT COUNT(*) FROM referral_awards').fetchone()[0],2)
 def test_four_role_label_pairs_are_simulation_only(self):
  """Four identity-label pairings must remain mock-only, not role authorization.

  ReferralStore accepts trusted IDs, not authenticated user roles. This test
  deliberately does NOT approve any teacher/learner eligibility policy.
  """
  cases=(('learner_a','learner_b'),('learner_c','teacher_a'),
         ('teacher_b','learner_d'),('teacher_c','teacher_d'))
  for index,(child,parent) in enumerate(cases):
   with self.subTest(pair=(child,parent)):
    event='role_event_'+str(index);lesson='role_lesson_'+str(index)
    self.assertTrue(self.s.link(child,parent))
    result=self.s.award(event,child,lesson,10000)
    self.assertEqual(result['recipients'],[{'user_id':parent,'amount_krw':300}])
    self.assertEqual(result['teacher_krw']+result['platform_krw']+
                     sum(x['amount_krw'] for x in result['recipients']),10000)
    self.assertIs(result['real_money'],False)
    self.assertIs(result['policy_approved'],False)
    self.assertIs(result['payment_enabled'],False)
    self.assertEqual(self.s.awards_for_lesson(lesson),result)
    self.assertEqual(self.s.award(event,child,lesson,10000),result)
  self.assertEqual(self.s.db.execute('SELECT COUNT(*) FROM referral_awards').fetchone()[0],4)
if __name__=='__main__':unittest.main()
