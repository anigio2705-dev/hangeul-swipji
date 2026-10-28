"""Actual HTTP instant matching -> verified Team13 SQLite -> Team14 ledger integration."""
import os
import sqlite3
import tempfile
import unittest
from team14_persistent import MonthlyStore,SimError
from team14_referral_store import ReferralStore
from team14_statements import lesson_statement
from team14_instant_verified_bridge import settle_verified_instant_event,refund_verified_instant_settlement
import instant_matching as matching
import server
from test_staging import StagingTests as Harness

class InstantSettlementJourney(unittest.TestCase):
    setUp=Harness.setUp
    tearDown=Harness.tearDown
    request=Harness.request
    def account(self,email,role='learner',approved=False,referral_code=None):
        body=dict(email=email,password='Disposable-Password-12345!',
                  nickname=email.split('@')[0],role=role,adultConsent=True)
        if referral_code:body['referralCode']=referral_code
        status,_,raw=self.request('/api/register',body)
        self.assertEqual(status,200,raw)
        import json
        uid=json.loads(raw)['user']['id']
        cookie=self.cookie
        if approved:
            with server.connect() as db:db.execute('UPDATE users SET approved=1 WHERE id=?',(uid,))
        return cookie,uid
    def call(self,cookie,action,data=None,expected=200):
        import json
        status,_,body=self.request('/api/instant/'+action,
            data if data is not None else (None if action in ('status','session','reservations') else {}),
            headers={'Cookie':cookie})
        self.assertEqual(status,expected,body)
        return json.loads(body)
    def prepare_settlement(self):
        self.settlement_dir=tempfile.TemporaryDirectory()
        self.sp=os.path.join(self.settlement_dir.name,'simulated-ledger.sqlite')
        self.rp=os.path.join(self.settlement_dir.name,'simulated-referrals.sqlite')
        self.store=MonthlyStore(self.sp)
        self.referrals=ReferralStore(self.rp)
    def dispose_settlement(self):
        self.store.close();self.referrals.close();self.settlement_dir.cleanup()
    def journey(self):
        parent,parent_id=self.account('parent@example.test')
        with server.connect() as db:
            ref_code=db.execute('SELECT referral_code FROM users WHERE id=?',(parent_id,)).fetchone()[0]
        learner,learner_id=self.account('student@example.test',referral_code=ref_code)
        teacher,teacher_id=self.account('partner@example.test','partner',True)
        stranger,_=self.account('stranger@example.test')
        self.assertEqual('waiting',self.call(learner,'join')['state'])
        offer=self.call(teacher,'join')
        self.assertEqual('offered',offer['state'])
        self.call(learner,'ready',{'matchId':offer['matchId']})
        self.call(teacher,'ready',{'matchId':offer['matchId']})
        booking_id=self.call(learner,'session')['bookingId']
        self.assertTrue(booking_id)
        self.call(stranger,'session-observe',{'matchId':offer['matchId']},409)
        self.call(learner,'session-finish',{'matchId':offer['matchId']},409)
        self.call(learner,'session-observe',{'matchId':offer['matchId']})
        self.call(teacher,'session-observe',{'matchId':offer['matchId']})
        completed=self.call(learner,'session-finish',{'matchId':offer['matchId']})
        event_id=completed['event']['eventId']
        with server.connect() as db:
            self.assertEqual('completed',db.execute('SELECT status FROM bookings WHERE id=?',(booking_id,)).fetchone()[0])
            amount=db.execute('SELECT price FROM bookings WHERE id=?',(booking_id,)).fetchone()[0]
            self.assertEqual(1,db.execute('SELECT COUNT(*) FROM instant_lesson_events WHERE booking_id=?',(booking_id,)).fetchone()[0])
            self.assertTrue(matching.verified_event_for_team14(db,event_id)['verifiedByServer'])
        return learner_id,teacher_id,stranger,booking_id,event_id,amount
    def test_http_match_completion_settlement_refund_replay_restart(self):
        self.prepare_settlement()
        try:
            learner_id,teacher_id,stranger,booking_id,event_id,price=self.journey()
            self.store.create_month('simmonth',[('simlesson',booking_id,price)])
            with server.connect() as db:
                result=settle_verified_instant_event(db,self.store,self.referrals,event_id)
                again=settle_verified_instant_event(db,self.store,self.referrals,event_id)
                self.assertFalse(result['payment_executed'])
                self.assertFalse(result['payout_eligible'])
                self.assertEqual(result,again)
                self.assertEqual(3,len(lesson_statement(self.store,'simmonth','simlesson')['ledger']))
                self.assertEqual(self.referrals.awards_for_lesson('simlesson')['recipients'][0]['user_id'],
                                 db.execute('SELECT referred_by FROM users WHERE id=?',(learner_id,)).fetchone()[0])
                with self.assertRaises(SimError):
                    refund_verified_instant_settlement(db,self.store,booking_id,'refund-other',1000,
                                                      db.execute('SELECT id FROM users WHERE email=?',('stranger@example.test',)).fetchone()[0])
                refunded=refund_verified_instant_settlement(db,self.store,booking_id,
                                                             'refund-one',5000,learner_id)
                replay=refund_verified_instant_settlement(db,self.store,booking_id,
                                                           'refund-one',5000,learner_id)
                self.assertEqual(refunded,replay)
                self.assertEqual(5000,lesson_statement(self.store,'simmonth','simlesson')['refunded_krw'])
            self.store.close();self.referrals.close()
            self.store=MonthlyStore(self.sp);self.referrals=ReferralStore(self.rp)
            with server.connect() as db:
                self.assertEqual(result,settle_verified_instant_event(db,self.store,self.referrals,event_id))
                self.assertEqual(refunded,refund_verified_instant_settlement(db,self.store,booking_id,
                                                                     'refund-one',5000,learner_id))
                self.assertEqual(5000,lesson_statement(self.store,'simmonth','simlesson')['refunded_krw'])
            self.assertEqual(7,len(lesson_statement(self.store,'simmonth','simlesson')['ledger']))
        finally:self.dispose_settlement()
    def test_forged_unverified_event_and_price_mismatch_blocked(self):
        self.prepare_settlement()
        try:
            learner_id,teacher_id,_,booking_id,event_id,price=self.journey()
            self.store.create_month('simmonth',[('simlesson',booking_id,price)])
            with server.connect() as db:
                with self.assertRaises(SimError):settle_verified_instant_event(db,self.store,self.referrals,'fake_event')
                db.execute('UPDATE bookings SET price=price+1 WHERE id=?',(booking_id,))
                with self.assertRaises(SimError):settle_verified_instant_event(db,self.store,self.referrals,event_id)
                self.assertEqual(0,self.store.db.execute('SELECT COUNT(*) FROM ledger').fetchone()[0])
        finally:self.dispose_settlement()
    def test_second_partial_refund_and_excess_refund_blocked(self):
        self.prepare_settlement()
        try:
            learner_id,_,_,booking_id,event_id,price=self.journey()
            self.store.create_month('simmonth',[('simlesson',booking_id,price)])
            with server.connect() as db:
                settle_verified_instant_event(db,self.store,self.referrals,event_id)
                refund_verified_instant_settlement(db,self.store,booking_id,'partial_one',3000,learner_id)
                refund_verified_instant_settlement(db,self.store,booking_id,'partial_two',2000,learner_id)
                self.assertEqual(5000,lesson_statement(self.store,'simmonth','simlesson')['refunded_krw'])
                with self.assertRaises(SimError):
                    refund_verified_instant_settlement(db,self.store,booking_id,'too_much',price,learner_id)
                self.assertEqual(5000,lesson_statement(self.store,'simmonth','simlesson')['refunded_krw'])
        finally:self.dispose_settlement()
    def test_full_refund_reverses_allocations_and_persists(self):
        self.prepare_settlement()
        try:
            learner_id,_,_,booking_id,event_id,price=self.journey()
            self.store.create_month('simmonth',[('simlesson',booking_id,price)])
            with server.connect() as db:
                settle_verified_instant_event(db,self.store,self.referrals,event_id)
                refund_verified_instant_settlement(db,self.store,booking_id,'full_refund',price,learner_id)
                self.assertEqual('refunded',lesson_statement(self.store,'simmonth','simlesson')['state'])
                self.assertEqual(0,lesson_statement(self.store,'simmonth','simlesson')['teacher_krw'])
                self.assertEqual(0,lesson_statement(self.store,'simmonth','simlesson')['referral_krw'])
                self.assertEqual(0,lesson_statement(self.store,'simmonth','simlesson')['platform_krw'])
                with self.assertRaises(SimError):
                    refund_verified_instant_settlement(db,self.store,booking_id,'extra',100,learner_id)
            self.store.close();self.referrals.close()
            self.store=MonthlyStore(self.sp);self.referrals=ReferralStore(self.rp)
            self.assertEqual(price,lesson_statement(self.store,'simmonth','simlesson')['refunded_krw'])
        finally:self.dispose_settlement()
    def test_no_completion_evidence_means_no_payout(self):
        self.prepare_settlement()
        try:
            learner,_=self.account('student@example.test')
            teacher,_=self.account('partner@example.test','partner',True)
            self.call(learner,'join');offer=self.call(teacher,'join')
            self.call(learner,'ready',{'matchId':offer['matchId']})
            self.call(teacher,'ready',{'matchId':offer['matchId']})
            booking_id=self.call(learner,'session')['bookingId']
            self.call(learner,'session-finish',{'matchId':offer['matchId']},409)
            with server.connect() as db:
                price=db.execute('SELECT price FROM bookings WHERE id=?',(booking_id,)).fetchone()[0]
                self.store.create_month('simmonth',[('simlesson',booking_id,price)])
                with self.assertRaises(SimError):
                    settle_verified_instant_event(db,self.store,self.referrals,'not_completed')
            self.assertEqual(0,self.store.db.execute('SELECT COUNT(*) FROM ledger').fetchone()[0])
        finally:self.dispose_settlement()

del Harness
if __name__=='__main__':unittest.main(verbosity=2)
