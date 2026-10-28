"""Opt-in instant matching in the isolated review DB; no hosted DB or money."""
import secrets
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
    ''')


def eligible(db, u, now):
    if not u or u['role'] not in ('learner', 'partner', 'teacher'):
        return False
    if u['role'] != 'learner' and not u['approved']:
        return False
    return not db.execute("""SELECT 1 FROM bookings b JOIN slots s ON s.id=b.slot_id
      WHERE (b.learner_id=? OR b.teacher_id=?) AND
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
        learner=db.execute('SELECT role FROM users WHERE id=?',(m['learner_id'],)).fetchone()
        partner=db.execute('SELECT role FROM users WHERE id=?',(m['partner_id'],)).fetchone()
        roles_ok=learner and learner['role']=='learner' and partner and partner['role'] in ('partner','teacher')
        if live != 2 or not roles_ok or (m['state']=='offered' and m['created']+OFFER_TTL<=now):
            end(db, m)


def end(db, m):
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
             'instantEligible':b['status'] not in ('test_paid','in_class')}
            for b in rows]


def transaction_event_contract(booking_id, event_id, event_type):
    """Contract only: consumer may persist after authorization; never emit money."""
    if event_type not in ('booking.created','booking.cancelled',
                          'lesson.started','lesson.completed'):
        raise server.Error('지원하지 않는 거래 이벤트',400)
    if not isinstance(booking_id,str) or not booking_id or not isinstance(event_id,str) or not event_id:
        raise server.Error('거래 이벤트 식별자 필요',400)
    return {'version':1,'bookingId':booking_id,'eventId':event_id,
            'type':event_type,'paymentExecuted':False}

def route(handler, db, path, data):
    u=handler.user(db)
    action=path.removeprefix('/api/instant/')
    allowed={'reservations':'GET','status':'GET','join':'POST','heartbeat':'POST','ready':'POST','leave':'POST'}
    if action not in allowed: raise server.Error('페이지 없음',404)
    if handler.command!=allowed[action]: raise server.Error('지원하지 않는 요청',405)
    now=time.time()
    cleanup(db,now)
    if action=='reservations':
        return {'reservations':reservation_snapshot(db,u['id'])},None
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
    elif action=='leave':
        m=current(db,u['id'])
        if m: end(db,m)
        db.execute('DELETE FROM instant_queue WHERE user_id=?',(u['id'],))
    return snapshot(db,u),None
