#!/usr/bin/env python3
"""Isolated local multi-user TEST backend. No payment processor or live DB writes."""
import argparse
import datetime as dt
import hashlib
import hmac
import http.cookies
import json
import math
import learning
import payments
import refund_ledger
import privacy_requests
import policy_consents
import support_requests
import session_evidence
import supabase_auth
import teacher_alerts
import availability
import os
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import re
import secrets
import sqlite3
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs, unquote

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
    with connect() as db:
        db.executescript((ROOT / 'schema.sql').read_text())
        teacher_alerts.initialize(db)
        availability.initialize(db)
        refund_ledger.initialize(db)
        privacy_requests.initialize(db)
        policy_consents.initialize(db)
        support_requests.initialize(db)
        session_evidence.initialize(db)
        learning.initialize_shares(db)
        db.execute('''CREATE TABLE IF NOT EXISTS dispute_statements (
            id TEXT PRIMARY KEY,
            dispute_id TEXT NOT NULL REFERENCES disputes(id),
            author_id TEXT NOT NULL REFERENCES users(id),
            role TEXT NOT NULL,
            text TEXT NOT NULL CHECK(length(text) BETWEEN 10 AND 5000),
            created_at REAL NOT NULL
        )''')
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
def public_user(row): return dict({k:row[k] for k in ('id','nickname','role','approved','languages','timezone','specialty','price','level','qualifications','referral_code')}, qualificationVerified=False)
def units():
    path = ROOT / 'content.json'
    data = json.loads(path.read_text()) if path.exists() else []
    original=data.get('units', []) if isinstance(data,dict) else data
    extra=json.loads((ROOT/'content-expansion.json').read_text())['units']+json.loads((ROOT/'content-remaining72.json').read_text())['units']
    return [learning.decorate(u) for u in original+extra]
def get_unit(uid):
    found = next((u for u in units() if str(u['id']) == str(uid)), None)
    if found is None: raise Error('단원이 없습니다',404)
    return found
def stamp(value):
    try:
        if isinstance(value,bool): raise ValueError()
        if isinstance(value,(int,float)):
            if not math.isfinite(value): raise ValueError()
            return float(value)
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

def remaining_refund(db, bid):
    entries=list(db.execute('SELECT * FROM ledger WHERE booking_id=?',(bid,)))
    originals=[row for row in entries if not row['kind'].endswith('_reversal') and '_reversal__refund_' not in row['kind']]
    used={row['original_id']:row['used'] for row in db.execute('SELECT original_id,SUM(amount) AS used FROM local_refund_adjustments WHERE booking_id=? GROUP BY original_id',(bid,))}
    allocations={}
    for entry in originals:
        peers=[row for row in originals if row['kind']==entry['kind']]
        reversed_amount=sum(abs(row['amount']) for row in entries if (row['kind'].endswith('_reversal') or '_reversal__refund_' in row['kind']) and (row['kind'].split('_reversal__refund_',1)[0] if '_reversal__refund_' in row['kind'] else row['kind'][:-len('_reversal')].split('__refund_',1)[0])==entry['kind'])
        legacy=reversed_amount-sum(used.get(str(row['id']),0) for row in peers)
        if legacy<0 or (legacy and len(peers)!=1):
            raise Error('기존 역분개의 원본 연결 확인이 필요합니다',409)
        remaining=abs(entry['amount'])-used.get(str(entry['id']),0)-legacy
        if remaining<0: raise Error('원본 항목의 누적 역분개 한도를 초과합니다',409)
        if remaining: allocations[str(entry['id'])]=remaining
    amount=sum(allocations.get(str(row['id']),0) for row in originals if row['kind']=='test_charge')
    return amount,allocations

def expire_holds(db):
    for b in list(db.execute("SELECT b.id FROM bookings b JOIN slots s ON s.id=b.slot_id WHERE b.status='reserved' AND (b.created_at+900<=? OR s.start<=?)",(time.time(),time.time()))):
        db.execute("UPDATE bookings SET status='expired' WHERE id=?",(b['id'],))
        audit(db,'system','unpaid_hold_expired',b['id'],'15 minute hold or lesson start reached')

def shared_seconds(db,bid):
    b=db.execute('SELECT learner_id,teacher_id FROM bookings WHERE id=?',(bid,)).fetchone()
    intervals=[]
    for uid in (b['learner_id'],b['teacher_id']):
        merged=[]
        for row in db.execute('SELECT start,end FROM attendance_intervals WHERE booking_id=? AND user_id=? ORDER BY start',(bid,uid)):
            if merged and row['start']<=merged[-1][1]: merged[-1][1]=max(merged[-1][1],row['end'])
            else: merged.append([row['start'],row['end']])
        intervals.append(merged)
    return sum(max(0,min(a[1],b[1])-max(a[0],b[0])) for a in intervals[0] for b in intervals[1])

def participant_events(db,bid,uid=None,sid=None):
    records=[]
    for row in db.execute("SELECT actor,action,detail FROM audit WHERE entity=? AND action IN ('participant_leave','participant_rejoin') ORDER BY id",(bid,)):
        detail=json.loads(row['detail'])
        if uid is not None and row['actor']!=uid: continue
        if sid is not None and detail['slotId']!=sid: continue
        records.append(dict(detail,actor=row['actor'],action=row['action']))
    return records

