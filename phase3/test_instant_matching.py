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
        status,_,raw=self.request('/api/instant/'+action,{} if data is None and action not in ('status','reservations') else data,headers={'Cookie':cookie})
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
            self.assertEqual('not_started',item['lessonState'])
            self.assertNotIn('room',str(response))
        self.assertEqual([],self.call(stranger,'reservations')['reservations'])
        with server.connect() as db:
            self.assertEqual(0,db.execute('SELECT count(*) FROM ledger').fetchone()[0])
            self.assertEqual(0,db.execute('SELECT count(*) FROM instant_matches').fetchone()[0])
        self.assertEqual('booking.created',
                         matching.transaction_event_contract('bridge-booking','event-1','booking.created')['type'])
        with self.assertRaises(server.Error):
            matching.transaction_event_contract('bridge-booking','event-2','payment.charge')


    def test_monthly_completion_event_contract_is_pure_and_rejects_invalid_indices(self):
        event=matching.transaction_event_contract(
            'booking-1','operation-1','lesson.completed',month_id='month-1',lesson_index=0)
        self.assertEqual('month-1',event['monthId'])
        self.assertEqual(0,event['lessonIndex'])
        self.assertEqual('operation-1',event['eventId'])
        self.assertFalse(event['paymentExecuted'])
        self.assertEqual(event,matching.transaction_event_contract(
            'booking-1','operation-1','lesson.completed',month_id='month-1',lesson_index=0))
        for kwargs in ({'month_id':'month-1'}, {'lesson_index':0},
                       {'month_id':'month-1','lesson_index':True},
                       {'month_id':'month-1','lesson_index':-1}):
            with self.subTest(kwargs=kwargs),self.assertRaises(server.Error):
                matching.transaction_event_contract('booking-1','operation-2','lesson.completed',**kwargs)
        with server.connect() as db:
            self.assertEqual(0,db.execute('SELECT count(*) FROM ledger').fetchone()[0])
            self.assertEqual(0,db.execute('SELECT count(*) FROM bookings').fetchone()[0])


    def test_active_room_revoked_when_partner_approval_is_removed(self):
        learner,_=self.account('revocation-learner@example.test')
        partner,partner_id=self.account('revocation-partner@example.test','partner',True)
        self.call(learner,'join')
        offered=self.call(partner,'join')
        self.call(learner,'ready',{'matchId':offered['matchId']})
        active=self.call(partner,'ready',{'matchId':offered['matchId']})
        self.assertEqual('active',active['state'])
        self.assertIn('roomUrl',active)
        with server.connect() as db:
            db.execute('UPDATE users SET approved=0 WHERE id=?',(partner_id,))
        for cookie in (learner,partner):
            state=self.call(cookie,'status')
            self.assertEqual('idle',state['state'])
            self.assertNotIn('roomUrl',state)
        self.call(partner,'join',expected=403)
        with server.connect() as db:
            self.assertEqual(0,db.execute("SELECT count(*) FROM instant_matches WHERE state<>'ended'").fetchone()[0])


    def test_reservation_lesson_states_survive_reconnect_and_hide_other_users(self):
        learner,learner_id=self.account('state-learner@example.test')
        teacher,teacher_id=self.account('state-teacher@example.test','teacher',True)
        outsider,_=self.account('state-outsider@example.test')
        now=time.time()
        statuses=('reserved','in_class','completed','cancelled','expired','refunded')
        with server.connect() as db:
            for i,status in enumerate(statuses):
                slot='state-slot-'+str(i)
                db.execute('INSERT INTO slots VALUES(?,?,?,?)',(slot,teacher_id,now+3600+i*7200,now+7200+i*7200))
                db.execute("""INSERT INTO bookings
                  (id,learner_id,teacher_id,slot_id,unit_id,status,price,room,created_at)
                  VALUES(?,?,?,?,?,?,?,?,?)""",
                  ('state-booking-'+str(i),learner_id,teacher_id,slot,'unit',status,20000,'private-room-'+str(i),now))
        expected=['not_started','in_progress','completed','cancelled','cancelled','cancelled']
        for cookie in (learner,teacher):
            for _ in range(2):
                data=self.call(cookie,'reservations')['reservations']
                self.assertEqual(expected,[item['lessonState'] for item in data])
                self.assertNotIn('private-room',str(data))
        self.assertEqual([],self.call(outsider,'reservations')['reservations'])


    def test_booked_room_participant_state_and_approval(self):
        learner,learner_id=self.account('room-learner@example.test')
        teacher,teacher_id=self.account('room-teacher@example.test','teacher',True)
        outsider,outsider_id=self.account('room-outsider@example.test')
        now=time.time()
        with server.connect() as db:
            db.execute('INSERT INTO slots VALUES(?,?,?,?)',('room-slot',teacher_id,now-30,now+3600))
            db.execute("""INSERT INTO bookings
              (id,learner_id,teacher_id,slot_id,unit_id,status,price,room,created_at)
              VALUES(?,?,?,?,?,?,?,?,?)""",
              ('room-booking',learner_id,teacher_id,'room-slot','unit','reserved',20000,'room-secret',now))
            def user(uid):
                return db.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()
            with self.assertRaises(server.Error) as err:
                matching.authorized_booking_room(db,'room-booking',user(learner_id))
            self.assertEqual(409,err.exception.status)
            db.execute("UPDATE bookings SET status='in_class' WHERE id='room-booking'")
            for uid in (learner_id,teacher_id):
                room=matching.authorized_booking_room(db,'room-booking',user(uid))
                self.assertEqual('https://meet.jit.si/room-secret',room['roomUrl'])
            with self.assertRaises(server.Error) as err:
                matching.authorized_booking_room(db,'room-booking',user(outsider_id))
            self.assertEqual(403,err.exception.status)
            db.execute('UPDATE users SET approved=0 WHERE id=?',(teacher_id,))
            with self.assertRaises(server.Error) as err:
                matching.authorized_booking_room(db,'room-booking',user(learner_id))
            self.assertEqual(403,err.exception.status)
            db.execute('UPDATE users SET approved=1 WHERE id=?',(teacher_id,))
            db.execute("UPDATE bookings SET status='completed' WHERE id='room-booking'")
            with self.assertRaises(server.Error) as err:
                matching.authorized_booking_room(db,'room-booking',user(learner_id))
            self.assertEqual(409,err.exception.status)
        self.assertEqual([],self.call(outsider,'reservations')['reservations'])


    def test_booked_room_http_endpoint_enforces_auth_ownership_and_revocation(self):
        learner,learner_id=self.account('http-room-learner@example.test')
        teacher,teacher_id=self.account('http-room-teacher@example.test','teacher',True)
        outsider,_=self.account('http-room-outsider@example.test')
        now=time.time()
        with server.connect() as db:
            db.execute('INSERT INTO slots VALUES(?,?,?,?)',('http-room-slot',teacher_id,now-30,now+3600))
            db.execute("""INSERT INTO bookings
              (id,learner_id,teacher_id,slot_id,unit_id,status,price,room,created_at)
              VALUES(?,?,?,?,?,?,?,?,?)""",
              ('http-room-booking',learner_id,teacher_id,'http-room-slot','unit','in_class',20000,'http-room-secret',now))
        request={'bookingId':'http-room-booking'}
        for cookie in (learner,teacher):
            reply=self.call(cookie,'booking-room',request)
            self.assertEqual('http-room-booking',reply['bookingId'])
            self.assertEqual('https://meet.jit.si/http-room-secret',reply['roomUrl'])
        self.call(outsider,'booking-room',request,expected=403)
        self.assertEqual(401,self.request('/api/instant/booking-room',request,headers={'Cookie':''})[0])
        with server.connect() as db:
            db.execute('UPDATE users SET approved=0 WHERE id=?',(teacher_id,))
        self.call(learner,'booking-room',request,expected=403)
        with server.connect() as db:
            db.execute('UPDATE users SET approved=1 WHERE id=?',(teacher_id,))
            db.execute("UPDATE bookings SET status='cancelled' WHERE id='http-room-booking'")
        self.call(learner,'booking-room',request,expected=409)
        self.call(teacher,'booking-room',request,expected=409)


    def test_lesson_event_http_outbox_idempotency_authorization_and_persistence(self):
        learner,learner_id=self.account('event-learner@example.test')
        teacher,teacher_id=self.account('event-teacher@example.test','teacher',True)
        outsider,_=self.account('event-outsider@example.test')
        now=time.time()
        with server.connect() as db:
            db.execute('INSERT INTO slots VALUES(?,?,?,?)',('event-slot',teacher_id,now-100,now+3600))
            db.execute("""INSERT INTO bookings
              (id,learner_id,teacher_id,slot_id,unit_id,status,price,room,created_at)
              VALUES(?,?,?,?,?,?,?,?,?)""",
              ('event-booking',learner_id,teacher_id,'event-slot','unit','completed',20000,'event-room',now))
        req={'bookingId':'event-booking','eventId':'event-once','type':'lesson.completed'}
        self.call(outsider,'lesson-event',req,expected=403)
        first=self.call(teacher,'lesson-event',req)['event']
        self.assertEqual('pending',first['deliveryStatus'])
        self.assertEqual(20000,first['amount'])
        self.assertFalse(first['paymentExecuted'])
        self.assertEqual(first,self.call(teacher,'lesson-event',req)['event'])
        self.call(learner,'lesson-event',req,expected=409)
        self.call(teacher,'lesson-event',{**req,'type':'booking.cancelled'},expected=409)
        self.call(teacher,'lesson-event',{**req,'eventId':'event-bad','type':'lesson.started'},expected=409)
        self.call(teacher,'lesson-event',{**req,'eventId':'event-second'},expected=409)
        with server.connect() as db:
            db.execute("UPDATE bookings SET status='cancelled' WHERE id=?",(req['bookingId'],))
        self.call(teacher,'lesson-event',{**req,'eventId':'event-cancel-after-complete','type':'booking.cancelled'},expected=409)
        with server.connect() as db:
            db.execute("UPDATE bookings SET status='completed' WHERE id=?",(req['bookingId'],))
        with server.connect() as db:
            events=list(db.execute('SELECT * FROM instant_lesson_events'))
            self.assertEqual(1,len(events))
            self.assertEqual(first,json.loads(events[0]['payload']))
            self.assertEqual([first],matching.pending_settlement_events(db))
            verified=matching.verified_event_for_team14(db,'event-once')
            self.assertTrue(verified['verifiedByServer'])
            self.assertEqual(teacher_id,verified['teacherId'])
            self.assertEqual(20000,verified['amount'])
            db.execute("UPDATE bookings SET status='cancelled' WHERE id=?",(verified['bookingId'],))
            with self.assertRaises(server.Error) as stale:
                matching.verified_event_for_team14(db,'event-once')
            self.assertEqual(409,stale.exception.status)
            db.execute("UPDATE bookings SET status='completed' WHERE id=?",(verified['bookingId'],))
            db.execute('UPDATE users SET approved=0 WHERE id=?',(teacher_id,))
            with self.assertRaises(server.Error) as revoked:
                matching.verified_event_for_team14(db,'event-once')
            self.assertEqual(403,revoked.exception.status)
            db.execute('UPDATE users SET approved=1 WHERE id=?',(teacher_id,))
            self.assertEqual([first],matching.pending_settlement_events(db,1))
            with self.assertRaises(server.Error):
                matching.pending_settlement_events(db,0)
            self.assertEqual(0,db.execute('SELECT count(*) FROM ledger').fetchone()[0])
        self.assertEqual(first,self.call(teacher,'lesson-event',req)['event'])


    def test_internal_settlement_acknowledgement_persists_and_deduplicates(self):
        learner,learner_id=self.account('ack-learner@example.test')
        teacher,teacher_id=self.account('ack-teacher@example.test','teacher',True)
        now=time.time()
        with server.connect() as db:
            db.execute('INSERT INTO slots VALUES(?,?,?,?)',('ack-slot',teacher_id,now-100,now+3600))
            db.execute("""INSERT INTO bookings
              (id,learner_id,teacher_id,slot_id,unit_id,status,price,room,created_at)
              VALUES(?,?,?,?,?,?,?,?,?)""",
              ('ack-booking',learner_id,teacher_id,'ack-slot','unit','completed',20000,'ack-room',now))
        req={'bookingId':'ack-booking','eventId':'ack-event','type':'lesson.completed'}
        self.call(teacher,'lesson-event',req)
        with server.connect() as db:
            self.assertEqual(1,len(matching.pending_settlement_events(db)))
            ack=matching.acknowledge_settlement_event(db,'ack-event','team14','receipt-1')
            self.assertTrue(ack['acknowledged'])
            self.assertEqual(ack,matching.acknowledge_settlement_event(db,'ack-event','team14','receipt-1'))
            self.assertEqual([],matching.pending_settlement_events(db))
            with self.assertRaises(server.Error) as err:
                matching.acknowledge_settlement_event(db,'ack-event','team14','receipt-2')
            self.assertEqual(409,err.exception.status)
        with server.connect() as db:
            self.assertEqual([],matching.pending_settlement_events(db))
            self.assertEqual(1,db.execute('SELECT count(*) FROM instant_event_deliveries').fetchone()[0])


    def test_mock_delivery_callback_atomic_replay_and_restart(self):
        learner,learner_id=self.account('deliver-learner@example.test')
        teacher,teacher_id=self.account('deliver-teacher@example.test','teacher',True)
        now=time.time()
        with server.connect() as db:
            db.execute('INSERT INTO slots VALUES(?,?,?,?)',('deliver-slot',teacher_id,now-100,now+3600))
            db.execute("""INSERT INTO bookings
              (id,learner_id,teacher_id,slot_id,unit_id,status,price,room,created_at)
              VALUES(?,?,?,?,?,?,?,?,?)""",
              ('deliver-booking',learner_id,teacher_id,'deliver-slot','unit','completed',20000,'deliver-room',now))
        self.call(teacher,'lesson-event',{'bookingId':'deliver-booking','eventId':'deliver-event','type':'lesson.completed'})
        def failing(db,event):
            db.execute('CREATE TABLE IF NOT EXISTS fake_receipts(id TEXT PRIMARY KEY)')
            db.execute('INSERT INTO fake_receipts VALUES(?)',(event['eventId'],))
            raise RuntimeError('simulated ledger failure')
        with self.assertRaises(RuntimeError):
            with server.connect() as db:
                matching.deliver_mock_events(db,failing)
        with server.connect() as db:
            self.assertEqual(1,len(matching.pending_settlement_events(db)))
            self.assertEqual(0,db.execute('SELECT count(*) FROM instant_event_deliveries').fetchone()[0])
            def consumer(db,event):
                db.execute('CREATE TABLE IF NOT EXISTS fake_receipts(id TEXT PRIMARY KEY)')
                db.execute('INSERT INTO fake_receipts VALUES(?)',(event['eventId'],))
                return 'receipt-'+event['eventId']
            receipts=matching.deliver_mock_events(db,consumer)
            self.assertEqual(1,len(receipts))
            self.assertEqual([],matching.deliver_mock_events(db,consumer))
        with server.connect() as db:
            self.assertEqual([],matching.pending_settlement_events(db))
            self.assertEqual(1,db.execute('SELECT count(*) FROM fake_receipts').fetchone()[0])
            self.assertEqual(1,db.execute('SELECT count(*) FROM instant_event_deliveries').fetchone()[0])



    def test_real_http_instant_booking_session_completion_and_outbox(self):
        learner,lid=self.account('flow-learner@example.test')
        partner,pid=self.account('flow-partner@example.test','partner',True)
        stranger,_=self.account('flow-stranger@example.test')
        self.assertEqual(401,self.request('/api/instant/join',{},headers={'Cookie':''})[0])
        self.assertEqual('waiting',self.call(learner,'join')['state'])
        offer=self.call(partner,'join')
        self.assertEqual('offered',offer['state'])
        self.assertIsNone(self.call(learner,'session')['bookingId'])
        self.call(learner,'ready',{'matchId':offer['matchId']})
        active=self.call(partner,'ready',{'matchId':offer['matchId']})
        self.assertEqual('active',active['state'])
        self.assertEqual('active',self.call(learner,'join')['state'])
        session=self.call(learner,'session')
        booking_id=session['bookingId']
        self.assertEqual(booking_id,self.call(partner,'session')['bookingId'])
        self.assertEqual(active['roomUrl'],session['roomUrl'])
        self.assertEqual(booking_id,self.call(learner,'session')['bookingId'])
        with server.connect() as db:
            b=db.execute('SELECT * FROM bookings WHERE id=?',(booking_id,)).fetchone()
            self.assertEqual((lid,pid,'in_class'),(b['learner_id'],b['teacher_id'],b['status']))
            self.assertEqual(1,db.execute('SELECT count(*) FROM instant_booking_links').fetchone()[0])
        self.call(learner,'session-finish',{'matchId':offer['matchId']},409)
        self.call(stranger,'session-observe',{'matchId':offer['matchId']},409)
        self.call(stranger,'lesson-event',{'bookingId':booking_id,'eventId':'forged','type':'lesson.completed'},403)
        self.call(learner,'lesson-event',{'bookingId':booking_id,'eventId':'early','type':'lesson.completed'},409)
        self.assertEqual(1,self.call(learner,'session-observe',{'matchId':offer['matchId']})['observedParticipants'])
        self.call(learner,'session-finish',{'matchId':offer['matchId']},409)
        self.assertEqual(2,self.call(partner,'session-observe',{'matchId':offer['matchId']})['observedParticipants'])
        result=self.call(learner,'session-finish',{'matchId':offer['matchId']})
        event=result['event']
        self.assertEqual('lesson.completed',event['type'])
        self.assertEqual(booking_id,event['bookingId'])
        self.assertEqual(lid,event['learnerId'])
        self.assertEqual(pid,event['teacherId'])
        self.assertEqual('idle',self.call(learner,'status')['state'])
        self.call(partner,'session-finish',{'matchId':offer['matchId']},409)
        self.call(partner,'lesson-event',{'bookingId':booking_id,'eventId':'duplicate','type':'lesson.completed'},409)
        with server.connect() as db:
            self.assertEqual('completed',db.execute('SELECT status FROM bookings WHERE id=?',(booking_id,)).fetchone()[0])
            self.assertEqual(1,db.execute('SELECT count(*) FROM instant_lesson_events WHERE booking_id=?',(booking_id,)).fetchone()[0])
            verified=matching.verified_event_for_team14(db,event['eventId'])
            self.assertEqual(booking_id,verified['bookingId'])
            self.assertEqual(1,len(matching.pending_settlement_events(db)))
        with server.connect() as db:
            self.assertEqual(1,len(matching.pending_settlement_events(db)))

    def test_instant_match_without_partner_reconnect_and_cancel(self):
        learner,_=self.account('waiting-learner@example.test')
        partner,_=self.account('waiting-partner@example.test','partner',True)
        self.assertEqual('waiting',self.call(learner,'join')['state'])
        self.assertIsNone(self.call(learner,'session')['bookingId'])
        self.assertEqual('waiting',self.call(learner,'join')['state'])
        with server.connect() as db:
            self.assertEqual(1,db.execute('SELECT count(*) FROM instant_queue').fetchone()[0])
        offer=self.call(partner,'join')
        self.call(learner,'ready',{'matchId':offer['matchId']})
        self.call(partner,'ready',{'matchId':offer['matchId']})
        self.call(learner,'session-observe',{'matchId':offer['matchId']})
        self.call(partner,'leave')
        self.call(learner,'session-finish',{'matchId':offer['matchId']},409)
        with server.connect() as db:
            self.assertEqual('in_class',db.execute('SELECT status FROM bookings JOIN instant_booking_links ON bookings.id=instant_booking_links.booking_id WHERE match_id=?',(offer['matchId'],)).fetchone()[0])
            self.assertEqual(0,db.execute('SELECT count(*) FROM instant_lesson_events').fetchone()[0])

del Harness

if __name__=='__main__': unittest.main()
