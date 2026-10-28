"""Opt-in instant matching in the isolated review DB; no hosted DB or money."""
import secrets
import json
import time
import server

TTL = 45
OFFER_TTL = 60


def initialize(db):
    db.executescript('''
    CREATE TABLE IF NOT EXISTS instant_queue(
      user_id TEXT PRIMARY KEY REFERENCES users(id), joined REAL NOT NULL, seen REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS instant_matches(
      id TEXT PRIMARY KEY, learner_id TEXT NOT NULL REFERENCES users(id),
      partner_id TEXT NOT NULL REFERENCES users(id), state TEXT NOT NULL CHECK(state IN ('offered','active','ended')),
      learner_ready INTEGER NOT NULL DEFAULT 0, partner_ready INTEGER NOT NULL DEFAULT 0,
      created REAL NOT NULL, room TEXT NOT NULL UNIQUE, CHECK(learner_id<>partner_id));
    CREATE UNIQUE INDEX IF NOT EXISTS instant_learner_open ON instant_matches(learner_id) WHERE state<>'ended';
    CREATE UNIQUE INDEX IF NOT EXISTS instant_partner_open ON instant_matches(partner_id) WHERE state<>'ended';
    CREATE TABLE IF NOT EXISTS instant_lesson_events(
      event_id TEXT PRIMARY KEY, booking_id TEXT NOT NULL REFERENCES bookings(id),
      actor_id TEXT NOT NULL REFERENCES users(id), event_type TEXT NOT NULL
      CHECK(event_type IN ('lesson.started','lesson.completed','booking.cancelled')),
      created REAL NOT NULL, payload TEXT NOT NULL);
    CREATE INDEX IF NOT EXISTS instant_lesson_events_booking ON instant_lesson_events(booking_id);
    CREATE UNIQUE INDEX IF NOT EXISTS instant_terminal_event_per_booking ON instant_lesson_events(booking_id) WHERE event_type IN ('lesson.completed','booking.cancelled');
    CREATE TABLE IF NOT EXISTS instant_event_deliveries(
      event_id TEXT PRIMARY KEY REFERENCES instant_lesson_events(event_id),
      consumer TEXT NOT NULL, acknowledged_at REAL NOT NULL, receipt_id TEXT NOT NULL UNIQUE);
    CREATE TABLE IF NOT EXISTS instant_booking_links(
      match_id TEXT PRIMARY KEY REFERENCES instant_matches(id),
      booking_id TEXT NOT NULL UNIQUE REFERENCES bookings(id));
    CREATE TABLE IF NOT EXISTS instant_session_evidence(
      match_id TEXT NOT NULL REFERENCES instant_matches(id),
      user_id TEXT NOT NULL REFERENCES users(id),
      observed REAL NOT NULL, PRIMARY KEY(match_id,user_id));
    CREATE TABLE IF NOT EXISTS instant_event_attempts(
      event_id TEXT PRIMARY KEY REFERENCES instant_lesson_events(event_id),
      attempts INTEGER NOT NULL DEFAULT 0, last_attempt REAL, last_error TEXT);
    ''')


def eligible(db, u, now):
    if not u or u['role'] not in ('learner', 'partner', 'teacher'):
        return False
    if u['role'] != 'learner' and not u['approved']:
        return False
    return not db.execute("""SELECT 1 FROM bookings b JOIN slots s ON s.id=b.slot_id
      LEFT JOIN instant_booking_links l ON l.booking_id=b.id
      WHERE l.booking_id IS NULL AND (b.learner_id=? OR b.teacher_id=?) AND
      (b.status='in_class' OR (b.status='test_paid' AND s.start<=? AND s.end>=?)) LIMIT 1""",
      (u['id'], u['id'], now+300, now-300)).fetchone()


