"""SQLite referral relationships and simulated award deduplication; NO real payments.

Caller must supply trusted server-side identities and booking data. This module is
never an HTTP endpoint and does not establish user authentication.
"""
import sqlite3
from team14_persistent import SimError, ident, amount
from team14_referral_eligibility import eligible_referral

class ReferralStore:
 def __init__(self, path=':memory:'):
  self.db = sqlite3.connect(path, isolation_level=None, timeout=10)
  self.db.row_factory = sqlite3.Row
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
 
 def close(self):
  self.db.close()
 
 def link(self, student_id, parent_id):
  ident(student_id); ident(parent_id)
  if student_id == parent_id:
   raise SimError('CONFLICT', 'self referral')
  self.db.execute('BEGIN IMMEDIATE')
  try:
   prior = self.db.execute('SELECT parent_id FROM referral_links WHERE student_id=?', (student_id,)).fetchone()
   if prior:
    if prior['parent_id'] != parent_id:
     raise SimError('CONFLICT', 'referral parent immutable')
    self.db.execute('COMMIT')
    return False
   cur = parent_id
   seen = {student_id}
   while True:
    if cur in seen:
     raise SimError('CONFLICT', 'referral cycle')
    seen.add(cur)
    r = self.db.execute('SELECT parent_id FROM referral_links WHERE student_id=?', (cur,)).fetchone()
    if not r:
     break
    cur = r['parent_id']
   self.db.execute('INSERT INTO referral_links VALUES(?, ?)', (student_id, parent_id))
   self.db.execute('COMMIT')
   return True
  except BaseException:
   self.db.execute('ROLLBACK')
   raise
 
 def award(self, event_id, student_id, lesson_id, gross_krw, depth_rates_bps=(300,), commission_bps=2000):
  import json

  # Validate input types and basic format for all string IDs
  for val, name in [(student_id, 'student_id'), (event_id, 'event_id'), (lesson_id, 'lesson_id')]:
   if not isinstance(val, str) or not val.strip():
    raise SimError('INVALID_INPUT', f'{name} must be a non-empty string')
   if any(c.isspace() for c in val):
    raise SimError('INVALID_INPUT', f'{name} must not contain whitespace characters')

  # Use external validators for further checks
  ident(event_id); ident(student_id); ident(lesson_id)
  amount(gross_krw, True)

  # Additional validation: depth_rates_bps and commission_bps types and values
  if (not isinstance(depth_rates_bps, (list, tuple)) or
      not all(isinstance(rate, int) and rate >= 0 for rate in depth_rates_bps)):
   raise SimError('INVALID_INPUT', 'depth_rates_bps must be a list or tuple of non-negative integers')

  if not isinstance(commission_bps, int) or commission_bps < 0:
   raise SimError('INVALID_INPUT', 'commission_bps must be a non-negative integer')

  # Defensive check: refuse to award if string IDs contain suspicious, whitespace, non-ASCII or control chars
  suspicious_chars = '\\"\'%;'
  for val, name in [(student_id, 'student_id'), (lesson_id, 'lesson_id'), (event_id, 'event_id')]:
   if any(c in val for c in suspicious_chars):
    raise SimError('INVALID_INPUT', f'{name} contains invalid characters')
   if not all(32 <= ord(c) <= 126 for c in val):
    raise SimError('INVALID_INPUT', f'{name} contains invalid characters')
   if any(c.isspace() for c in val):
    raise SimError('INVALID_INPUT', f'{name} must not contain whitespace characters')

  # Defensive check: refuse to award an event ID that already exists but with empty or inconsistent essential fields
  if not event_id or len(event_id) == 0:
    raise SimError('INVALID_INPUT', 'event_id must be a non-empty string')

  # New stricter check for event_id: reject if contains any control chars or non-printable ASCII
  for c in event_id:
   if ord(c) < 33 or ord(c) > 126:
    raise SimError('INVALID_INPUT', 'event_id contains control or non-printable characters')

  # New stricter check for student_id and lesson_id: disallow leading or trailing whitespace
  for val, name in [(student_id, 'student_id'), (lesson_id, 'lesson_id')]:
   if val != val.strip():
    raise SimError('INVALID_INPUT', f'{name} must not have leading or trailing whitespace')

  signature = json.dumps([student_id, lesson_id, gross_krw, list(depth_rates_bps), commission_bps], separators=(',', ':'))
  self.db.execute('BEGIN IMMEDIATE')
  try:
   # Check for replay conflict
   old = self.db.execute('SELECT signature, result FROM referral_awards WHERE event_id=?', (event_id,)).fetchone()
   if old:
    if old['signature'] != signature:
     raise SimError('CONFLICT', 'event replay changed')
    self.db.execute('COMMIT')
    return json.loads(old['result'])

   # Strict check that this lesson has no prior award
   if self.db.execute('SELECT 1 FROM referral_awards WHERE lesson_id=?', (lesson_id,)).fetchone():
    raise SimError('CONFLICT', 'lesson already awarded')

   # Defensive check: ensure gross_krw > 0
   if gross_krw <= 0:
    raise SimError('INVALID_INPUT', 'gross_krw must be positive')

   edges = [(r['student_id'], r['parent_id']) for r in self.db.execute('SELECT student_id, parent_id FROM referral_links')]
   result = eligible_referral(gross_krw, student_id, edges, depth_rates_bps, commission_bps)
   self.db.execute('INSERT INTO referral_awards VALUES(?,?,?,?,?,?)',
                   (event_id, student_id, lesson_id, gross_krw, signature, json.dumps(result, sort_keys=True)))
   self.db.execute('COMMIT')
   return result
  except BaseException:
   self.db.execute('ROLLBACK')
   raise
 
 def awards_for_lesson(self, lesson_id):
  import json
  ident(lesson_id)
  r = self.db.execute('SELECT result FROM referral_awards WHERE lesson_id=?', (lesson_id,)).fetchone()
  if not r:
   raise SimError('NOT_FOUND', 'award not found')
  return json.loads(r['result'])
