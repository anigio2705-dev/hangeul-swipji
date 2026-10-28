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
 def test_second_lesson_is_distinct(self):
  self.s.link('student','alice')
  self.s.award('event1','student','lesson1',10000)
  self.s.award('event2','student','lesson2',10000)
  self.assertEqual(self.s.db.execute('SELECT COUNT(*) FROM referral_awards').fetchone()[0],2)
if __name__=='__main__':unittest.main()