def cleanup(db, now):
    db.execute('DELETE FROM instant_queue WHERE seen<=?', (now-TTL,))
    for q in list(db.execute('SELECT user_id FROM instant_queue')):
        if not eligible(db, db.execute('SELECT * FROM users WHERE id=?', (q['user_id'],)).fetchone(), now):
            db.execute('DELETE FROM instant_queue WHERE user_id=?', (q['user_id'],))
    for m in list(db.execute("SELECT * FROM instant_matches WHERE state<>'ended'")):
        live = db.execute('SELECT count(*) FROM instant_queue WHERE user_id IN (?,?)',
                          (m['learner_id'], m['partner_id'])).fetchone()[0]
        learner=db.execute('SELECT * FROM users WHERE id=?',(m['learner_id'],)).fetchone()
        partner=db.execute('SELECT * FROM users WHERE id=?',(m['partner_id'],)).fetchone()
        roles_ok=(learner and learner['role']=='learner' and partner
                  and partner['role'] in ('partner','teacher')
                  and eligible(db,learner,now) and eligible(db,partner,now))
        if live != 2 or not roles_ok or (m['state']=='offered' and m['created']+OFFER_TTL<=now):
            end(db, m)


def end(db, m):
    """Close a match without leaving an abandoned simulated booking in_class.

    A completed booking is never cancelled; only an unfinished instant booking
    is transitioned to cancelled.  The deterministic cancellation event is
    stored in the same SQLite transaction as the status change and can be
    replayed safely to Team14 via the existing outbox.
    """
    booking = linked_booking(db, m['id'])
    if booking and booking['status'] == 'in_class':
        db.execute("UPDATE bookings SET status='cancelled' WHERE id=? AND status='in_class'",
                   (booking['id'],))
        learner = db.execute('SELECT * FROM users WHERE id=?',
                             (m['learner_id'],)).fetchone()
        if learner:
            record_lesson_event(db, learner, booking['id'],
                                'instant-cancel-'+m['id'], 'booking.cancelled')
    db.execute("UPDATE instant_matches SET state='ended' WHERE id=?", (m['id'],))
    db.execute('DELETE FROM instant_queue WHERE user_id IN (?,?)', (m['learner_id'], m['partner_id']))


def current(db, uid):
    return db.execute("SELECT * FROM instant_matches WHERE state<>'ended' AND (learner_id=? OR partner_id=?)",
                      (uid, uid)).fetchone()


def assign(db, now):
    # Handler serializes mutations with BEGIN IMMEDIATE; indexes also guard races.
    available = list(db.execute("""SELECT u.id,u.role FROM instant_queue q JOIN users u ON u.id=q.user_id
       WHERE NOT EXISTS(SELECT 1 FROM instant_matches m WHERE m.state<>'ended'
       AND (m.learner_id=u.id OR m.partner_id=u.id)) ORDER BY q.joined,u.id"""))
    learners = [u for u in available if u['role']=='learner']
    partners = [u for u in available if u['role'] in ('partner','teacher')]
    for learner, partner in zip(learners, partners):
        db.execute('INSERT INTO instant_matches(id,learner_id,partner_id,state,created,room) VALUES(?,?,?,?,?,?)',
          (server.ident(), learner['id'], partner['id'], 'offered', now, 'hs-match-'+secrets.token_hex(24)))


def snapshot(db, u):
    m = current(db, u['id'])
    value = {'user': {'nickname':u['nickname'], 'role':u['role']},
             'eligible': eligible(db,u,time.time()), 'state':'idle'}
    if m:
        learner = u['id']==m['learner_id']
        other = db.execute('SELECT nickname FROM users WHERE id=?',
                           (m['partner_id'] if learner else m['learner_id'],)).fetchone()
        value.update(state=m['state'], matchId=m['id'], partnerName=other['nickname'],
                     ready=bool(m['learner_ready'] if learner else m['partner_ready']),
                     expiresAt=m['created']+OFFER_TTL if m['state']=='offered' else None)
        if m['state']=='active': value['roomUrl']='https://meet.jit.si/'+m['room']
    elif db.execute('SELECT 1 FROM instant_queue WHERE user_id=?',(u['id'],)).fetchone():
        value['state']='waiting'
    return value



