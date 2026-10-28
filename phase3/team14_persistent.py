"""TEST ONLY: persistent booking/month/lesson settlement; no money APIs."""
import sqlite3,json,re
from contextlib import contextmanager
MAX=10**15
class SimError(ValueError):
 def __init__(self,code,message): self.code=code;super().__init__(message)
def ident(v):
 if not isinstance(v,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}',v): raise SimError('VALIDATION_ERROR','invalid identifier')
 return v
def amount(v,positive=False):
 if type(v)!=int or v<(1 if positive else 0) or v>MAX: raise SimError('VALIDATION_ERROR','invalid KRW amount')
 return v
class MonthlyStore:
 def __init__(self,path=':memory:'):
  self.db=sqlite3.connect(path,isolation_level=None,timeout=10)
  self.db.row_factory=sqlite3.Row
  self.db.execute('PRAGMA foreign_keys=ON')
  self.db.executescript("""
CREATE TABLE IF NOT EXISTS months(id TEXT PRIMARY KEY,currency TEXT NOT NULL CHECK(currency='KRW'),commission INTEGER NOT NULL,referral INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS lessons(id TEXT PRIMARY KEY,month_id TEXT NOT NULL REFERENCES months(id),booking_id TEXT NOT NULL UNIQUE,amount INTEGER NOT NULL,state TEXT NOT NULL,refunded INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS operations(id TEXT PRIMARY KEY,signature TEXT NOT NULL,result TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ledger(id INTEGER PRIMARY KEY AUTOINCREMENT,transaction_id TEXT NOT NULL,lesson_id TEXT NOT NULL REFERENCES lessons(id),kind TEXT NOT NULL,amount INTEGER NOT NULL,UNIQUE(transaction_id,kind));
""")
 def close(self): self.db.close()
 @contextmanager
 def atomic(self):
  self.db.execute('BEGIN IMMEDIATE')
  try:
   yield
   self.db.execute('COMMIT')
  except BaseException:
   self.db.execute('ROLLBACK')
   raise
 def once(self,op,signature,apply):
  ident(op);sig=json.dumps(signature,sort_keys=True)
  with self.atomic():
   prior=self.db.execute('SELECT * FROM operations WHERE id=?',(op,)).fetchone()
   if prior:
    if prior['signature']!=sig: raise SimError('CONFLICT','idempotency conflict')
    return json.loads(prior['result'])
   result=apply()
   self.db.execute('INSERT INTO operations VALUES(?,?,?)',(op,sig,json.dumps(result)))
   return result
 def create_month(self,month_id,lessons,currency='KRW',commission_bps=2000,referral_bps=300,operation_id=None):
  ident(month_id)
  if currency!='KRW': raise SimError('VALIDATION_ERROR','currency mismatch')
  if any(type(x)!=int or x<0 or x>10000 for x in (commission_bps,referral_bps)) or commission_bps+referral_bps>10000: raise SimError('VALIDATION_ERROR','rates')
  if not isinstance(lessons,(list,tuple)) or not lessons: raise SimError('VALIDATION_ERROR','lessons required')
  items=[(ident(a),ident(b),amount(c,True)) for a,b,c in lessons]
  if len(set(a for a,b,c in items))!=len(items) or len(set(b for a,b,c in items))!=len(items) or sum(c for a,b,c in items)>MAX: raise SimError('VALIDATION_ERROR','duplicate or over maximum')
  def apply():
   self.db.execute('INSERT INTO months VALUES(?,?,?,?)',(month_id,currency,commission_bps,referral_bps))
   self.db.executemany("INSERT INTO lessons(id,booking_id,amount,month_id,state) VALUES(?,?,?,?,'reserved')",((a,b,c,month_id) for a,b,c in items))
   return dict(month_id=month_id,currency=currency,real_money=False)
  return self.once(operation_id or 'create_'+month_id,['create',month_id,items,currency,commission_bps,referral_bps],apply)
 def event(self,month_id,lesson_id,booking_id,transaction_id,operation_id,action,amount_krw=0,currency='KRW',booking_state=None):
  for x in (month_id,lesson_id,booking_id,transaction_id,operation_id): ident(x)
  if currency!='KRW': raise SimError('VALIDATION_ERROR','currency mismatch')
  if action not in ('complete','refund','cancel'): raise SimError('VALIDATION_ERROR','action')
  amount(amount_krw,action=='refund')
  if action!='refund' and amount_krw!=0: raise SimError('VALIDATION_ERROR','unexpected amount')
  target={'complete':'completed','refund':'refunded','cancel':'cancelled'}[action]
  if booking_state is not None and booking_state!=target: raise SimError('INVALID_STATE','booking event')
  def apply():
   row=self.db.execute('SELECT l.*,m.commission,m.referral FROM lessons l JOIN months m ON m.id=l.month_id WHERE l.id=? AND l.month_id=? AND l.booking_id=?',(lesson_id,month_id,booking_id)).fetchone()
   if row is None: raise SimError('NOT_FOUND','booking/lesson mismatch')
   state,price,refunded=row['state'],row['amount'],row['refunded']
   if action=='complete':
    if state!='reserved': raise SimError('INVALID_STATE','already processed')
    teacher=price*(10000-row['commission'])//10000
    referral=price*row['referral']//10000
    entries=[('teacher_accrual',teacher),('referral_accrual',referral),('platform_remainder',price-teacher-referral)]
    next_state='completed';new_refunded=refunded
   elif action=='refund':
    if state not in ('reserved','partially_refunded') or refunded+amount_krw>price: raise SimError('INVALID_STATE','refund not permitted')
    entries=[('refund_reversal',-amount_krw)]
    new_refunded=refunded+amount_krw
    next_state='refunded' if new_refunded==price else 'partially_refunded'
   else:
    if state!='reserved': raise SimError('INVALID_STATE','cancel not permitted')
    entries=[('refund_reversal',-price)]
    next_state='cancelled';new_refunded=price
   # Transaction ID is unique across all ledger kinds.
   if self.db.execute('SELECT 1 FROM ledger WHERE transaction_id=? LIMIT 1',(transaction_id,)).fetchone():
    raise SimError('CONFLICT','transaction reused across operations')
   try:
    self.db.executemany('INSERT INTO ledger(transaction_id,lesson_id,kind,amount) VALUES(?,?,?,?)',((transaction_id,lesson_id,k,v) for k,v in entries))
   except sqlite3.IntegrityError as exc:
    raise SimError('CONFLICT','transaction reused') from exc
   self.db.execute('UPDATE lessons SET state=?,refunded=? WHERE id=?',(next_state,new_refunded,lesson_id))
   return dict(transaction_id=transaction_id,state=next_state,real_money=False)
  return self.once(operation_id,['event',month_id,lesson_id,booking_id,transaction_id,action,amount_krw,currency,booking_state],apply)
 def totals(self,month_id):
  ident(month_id)
  lessons=self.db.execute('SELECT * FROM lessons WHERE month_id=?',(month_id,)).fetchall()
  if not lessons: raise SimError('NOT_FOUND','month')
  gross=sum(r['amount'] for r in lessons);refunds=sum(r['refunded'] for r in lessons)
  sums={r['kind']:r['total'] for r in self.db.execute('SELECT kind,SUM(amount) total FROM ledger WHERE lesson_id IN (SELECT id FROM lessons WHERE month_id=?) GROUP BY kind',(month_id,))}
  teacher=sums.get('teacher_accrual',0);referral=sums.get('referral_accrual',0);platform=sums.get('platform_remainder',0)
  pending=gross-refunds-teacher-referral-platform
  if pending<0 or sums.get('refund_reversal',0)!=-refunds: raise AssertionError('conservation')
  return dict(gross=gross,teacher=teacher,referral=referral,platform=platform,refunded=refunds,pending=pending,real_money=False,rates_approved=False)