class Handler(BaseHTTPRequestHandler):
    server_version = 'HSPhase3Test'
    def log_message(self,*args): pass
    def send(self, status, value, cookie=None):
        body = json.dumps(dict(mode='test', **value),ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        if cookie:
            if getattr(self.server,'secure_cookies',False): cookie += '; Secure'
            self.send_header('Set-Cookie',cookie)
        self.send_header('Content-Length',str(len(body)))
        self.end_headers(); self.wfile.write(body)
    def do_GET(self): self.handle_request()
    def do_POST(self): self.handle_request()
    def do_PUT(self): self.handle_request()
    def check_request_context(self):
        # Default remains loopback-only. The separate staging launcher overrides this.
        host = self.headers.get('Host','')
        if host not in (f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'):
            raise Error('허용되지 않은 호스트',403)
        if self.command!='GET':
            origin=self.headers.get('Origin')
            if origin and origin != f'http://{host}': raise Error('다른 출처 요청 거부',403)
    def handle_request(self):
        db=None
        try:
            self.check_request_context()
            path = urlsplit(self.path).path
            if not path.startswith('/api/'):
                if self.command!='GET': raise Error('지원하지 않는 요청',405)
                return self.static(path)
            if self.command!='GET':
                if self.headers.get('Content-Type','').split(';')[0] != 'application/json': raise Error('JSON 요청이 필요합니다',415)
                size=int(self.headers.get('Content-Length','0'))
                if size<0 or size>MAX_BODY: raise Error('요청이 너무 큽니다',413)
                try:
                    self.raw_body=self.rfile.read(size) or b'{}'
                    data=json.loads(self.raw_body)
                except (ValueError,UnicodeDecodeError): raise Error('잘못된 JSON')
                if not isinstance(data,dict): raise Error('JSON 객체가 필요합니다')
            else: data={}
            db=connect(); db.execute('BEGIN IMMEDIATE')
            statement_request=re.fullmatch('/api/bookings/([0-9a-f]+)/disputes/([0-9a-f]+)/statements',path)
            content_report=self.command=='POST' and re.fullmatch('/api/bookings/([0-9a-f]+)/dispute',path) and data.get('category')=='content'
            observation_request=re.fullmatch('/api/bookings/([0-9a-f]+)/observations',path)
            if path not in ('/api/privacy/requests','/api/auth/revoke-sessions','/api/support/requests','/api/admin/support/requests','/api/payments/monthly') and not statement_request and not content_report and not observation_request: expire_holds(db)
            result,cookie=self.route(db,path,data,parse_qs(urlsplit(self.path).query,keep_blank_values=path in ('/api/admin/providers','/api/support/requests','/api/admin/support/requests','/api/payments/monthly')))
            db.commit(); self.send(200,result,cookie)
        except (payments.PaymentError,supabase_auth.AuthError) as e:
            if db: db.rollback()
            self.send(503 if isinstance(e,(payments.NotConfigured,supabase_auth.NotConfigured)) else 400,dict(error=str(e)))
        except (Error, availability.ScheduleError, refund_ledger.RefundError, policy_consents.PolicyConsentError) as e:
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
        # One canonical homepage; old studio/free URLs are compatibility redirects only.
        if path.startswith('/free/') and any(ord(c)<32 or 127<=ord(c)<=159 for c in unquote(self.path)):
            raise Error('잘못된 리디렉션 경로입니다',400)
        query=urlsplit(self.path).query
        if path.startswith('/free/') or path in ('/phase3/','/phase3/index.html','/teaching-platform.html'):
            destination=path[len('/free/'):] if path.startswith('/free/') else 'index.html'
            decoded=unquote(destination)
            if decoded.startswith('/') or '\\' in decoded or any(ord(c)<32 or 127<=ord(c)<=159 for c in decoded):
                raise Error('잘못된 리디렉션 경로입니다',400)
            destination='/' + (destination or 'index.html')
            if query: destination+='?'+query
            if not path.startswith('/free/'):destination+='#teaching-platform'
            self.send_response(302);self.send_header('Location',destination);self.send_header('Content-Length','0');self.end_headers();return
        name=unquote(path.lstrip('/')) or 'index.html'
        public=set(json.loads((ROOT/'free-public-files.json').read_text()))
        studio={'phase3/shell.html','phase3/app.js','phase3/style.css'}
        docs={f:f for f in ('POLICIES-DRAFT.md','LEGAL-REVIEW.md','REFERENCE-RESEARCH.md','CURRICULUM.md','README.md','BUSINESS.md','SECURITY-REVIEW.md','SUPABASE-INTEGRATION.md','STATUS.md','PAYMENTS.md','AUTH-TESTING.md','REVIEW-ROUND2.md')}
        if name in public or name in studio:
            target=(ROOT.parent/name).resolve()
        elif name in docs:target=(ROOT/name).resolve()
        else:raise Error('페이지 없음',404)
        if not target.is_relative_to(ROOT.parent) or not target.is_file():raise Error('페이지 없음',404)
        import mimetypes
        body=target.read_bytes();self.send_response(200)
        self.send_header('Content-Type',(mimetypes.guess_type(name)[0] or 'application/octet-stream') + ('; charset=utf-8' if target.suffix in ('.html','.js','.css','.json','.md') else ''))
        self.send_header('X-Content-Type-Options','nosniff');self.send_header('X-Frame-Options','DENY');self.send_header('Referrer-Policy','no-referrer');self.send_header('Cache-Control','no-cache')
        self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
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
        if method=='GET' and path=='/api/integrations':
            return {'supabaseTestConfigured':supabase_auth.configured(),'pgTestConfigured':payments.configured(),'realMoneyEnabled':False,'productionDatabaseUsed':False},None
        if method=='POST' and path=='/api/auth/supabase':
            if d.get('role') not in ('learner','partner','teacher') or d.get('adultConsent') is not True: raise Error('참여 유형과 성인 테스트 동의가 필요합니다')
            verified=supabase_auth.verify_user(d.get('token'))
            mapped=db.execute('SELECT user_id FROM external_identities WHERE project_ref=? AND subject=?',(verified['projectRef'],verified['subject'])).fetchone()
            if mapped: uid=mapped['user_id']
            else:
                nickname=text(d.get('nickname',''),40)
                if len(nickname)<2:raise Error('활동명은 2자 이상 필요합니다')
                if db.execute('SELECT 1 FROM users WHERE email=?',(verified['email'],)).fetchone():raise Error('같은 이메일의 로컬 계정이 있습니다. 자동 연결하지 않습니다',409)
                uid=ident()
                db.execute('INSERT INTO users(id,email,password,nickname,role,referral_code,created_at) VALUES(?,?,?,?,?,?,?)',(uid,verified['email'],hash_password(secrets.token_urlsafe(48)),nickname,d['role'],secrets.token_hex(5),time.time()))
                db.execute('INSERT INTO external_identities VALUES(?,?,?)',(verified['projectRef'],verified['subject'],uid))
            audit(db,uid,'supabase_test_identity_verified',uid,verified['projectRef'])
            return {'user':public_user(db.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()),'identityMode':'supabase-test-verified'},self.session(db,uid)
        if method=='POST' and path=='/api/payments/stripe-test/webhook':
            event=payments.verify_event(self.raw_body,self.headers.get('Stripe-Signature',''),os.environ.get('HS_STRIPE_TEST_WEBHOOK_SECRET',''))
            obj=event.get('data',{}).get('object',{})
            session=db.execute('SELECT * FROM payment_sessions WHERE session_id=?',(obj.get('id'),)).fetchone()
            if not session:raise Error('저장된 테스트 결제 세션이 없습니다',409)
            booking=db.execute('SELECT * FROM bookings WHERE id=?',(session['booking_id'],)).fetchone()
            verified=payments.validate_checkout_event(event,dict(booking),session['session_id'])
            prior=db.execute('SELECT * FROM provider_events WHERE event_id=?',(verified['event_id'],)).fetchone()
            if prior:
                if prior['booking_id']!=booking['id'] or prior['session_id']!=session['session_id']:raise Error('이벤트 재사용 충돌',409)
                return {'received':True,'duplicate':True,'realMoney':False},None
            db.execute('INSERT INTO provider_events VALUES(?,?,?,?)',(verified['event_id'],session['session_id'],booking['id'],time.time()))
            charged=db.execute("SELECT 1 FROM ledger WHERE booking_id=? AND kind='test_charge'",(booking['id'],)).fetchone()
            if booking['status']=='reserved' and not charged:
                db.execute("INSERT INTO ledger(booking_id,kind,amount,beneficiary,created_at) VALUES(?,?,?,?,?)",(booking['id'],'test_charge',booking['price'],booking['learner_id'],time.time()))
                db.execute("UPDATE bookings SET status='test_paid' WHERE id=?",(booking['id'],))
                audit(db,'stripe-test','provider_test_payment_confirmed',booking['id'],verified['event_id'])
            elif booking['status'] not in ('test_paid','in_class','completed','test_settled'):
                audit(db,'stripe-test','late_payment_review_required',booking['id'],verified['event_id'])
                return {'received':True,'heldForReview':True,'realMoney':False},None
            return {'received':True,'duplicate':bool(charged),'realMoney':False},None
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
            key=(self.client_address[0],text(d.get('email',''),254).lower()); attempts=self.server.failures.setdefault(key,[]); now=time.time(); attempts[:]=[t for t in attempts if t>now-300]
            ip_attempts=self.server.failures.setdefault(('aggregate',self.client_address[0]),[]); ip_attempts[:]=[t for t in ip_attempts if t>now-300]
            if len(attempts)>=12 or len(ip_attempts)>=60: raise Error('로그인 시도가 많습니다. 잠시 후 다시 시도하세요',429)
            u=db.execute('SELECT * FROM users WHERE email=?',(text(d.get('email',''),254).lower(),)).fetchone()
            pw=d.get('password','')
            if not isinstance(pw,str) or len(pw)>128 or not u or not password_ok(pw,u['password']):
                attempts.append(now);ip_attempts.append(now); raise Error('로그인 정보를 확인하세요',401)
            attempts.clear(); audit(db,u['id'],'login',u['id'])
            return {'user':public_user(u)},self.session(db,u['id'])
        if method=='GET' and path=='/api/curriculum': return learning.catalog(),None
        if method=='GET' and path=='/api/units': return {'units':[{k:v for k,v in x.items() if k in ('id','title','level','durationMinutes','objectives','learningPath')} for x in units()]},None
        if method=='GET' and path.startswith('/api/units/'):
            unit=dict(get_unit(path.split('/')[-1])); u=self.user(db)
            unit=learning.public_unit(unit,u['role']=='admin' or (u['role'] in ('teacher','partner') and bool(u['approved'])))
            return {'unit':unit},None
        if method=='GET' and path=='/api/scenarios':
            price=int(q.get('price',['20000'])[0]); tax=int(q.get('taxBps',['0'])[0]); refund=int(q.get('refundBps',['300'])[0])
            if not 1000<=price<=1000000: raise Error('가격 범위를 확인하세요')
            return {'currency':'KRW','basis':'hypothetical-test-only','scenarios':[dict(commissionBps=c,referralBps=r,processorBps=300,refundReserveBps=refund,taxReserveBps=tax,**money(price,c,r,300,tax,refund)) for c in (1500,2000,2500) for r in (0,300,500)],'note':'PG 3%·환불 충당·세금 충당은 가정값입니다. 법정 세율·확정 요율·순이익이 아니며 고정비·실제 세금은 별도입니다.'},None
        u=self.user(db); uid=u['id']
        if method=='GET' and path=='/api/payments/monthly':
            if u['role']!='learner': raise Error('학습자만 조회할 수 있습니다',403)
            if set(q)!={'month'} or len(q['month'])!=1:
                raise Error('month를 하나만 지정하세요',400)
            month=q['month'][0]
            if not re.fullmatch(r'[0-9]{4}-(0[1-9]|1[0-2])',month):
                raise Error('month는 YYYY-MM 형식이어야 합니다',400)
            year,number=map(int,month.split('-'))
            if not 1<=year<=9998: raise Error('연도는 0001~9998이어야 합니다',400)
            start=dt.datetime(year,number,1,tzinfo=dt.timezone.utc).timestamp()
            end=dt.datetime(year+1 if number==12 else year,1 if number==12 else number+1,1,tzinfo=dt.timezone.utc).timestamp()
            categories={'completed':'completed','test_settled':'completed',
                        'test_paid':'remaining','in_class':'remaining',
                        'cancelled':'cancelled','refunded':'cancelled'}
            counts=dict(total=0,completed=0,remaining=0,cancelled=0)
            payments_by_booking={}
            rows=db.execute('''SELECT b.id AS booking_id,b.slot_id,b.unit_id,b.status,b.price,
                s.start AS slot_start,s.end AS slot_end,
                l.id AS charge_id,l.amount,l.created_at
                FROM ledger l JOIN bookings b ON b.id=l.booking_id
                JOIN slots s ON s.id=b.slot_id
                WHERE l.kind='test_charge' AND l.beneficiary=? AND b.learner_id=?
                AND l.created_at>=? AND l.created_at<?
                ORDER BY b.id,l.created_at,l.id''',(uid,uid,start,end))
            for row in rows:
                category=categories.get(row['status'])
                if category is None:
                    raise Error('결제된 예약의 상태 확인이 필요합니다',409)
                bid=row['booking_id']
                if bid not in payments_by_booking:
                    payments_by_booking[bid]=dict(bookingId=bid,slotId=row['slot_id'],
                        unitId=row['unit_id'],status=row['status'],price=row['price'],
                        slotStart=row['slot_start'],slotEnd=row['slot_end'],charges=[])
                    counts['total']+=1
                    counts[category]+=1
                payments_by_booking[bid]['charges'].append(dict(id=row['charge_id'],
                    amount=row['amount'],createdAt=row['created_at']))
            return dict(month=month,timezone='UTC',currency='KRW',realMoney=False,
                        payments=list(payments_by_booking.values()),counts=counts),None
        if method=='GET' and path=='/api/policies':
            return {'policies':policy_consents.catalog(u['role']),'simulated':True,'legallyApproved':False},None
        if path=='/api/policy-consents' and method in ('GET','POST'):
            if q: raise Error('정책 확인 조회 조건은 지정할 수 없습니다',400)
            if method=='GET':
                return {'records':policy_consents.list_records(db,user_id=uid),'simulated':True,'legallyApproved':False},None
            if set(d)!={'simulated','acknowledgements'} or d['simulated'] is not True:
                raise Error('simulated=True와 acknowledgements만 입력할 수 있습니다',400)
            records=policy_consents.record(db,user_id=uid,acknowledgements=d['acknowledgements'],simulated=d['simulated'],now=time.time())
            return {'records':records,'simulated':True,'legallyApproved':False},None
        if path=='/api/support/requests' and method in ('GET','POST'):
            if q: raise Error('문의 조회 조건은 지정할 수 없습니다',400)
            if method=='GET':
                return {'requests':support_requests.list_requests(db,uid)},None
            if set(d)!={'subject','body'}: raise Error('subject와 body만 입력할 수 있습니다',400)
            result=support_requests.submit(db,uid,subject=d['subject'],body=d['body'],now=time.time())
            audit(db,uid,'support_request',result['requestId'])
            return result,None
        if method=='GET' and path=='/api/admin/support/requests':
            self.admin(db)
            if set(q)-{'limit','offset'} or any(len(values)!=1 for values in q.values()):
                raise Error('지원하지 않거나 중복된 조회 조건입니다',400)
            page={}
            for key,default in (('limit','20'),('offset','0')):
                value=q.get(key,[default])[0]
                if not re.fullmatch(r'[0-9]+',value): raise Error('페이지 범위를 확인하세요',400)
                page[key]=int(value)
            if not 1<=page['limit']<=100 or page['offset']<0:
                raise Error('페이지 범위를 확인하세요',400)
            if page['offset']>9223372036854775807:
                return {'requests':[],'limit':page['limit'],'offset':page['offset'],'hasMore':False},None
            return support_requests.list_admin_requests(db,**page),None
        if method=='POST' and path=='/api/auth/revoke-sessions':
            if set(d)!={'password'} or not isinstance(d['password'],str) or not 1<=len(d['password'])<=128:
                raise Error('password 문자열 1~128자만 입력할 수 있습니다',400)
            if not password_ok(d['password'],u['password']):
                raise Error('비밀번호를 확인하세요',401)
            db.execute('DELETE FROM sessions WHERE user_id=?',(uid,))
            audit(db,uid,'sessions_revoked',uid)
            return {'ok':True},'hs3=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'
        if path=='/api/privacy/requests':
            if method=='GET':
                return {'requests':privacy_requests.list_requests(db,uid)},None
            if method=='POST':
                if set(d)!={'kind'}: raise Error('kind만 입력할 수 있습니다',400)
                try:
                    result=privacy_requests.submit(db,uid,kind=d['kind'],now=time.time())
                except ValueError as e:
                    raise Error(str(e),400) from None
                return result,None
        if method=='POST' and path=='/api/teacher-alerts':
            try:
                result=teacher_alerts.register(db,uid,d.get('filters'))
            except ValueError as e:
                raise Error(str(e)) from None
            return result,None
        if method=='GET' and path=='/api/learning':return learning.summary(db,uid),None
        if method=='POST' and path=='/api/learning/share':
            if u['role']!='learner':raise Error('학습자만 요약을 전달할 수 있습니다',403)
            try:
                result=learning.share_placement(db,uid,d.get('teacherId'),d.get('consent'))
            except ValueError as e:
                raise Error(str(e),400) from None
            return result,None
        if method=='GET' and path=='/api/learning/shared':
            if u['role'] not in ('teacher','partner'):raise Error('수업 제공자만 전달된 요약을 조회할 수 있습니다',403)
            return {'shares':learning.received_placements(db,uid)},None
        learning_booking=re.fullmatch('/api/learning/booking/([0-9a-f]+)',path)
        if method=='GET' and learning_booking:
            b=self.booking(db,learning_booking[1],u);records=[]
            for row in db.execute('SELECT * FROM learning_checks WHERE booking_id=? ORDER BY created_at DESC,rowid DESC LIMIT 100',(b['id'],)):
                record=dict(row);record['skills']=json.loads(record.pop('skills_json'));records.append(record)
            return {'records':records,'bookingId':b['id']},None
        if method=='POST' and path=='/api/learning/placement':
            if u['role']!='learner':raise Error('학습자만 저장할 수 있습니다',403)
            return learning.save_placement(db,uid,d.get('groups')),None
        diagnostic_match=re.fullmatch('/api/diagnostics/([A-Za-z0-9-]+)',path)
        if diagnostic_match and method=='GET':
            unit=get_unit(diagnostic_match[1]);phase=q.get('phase',['pre'])[0]
            qs=learning.diagnostic(unit['id'],phase)
            if q.get('bookingId'):
                b=self.booking(db,q['bookingId'][0],u)
                if b['unit_id']!=unit['id']:raise Error('예약 교재가 다릅니다',403)
                snap=db.execute('SELECT content FROM unit_snapshots WHERE booking_id=?',(b['id'],)).fetchone();qs=json.loads(snap['content']).get('_diagnostics',{}).get(phase,qs)
            return {'questions':learning.safe_questions(qs),'phase':phase,'kind':'text-check'},None
        if method=='POST' and path=='/api/learning/check':
            if u['role']!='learner':raise Error('학습자만 응답할 수 있습니다',403)
            unit=get_unit(d.get('unitId'));phase=d.get('phase');bid=d.get('bookingId');frozen=None
            if phase=='post' or bid:
                b=self.booking(db,bid,u)
                allowed_states=('reserved','test_paid','in_class','completed','test_settled') if phase=='pre' else ('in_class','completed','test_settled')
                if b['learner_id']!=uid or b['unit_id']!=unit['id'] or b['status'] not in allowed_states:raise Error('진단 가능한 본인 수업이 아닙니다',403)
                snapshot=db.execute('SELECT content FROM unit_snapshots WHERE booking_id=?',(bid,)).fetchone();frozen=json.loads(snapshot['content']).get('_diagnostics',{}).get(phase)
            return learning.submit(db,uid,unit['id'],phase,d.get('answers'),bid,questions=frozen),None
        if method=='POST' and path=='/api/learning/observation':
            b=self.booking(db,d.get('bookingId'),u)
            if uid!=b['teacher_id'] or u['role'] not in ('teacher','partner'):raise Error('예약된 수업 제공자만 수행 평가할 수 있습니다',403)
            permitted=('reserved','test_paid','in_class','completed','test_settled') if d.get('phase')=='pre' else ('in_class','completed','test_settled')
            if b['status'] not in permitted:raise Error('이 수업 상태에서는 수행 평가할 수 없습니다',409)
            return learning.teacher_rating(db,b,uid,d.get('phase'),d.get('ratings'),d.get('note')),None
        if method=='POST' and path=='/api/logout':
            cookie=http.cookies.SimpleCookie(self.headers.get('Cookie',''))
            db.execute('DELETE FROM sessions WHERE token=?',(hashlib.sha256(cookie['hs3'].value.encode()).hexdigest(),))
            return {'ok':True},'hs3=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'
        if method=='GET' and path=='/api/me': return {'user':public_user(u)},None
        if method=='GET' and path=='/api/earnings':
            entries=[dict(x) for x in db.execute("SELECT booking_id,kind,amount,created_at FROM ledger WHERE beneficiary=? AND (kind LIKE 'test_teacher_accrual%' OR kind LIKE 'test_referral_accrual%') ORDER BY id",(uid,))]
            return {'currency':'KRW','realPayout':False,'teacherAccrued':sum(x['amount'] for x in entries if x['kind'].startswith('test_teacher_accrual')),'referralAccrued':sum(x['amount'] for x in entries if x['kind'].startswith('test_referral_accrual')),'entries':entries},None
        if method=='PUT' and path=='/api/profile':
            profile={k:text(d.get(k,u[k]),2000 if k=='qualifications' else 200) for k in ('nickname','languages','timezone','specialty','level','qualifications')}
            if profile['timezone']:
                try:
                    ZoneInfo(profile['timezone'])
                except (ZoneInfoNotFoundError, ValueError):
                    raise Error('잘못된 시간대입니다',400)
            price=d.get('price',u['price'])
            if isinstance(price,bool) or not isinstance(price,int) or not 1000<=price<=1000000 or len(profile['nickname'])<2: raise Error('가격 또는 이름이 잘못되었습니다')
            db.execute('UPDATE users SET nickname=?,languages=?,timezone=?,specialty=?,level=?,qualifications=?,price=?,approved=CASE WHEN role IN (\'partner\',\'teacher\') THEN 0 ELSE approved END WHERE id=?',(*profile.values(),price,uid))
            audit(db,uid,'profile_update',uid,'provider reapproval required')
            return {'user':public_user(db.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone())},None
        if method=='GET' and path=='/api/teachers':
            clauses=["u.approved=1", "u.role IN ('teacher','partner')"];params=[]
            if q.get('id'):clauses.append('u.id=?');params.append(text(q['id'][0],64))
            for field,param in [('role','role'),('languages','language'),('level','level'),('specialty','purpose')]:
                if q.get(param):clauses.append('instr(lower(u.'+field+'),lower(?))>0');params.append(text(q[param][0],200))
            if q.get('maxPrice'):
                price=int(q['maxPrice'][0])
                if not 1000<=price<=1000000:raise Error('가격 범위를 확인하세요')
                clauses.append('u.price<=?');params.append(price)
            if q.get('q'):
                clauses.append("instr(lower(u.nickname||' '||u.specialty),lower(?))>0");params.append(text(q['q'][0],200))
            if q.get('from') or q.get('to'):
                if not q.get('from') or not q.get('to'):raise Error('검색 시작과 종료 시각이 모두 필요합니다')
                start,end=stamp(q['from'][0]),stamp(q['to'][0])
                if end<=start:raise Error('검색 종료는 시작 이후여야 합니다')
                clauses.append("EXISTS(SELECT 1 FROM slots s WHERE s.teacher_id=u.id AND s.start>=? AND s.end<=? AND s.start>? AND NOT EXISTS(SELECT 1 FROM time_off t WHERE t.teacher_id=s.teacher_id AND t.start<s.end AND t.end>s.start) AND NOT EXISTS(SELECT 1 FROM bookings b WHERE b.slot_id=s.id AND b.status NOT IN ('cancelled','refunded','expired')))");params.extend((start,end,time.time()))
            limit=int(q.get('limit',['20'])[0]);offset=int(q.get('offset',['0'])[0])
            if not 1<=limit<=100 or offset<0:raise Error('페이지 범위를 확인하세요')
            where=' AND '.join(clauses)
            total=db.execute('SELECT count(*) FROM users u WHERE '+where,params).fetchone()[0]
            rows=[public_user(x) for x in db.execute('SELECT u.* FROM users u WHERE '+where+' ORDER BY u.nickname,u.id LIMIT ? OFFSET ?',(*params,limit,offset))]
            for r in rows:
                r.pop('referral_code',None)
                avg=db.execute("SELECT avg(rating),count(rating) FROM bookings WHERE teacher_id=? AND rating IS NOT NULL AND status IN ('completed','test_settled')",(r['id'],)).fetchone()
                r.update(rating=avg[0],reviewCount=avg[1],verification='local-test-review-only')
            return {'teachers':rows,'total':total,'offset':offset,'limit':limit,'hasMore':offset+len(rows)<total},None
        if path=='/api/availability/time-off' and method in ('GET','POST'):
            if u['role'] not in ('partner','teacher'): raise Error('수업 제공자만 가능합니다',403)
            if method=='GET':
                return {'timeOff':availability.list_time_off(db,uid,time.time())},None
            time_off=availability.add_time_off(db,uid,stamp(d.get('start')),stamp(d.get('end')),time.time())
            return {'timeOffId':time_off['id']},None
        slot_update=re.fullmatch('/api/availability/([^/]+)',path)
        if method=='PUT' and slot_update:
            if u['role'] not in ('partner','teacher'): raise Error('수업 제공자만 가능합니다',403)
            sid=slot_update[1]
            owner=db.execute('SELECT teacher_id FROM slots WHERE id=?',(sid,)).fetchone()
            if not owner: raise Error('일정이 없습니다',404)
            if owner['teacher_id']!=uid: raise Error('본인 일정만 수정할 수 있습니다',403)
            slot=availability.update_slot(db,uid,sid,stamp(d.get('start')),stamp(d.get('end')),time.time())
            return {'slotId':sid,'slot':slot},None
        if path=='/api/availability':
            if method=='GET':
                tid=q.get('teacherId',[uid])[0]
                return {'slots':[dict(x) for x in db.execute("SELECT s.* FROM slots s JOIN users u ON u.id=s.teacher_id WHERE s.teacher_id=? AND (u.approved=1 OR s.teacher_id=?) AND s.start>? AND NOT EXISTS(SELECT 1 FROM time_off t WHERE t.teacher_id=s.teacher_id AND t.start<s.end AND t.end>s.start) AND NOT EXISTS(SELECT 1 FROM bookings b WHERE b.slot_id=s.id AND b.status NOT IN ('cancelled','refunded','expired')) ORDER BY s.start",(tid,uid,time.time()))]},None
            if method=='POST':
                if u['role'] not in ('partner','teacher'): raise Error('수업 제공자만 가능합니다',403)
                start,end=stamp(d.get('start')),stamp(d.get('end'))
                if start<time.time() or not 300<=end-start<=7200: raise Error('미래의 5~120분 수업만 등록하세요')
                if db.execute('SELECT 1 FROM slots WHERE teacher_id=? AND start<? AND end>?',(uid,end,start)).fetchone(): raise Error('시간이 겹칩니다',409)
                availability.assert_available(db,uid,start,end)
                sid=ident(); db.execute('INSERT INTO slots VALUES(?,?,?,?)',(sid,uid,start,end)); audit(db,uid,'availability',sid)
                return {'slotId':sid},None
        if path=='/api/bookings':
            if method=='GET':
                rows=[]
                for b in db.execute('SELECT b.*, learner.timezone AS learnerTimezone, teacher.timezone AS teacherTimezone FROM bookings b LEFT JOIN users learner ON learner.id=b.learner_id LEFT JOIN users teacher ON teacher.id=b.teacher_id WHERE b.learner_id=? OR b.teacher_id=? ORDER BY b.created_at DESC',(uid,uid)):
                    v=dict(b); v.pop('room',None); v['sharedSeconds']=shared_seconds(db,b['id']); v['paymentMode']='provider-test' if db.execute('SELECT 1 FROM payment_sessions WHERE booking_id=?',(b['id'],)).fetchone() else 'simulated-test-only'; v['attendance']=[dict(a) for a in db.execute('SELECT * FROM attendance WHERE booking_id=?',(b['id'],))]; v['slot']=dict(db.execute('SELECT * FROM slots WHERE id=?',(b['slot_id'],)).fetchone()); v['disputes']=[dict(x) for x in db.execute('SELECT * FROM disputes WHERE booking_id=?',(b['id'],))]; rows.append(v)
                for v in rows:
                    v['observations']=session_evidence.list_observations(db,booking_id=v['id'])
                    for a in v['attendance']:
                        a['lateSeconds']=max(0,a['joined']-v['slot']['start'])
                    v['leaveRecords']=[dict(e,userId=e['actor'],early=e['leftAt']<e['slotEnd']) for e in participant_events(db,v['id']) if e['action']=='participant_leave']
                    v['attendanceNotice']='출석·지각·자기보고 종료는 실제 통화 또는 이행의 확정 증거가 아닙니다. 브라우저 종료·요청 유실·외부 Jitsi 퇴장은 확정할 수 없습니다.'
                return {'bookings':rows},None
            if method=='POST':
                if u['role']!='learner': raise Error('학습자만 예약할 수 있습니다',403)
                unit=get_unit(d.get('unitId')); slot=db.execute('SELECT s.*,u.price,u.approved,u.role FROM slots s JOIN users u ON s.teacher_id=u.id WHERE s.id=?',(d.get('slotId'),)).fetchone()
                if not slot or slot['teacher_id']!=d.get('teacherId') or slot['teacher_id']==uid or not slot['approved'] or slot['role'] not in ('teacher','partner') or slot['start']<=time.time(): raise Error('예약 가능한 일정이 아닙니다')
                availability.assert_available(db,slot['teacher_id'],slot['start'],slot['end'])
                if db.execute("SELECT 1 FROM bookings b JOIN slots s ON s.id=b.slot_id WHERE b.status NOT IN ('cancelled','refunded','expired') AND (b.slot_id=? OR (b.teacher_id=? AND s.start<? AND s.end>?))",(slot['id'],slot['teacher_id'],slot['end'],slot['start'])).fetchone(): raise Error('강사 일정이 겹치거나 이미 예약된 일정입니다',409)
                if slot['end']-slot['start'] < int(unit.get('durationMinutes',30))*60: raise Error('단원 수업시간보다 일정이 짧습니다')
                if db.execute("SELECT 1 FROM bookings b JOIN slots s ON s.id=b.slot_id WHERE b.learner_id=? AND b.status NOT IN ('cancelled','refunded','expired') AND s.start<? AND s.end>?",(uid,slot['end'],slot['start'])).fetchone(): raise Error('학습자 일정이 겹칩니다',409)
                ref=u['referred_by']
                if d.get('referralCode'):
                    r=db.execute('SELECT id FROM users WHERE referral_code=?',(text(d['referralCode'],40),)).fetchone()
                    if not r: raise Error('추천코드가 없습니다')
                    if ref and ref!=r['id']: raise Error('가입 시 추천인을 변경할 수 없습니다')
                    ref=r['id']
                if ref in (uid,slot['teacher_id']): raise Error('본인 또는 거래 상대 추천은 보상 대상이 아닙니다')
                if ref and not u['referred_by']:
                    db.execute('UPDATE users SET referred_by=? WHERE id=? AND referred_by IS NULL',(ref,uid))
                    audit(db,uid,'direct_referrer_bound',uid,ref)
                bid=ident(); db.execute('INSERT INTO bookings(id,learner_id,teacher_id,slot_id,unit_id,price,referrer_id,room,created_at) VALUES(?,?,?,?,?,?,?,?,?)',(bid,uid,slot['teacher_id'],slot['id'],str(unit['id']),slot['price'],ref,'hs-test-'+secrets.token_urlsafe(24),time.time())); audit(db,uid,'booking',bid)
                db.execute('INSERT INTO rate_snapshots(booking_id,commission_bps,referral_bps,processor_bps,refund_bps,tax_bps) VALUES(?,?,?,?,?,?)',(bid,2000,300 if ref else 0,300,300,0))
                content=json.dumps(unit,ensure_ascii=False,sort_keys=True); db.execute('INSERT INTO unit_snapshots VALUES(?,?,?)',(bid,content,hashlib.sha256(content.encode()).hexdigest()))
                policy_consents.link_booking(db,booking_id=bid,user_id=uid)
                return {'bookingId':bid},None
        statement_match=re.fullmatch('/api/bookings/([0-9a-f]+)/disputes/([0-9a-f]+)/statements',path)
        if statement_match and method in ('GET','POST'):
            bid,did=statement_match.groups()
            case=db.execute('SELECT * FROM disputes WHERE id=? AND booking_id=?',(did,bid)).fetchone()
            if not case: raise Error('신고가 없습니다',404)
            b=self.booking(db,bid,u)
            if method=='GET':
                reporter=db.execute('SELECT role FROM users WHERE id=?',(case['reporter_id'],)).fetchone()
                original=dict(id='dispute:'+did,authorId=case['reporter_id'],role='learner' if case['reporter_id']==b['learner_id'] else reporter['role'],text=case['reason'],createdAt=case['created_at'])
                statements=[dict(id=row['id'],authorId=row['author_id'],role=row['role'],text=row['text'],createdAt=row['created_at']) for row in db.execute('SELECT * FROM dispute_statements WHERE dispute_id=? ORDER BY rowid',(did,))]
                return {'disputeId':did,'statements':[original]+statements},None
            if u['role']=='admin' or uid not in (b['learner_id'],b['teacher_id']): raise Error('예약 당사자 본인만 진술할 수 있습니다',403)
            if case['status']!='open': raise Error('종료된 분쟁에는 진술을 추가할 수 없습니다',409)
            if set(d)!={'text'}: raise Error('text만 입력할 수 있습니다')
            body=text(d.get('text'),5000)
            if len(body)<10: raise Error('진술은 10~5000자여야 합니다')
            sid=ident(); now=time.time()
            db.execute('INSERT INTO dispute_statements(id,dispute_id,author_id,role,text,created_at) VALUES(?,?,?,?,?,?)',(sid,did,uid,u['role'],body,now))
            audit(db,uid,'dispute_statement',did,json.dumps(dict(bookingId=bid,statementId=sid)))
            return {'statementId':sid},None
        observation_match=re.fullmatch('/api/bookings/([0-9a-f]+)/observations',path)
        if observation_match and method=='POST':
            b=self.booking(db,observation_match[1],u)
            if u['role']=='admin' or uid not in (b['learner_id'],b['teacher_id']):
                raise Error('예약 당사자만 기록할 수 있습니다',403)
            if b['status'] not in ('test_paid','in_class'):
                raise Error('테스트 결제 후 진행 중인 수업만 기록할 수 있습니다',409)
            if set(d)!={'kind','outcome'}:
                raise Error('kind와 outcome만 입력할 수 있습니다',400)
            observation=session_evidence.append_observation(
                db,booking_id=b['id'],slot_id=b['slot_id'],actor_id=uid,
                kind=d['kind'],outcome=d['outcome'],now=time.time())
            return {'observation':observation},None
        snapshot_match=re.fullmatch('/api/bookings/([0-9a-f]+)/unit',path)
        if snapshot_match and method=='GET':
            b=self.booking(db,snapshot_match[1],u); snapshot=db.execute('SELECT * FROM unit_snapshots WHERE booking_id=?',(b['id'],)).fetchone(); unit=json.loads(snapshot['content'])
            unit=learning.public_unit(unit,uid==b['teacher_id'] or u['role']=='admin')
            return {'unit':unit,'sha256':snapshot['sha256'],'version':'booking-snapshot'},None
        m=re.fullmatch('/api/bookings/([0-9a-f]+)/([a-z-]+)',path)
        if m and method=='POST':
            bid,action=m.groups(); b=self.booking(db,bid,u)
            if u['role']=='admin': raise Error('수업 참가자만 수행할 수 있습니다',403)
            if action=='checkout-test':
                if uid!=b['learner_id'] or b['status']!='reserved':raise Error('학습자의 유효한 미결제 예약만 가능합니다',409)
                existing=db.execute('SELECT * FROM payment_sessions WHERE booking_id=?',(bid,)).fetchone()
                if existing:return {'checkoutUrl':existing['url'],'paymentMode':'provider-test','realMoney':False},None
                base='http://'+self.headers['Host']
                checkout=payments.create_checkout(dict(b),success_url=base+'/?checkout=test-return',cancel_url=base+'/?checkout=test-cancel')
                db.execute('INSERT INTO payment_sessions VALUES(?,?,?,?)',(bid,checkout['id'],checkout['url'],time.time()))
                audit(db,uid,'provider_test_checkout_created',bid,checkout['id'])
                return {'checkoutUrl':checkout['url'],'paymentMode':'provider-test','realMoney':False},None
            if action=='pay-test':
                if uid!=b['learner_id']: raise Error('학습자만 가능합니다',403)
                if db.execute('SELECT 1 FROM payment_sessions WHERE booking_id=?',(bid,)).fetchone():raise Error('PG 테스트 세션이 있어 모의 결제와 혼합할 수 없습니다',409)
                if b['status']=='reserved':
                    slot=db.execute('SELECT start FROM slots WHERE id=?',(b['slot_id'],)).fetchone()
                    if time.time()>=min(b['created_at']+900,slot['start']): raise Error('미결제 예약 유효기간이 지났습니다',409)
                    db.execute("UPDATE bookings SET status='test_paid' WHERE id=?",(bid,)); db.execute('INSERT INTO ledger(booking_id,kind,amount,beneficiary,created_at) VALUES(?,?,?,?,?)',(bid,'test_charge',b['price'],uid,time.time())); audit(db,uid,'test_charge',bid)
                elif b['status'] not in ('test_paid','in_class','completed','test_settled'): raise Error('테스트 결제 불가 상태',409)
                return {'ok':True,'payment':'simulated-test-only','chargedRealMoney':False},None
            if action=='leave':
                previous=db.execute('SELECT * FROM attendance WHERE booking_id=? AND user_id=?',(bid,uid)).fetchone()
                events=participant_events(db,bid,uid,b['slot_id'])
                if events and events[-1]['action']=='participant_leave':
                    return {'ok':True,'leftAt':events[-1]['leftAt'],'source':'participant_report'},None
                if b['status']!='in_class' or not previous: raise Error('진행 중인 본인 출석 기록이 필요합니다',409)
                slot=db.execute('SELECT * FROM slots WHERE id=?',(b['slot_id'],)).fetchone()
                now=time.time()
                detail=dict(bookingId=bid,slotId=b['slot_id'],leftAt=now,slotEnd=slot['end'],source='participant_report')
                audit(db,uid,'participant_leave',bid,json.dumps(detail))
                return {'ok':True,'leftAt':now,'source':'participant_report'},None
            if action in ('join','attendance'):
                if b['status'] not in ('test_paid','in_class'): raise Error('테스트 결제 후 입장할 수 있습니다',409)
                slot=db.execute('SELECT * FROM slots WHERE id=?',(b['slot_id'],)).fetchone(); now=time.time()
                if not slot['start']-300<=now<=slot['end']+300: raise Error('수업 시간에만 입장할 수 있습니다',409)
                previous=db.execute('SELECT * FROM attendance WHERE booking_id=? AND user_id=?',(bid,uid)).fetchone()
                events=participant_events(db,bid,uid,b['slot_id'])
                returning=bool(events and events[-1]['action']=='participant_leave')
                if previous and returning:
                    # Explicit leave closes the baseline without granting the intervening gap.
                    db.execute('UPDATE attendance SET last_seen=? WHERE booking_id=? AND user_id=?',(now,bid,uid))
                    audit(db,uid,'participant_rejoin',bid,json.dumps(dict(bookingId=bid,slotId=b['slot_id'],joinedAt=now)))
                elif previous:
                    # Heartbeat interval <=90s is counted; leaving a tab idle does not grant elapsed hours.
                    delta=max(0,now-previous['last_seen']); increment=max(0,min(now,slot['end'])-max(previous['last_seen'],slot['start'])) if delta<=90 else 0
                    db.execute('UPDATE attendance SET last_seen=?,seconds=seconds+? WHERE booking_id=? AND user_id=?',(now,increment,bid,uid))
                    if increment>0: db.execute('INSERT INTO attendance_intervals(booking_id,user_id,start,end) VALUES(?,?,?,?)',(bid,uid,max(previous['last_seen'],slot['start']),min(now,slot['end'])))
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
                if count==2 and shared_seconds(db,bid)<duration: raise Error('양측이 함께 참여한 수업시간이 부족합니다',409)
                if count==2 and b['evidence'] and not db.execute("SELECT 1 FROM disputes WHERE booking_id=? AND status='open'",(bid,)).fetchone(): db.execute("UPDATE bookings SET status='completed' WHERE id=?",(bid,))
                audit(db,uid,'completion_confirmation',bid)
                return {'ok':True,'status':db.execute('SELECT status FROM bookings WHERE id=?',(bid,)).fetchone()[0]},None
            if action=='homework':
                if uid!=b['learner_id'] or b['status'] in ('cancelled','refunded','expired'): raise Error('과제 제출 권한이 없습니다',403)
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
                if db.execute("SELECT 1 FROM disputes WHERE booking_id=? AND reporter_id=? AND status='open'",(bid,uid)).fetchone(): raise Error('이미 이 예약에 본인의 미처리 신고가 있습니다. 중복 신고는 할 수 없습니다',409)
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
                availability.assert_available(db,b['teacher_id'],slot['start'],slot['end'])
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
            if method=='GET' and path=='/api/admin/providers':
                for key in ('role','approved','limit','offset'):
                    if key in q and len(q[key])!=1: raise Error('검색 조건은 하나씩 지정하세요')
                clauses=["role IN ('teacher','partner')"];params=[]
                if 'role' in q:
                    if q['role'][0] not in ('teacher','partner'): raise Error('참여 유형을 확인하세요')
                    clauses.append('role=?');params.append(q['role'][0])
                if 'approved' in q:
                    if q['approved'][0] not in ('0','1'): raise Error('승인 상태를 확인하세요')
                    clauses.append('approved=?');params.append(int(q['approved'][0]))
                page={}
                for key,default in (('limit','20'),('offset','0')):
                    value=q.get(key,[default])[0]
                    if not re.fullmatch(r'[0-9]+',value): raise Error('페이지 범위를 확인하세요')
                    page[key]=int(value)
                limit,offset=page['limit'],page['offset']
                if not 1<=limit<=100 or offset<0: raise Error('페이지 범위를 확인하세요')
                where=' AND '.join(clauses)
                total=db.execute('SELECT count(*) FROM users WHERE '+where,params).fetchone()[0]
                rows=[public_user(x) for x in db.execute('SELECT * FROM users WHERE '+where+' ORDER BY created_at ASC,id ASC LIMIT ? OFFSET ?',(*params,limit,min(offset,total)))]
                return {'providers':rows,'total':total,'limit':limit,'offset':offset,'hasMore':offset+len(rows)<total},None
            if method=='GET' and path=='/api/admin':
                result={'bookings':[dict(x) for x in db.execute('SELECT b.*, learner.timezone AS learnerTimezone, teacher.timezone AS teacherTimezone FROM bookings b LEFT JOIN users learner ON learner.id=b.learner_id LEFT JOIN users teacher ON teacher.id=b.teacher_id')],'disputes':[dict(x) for x in db.execute('SELECT * FROM disputes')],'ledger':[dict(x) for x in db.execute('SELECT * FROM ledger')],'audit':[dict(x) for x in db.execute('SELECT * FROM audit ORDER BY id DESC LIMIT 500')]}
                if q.get('includeUsers')==['0']:
                    result['userCount']=db.execute('SELECT count(*) FROM users').fetchone()[0]
                else:
                    result['users']=[public_user(x) for x in db.execute('SELECT * FROM users')]
                return result,None
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
                if db.execute("SELECT 1 FROM ledger WHERE booking_id=? AND (kind='test_charge_reversal' OR kind GLOB 'test_charge__refund_*_reversal' OR kind GLOB 'test_charge_reversal__refund_*')",(b['id'],)).fetchone():
                    raise Error('부분 환불 이력이 있어 기존 전액 기준으로 정산할 수 없습니다',409)
                rates=db.execute('SELECT * FROM rate_snapshots WHERE booking_id=?',(b['id'],)).fetchone()
                split=money(b['price'],rates['commission_bps'],rates['referral_bps'],rates['processor_bps'],rates['tax_bps'],rates['refund_bps'])
                for kind,amount,who in [('test_teacher_accrual',split['teacher'],b['teacher_id']),('test_referral_accrual',split['referral'],b['referrer_id']),('test_platform_contribution',split['platform'],None),('test_processor_cost',split['processor'],None),('test_refund_reserve',split['refund'],None),('test_tax_reserve',split['tax'],None)]:
                    db.execute('INSERT INTO ledger(booking_id,kind,amount,beneficiary,created_at) VALUES(?,?,?,?,?)',(b['id'],kind,amount,who,time.time()))
                db.execute("UPDATE bookings SET status='test_settled' WHERE id=?",(b['id'],)); audit(db,uid,'test_settlement',b['id'],'no real payout')
                return {'ok':True,'realPayout':False,'split':split},None
            m=re.fullmatch('/api/admin/disputes/([0-9a-f]+)',path)
            if method=='POST' and m:
                case=db.execute('SELECT * FROM disputes WHERE id=?',(m[1],)).fetchone(); reason=text(d.get('reason',''),5000); decision=d.get('decision')
                if not case: raise Error('신고가 없습니다',404)
                b=self.booking(db,case['booking_id'],u)
                refund_result=None
                if decision=='refund':
                    explicit='amount' in d
                    request_id=d.get('requestId') if explicit else d.get('requestId','dispute:'+case['id'])
                    if not isinstance(request_id,str) or not request_id.strip(): raise Error('requestId가 필요합니다')
                    if explicit and 'allocations' not in d: raise Error('원본 항목별 배분이 필요합니다')
                    previous=db.execute('SELECT amount,allocations FROM local_refund_requests WHERE booking_id=? AND request_id=?',(b['id'],request_id)).fetchone()
                    if explicit:
                        amount,allocations=d['amount'],d['allocations']
                    elif previous:
                        amount,allocations=previous['amount'],json.loads(previous['allocations'])
                        if 'allocations' in d and d['allocations']!=allocations: raise Error('같은 요청 ID의 환불 입력이 다릅니다',409)
                    else:
                        amount,allocations=remaining_refund(db,b['id'])
                        if 'allocations' in d: allocations=d['allocations']
                    if previous:
                        refund_result=refund_ledger.apply_refund(db,booking_id=b['id'],request_id=request_id,amount=amount,allocations=allocations,actor_id=admin['id'])
                        return dict(refund_result,ok=True,realRefund=False),None
                if case['status']!='open' or len(reason)<10 or decision not in ('refund','dismiss','reschedule'): raise Error('미처리 신고와 판단 근거를 확인하세요',409)
                counterpart=b['teacher_id'] if case['reporter_id']==b['learner_id'] else b['learner_id']
                statements=list(db.execute('SELECT id,author_id FROM dispute_statements WHERE dispute_id=? ORDER BY rowid',(case['id'],)))
                if not any(row['author_id']==counterpart for row in statements): raise Error('관리자 판단 전에 상대방 본인의 진술이 필요합니다',409)
                if decision=='refund':
                    # Only virtual ledger reversal. Never claw back real teacher compensation.
                    refund_result=refund_ledger.apply_refund(db,booking_id=b['id'],request_id=request_id,amount=amount,allocations=allocations,actor_id=admin['id'])
                elif decision=='reschedule':
                    # Test replacement retains payment/rates/content, explicit mutual consent required.
                    consents=db.execute('SELECT count(*) FROM reschedule_consents WHERE booking_id=? AND slot_id=? AND user_id IN (?,?) AND created_at>?',(b['id'],d.get('slotId'),b['learner_id'],b['teacher_id'],time.time()-86400)).fetchone()[0]
                    if consents!=2: raise Error('재수업에는 양측이 직접 저장한 동일 일정 동의가 필요합니다')
                    if b['status'] in ('completed','test_settled','refunded','cancelled'): raise Error('완료·정산된 수업 보수는 자동 조정하지 않습니다',409)
                    replacement=db.execute('SELECT * FROM slots WHERE id=? AND teacher_id=?',(d.get('slotId'),b['teacher_id'])).fetchone()
                    if not replacement or replacement['start']<=time.time(): raise Error('같은 강사의 미래 대체 일정을 선택하세요')
                    availability.assert_available(db,b['teacher_id'],replacement['start'],replacement['end'])
                    if db.execute("SELECT 1 FROM bookings x JOIN slots s ON s.id=x.slot_id WHERE x.id<>? AND x.status NOT IN ('cancelled','refunded','expired') AND (x.slot_id=? OR (x.teacher_id=? AND s.start<? AND s.end>?))",(b['id'],replacement['id'],b['teacher_id'],replacement['end'],replacement['start'])).fetchone(): raise Error('강사 대체 일정 충돌 또는 대상 일정 점유',409)
                    duration=int(json.loads(db.execute('SELECT content FROM unit_snapshots WHERE booking_id=?',(b['id'],)).fetchone()[0]).get('durationMinutes',30))*60
                    if replacement['end']-replacement['start']<duration: raise Error('대체 일정 수업시간 부족')
                    if db.execute("SELECT 1 FROM bookings x JOIN slots s ON x.slot_id=s.id WHERE x.id<>? AND x.learner_id=? AND x.status NOT IN ('cancelled','refunded','expired') AND s.start<? AND s.end>?",(b['id'],b['learner_id'],replacement['end'],replacement['start'])).fetchone(): raise Error('학습자 대체 일정 충돌',409)
                    audit(db,uid,'reschedule_previous_slot',b['id'],json.dumps({'slotId':b['slot_id'],'replacementSlotId':replacement['id'],'consentEvidence':reason,'attendance':[dict(x) for x in db.execute('SELECT * FROM attendance WHERE booking_id=?',(b['id'],))]}))
                    db.execute('DELETE FROM attendance WHERE booking_id=?',(b['id'],))
                    db.execute('DELETE FROM attendance_intervals WHERE booking_id=?',(b['id'],))
                    db.execute('DELETE FROM reschedule_consents WHERE booking_id=?',(b['id'],))
                    db.execute("UPDATE bookings SET slot_id=?,status=CASE WHEN status='reserved' THEN 'reserved' ELSE 'test_paid' END,evidence='',room=? WHERE id=?",(replacement['id'],'hs-test-'+secrets.token_urlsafe(24),b['id']))
                db.execute("UPDATE disputes SET status='resolved',decision=?,resolution=? WHERE id=?",(decision,reason,case['id']))
                audit(db,admin['id'],'dispute_'+decision,case['id'],json.dumps(dict(bookingId=b['id'],disputeId=case['id'],originalStatement=dict(id='dispute:'+case['id'],reporterId=case['reporter_id'],reason=case['reason']),statementIds=[row['id'] for row in statements],adminId=admin['id'],decidedAt=time.time(),decision=decision,reason=reason),ensure_ascii=False))
                return dict(refund_result or {},ok=True,realRefund=False),None
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