# Read-only bridge: existing one-off bookings and future monthly-session bookings
# share booking ownership/status without creating a second match or charging money.
def reservation_snapshot(db, user_id):
    rows = db.execute("""SELECT b.id,b.status,b.learner_id,b.teacher_id,s.start,s.end
      FROM bookings b JOIN slots s ON s.id=b.slot_id
      WHERE b.learner_id=? OR b.teacher_id=? ORDER BY s.start,b.id""",
      (user_id,user_id)).fetchall()
    return [{'bookingId':b['id'], 'status':b['status'],
             'participantRole':'learner' if b['learner_id']==user_id else 'teacher',
             'start':b['start'], 'end':b['end'],
             'instantEligible':b['status'] not in ('test_paid','in_class'),
             'lessonState':('completed' if b['status'] in ('completed','test_settled')
                            else 'cancelled' if b['status'] in ('cancelled','refunded','expired')
                            else 'in_progress' if b['status']=='in_class'
                            else 'not_started')}
            for b in rows]



def authorized_booking_room(db, booking_id, user):
    """Return a reserved room only to an authenticated booking participant.

    Does not authenticate the external Jitsi provider: an already shared URL
    remains accessible until the provider enforces its own access controls.
    """
    if not isinstance(booking_id,str) or not booking_id:
        raise server.Error('예약 식별자가 필요합니다',400)
    if user is None:
        raise server.Error('로그인이 필요합니다',401)
    b=db.execute("""SELECT b.*,s.start,s.end FROM bookings b
                    JOIN slots s ON s.id=b.slot_id WHERE b.id=?""",
                 (booking_id,)).fetchone()
    if not b:
        raise server.Error('예약이 없습니다',404)
    if user['id'] not in (b['learner_id'],b['teacher_id']):
        raise server.Error('예약 참여자만 입장할 수 있습니다',403)
    if b['status']!='in_class':
        raise server.Error('수업이 진행 중인 예약만 입장할 수 있습니다',409)
    teacher=db.execute('SELECT role,approved FROM users WHERE id=?',(b['teacher_id'],)).fetchone()
    if not teacher or teacher['role'] not in ('partner','teacher') or not teacher['approved']:
        raise server.Error('승인되지 않은 강사입니다',403)
    if not b['room']:
        raise server.Error('화상방이 준비되지 않았습니다',409)
    return {'bookingId':b['id'],'roomUrl':'https://meet.jit.si/'+b['room'],
            'participantRole':'learner' if user['id']==b['learner_id'] else 'teacher'}



def linked_booking(db, match_id):
    return db.execute("""SELECT b.* FROM instant_booking_links l
      JOIN bookings b ON b.id=l.booking_id WHERE l.match_id=?""",(match_id,)).fetchone()


def create_instant_booking(db, m, now):
    """Server-owned test booking once both matched parties have consented.

    This is a simulated session, not a charge; no payment provider is invoked.
    """
    existing=linked_booking(db,m['id'])
    if existing: return existing
    learner=db.execute('SELECT * FROM users WHERE id=?',(m['learner_id'],)).fetchone()
    partner=db.execute('SELECT * FROM users WHERE id=?',(m['partner_id'],)).fetchone()
    if (not learner or learner['role']!='learner' or not partner
        or partner['role'] not in ('teacher','partner') or not partner['approved']):
        raise server.Error('매칭 당사자 또는 강사 승인이 유효하지 않습니다',403)
    slot_id=server.ident()
    booking_id=server.ident()
    db.execute('INSERT INTO slots VALUES(?,?,?,?)',
               (slot_id,m['partner_id'],now-1,now+3600))
    db.execute("""INSERT INTO bookings
      (id,learner_id,teacher_id,slot_id,unit_id,status,price,room,created_at)
      VALUES(?,?,?,?,?,?,?,?,?)""",
      (booking_id,m['learner_id'],m['partner_id'],slot_id,
       'instant-simulated-session','in_class',partner['price'],m['room'],now))
    db.execute('INSERT INTO instant_booking_links VALUES(?,?)',(m['id'],booking_id))
    return linked_booking(db,m['id'])


def instant_session(db, u, match_id):
    m=current(db,u['id'])
    if not m or m['id']!=match_id or m['state']!='active':
        raise server.Error('현재 진행 중인 본인 매칭이 아닙니다',409)
    b=linked_booking(db,m['id'])
    if not b or b['status']!='in_class':
        raise server.Error('수업이 진행 중인 예약이 아닙니다',409)
    return m,b


