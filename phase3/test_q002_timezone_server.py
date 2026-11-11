import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import server


class ServerQ002Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = sqlite3.connect(str(Path(self.tmp.name) / 'review.sqlite3'))
        self.addCleanup(self.db.close)
        self.db.row_factory = sqlite3.Row
        # Isolated fixture schema: route executes real SQL without touching DB_PATH.
        self.db.executescript('''
            CREATE TABLE users (
                id TEXT PRIMARY KEY, nickname TEXT, role TEXT, approved INTEGER,
                languages TEXT, timezone TEXT, specialty TEXT, price INTEGER,
                level TEXT, qualifications TEXT, referral_code TEXT
            );
            CREATE TABLE audit (
                actor TEXT, action TEXT, entity TEXT, detail TEXT, created_at REAL
            );
            CREATE TABLE slots (
                id TEXT PRIMARY KEY, teacher_id TEXT, start REAL, end REAL
            );
            CREATE TABLE bookings (
                id TEXT PRIMARY KEY, learner_id TEXT, teacher_id TEXT,
                slot_id TEXT, room TEXT, created_at REAL, status TEXT,
                unit_id TEXT, price INTEGER
            );
            CREATE TABLE attendance (
                booking_id TEXT, user_id TEXT, joined REAL, last_seen REAL,
                seconds REAL, confirmed INTEGER
            );
            CREATE TABLE attendance_intervals (
                booking_id TEXT, user_id TEXT, start REAL, end REAL
            );
            CREATE TABLE payment_sessions (booking_id TEXT);
            CREATE TABLE disputes (
                id TEXT, booking_id TEXT, created_at REAL
            );
        ''')
        for uid, role, zone in (
            ('learner', 'learner', 'Asia/Kathmandu'),
            ('teacher', 'teacher', 'America/New_York'),
            ('other', 'learner', 'Asia/Seoul'),
        ):
            self.db.execute(
                'INSERT INTO users VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                (uid, uid, role, 1, 'ko,en', zone, 'conversation',
                 20000, 'beginner', 'fixture', 'ref-' + uid),
            )
        self.db.execute('INSERT INTO slots VALUES (?,?,?,?)',
                        ('slot', 'teacher', 1900000000.125, 1900001800.125))
        self.db.execute('INSERT INTO bookings VALUES (?,?,?,?,?,?,?,?,?)',
                        ('abc123', 'learner', 'teacher', 'slot', 'secret-room',
                         1899990000.25, 'test_paid', 'unit', 20000))
        self.db.execute('INSERT INTO attendance VALUES (?,?,?,?,?,?)',
                        ('abc123', 'learner', 1900000001.25,
                         1900000061.5, 60.25, 0))
        self.db.execute('INSERT INTO disputes VALUES (?,?,?)',
                        ('case', 'abc123', 1900000070.75))
        self.db.commit()
        self.handler = object.__new__(server.Handler)

    def call(self, uid, method, path, data=None):
        self.handler.command = method
        user = self.db.execute('SELECT * FROM users WHERE id=?', (uid,)).fetchone()
        with patch.object(self.handler, 'user', return_value=user):
            return self.handler.route(self.db, path, data or {}, {})

    def users(self):
        return [dict(row) for row in self.db.execute('SELECT * FROM users ORDER BY id')]

    def test_valid_iana_zones(self):
        for zone in ('Asia/Seoul', 'America/New_York', 'Asia/Kathmandu'):
            with self.subTest(zone=zone):
                result, cookie = self.call(
                    'learner', 'PUT', '/api/profile', {'timezone': zone})
                self.assertIsNone(cookie)
                self.assertEqual(result['user']['timezone'], zone)
                self.assertEqual(self.db.execute(
                    "SELECT timezone FROM users WHERE id='learner'"
                ).fetchone()[0], zone)

    def test_invalid_zone_rejected_before_any_update(self):
        for zone in ('Invalid/Definitely_Not_A_Zone', '../Asia/Seoul'):
            with self.subTest(zone=zone):
                before = self.users()
                audit_before = self.db.execute('SELECT count(*) FROM audit').fetchone()[0]
                statements = []
                self.db.set_trace_callback(statements.append)
                try:
                    with self.assertRaises(server.Error) as raised:
                        self.call('teacher', 'PUT', '/api/profile', {
                            'timezone': zone, 'nickname': 'Changed teacher',
                            'languages': 'changed', 'price': 31000,
                        })
                    self.assertEqual(raised.exception.status, 400)
                    # Check immediately, without rollback concealing an UPDATE.
                    self.assertEqual(self.users(), before)
                    self.assertEqual(self.db.execute(
                        'SELECT count(*) FROM audit').fetchone()[0], audit_before)
                    self.assertFalse(any(
                        sql.lstrip().upper().startswith('UPDATE')
                        for sql in statements
                    ), statements)
                finally:
                    self.db.set_trace_callback(None)

    def test_empty_legacy_zone_explicit_and_omitted(self):
        self.db.execute("UPDATE users SET timezone='' WHERE id='learner'")
        for data in ({'nickname': 'Legacy learner'}, {'timezone': ''}):
            with self.subTest(data=data):
                result, _ = self.call('learner', 'PUT', '/api/profile', data)
                self.assertEqual(result['user']['timezone'], '')
                self.assertEqual(self.db.execute(
                    "SELECT timezone FROM users WHERE id='learner'"
                ).fetchone()[0], '')

    def test_booking_participant_views_authorization_and_utc(self):
        booking_before = dict(self.db.execute('SELECT * FROM bookings').fetchone())
        slot_before = dict(self.db.execute('SELECT * FROM slots').fetchone())
        attendance_before = [dict(r) for r in self.db.execute('SELECT * FROM attendance')]
        disputes_before = [dict(r) for r in self.db.execute('SELECT * FROM disputes')]
        for uid in ('learner', 'teacher'):
            with self.subTest(uid=uid):
                result, cookie = self.call(uid, 'GET', '/api/bookings')
                self.assertIsNone(cookie)
                self.assertEqual(len(result['bookings']), 1)
                booking = result['bookings'][0]
                self.assertEqual(booking['learnerTimezone'], 'Asia/Kathmandu')
                self.assertEqual(booking['teacherTimezone'], 'America/New_York')
                self.assertNotIn('room', booking)
                for key, value in booking_before.items():
                    if key != 'room':
                        self.assertEqual(booking[key], value, key)
                self.assertEqual(booking['slot'], slot_before)
                self.assertEqual(booking['attendance'], attendance_before)
                self.assertEqual(booking['disputes'], disputes_before)
                self.assertEqual(booking['sharedSeconds'], 0)
                self.assertEqual(booking['paymentMode'], 'simulated-test-only')
        result, _ = self.call('other', 'GET', '/api/bookings')
        self.assertEqual(result['bookings'], [])
        self.assertEqual(dict(self.db.execute('SELECT * FROM bookings').fetchone()),
                         booking_before)
        self.assertEqual(dict(self.db.execute('SELECT * FROM slots').fetchone()),
                         slot_before)

    def test_booking_keeps_empty_participant_timezone(self):
        self.db.execute("UPDATE users SET timezone='' WHERE id='teacher'")
        for uid in ('learner', 'teacher'):
            with self.subTest(uid=uid):
                result, _ = self.call(uid, 'GET', '/api/bookings')
                self.assertEqual(result['bookings'][0]['teacherTimezone'], '')
                self.assertEqual(result['bookings'][0]['learnerTimezone'],
                                 'Asia/Kathmandu')


if __name__ == '__main__':
    unittest.main()
