"""Actual gated HTTP requests, disposable SQLite only; no external media."""
import concurrent.futures
import http.client
import json
import time
import unittest
from unittest.mock import patch
import server
import instant_matching as matching
from test_staging import StagingTests as Harness


class InstantMatchingTests(unittest.TestCase):
    setUp = Harness.setUp
    tearDown = Harness.tearDown
    request = Harness.request

    def account(self, email, role='learner', approved=False):
        status, _, raw=self.request('/api/register',dict(email=email,password='Disposable-Password-12345!',nickname=email.split('@')[0],role=role,adultConsent=True))
        self.assertEqual(200,status)
        uid=json.loads(raw)['user']['id']
        if approved:
            with server.connect() as db: db.execute('UPDATE users SET approved=1 WHERE id=?',(uid,))
        return self.cookie,uid

    def call(self,cookie,action,data=None,expected=200):
        status,_,raw=self.request('/api/instant/'+action,{} if data is None and action!='status' else data,headers={'Cookie':cookie})
        self.assertEqual(expected,status,raw)
        return json.loads(raw)

    def test_wait_match_consent_room_privacy_and_end(self):
        a,aid=self.account('learner@example.test')
        b,bid=self.account('partner@example.test','partner',True)
        stranger,_=self.account('other@example.test')
        self.assertEqual('waiting',self.call(a,'join')['state'])
        m=self.call(b,'join');self.assertEqual('offered',m['state']);self.assertNotIn('roomUrl',m)
        first=self.call(a,'status');self.assertEqual(m['matchId'],first['matchId'])
        self.assertEqual('idle',self.call(stranger,'status')['state'])
        self.call(stranger,'ready',{'matchId':m['matchId']},409)
        self.assertEqual('offered',self.call(a,'ready',{'matchId':m['matchId']})['state'])
        active=self.call(b,'ready',{'matchId':m['matchId']})
        self.assertEqual('active',active['state'])
        self.assertEqual(active['roomUrl'],self.call(a,'status')['roomUrl'])
        self.assertRegex(active['roomUrl'],r'^https://meet.jit.si/hs-match-[0-9a-f]{48}$')
        self.assertNotIn('email',str(first));self.assertNotIn('password',str(first))
        self.assertEqual(active['roomUrl'],self.call(a,'join')['roomUrl'])
        self.call(b,'leave');self.assertEqual('idle',self.call(a,'status')['state'])
        self.assertEqual('idle',self.call(b,'leave')['state'])
        with server.connect() as db:
            for table in ('bookings','ledger','attendance','slots'):
                self.assertEqual(0,db.execute('SELECT count(*) FROM '+table).fetchone()[0])

    def test_expired_presence_and_offers_do_not_requeue(self):
        a,_=self.account('learner@example.test');b,_=self.account('partner@example.test','partner',True)
        self.call(a,'join');self.call(b,'join')
        future=time.time()+matching.TTL+1
        with patch.object(matching.time,'time',return_value=future):
            self.assertEqual('idle',self.call(a,'heartbeat')['state'])
            self.assertEqual('idle',self.call(b,'status')['state'])
        self.call(a,'join');m=self.call(b,'join')
        with server.connect() as db: db.execute('UPDATE instant_matches SET created=created-? WHERE id=?',(matching.OFFER_TTL+1,m['matchId']))
        self.assertEqual('idle',self.call(a,'status')['state'])

    def test_ineligible_roles_revocation_and_methods(self):
        unapproved,_=self.account('unapproved@example.test','partner')
        self.call(unapproved,'join',expected=403)
        a,_=self.account('learner@example.test');b,bid=self.account('partner@example.test','teacher',True)
        self.call(a,'join');self.call(b,'join')
        with server.connect() as db: db.execute('UPDATE users SET approved=0 WHERE id=?',(bid,))
        self.assertEqual('idle',self.call(a,'status')['state'])
        with server.connect() as db: db.execute('UPDATE users SET approved=1 WHERE id=?',(bid,))
        self.call(a,'join');self.call(b,'join')
        with server.connect() as db: db.execute("UPDATE users SET role='learner' WHERE id=?",(bid,))
        self.assertEqual('idle',self.call(a,'status')['state'])
        self.assertEqual(405,self.request('/api/instant/join',headers={'Cookie':a})[0])
        self.assertEqual(401,self.request('/api/instant/status',headers={'Cookie':''})[0])
        self.assertEqual(403,self.request('/api/instant/join',{},headers={'Cookie':a,'Origin':'https://foreign.test'})[0])

    def test_concurrent_join_assigns_only_one_partner(self):
        a,_=self.account('learner@example.test')
        b,_=self.account('partner1@example.test','partner',True)
        c,_=self.account('partner2@example.test','partner',True)
        self.call(a,'join')
        def join(cookie):
            conn=http.client.HTTPConnection('127.0.0.1',self.http.server_port)
            conn.request('POST','/api/instant/join','{}',{'Host':'review.example.test','Origin':self.settings.origin,'Content-Type':'application/json','Cookie':cookie})
            r=conn.getresponse();result=(r.status,json.loads(r.read()));conn.close();return result
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool: replies=list(pool.map(join,(b,c)))
        self.assertTrue(all(s==200 for s,v in replies),replies)
        self.assertEqual(['offered','waiting'],sorted(v['state'] for s,v in replies))
        with server.connect() as db:
            self.assertEqual(1,db.execute("SELECT count(*) FROM instant_matches WHERE state<>'ended'").fetchone()[0])

    def test_new_tables_do_not_modify_existing_booking(self):
        a,aid=self.account('learner@example.test');b,bid=self.account('partner@example.test','partner',True)
        now=time.time()
        with server.connect() as db:
            db.execute('INSERT INTO slots VALUES(?,?,?,?)',('old-slot',bid,now+100,now+3700))
            db.execute('INSERT INTO bookings(id,learner_id,teacher_id,slot_id,unit_id,status,price,room,created_at) VALUES(?,?,?,?,?,?,?,?,?)',('old-booking',aid,bid,'old-slot','test-unit','test_paid',20000,'old-room',now))
            before=dict(db.execute('SELECT * FROM bookings').fetchone())
            matching.initialize(db)
        self.call(a,'join',expected=403);self.call(b,'join',expected=403)
        with server.connect() as db:
            self.assertEqual(before,dict(db.execute('SELECT * FROM bookings').fetchone()))
            db.execute('UPDATE slots SET start=?,end=?',(now+7200,now+10800))
        self.call(a,'join');self.call(b,'join');self.call(b,'leave')
        with server.connect() as db:
            self.assertEqual(before,dict(db.execute('SELECT * FROM bookings').fetchone()))


    def test_unapproved_partner_cannot_join_or_obtain_room(self):
        learner,_=self.account('learner@example.test')
        unapproved,_=self.account('unapproved@example.test','partner')
        approved,_=self.account('approved@example.test','partner',True)
        self.assertEqual('waiting',self.call(learner,'join')['state'])
        self.call(unapproved,'join',expected=403)
        self.assertEqual('idle',self.call(unapproved,'status')['state'])
        offer=self.call(approved,'join')
        self.assertNotIn('roomUrl',offer)
        self.call(learner,'ready',{'matchId':offer['matchId']})
        active=self.call(approved,'ready',{'matchId':offer['matchId']})
        self.assertIn('roomUrl',active)
        self.assertNotIn('roomUrl',self.call(unapproved,'status'))
        self.call(unapproved,'ready',{'matchId':offer['matchId']},expected=409)

    def test_disconnect_expiry_and_rejoin_require_explicit_opt_in(self):
        learner,_=self.account('learner@example.test')
        partner,_=self.account('partner@example.test','partner',True)
        self.call(learner,'join')
        self.call(partner,'join')
        with server.connect() as db:
            db.execute('UPDATE instant_queue SET seen=seen-? WHERE user_id=(SELECT learner_id FROM instant_matches WHERE state=\'offered\')',(matching.TTL+1,))
        self.assertEqual('idle',self.call(partner,'status')['state'])
        self.assertEqual('idle',self.call(learner,'status')['state'])
        self.assertEqual('waiting',self.call(learner,'join')['state'])
        self.assertEqual('offered',self.call(partner,'join')['state'])


    def test_reservation_bridge_only_returns_own_bookings_and_never_charges(self):
        learner, learner_id = self.account('learner@example.test')
        teacher, teacher_id = self.account('teacher@example.test','teacher',True)
        stranger, _ = self.account('stranger@example.test')
        now=time.time()
        with server.connect() as db:
            db.execute('INSERT INTO slots VALUES(?,?,?,?)',('bridge-slot',teacher_id,now+3600,now+7200))
            db.execute("""INSERT INTO bookings
              (id,learner_id,teacher_id,slot_id,unit_id,status,price,room,created_at)
              VALUES(?,?,?,?,?,?,?,?,?)""",
              ('bridge-booking',learner_id,teacher_id,'bridge-slot','unit','reserved',20000,'bridge-private-room',now))
        for cookie,expected_role in ((learner,'learner'),(teacher,'teacher')):
            response=self.call(cookie,'reservations')
            self.assertEqual(1,len(response['reservations']))
            item=response['reservations'][0]
            self.assertEqual('bridge-booking',item['bookingId'])
            self.assertEqual(expected_role,item['participantRole'])
            self.assertNotIn('room',str(response))
        self.assertEqual([],self.call(stranger,'reservations')['reservations'])
        with server.connect() as db:
            self.assertEqual(0,db.execute('SELECT count(*) FROM ledger').fetchone()[0])
            self.assertEqual(0,db.execute('SELECT count(*) FROM instant_matches').fetchone()[0])
        self.assertEqual('booking.created',
                         matching.transaction_event_contract('bridge-booking','event-1','booking.created')['type'])
        with self.assertRaises(server.Error):
            matching.transaction_event_contract('bridge-booking','event-2','payment.charge')


del Harness

if __name__=='__main__': unittest.main()