def transaction_event_contract(booking_id, event_id, event_type, *, lesson_index=None, month_id=None):
    """Pure Team13 -> Team14 handoff. No ledger writes or payment calls.

    eventId is the downstream idempotency key. Team14 must authenticate the
    sender, validate completion evidence, and deduplicate before settlement.
    """
    if event_type not in ('booking.created','booking.cancelled',
                          'lesson.started','lesson.completed'):
        raise server.Error('지원하지 않는 거래 이벤트',400)
    if not isinstance(booking_id,str) or not booking_id or not isinstance(event_id,str) or not event_id:
        raise server.Error('거래 이벤트 식별자 필요',400)
    if (month_id is None) != (lesson_index is None):
        raise server.Error('월 과정과 회차는 함께 지정하세요',400)
    if month_id is not None and (not isinstance(month_id,str) or not month_id
                                or type(lesson_index) is not int or lesson_index<0):
        raise server.Error('월 과정 회차 형식 오류',400)
    event={'version':1,'bookingId':booking_id,'eventId':event_id,
           'type':event_type,'paymentExecuted':False}
    if month_id is not None:
        event.update(monthId=month_id,lessonIndex=lesson_index)
    return event


def record_lesson_event(db, user, booking_id, event_id, event_type):
    """Persist an authenticated, idempotent mock event for Team14 consumption.

    Does not settle money or mutate the booking lifecycle owned by Team11.
    """
    if event_type not in ('lesson.started','lesson.completed','booking.cancelled'):
        raise server.Error('지원하지 않는 수업 이벤트',400)
    if not isinstance(booking_id,str) or not booking_id or not isinstance(event_id,str) or not event_id:
        raise server.Error('예약 및 이벤트 식별자가 필요합니다',400)
    b=db.execute('SELECT * FROM bookings WHERE id=?',(booking_id,)).fetchone()
    if not b: raise server.Error('예약이 없습니다',404)
    if user['id'] not in (b['learner_id'],b['teacher_id']):
        raise server.Error('예약 참여자만 기록할 수 있습니다',403)
    instant=db.execute('SELECT match_id FROM instant_booking_links WHERE booking_id=?',(booking_id,)).fetchone()
    if instant and event_type=='lesson.completed':
        if b['status']!='completed' or db.execute(
            'SELECT count(*) FROM instant_session_evidence WHERE match_id=?',(instant['match_id'],)
        ).fetchone()[0]!=2:
            raise server.Error('양측 수업 연결 확인이 완료되지 않았습니다',409)
    teacher=db.execute('SELECT role,approved FROM users WHERE id=?',(b['teacher_id'],)).fetchone()
    if not teacher or teacher['role'] not in ('teacher','partner') or not teacher['approved']:
        raise server.Error('강사 승인이 유효하지 않습니다',403)
    existing=db.execute('SELECT * FROM instant_lesson_events WHERE event_id=?',(event_id,)).fetchone()
    if existing:
        if (existing['booking_id'],existing['actor_id'],existing['event_type']) != (booking_id,user['id'],event_type):
            raise server.Error('다른 요청에 사용된 이벤트 식별자입니다',409)
        return json.loads(existing['payload'])
    allowed={'lesson.started':('test_paid','in_class'),
             'lesson.completed':('completed','test_settled'),
             'booking.cancelled':('cancelled','refunded','expired')}
    if b['status'] not in allowed[event_type]:
        raise server.Error('예약 상태와 이벤트가 일치하지 않습니다',409)
    if event_type=='lesson.completed' and not instant:
        # For normal Team11 bookings, require server-tracked mutual attendance,
        # confirmation and lesson evidence rather than a forged browser event.
        rows=db.execute('SELECT user_id,confirmed FROM attendance WHERE booking_id=?',(booking_id,)).fetchall()
        if (len(rows)!=2 or any(not row['confirmed'] for row in rows)
            or not b['evidence']):
            raise server.Error('예약 수업 완료에 대한 서버 검증 근거가 부족합니다',409)
    if event_type in ('lesson.completed','booking.cancelled'):
        prior=db.execute("""SELECT event_id FROM instant_lesson_events
            WHERE booking_id=? AND event_type IN ('lesson.completed','booking.cancelled')
            LIMIT 1""",(booking_id,)).fetchone()
        if prior:
            raise server.Error('이미 기록된 예약 수업 이벤트입니다',409)
    payload=transaction_event_contract(booking_id,event_id,event_type)
    payload.update(actorId=user['id'],learnerId=b['learner_id'],teacherId=b['teacher_id'],
                   amount=b['price'],bookingStatus=b['status'],deliveryStatus='pending')
    db.execute('INSERT INTO instant_lesson_events VALUES(?,?,?,?,?,?)',
               (event_id,booking_id,user['id'],event_type,time.time(),json.dumps(payload,ensure_ascii=False)))
    return payload




