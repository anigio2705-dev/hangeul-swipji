"""SQLite referral relationships and simulated award deduplication; NO real payments.

Caller must supply trusted server-side identities and booking data. This module is
never an HTTP endpoint and does not establish user authentication.
"""
import sqlite3
from team14_persistent import SimError,ident,amount
from team14_referral_eligibility import eligible_referral
import json

def _verified_award(raw, student_id, gross_krw):
 """Fail closed on corrupt persisted mock awards, including idempotent replays."""
 try:
  result=json.loads(raw)
  if not isinstance(result,dict) or result.get('student_id')!=student_id or result.get('gross_krw')!=gross_krw:
   raise ValueError('award identity mismatch')
  recipients=result.get('recipients')
  if not isinstance(recipients,list) or len(recipients)>10:
   raise ValueError('invalid recipients')
  seen=set()
  for row in recipients:
   if not isinstance(row,dict) or type(row.get('amount_krw')) is not int or row['amount_krw']<0:
    raise ValueError('invalid recipient amount')
   recipient=ident(row.get('user_id'))
   if recipient==student_id or recipient in seen:
    raise ValueError('duplicate or self recipient')
   seen.add(recipient)
  teacher=result.get('teacher_krw');platform=result.get('platform_krw')
  if (type(teacher) is not int or type(platform) is not int or teacher<0 or platform<0
      or teacher+platform+sum(row['amount_krw'] for row in recipients)!=gross_krw
      or result.get('real_money') is not False
      or result.get('policy_approved') is not False
      or result.get('payment_enabled') is not False):
   raise ValueError('invalid award totals or safety flags')
  return result
 except (TypeError,ValueError,KeyError,SimError) as exc:
  raise SimError('CONFLICT','stored referral award invalid') from exc

class ReferralStore:
 def __init__(self,path=':memory:'):
  self.db=sqlite3.connect(path,isolation_level=None,timeout=10)
  self.db.row_factory=sqlite3.Row
  self.db.execute('PRAGMA foreign_keys=ON')
  self.db.executescript("""
CREATE TABLE IF NOT EXISTS referral_links(
 student_id TEXT PRIMARY KEY,parent_id TEXT NOT NULL,
 CHECK(student_id <> parent_id));
CREATE TABLE IF NOT EXISTS referral_awards(
 event_id TEXT PRIMARY KEY,student_id TEXT NOT NULL,lesson_id TEXT NOT NULL,
 gross_krw INTEGER NOT NULL,signature TEXT NOT NULL,result TEXT NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS one_referral_award_per_lesson
 ON referral_awards(lesson_id);
""")
 def close(self):self.db.close()
 def link(self,student_id,parent_id):
  ident(student_id);ident(parent_id)
  if student_id==parent_id:raise SimError('CONFLICT','self referral')
  self.db.execute('BEGIN IMMEDIATE')
  try:
   prior=self.db.execute('SELECT parent_id FROM referral_links WHERE student_id=?',(student_id,)).fetchone()
   if prior:
    if prior['parent_id']!=parent_id:raise SimError('CONFLICT','referral parent immutable')
    self.db.execute('COMMIT');return False
   cur=parent_id;seen={student_id}
   while True:
    if cur in seen:raise SimError('CONFLICT','referral cycle')
    seen.add(cur)
    r=self.db.execute('SELECT parent_id FROM referral_links WHERE student_id=?',(cur,)).fetchone()
    if not r:break
    cur=r['parent_id']
   self.db.execute('INSERT INTO referral_links VALUES(?,?)',(student_id,parent_id))
   self.db.execute('COMMIT');return True
  except BaseException:
   self.db.execute('ROLLBACK');raise
 def award(self,event_id,student_id,lesson_id,gross_krw,depth_rates_bps=(300,),commission_bps=2000):
  import json
  ident(event_id);ident(student_id);ident(lesson_id);amount(gross_krw,True)
  if not isinstance(depth_rates_bps,(list,tuple)) or len(depth_rates_bps)>10:
   raise SimError('VALIDATION_ERROR','referral rate policy must be a bounded list')
  signature=json.dumps([student_id,lesson_id,gross_krw,list(depth_rates_bps),commission_bps],separators=(',',':'))
  self.db.execute('BEGIN IMMEDIATE')
  try:
   old=self.db.execute('SELECT signature,result FROM referral_awards WHERE event_id=?',(event_id,)).fetchone()
   if old:
    if old['signature']!=signature:raise SimError('CONFLICT','event replay changed')
    verified=_verified_award(old['result'],student_id,gross_krw)
    self.db.execute('COMMIT');return verified
   if self.db.execute('SELECT 1 FROM referral_awards WHERE lesson_id=?',(lesson_id,)).fetchone():
    raise SimError('CONFLICT','lesson already awarded')
   edges=[(r['student_id'],r['parent_id']) for r in self.db.execute('SELECT student_id,parent_id FROM referral_links')]
   result=eligible_referral(gross_krw,student_id,edges,depth_rates_bps,commission_bps)
   self.db.execute('INSERT INTO referral_awards VALUES(?,?,?,?,?,?)',
    (event_id,student_id,lesson_id,gross_krw,signature,json.dumps(result,sort_keys=True)))
   self.db.execute('COMMIT');return result
  except BaseException:
   self.db.execute('ROLLBACK');raise
 def awards_for_lesson(self,lesson_id):
  import json
  ident(lesson_id)
  r=self.db.execute('SELECT student_id,gross_krw,result FROM referral_awards WHERE lesson_id=?',(lesson_id,)).fetchone()
  if not r:raise SimError('NOT_FOUND','award not found')
  return _verified_award(r['result'],r['student_id'],r['gross_krw'])
