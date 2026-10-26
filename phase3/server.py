#!/usr/bin/env python3
"""Isolated local multi-user TEST backend. No payment processor or live DB writes."""
import argparse
import datetime as dt
import hashlib
import hmac
import http.cookies
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs

ROOT = Path(__file__).resolve().parent
DB_PATH = os.environ.get('HS_PHASE3_DB', '/tmp/hangeul-swipji-phase3-test.sqlite3')
MAX_BODY = 65536

class Error(Exception):
    def __init__(self, message, status=400): self.message, self.status = message, status

def connect():
    db = sqlite3.connect(DB_PATH, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    return db

def init_db():
    with connect() as db: db.executescript((ROOT / 'schema.sql').read_text())
    try: os.chmod(DB_PATH, 0o600)
    except OSError: pass

def ident(): return secrets.token_hex(16)
def hash_password(password):
    salt = secrets.token_bytes(16)
    return salt.hex() + ':' + hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1).hex()
def password_ok(password, stored):
    salt, expected = stored.split(':')
    actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return hmac.compare_digest(actual, expected)
def text(value, maximum=1000):
    if not isinstance(value, str) or len(value.strip()) > maximum: raise Error('잘못된 텍스트입니다')
    return value.strip()
def audit(db, actor, action, entity, detail=''):
    db.execute('INSERT INTO audit(actor,action,entity,detail,created_at) VALUES(?,?,?,?,?)', (actor,action,entity,detail,time.time()))
def public_user(row): return {k:row[k] for k in ('id','nickname','role','approved','languages','timezone','specialty','price','level','qualifications','referral_code')}
def units():
    path = ROOT / 'content.json'
    data = json.loads(path.read_text()) if path.exists() else []
    return data.get('units', []) if isinstance(data,dict) else data
def get_unit(uid):
    found = next((u for u in units() if str(u['id']) == str(uid)), None)
    if found is None: raise Error('단원이 없습니다',404)
    return found
def stamp(value):
    try:
        if isinstance(value,(int,float)): return float(value)
        parsed = dt.datetime.fromisoformat(value.replace('Z','+00:00'))
        if parsed.tzinfo is None: raise ValueError()
        return parsed.timestamp()
    except (ValueError,AttributeError,TypeError): raise Error('시간대가 포함된 ISO 일시가 필요합니다')
def money(price, commission=2000, referral=300, processor=300, tax=0, refund=300):
    # basis points; policy scenarios only, never a legally approved production tariff.
    values=(price,commission,referral,processor,tax,refund)
    if any(isinstance(x,bool) or not isinstance(x,int) or x<0 for x in values) or any(x>10000 for x in values[1:]): raise Error('잘못된 수익 시나리오')
    teacher = price * (10000-commission)//10000
    reward = price*referral//10000
    fee = price*processor//10000
    tax_reserve=price*tax//10000; refund_reserve=price*refund//10000
    return dict(gross=price,teacher=teacher,referral=reward,processor=fee,tax=tax_reserve,refund=refund_reserve,platform=price-teacher-reward-fee-tax_reserve-refund_reserve)