def verified_outbox_envelope(db, event_id):
    """Read-only versioned handoff built exclusively from trusted SQLite state.

    A read is not an acknowledgement. Do not expose this internal API to browsers.
    """
    verified=verified_event_for_team14(db,event_id)
    row=db.execute('SELECT created,payload FROM instant_lesson_events WHERE event_id=?',(event_id,)).fetchone()
    delivery=db.execute('SELECT consumer,receipt_id FROM instant_event_deliveries WHERE event_id=?',(event_id,)).fetchone()
    attempts=db.execute('SELECT attempts FROM instant_event_attempts WHERE event_id=?',(event_id,)).fetchone()
    payload=json.loads(row['payload'])
    if payload.get('version')!=1 or payload.get('paymentExecuted') is not False:
        raise server.Error('지원하지 않는 이벤트 버전 또는 결제 상태',409)
    return {'version':1,'eventId':event_id,'bookingId':verified['bookingId'],
            'learnerId':verified['learnerId'],'teacherId':verified['teacherId'],
            'amount':verified['amount'],'currency':'KRW',
            'completedAt':row['created'],'type':verified['type'],
            'bookingStatus':verified['status'],
            'deliveryStatus':'acknowledged' if delivery else 'pending',
            'attempts':attempts['attempts'] if attempts else 0,
            'receiptId':delivery['receipt_id'] if delivery else None,
            'paymentExecuted':False,'verifiedByServer':True}


def confirm_settlement_receipt(db, event_id, consumer, receipt_id, settlement_confirmed=False):
    """Only a trusted caller may acknowledge a durable downstream ledger receipt.

    Explicit confirmation is mandatory; event delivery or a transport response alone
    is insufficient. A separate Team14 database needs replay-safe event IDs.
    """
    if settlement_confirmed is not True:
        raise server.Error('모의 정산 확정 증빙이 필요합니다',409)
    verified_outbox_envelope(db,event_id)
    return acknowledge_settlement_event(db,event_id,consumer,receipt_id)


def pending_settlement_events(db, limit=100):
    """Internal-only Team14 handoff; never exposed as a user HTTP endpoint.

    Caller must run within a trusted server transaction and validate ownership
    and settlement evidence before recording any simulated ledger entry.
    """
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise server.Error('이벤트 조회 범위 오류',400)
    rows=db.execute("""SELECT e.payload FROM instant_lesson_events e
      JOIN bookings b ON b.id=e.booking_id
      LEFT JOIN instant_event_deliveries d ON d.event_id=e.event_id
      WHERE e.event_type IN ('lesson.completed','booking.cancelled') AND d.event_id IS NULL
      ORDER BY e.created,e.event_id LIMIT ?""",(limit,)).fetchall()
    return [json.loads(row['payload']) for row in rows]



