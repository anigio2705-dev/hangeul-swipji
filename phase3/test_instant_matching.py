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
        # An active instant room creates a real test booking and slot. Capture
        # its ID before leave, then prove the room is revoked without erasing
        # the booking history or allowing a stranger to retrieve the URL.
        status,_,raw=self.request('/api/instant/session',headers={'Cookie':a})
        self.assertEqual(200,status,raw)
        booking_id=json.loads(raw)['bookingId']
        self.call(b,'leave');self.assertEqual('idle',self.call(a,'status')['state'])
        self.assertEqual('idle',self.call(b,'leave')['state'])
        self.assertEqual(409,self.request('/api/instant/booking-room',
                         {'bookingId':booking_id},headers={'Cookie':a})[0])
        self.assertEqual(403,self.request('/api/instant/booking-room',
                         {'bookingId':booking_id},headers={'Cookie':stranger})[0])
        with server.connect() as db:
            self.assertEqual(0,db.execute('SELECT count(*) FROM ledger').fetchone()[0])
            self.assertEqual(0,db.execute('SELECT count(*) FROM attendance').fetchone()[0])
            self.assertEqual(0,db.execute("SELECT count(*) FROM instant_matches WHERE state<>'ended'").fetchone()[0])
            self.assertEqual(0,db.execute('SELECT count(*) FROM instant_queue').fetchone()[0])
            booking=db.execute('SELECT status,slot_id FROM bookings WHERE id=?',(booking_id,)).fetchone()
            self.assertIsNotNone(booking,'legal booking history must not be deleted')
            self.assertEqual('cancelled',booking['status'])
            self.assertIsNotNone(db.execute('SELECT id FROM slots WHERE id=?',
                                            (booking['slot_id'],)).fetchone())

    def test_closed_booking_revokes_active_room(self):
        learner,learner_id=self.account('revoke-learner@example.test')
        partner,_=self.account('revoke-partner@example.test','partner',True)
        self.call(learner,'join')
        offer=self.call(partner,'join')
        self.call(learner,'ready',{'matchId':offer['matchId']})
        active=self.call(partner,'ready',{'matchId':offer['matchId']})
        self.assertIn('roomUrl',active)
        with server.connect() as db:
            booking=db.execute('''SELECT b.id FROM bookings b JOIN instant_booking_links l
              ON l.booking_id=b.id WHERE l.match_id=?''',(offer['matchId'],)).fetchone()
            self.assertIsNotNone(booking)
            db.execute("UPDATE bookings SET status='cancelled' WHERE id=?",(booking['id'],))
            user=db.execute('SELECT * FROM users WHERE id=?',(learner_id,)).fetchone()
            # Even before cleanup runs, a stale match must not leak a room URL.
            self.assertNotIn('roomUrl',matching.snapshot(db,user))
            matching.cleanup(db,time.time())
            self.assertIsNone(matching.current(db,learner_id))
        self.assertEqual('idle',self.call(learner,'status')['state'])
        self.assertEqual(409,self.request('/api/instant/booking-room',
                         {'bookingId':booking['id']},headers={'Cookie':learner})[0])

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


del Harness

if __name__=='__main__': unittest.main()