class Handler(BaseHTTPRequestHandler):
    server_version = 'HSPhase3Test'
    def log_message(self,*args): pass
    def send(self, status, value, cookie=None):
        body = json.dumps(dict(mode='test', **value),ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        if cookie: self.send_header('Set-Cookie',cookie)
        self.send_header('Content-Length',str(len(body)))
        self.end_headers(); self.wfile.write(body)
    def do_GET(self): self.handle_request()
    def do_POST(self): self.handle_request()
    def do_PUT(self): self.handle_request()
    def handle_request(self):
        db=None
        try:
            host = self.headers.get('Host','')
            if host not in (f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'):
                raise Error('허용되지 않은 호스트',403)
            path = urlsplit(self.path).path
            if not path.startswith('/api/'):
                if self.command!='GET': raise Error('지원하지 않는 요청',405)
                return self.static(path)
            if self.command!='GET':
                origin=self.headers.get('Origin')
                if origin and origin != f'http://{host}': raise Error('다른 출처 요청 거부',403)
                if self.headers.get('Content-Type','').split(';')[0] != 'application/json': raise Error('JSON 요청이 필요합니다',415)
                size=int(self.headers.get('Content-Length','0'))
                if size<0 or size>MAX_BODY: raise Error('요청이 너무 큽니다',413)
                try: data=json.loads(self.rfile.read(size) or b'{}')
                except (ValueError,UnicodeDecodeError): raise Error('잘못된 JSON')
                if not isinstance(data,dict): raise Error('JSON 객체가 필요합니다')
            else: data={}
            db=connect(); db.execute('BEGIN IMMEDIATE')
            result,cookie=self.route(db,path,data,parse_qs(urlsplit(self.path).query))
            db.commit(); self.send(200,result,cookie)
        except Error as e:
            if db: db.rollback()
            self.send(e.status,dict(error=e.message))
        except sqlite3.IntegrityError:
            if db: db.rollback()
            self.send(409,dict(error='중복되거나 충돌하는 요청입니다'))
        except (ValueError,TypeError,KeyError):
            if db: db.rollback()
            self.send(400,dict(error='필수 입력값 또는 형식을 확인하세요'))
        except Exception:
            if db: db.rollback()
            self.send(500,dict(error='서버 오류입니다. 운영자 로그를 확인하세요'))
        finally:
            if db: db.close()
    def static(self,path):
        name=path.lstrip('/') or 'index.html'
        allowed={'index.html':'text/html','app.js':'text/javascript','style.css':'text/css',**{name:'text/plain' for name in ('POLICIES-DRAFT.md','LEGAL-REVIEW.md','REFERENCE-RESEARCH.md','CURRICULUM.md','README.md','BUSINESS.md','SECURITY-REVIEW.md','SUPABASE-INTEGRATION.md','STATUS.md')}}
        if name not in allowed or not (ROOT/name).exists(): raise Error('페이지 없음',404)
        body=(ROOT/name).read_bytes(); self.send_response(200)
        self.send_header('Content-Type',allowed[name]+'; charset=utf-8')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; frame-src https://meet.jit.si; connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
    def user(self,db):
        try:
            cookies=http.cookies.SimpleCookie(self.headers.get('Cookie',''))
            token=cookies['hs3'].value
        except (KeyError,http.cookies.CookieError): raise Error('로그인이 필요합니다',401)
        row=db.execute('SELECT u.* FROM users u JOIN sessions s ON u.id=s.user_id WHERE s.token=? AND s.expires>?',(hashlib.sha256(token.encode()).hexdigest(),time.time())).fetchone()
        if not row: raise Error('로그인이 필요합니다',401)
        return row
    def admin(self,db):
        u=self.user(db)
        if u['role']!='admin': raise Error('관리자 권한이 필요합니다',403)
        return u
    def session(self,db,uid):
        token=secrets.token_urlsafe(32)
        db.execute('INSERT INTO sessions VALUES(?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),uid,time.time()+28800))
        return f'hs3={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800'
    def booking(self,db,bid,u):
        b=db.execute('SELECT * FROM bookings WHERE id=?',(bid,)).fetchone()
        if not b: raise Error('예약이 없습니다',404)
        if u['role']!='admin' and u['id'] not in (b['learner_id'],b['teacher_id']): raise Error('접근 권한이 없습니다',403)
        return b
    def route(self,db,path,d,q):
        method=self.command
        if method=='POST' and path=='/api/register':
            email=text(d.get('email',''),254).lower(); password=d.get('password',''); nickname=text(d.get('nickname',''),40); role=d.get('role')
            if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) or not isinstance(password,str) or not 12<=len(password)<=128 or len(nickname)<2 or role not in ('learner','partner','teacher') or d.get('adultConsent') is not True: raise Error('이메일·12자 이상 비밀번호·이름·성인 동의를 확인하세요')
            rid=None
            if d.get('referralCode'):
                ref=db.execute('SELECT id FROM users WHERE referral_code=?',(text(d['referralCode'],40),)).fetchone()
                if not ref: raise Error('추천코드가 없습니다')
                rid=ref['id']
            uid=ident(); code=secrets.token_hex(5)
            db.execute('INSERT INTO users(id,email,password,nickname,role,referral_code,referred_by,created_at) VALUES(?,?,?,?,?,?,?,?)',(uid,email,hash_password(password),nickname,role,code,rid,time.time()))
            audit(db,uid,'register',uid,'adult-test-consent')
            return {'user':public_user(db.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone())},self.session(db,uid)
        if method=='POST' and path=='/api/login':
            # bounded per-IP failures, held in memory; local test server only.
            key=self.client_address[0]; attempts=self.server.failures.setdefault(key,[]); now=time.time(); attempts[:]=[t for t in attempts if t>now-300]
            if len(attempts)>=12: raise Error('로그인 시도가 많습니다. 잠시 후 다시 시도하세요',429)
            u=db.execute('SELECT * FROM users WHERE email=?',(text(d.get('email',''),254).lower(),)).fetchone()
            pw=d.get('password','')
            if not isinstance(pw,str) or len(pw)>128 or not u or not password_ok(pw,u['password']):
                attempts.append(now); raise Error('로그인 정보를 확인하세요',401)
            attempts.clear(); audit(db,u['id'],'login',u['id'])
            return {'user':public_user(u)},self.session(db,u['id'])
        if method=='GET' and path=='/api/units': return {'units':[{k:v for k,v in x.items() if k!='teacherGuide'} for x in units()]},None
        if method=='GET' and path.startswith('/api/units/'):
            unit=dict(get_unit(path.split('/')[-1])); u=self.user(db)
            if u['role']=='learner': unit.pop('teacherGuide',None)
            return {'unit':unit},None
        if method=='GET' and path=='/api/scenarios':
            price=int(q.get('price',['20000'])[0]); tax=int(q.get('taxBps',['0'])[0]); refund=int(q.get('refundBps',['300'])[0])
            if not 1000<=price<=1000000: raise Error('가격 범위를 확인하세요')
            return {'currency':'KRW','basis':'hypothetical-test-only','scenarios':[dict(commissionBps=c,referralBps=r,processorBps=300,refundReserveBps=refund,taxReserveBps=tax,**money(price,c,r,300,tax,refund)) for c in (1500,2000,2500) for r in (0,300,500)],'note':'PG 3%·환불 충당·세금 충당은 가정값입니다. 법정 세율·확정 요율·순이익이 아니며 고정비·실제 세금은 별도입니다.'},None
        u=self.user(db); uid=u['id']
        if method=='POST' and path=='/api/logout':
            cookie=http.cookies.SimpleCookie(self.headers.get('Cookie',''))
            db.execute('DELETE FROM sessions WHERE token=?',(hashlib.sha256(cookie['hs3'].value.encode()).hexdigest(),))
            return {'ok':True},'hs3=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'
        if method=='GET' and path=='/api/me': return {'user':public_user(u)},None
        if method=='PUT' and path=='/api/profile':
            profile={k:text(d.get(k,u[k]),2000 if k=='qualifications' else 200) for k in ('nickname','languages','timezone','specialty','level','qualifications')}
            price=d.get('price',u['price'])
            if isinstance(price,bool) or not isinstance(price,int) or not 1000<=price<=1000000 or len(profile['nickname'])<2: raise Error('가격 또는 이름이 잘못되었습니다')
            db.execute('UPDATE users SET nickname=?,languages=?,timezone=?,specialty=?,level=?,qualifications=?,price=?,approved=CASE WHEN role IN (\'partner\',\'teacher\') THEN 0 ELSE approved END WHERE id=?',(*profile.values(),price,uid))
            audit(db,uid,'profile_update',uid,'provider reapproval required')
            return {'user':public_user(db.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone())},None
        if method=='GET' and path=='/api/teachers':
            rows=[public_user(x) for x in db.execute("SELECT * FROM users WHERE approved=1 AND role IN ('teacher','partner') ORDER BY nickname")]
            for field,param in [('role','role'),('languages','language'),('level','level')]:
                if q.get(param): rows=[r for r in rows if q[param][0].lower() in str(r[field]).lower()]
            if q.get('maxPrice'): rows=[r for r in rows if r['price']<=int(q['maxPrice'][0])]
            if q.get('q'): rows=[r for r in rows if q['q'][0].lower() in (r['nickname']+' '+r['specialty']).lower()]
            for r in rows:
                r.pop('referral_code',None)
                avg=db.execute("SELECT avg(rating),count(rating) FROM bookings WHERE teacher_id=? AND rating IS NOT NULL AND status IN ('completed','test_settled')",(r['id'],)).fetchone()
                r.update(rating=avg[0],reviewCount=avg[1],verification='local-test-review-only')
            return {'teachers':rows},None
        if path=='/api/availability':
            if method=='GET':
                tid=q.get('teacherId',[uid])[0]
                return {'slots':[dict(x) for x in db.execute("SELECT s.* FROM slots s JOIN users u ON u.id=s.teacher_id WHERE s.teacher_id=? AND u.approved=1 AND s.start>? AND NOT EXISTS(SELECT 1 FROM bookings b WHERE b.slot_id=s.id AND b.status NOT IN ('cancelled','refunded')) ORDER BY s.start",(tid,time.time()))]},None
            if method=='POST':
                if u['role'] not in ('partner','teacher') or not u['approved']: raise Error('승인된 수업 제공자만 가능합니다',403)
                start,end=stamp(d.get('start')),stamp(d.get('end'))
                if start<time.time() or not 300<=end-start<=7200: raise Error('미래의 5~120분 수업만 등록하세요')
                if db.execute('SELECT 1 FROM slots WHERE teacher_id=? AND start<? AND end>?',(uid,end,start)).fetchone(): raise Error('시간이 겹칩니다',409)
                sid=ident(); db.execute('INSERT INTO slots VALUES(?,?,?,?)',(sid,uid,start,end)); audit(db,uid,'availability',sid)
                return {'slotId':sid},None
        if path=='/api/bookings':
            if method=='GET':
                rows=[]
                for b in db.execute('SELECT * FROM bookings WHERE learner_id=? OR teacher_id=? ORDER BY created_at DESC',(uid,uid)):
                    v=dict(b); v.pop('room',None); v['attendance']=[dict(a) for a in db.execute('SELECT * FROM attendance WHERE booking_id=?',(b['id'],))]; v['slot']=dict(db.execute('SELECT * FROM slots WHERE id=?',(b['slot_id'],)).fetchone()); v['disputes']=[dict(x) for x in db.execute('SELECT * FROM disputes WHERE booking_id=?',(b['id'],))]; rows.append(v)
                return {'bookings':rows},None
            if method=='POST':
                if u['role']!='learner': raise Error('학습자만 예약할 수 있습니다',403)
                unit=get_unit(d.get('unitId')); slot=db.execute('SELECT s.*,u.price,u.approved,u.role FROM slots s JOIN users u ON s.teacher_id=u.id WHERE s.id=?',(d.get('slotId'),)).fetchone()
                if not slot or slot['teacher_id']!=d.get('teacherId') or slot['teacher_id']==uid or not slot['approved'] or slot['role'] not in ('teacher','partner') or slot['start']<=time.time(): raise Error('예약 가능한 일정이 아닙니다')
                if slot['end']-slot['start'] < int(unit.get('durationMinutes',30))*60: raise Error('단원 수업시간보다 일정이 짧습니다')
                if db.execute("SELECT 1 FROM bookings b JOIN slots s ON s.id=b.slot_id WHERE b.learner_id=? AND b.status NOT IN ('cancelled','refunded') AND s.start<? AND s.end>?",(uid,slot['end'],slot['start'])).fetchone(): raise Error('학습자 일정이 겹칩니다',409)
                ref=u['referred_by']
                if d.get('referralCode'):
                    r=db.execute('SELECT id FROM users WHERE referral_code=?',(text(d['referralCode'],40),)).fetchone()
                    if not r: raise Error('추천코드가 없습니다')
                    if ref and ref!=r['id']: raise Error('가입 시 추천인을 변경할 수 없습니다')
                    ref=r['id']
                if ref in (uid,slot['teacher_id']): raise Error('본인 또는 거래 상대 추천은 보상 대상이 아닙니다')
                bid=ident(); db.execute('INSERT INTO bookings(id,learner_id,teacher_id,slot_id,unit_id,price,referrer_id,room,created_at) VALUES(?,?,?,?,?,?,?,?,?)',(bid,uid,slot['teacher_id'],slot['id'],str(unit['id']),slot['price'],ref,'hs-test-'+secrets.token_urlsafe(24),time.time())); audit(db,uid,'booking',bid)
                db.execute('INSERT INTO rate_snapshots(booking_id,commission_bps,referral_bps,processor_bps,refund_bps,tax_bps) VALUES(?,?,?,?,?,?)',(bid,2000,300 if ref else 0,300,300,0))
                content=json.dumps(unit,ensure_ascii=False,sort_keys=True); db.execute('INSERT INTO unit_snapshots VALUES(?,?,?)',(bid,content,hashlib.sha256(content.encode()).hexdigest()))
                return {'bookingId':bid},None
        snapshot_match=re.fullmatch('/api/bookings/([0-9a-f]+)/unit',path)
        if snapshot_match and method=='GET':
            b=self.booking(db,snapshot_match[1],u); snapshot=db.execute('SELECT * FROM unit_snapshots WHERE booking_id=?',(b['id'],)).fetchone(); unit=json.loads(snapshot['content'])
            if uid==b['learner_id']: unit.pop('teacherGuide',None)
            return {'unit':unit,'sha256':snapshot['sha256'],'version':'booking-snapshot'},None
        m=re.fullmatch('/api/bookings/([0-9a-f]+)/([a-z-]+)',path)
        if m and method=='POST':
            bid,action=m.groups(); b=self.booking(db,bid,u)
            if u['role']=='admin': raise Error('수업 참가자만 수행할 수 있습니다',403)
            if action=='pay-test':
                if uid!=b['learner_id']: raise Error('학습자만 가능합니다',403)
                if b['status']=='reserved':
                    db.execute("UPDATE bookings SET status='test_paid' WHERE id=?",(bid,)); db.execute('INSERT INTO ledger(booking_id,kind,amount,beneficiary,created_at) VALUES(?,?,?,?,?)',(bid,'test_charge',b['price'],uid,time.time())); audit(db,uid,'test_charge',bid)
                elif b['status'] not in ('test_paid','in_class','completed','test_settled'): raise Error('테스트 결제 불가 상태',409)
                return {'ok':True,'payment':'simulated-test-only','chargedRealMoney':False},None
            if action in ('join','attendance'):
                if b['status'] not in ('test_paid','in_class'): raise Error('테스트 결제 후 입장할 수 있습니다',409)
                slot=db.execute('SELECT * FROM slots WHERE id=?',(b['slot_id'],)).fetchone(); now=time.time()
                if not slot['start']-300<=now<=slot['end']+300: raise Error('수업 시간에만 입장할 수 있습니다',409)
                previous=db.execute('SELECT * FROM attendance WHERE booking_id=? AND user_id=?',(bid,uid)).fetchone()
                if previous:
                    # Heartbeat interval <=90s is counted; leaving a tab idle does not grant elapsed hours.
                    delta=max(0,now-previous['last_seen']); increment=max(0,min(now,slot['end'])-max(previous['last_seen'],slot['start'])) if delta<=90 else 0
                    db.execute('UPDATE attendance SET last_seen=?,seconds=seconds+? WHERE booking_id=? AND user_id=?',(now,increment,bid,uid))
                else: db.execute('INSERT INTO attendance(booking_id,user_id,joined,last_seen) VALUES(?,?,?,?)',(bid,uid,now,now))
                db.execute("UPDATE bookings SET status='in_class' WHERE id=?",(bid,)); audit(db,uid,action,bid)
                return {'roomUrl':'https://meet.jit.si/'+b['room'],'unitId':b['unit_id'],'warning':'공개 Jitsi 테스트 방은 인증된 비공개 수업이 아닙니다. 녹화 금지.'},None
            if action=='complete':
                if b['status'] in ('completed','test_settled'): return {'ok':True,'status':b['status']},None
                if b['status']!='in_class': raise Error('진행 중 수업만 확인할 수 있습니다',409)
                attendance=db.execute('SELECT * FROM attendance WHERE booking_id=? AND user_id=?',(bid,uid)).fetchone()
                duration=int(json.loads(db.execute('SELECT content FROM unit_snapshots WHERE booking_id=?',(bid,)).fetchone()[0]).get('durationMinutes',30))*60
                if not attendance or attendance['seconds']<duration: raise Error('서버 확인 수업시간이 부족합니다',409)
                db.execute('UPDATE attendance SET confirmed=1 WHERE booking_id=? AND user_id=?',(bid,uid))
                count=db.execute('SELECT count(*) FROM attendance WHERE booking_id=? AND confirmed=1 AND seconds>=?',(bid,duration)).fetchone()[0]
                if count==2 and b['evidence'] and not db.execute("SELECT 1 FROM disputes WHERE booking_id=? AND status='open'",(bid,)).fetchone(): db.execute("UPDATE bookings SET status='completed' WHERE id=?",(bid,))
                audit(db,uid,'completion_confirmation',bid)
                return {'ok':True,'status':db.execute('SELECT status FROM bookings WHERE id=?',(bid,)).fetchone()[0]},None
            if action=='homework':
                if uid!=b['learner_id'] or b['status'] in ('cancelled','refunded'): raise Error('과제 제출 권한이 없습니다',403)
                value=text(d.get('text',''),10000)
                db.execute('UPDATE bookings SET homework=? WHERE id=?',(value,bid)); audit(db,uid,'homework',bid)
                return {'ok':True},None
            if action=='feedback':
                score=d.get('score')
                if uid!=b['teacher_id'] or not isinstance(score,int) or isinstance(score,bool) or not 0<=score<=100 or b['status'] not in ('in_class','completed','test_settled'): raise Error('평가 권한 또는 점수를 확인하세요',403)
                db.execute('UPDATE bookings SET feedback=?,score=? WHERE id=?',(text(d.get('text',''),10000),score,bid)); audit(db,uid,'feedback',bid)
                return {'ok':True},None
            if action=='review':
                rating=d.get('rating')
                if uid!=b['learner_id'] or b['status'] not in ('completed','test_settled') or not isinstance(rating,int) or isinstance(rating,bool) or not 1<=rating<=5: raise Error('완료된 수업 학습자만 후기 작성 가능',403)
                db.execute('UPDATE bookings SET review=?,rating=? WHERE id=?',(text(d.get('text',''),2000),rating,bid)); audit(db,uid,'review',bid)
                return {'ok':True},None
            if action=='dispute':
                category=d.get('category','other'); reason=text(d.get('reason',''),5000)
                if len(reason)<10 or category not in ('teacher_no_show','learner_no_show','short_lesson','content','connection','false_attendance','false_completion','referral_fraud','refund','review','other'): raise Error('신고 유형과 10자 이상 증빙 설명이 필요합니다')
                if b['status'] in ('refunded','cancelled'): raise Error('종료된 예약에는 이의신청을 작성하세요',409)
                did=ident(); db.execute('INSERT INTO disputes(id,booking_id,reporter_id,category,reason,created_at) VALUES(?,?,?,?,?,?)',(did,bid,uid,category,reason,time.time())); audit(db,uid,'dispute',did)
                return {'disputeId':did,'settlement':'held'},None
            if action=='appeal':
                reason=text(d.get('reason',''),5000); original=d.get('disputeId')
                case=db.execute("SELECT * FROM disputes WHERE id=? AND booking_id=? AND status='resolved'",(original,bid)).fetchone()
                if not case or len(reason)<10: raise Error('해결된 신고와 10자 이상 이의신청 근거 필요')
                if db.execute("SELECT 1 FROM disputes WHERE booking_id=? AND status='open'",(bid,)).fetchone(): raise Error('이미 조사 중인 신고가 있습니다',409)
                did=ident(); db.execute('INSERT INTO disputes(id,booking_id,reporter_id,category,reason,created_at) VALUES(?,?,?,?,?,?)',(did,bid,uid,'appeal','Original '+original+': '+reason,time.time())); audit(db,uid,'appeal',did,original)
                return {'disputeId':did,'settlement':'held'},None
            if action=='reschedule-consent':
                slot=db.execute('SELECT * FROM slots WHERE id=? AND teacher_id=?',(d.get('slotId'),b['teacher_id'])).fetchone()
                if not slot or slot['start']<=time.time() or b['status'] in ('completed','test_settled','refunded','cancelled'): raise Error('대체 일정 또는 수업 상태를 확인하세요',409)
                db.execute('INSERT INTO reschedule_consents VALUES(?,?,?,?) ON CONFLICT(booking_id,user_id) DO UPDATE SET slot_id=excluded.slot_id,created_at=excluded.created_at',(bid,uid,slot['id'],time.time()))
                audit(db,uid,'reschedule_consent',bid,slot['id'])
                return {'ok':True,'slotId':slot['id']},None
            if action=='cancel':
                if b['status']=='cancelled': return {'ok':True},None
                if b['status']!='reserved': raise Error('테스트 결제 후에는 신고·환불 심사를 요청하세요',409)
                db.execute("UPDATE bookings SET status='cancelled' WHERE id=?",(bid,)); audit(db,uid,'cancel',bid)
                return {'ok':True},None
        if path.startswith('/api/admin'):
            admin=self.admin(db)
            if method=='GET' and path=='/api/admin':
                return {'users':[public_user(x) for x in db.execute('SELECT * FROM users')],'bookings':[dict(x) for x in db.execute('SELECT * FROM bookings')],'disputes':[dict(x) for x in db.execute('SELECT * FROM disputes')],'ledger':[dict(x) for x in db.execute('SELECT * FROM ledger')],'audit':[dict(x) for x in db.execute('SELECT * FROM audit ORDER BY id DESC LIMIT 500')]},None
            if method=='POST' and path=='/api/admin/verify':
                reason=text(d.get('reason',''),2000)
                if len(reason)<10 or not isinstance(d.get('approved'),bool): raise Error('승인 판단 근거 10자 이상 필요')
                target=db.execute('SELECT * FROM users WHERE id=?',(d.get('userId'),)).fetchone()
                if not target or target['role'] not in ('teacher','partner'): raise Error('강사 또는 파트너를 선택하세요')
                db.execute('UPDATE users SET approved=? WHERE id=?',(int(d['approved']),target['id'])); audit(db,uid,'test_provider_review',target['id'],reason)
                return {'ok':True,'verification':'local-test-only; real identity not verified'},None
            if method=='POST' and path=='/api/admin/evidence':
                b=self.booking(db,d.get('bookingId'),u); reason=text(d.get('reason',''),2000)
                if len(reason)<10 or b['status']!='in_class': raise Error('진행 중 수업과 10자 이상 근거 필요')
                db.execute('UPDATE bookings SET evidence=? WHERE id=?',(reason,b['id'])); audit(db,uid,'test_evidence_review',b['id'],reason)
                # Does not silently complete: participants repeat completion after evidence review.
                return {'ok':True},None
            if method=='POST' and path=='/api/admin/settle':
                b=self.booking(db,d.get('bookingId'),u)
                if db.execute("SELECT 1 FROM disputes WHERE booking_id=? AND status='open'",(b['id'],)).fetchone(): raise Error('분쟁 조사 중 정산 보류',409)
                if b['status']=='test_settled': return {'ok':True,'realPayout':False},None
                if b['status']!='completed': raise Error('수업 완료 확인 전 정산 불가',409)
                rates=db.execute('SELECT * FROM rate_snapshots WHERE booking_id=?',(b['id'],)).fetchone()
                split=money(b['price'],rates['commission_bps'],rates['referral_bps'],rates['processor_bps'],rates['tax_bps'],rates['refund_bps'])
                for kind,amount,who in [('test_teacher_accrual',split['teacher'],b['teacher_id']),('test_referral_accrual',split['referral'],b['referrer_id']),('test_platform_contribution',split['platform'],None),('test_processor_cost',split['processor'],None),('test_refund_reserve',split['refund'],None),('test_tax_reserve',split['tax'],None)]:
                    db.execute('INSERT INTO ledger(booking_id,kind,amount,beneficiary,created_at) VALUES(?,?,?,?,?)',(b['id'],kind,amount,who,time.time()))
                db.execute("UPDATE bookings SET status='test_settled' WHERE id=?",(b['id'],)); audit(db,uid,'test_settlement',b['id'],'no real payout')
                return {'ok':True,'realPayout':False,'split':split},None
            m=re.fullmatch('/api/admin/disputes/([0-9a-f]+)',path)
            if method=='POST' and m:
                case=db.execute('SELECT * FROM disputes WHERE id=?',(m[1],)).fetchone(); reason=text(d.get('reason',''),5000); decision=d.get('decision')
                if not case or case['status']!='open' or len(reason)<10 or decision not in ('refund','dismiss','reschedule'): raise Error('미처리 신고와 판단 근거를 확인하세요',409)
                b=self.booking(db,case['booking_id'],u)
                if decision=='refund':
                    # Only virtual ledger reversal. Never claw back real teacher compensation.
                    for entry in list(db.execute('SELECT * FROM ledger WHERE booking_id=?',(b['id'],))):
                        if not entry['kind'].endswith('_reversal'):
                            db.execute('INSERT OR IGNORE INTO ledger(booking_id,kind,amount,beneficiary,created_at) VALUES(?,?,?,?,?)',(b['id'],entry['kind']+'_reversal',-entry['amount'],entry['beneficiary'],time.time()))
                    db.execute("UPDATE bookings SET status='refunded' WHERE id=?",(b['id'],))
                elif decision=='reschedule':
                    # Test replacement retains payment/rates/content, explicit mutual consent required.
                    consents=db.execute('SELECT count(*) FROM reschedule_consents WHERE booking_id=? AND slot_id=? AND user_id IN (?,?) AND created_at>?',(b['id'],d.get('slotId'),b['learner_id'],b['teacher_id'],time.time()-86400)).fetchone()[0]
                    if consents!=2: raise Error('재수업에는 양측이 직접 저장한 동일 일정 동의가 필요합니다')
                    if b['status'] in ('completed','test_settled','refunded','cancelled'): raise Error('완료·정산된 수업 보수는 자동 조정하지 않습니다',409)
                    replacement=db.execute('SELECT * FROM slots WHERE id=? AND teacher_id=?',(d.get('slotId'),b['teacher_id'])).fetchone()
                    if not replacement or replacement['start']<=time.time(): raise Error('같은 강사의 미래 대체 일정을 선택하세요')
                    duration=int(json.loads(db.execute('SELECT content FROM unit_snapshots WHERE booking_id=?',(b['id'],)).fetchone()[0]).get('durationMinutes',30))*60
                    if replacement['end']-replacement['start']<duration: raise Error('대체 일정 수업시간 부족')
                    if db.execute("SELECT 1 FROM bookings x JOIN slots s ON x.slot_id=s.id WHERE x.id<>? AND x.learner_id=? AND x.status NOT IN ('cancelled','refunded') AND s.start<? AND s.end>?",(b['id'],b['learner_id'],replacement['end'],replacement['start'])).fetchone(): raise Error('학습자 대체 일정 충돌',409)
                    audit(db,uid,'reschedule_previous_slot',b['id'],json.dumps({'slotId':b['slot_id'],'replacementSlotId':replacement['id'],'consentEvidence':reason,'attendance':[dict(x) for x in db.execute('SELECT * FROM attendance WHERE booking_id=?',(b['id'],))]}))
                    db.execute('DELETE FROM attendance WHERE booking_id=?',(b['id'],))
                    db.execute('DELETE FROM reschedule_consents WHERE booking_id=?',(b['id'],))
                    db.execute("UPDATE bookings SET slot_id=?,status=CASE WHEN status='reserved' THEN 'reserved' ELSE 'test_paid' END,evidence='' WHERE id=?",(replacement['id'],b['id']))
                db.execute("UPDATE disputes SET status='resolved',decision=?,resolution=? WHERE id=?",(decision,reason,case['id'])); audit(db,uid,'dispute_'+decision,case['id'],reason)
                return {'ok':True,'realRefund':False},None
        raise Error('지원하지 않는 API 또는 요청 방식입니다',404)

def create_admin(email,password):
    if len(password)<16: raise ValueError('관리자 비밀번호 16자 이상 필요')
    with connect() as db:
        uid=ident(); db.execute('INSERT INTO users(id,email,password,nickname,role,referral_code,created_at) VALUES(?,?,?,?,?,?,?)',(uid,email.lower(),hash_password(password),'테스트 관리자','admin',secrets.token_hex(5),time.time())); audit(db,uid,'admin_bootstrap',uid)

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--port',type=int,default=8765); parser.add_argument('--create-admin',metavar='EMAIL'); args=parser.parse_args(); init_db()
    if args.create_admin:
        create_admin(args.create_admin,os.environ.get('HS_PHASE3_ADMIN_PASSWORD','')); print('Local test admin created.'); return
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler); server.failures={}
    print(f'LOCAL TEST ONLY http://127.0.0.1:{args.port} — no real charges or payouts',flush=True)
    server.serve_forever()
if __name__=='__main__': main()