def acknowledge_settlement_event(db, event_id, consumer, receipt_id):
    """Trusted Team14 adapter: idempotent acknowledgement after mock ledger commit.

    Must be called inside the SAME DB transaction as the downstream mock ledger
    write. Acknowledgement alone does not imply that a settlement occurred.
    """
    if any(not isinstance(v,str) or not v.strip() or len(v)>128
           for v in (event_id,consumer,receipt_id)):
        raise server.Error('정산 수신 확인 식별자 오류',400)
    event=db.execute('SELECT event_type FROM instant_lesson_events WHERE event_id=?',(event_id,)).fetchone()
    if not event or event['event_type'] not in ('lesson.completed','booking.cancelled'):
        raise server.Error('전달 가능한 이벤트가 아닙니다',404)
    existing=db.execute('SELECT * FROM instant_event_deliveries WHERE event_id=?',(event_id,)).fetchone()
    if existing:
        if (existing['consumer'],existing['receipt_id'])!=(consumer,receipt_id):
            raise server.Error('이벤트 수신 확인이 충돌합니다',409)
        return {'eventId':event_id,'receiptId':receipt_id,'acknowledged':True}
    db.execute('INSERT INTO instant_event_deliveries VALUES(?,?,?,?)',
               (event_id,consumer,time.time(),receipt_id))
    return {'eventId':event_id,'receiptId':receipt_id,'acknowledged':True}



def deliver_mock_events(db, consumer, limit=100):
    """Team13 outbox adapter. Consumer runs within caller's SQLite transaction.

    The callback must validate the booking and write its mock ledger before
    returning a durable receipt ID. Exceptions roll back the entire transaction
    when the caller uses its normal transaction context.
    """
    if not callable(consumer):
        raise server.Error('모의 정산 소비자가 필요합니다',400)
    results=[]
    for event in pending_settlement_events(db,limit):
        event_id=event['eventId']
        db.execute("""INSERT INTO instant_event_attempts(event_id,attempts,last_attempt,last_error)
                      VALUES(?,1,?,NULL)
                      ON CONFLICT(event_id) DO UPDATE SET
                        attempts=attempts+1,last_attempt=excluded.last_attempt,last_error=NULL""",
                   (event_id,time.time()))
        verified_outbox_envelope(db,event_id)
        receipt=consumer(db,event)
        if not isinstance(receipt,str) or not receipt.strip():
            raise server.Error('모의 정산 처리 확인이 없습니다',409)
        # Legacy same-SQLite adapter: consumer must have committed its ledger in
        # this transaction. Separate DB consumers must replay with stable eventId.
        results.append(confirm_settlement_receipt(db,event_id,'team14',receipt,
                                                   settlement_confirmed=True))
    return results



def verified_event_for_team14(db, event_id):
    """Resolve Team14's trusted event and booking callbacks from server DB only.

    A monthly settlement mapping is required; no invented month or lesson IDs.
    This is an internal adapter, never a public HTTP endpoint.
    """
    if not isinstance(event_id,str) or not event_id:
        raise server.Error('이벤트 식별자 필요',400)
    row=db.execute("""SELECT e.*,b.learner_id,b.teacher_id,b.status,b.price,
                      u.role,u.approved
                      FROM instant_lesson_events e JOIN bookings b ON b.id=e.booking_id
                      JOIN users u ON u.id=b.teacher_id WHERE e.event_id=?""",
                   (event_id,)).fetchone()
    if not row: raise server.Error('이벤트가 없습니다',404)
    if row['role'] not in ('teacher','partner') or not row['approved']:
        raise server.Error('강사 승인이 유효하지 않습니다',403)
    allowed={'lesson.completed':('completed','test_settled'),
             'booking.cancelled':('cancelled','refunded','expired'),
             'lesson.started':('test_paid','in_class')}
    if row['event_type'] not in allowed or row['status'] not in allowed[row['event_type']]:
        raise server.Error('현재 예약 상태에서 유효하지 않은 수업 이벤트입니다',409)
    payload=json.loads(row['payload'])
    if (payload.get('eventId')!=event_id or payload.get('bookingId')!=row['booking_id']
        or payload.get('learnerId')!=row['learner_id']
        or payload.get('teacherId')!=row['teacher_id']
        or payload.get('amount')!=row['price']
        or payload.get('bookingStatus')!=row['status']):
        raise server.Error('이벤트와 서버 예약 데이터가 일치하지 않습니다',409)
    return {'eventId':event_id,'bookingId':row['booking_id'],
            'learnerId':row['learner_id'],'teacherId':row['teacher_id'],
            'amount':row['price'],'status':row['status'],
            'type':row['event_type'],'verifiedByServer':True}


def route(handler, db, path, data):
    u=handler.user(db)
    action=path.removeprefix('/api/instant/')
    allowed={'reservations':'GET','booking-room':'POST','lesson-event':'POST','session':'GET','session-observe':'POST','session-finish':'POST','status':'GET','join':'POST','heartbeat':'POST','ready':'POST','leave':'POST'}
    if action not in allowed: raise server.Error('페이지 없음',404)
    if handler.command!=allowed[action]: raise server.Error('지원하지 않는 요청',405)
    now=time.time()
    cleanup(db,now)
    if action=='reservations':
        return {'reservations':reservation_snapshot(db,u['id'])},None
    if action=='booking-room':
        return authorized_booking_room(db,data.get('bookingId'),u),None
    if action=='lesson-event':
        return {'event':record_lesson_event(db,u,data.get('bookingId'),data.get('eventId'),data.get('type'))},None
    if action=='session':
        m=current(db,u['id'])
        if not m or m['state']!='active':
            return {'state':snapshot(db,u)['state'],'bookingId':None},None
        m,b=instant_session(db,u,m['id'])
        return {'state':'active','bookingId':b['id'],'matchId':m['id'],
                'roomUrl':'https://meet.jit.si/'+m['room']},None
    if action=='session-observe':
        m,b=instant_session(db,u,data.get('matchId'))
        db.execute("""INSERT INTO instant_session_evidence VALUES(?,?,?)
          ON CONFLICT(match_id,user_id) DO UPDATE SET observed=excluded.observed""",
          (m['id'],u['id'],now))
        return {'state':'active','bookingId':b['id'],
                'observedParticipants':db.execute('SELECT count(*) FROM instant_session_evidence WHERE match_id=?',(m['id'],)).fetchone()[0]},None
    if action=='session-finish':
        m,b=instant_session(db,u,data.get('matchId'))
        evidence=db.execute('SELECT count(*) FROM instant_session_evidence WHERE match_id=?',(m['id'],)).fetchone()[0]
        if evidence!=2:
            raise server.Error('양측의 서버 수업 연결 기록이 필요합니다',409)
        # Session observation is a test-only criterion; commercial duration policy is unapproved.
        db.execute("UPDATE bookings SET status='completed' WHERE id=? AND status='in_class'",(b['id'],))
        event_id='instant-complete-'+m['id']
        event=record_lesson_event(db,u,b['id'],event_id,'lesson.completed')
        end(db,m)
        return {'event':event,'bookingId':b['id'],'verification':'both-participants-observed-test-only'},None
    if action=='join':
        if not eligible(db,u,now):
            raise server.Error('학생 또는 승인된 대화 파트너로 참여하세요. 예약 수업 중에는 대기할 수 없습니다.',403)
        db.execute('INSERT INTO instant_queue VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET seen=excluded.seen',
                   (u['id'],now,now))
        assign(db,now)
    elif action=='heartbeat':
        db.execute('UPDATE instant_queue SET seen=? WHERE user_id=?',(now,u['id']))
        assign(db,now)
    elif action=='ready':
        m=current(db,u['id'])
        if not m or data.get('matchId')!=m['id']:
            raise server.Error('매칭이 종료되었거나 다른 대화입니다. 다시 대기를 시작하세요.',409)
        db.execute('UPDATE instant_queue SET seen=? WHERE user_id=?',(now,u['id']))
        field='learner_ready' if u['id']==m['learner_id'] else 'partner_ready'
        db.execute('UPDATE instant_matches SET '+field+'=1 WHERE id=?',(m['id'],))
        db.execute("UPDATE instant_matches SET state='active' WHERE id=? AND learner_ready=1 AND partner_ready=1",(m['id'],))
        active=current(db,u['id'])
        if active and active['state']=='active':
            create_instant_booking(db,active,now)
    elif action=='leave':
        m=current(db,u['id'])
        if m: end(db,m)
        db.execute('DELETE FROM instant_queue WHERE user_id=?',(u['id'],))
    return snapshot(db,u),None
