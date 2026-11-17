"""Local test-only crash injection. Real HTTP/SQLite; no live services or money.

The child uses the unchanged product routes. A test Connection subclass pauses
immediately before commit; a test Handler pauses after commit, before response.
The parent SIGKILLs that child, then starts a new process against the same DB.
This is harness-driven restart, not proof of an ABCD/AS supervisor recovering.
"""
import concurrent.futures
import hashlib
import http.client
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]


def child(database, port, control):
    os.environ['HS_PHASE3_DB'] = database
    sys.path.insert(0, str(ROOT / 'phase3'))
    import server
    arm = Path(control) / 'arm.json'
    marker = Path(control) / 'paused.json'

    def pause(phase, endpoint=None):
        if not arm.exists():
            return
        setting = json.loads(arm.read_text())
        if setting['phase'] != phase or (endpoint and endpoint != setting['endpoint']):
            return
        marker.write_text(json.dumps({'phase': phase, 'pid': os.getpid()}))
        # The parent always kills this child, with a bounded timeout on its wait.
        threading.Event().wait(30)
        raise RuntimeError('crash injection parent did not kill child')

    class CrashConnection(sqlite3.Connection):
        def commit(self):
            pause('before_commit')
            return super().commit()

    def connect():
        db = sqlite3.connect(database, timeout=10, factory=CrashConnection)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        return db

    class CrashHandler(server.Handler):
        def send(self, status, value, cookie=None):
            if status == 200:
                pause('after_commit_before_response', self.path)
            return super().send(status, value, cookie)

    server.connect = connect
    server.init_db()
    with server.connect() as db:
        existing = db.execute('SELECT id FROM users WHERE email=?', ('crash-admin@example.test',)).fetchone()
    if existing is None:
        server.create_admin('crash-admin@example.test', 'Local-Crash-Admin-12345!')
    app = server.ThreadingHTTPServer(('127.0.0.1', int(port)), CrashHandler)
    app.failures = {}
    print('READY', flush=True)
    app.serve_forever()


class CrashBoundaries(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='hs-crash-only-')
        self.folder = Path(self.temp.name)
        self.database = self.folder / 'test.sqlite3'
        self.arm = self.folder / 'arm.json'
        self.marker = self.folder / 'paused.json'
        self.process = None
        self.events = []
        self.log = (self.folder / 'server.log').open('w')
        self.addCleanup(self.cleanup)
        self.launch()
        self.admin = self.login('crash-admin@example.test', 'Local-Crash-Admin-12345!')
        self.learner, _ = self.register('crash-learner', 'learner')
        self.teacher, user = self.register('crash-teacher', 'teacher')
        self.expect('/api/admin/verify', {'userId': user['id'], 'approved': True,
                    'reason': 'Disposable test-only provider review.'}, self.admin)
        units = self.expect('/api/units')['units']
        slot = self.expect('/api/availability', {'start': time.time()+600,
                           'end': time.time()+4200}, self.teacher)
        self.bid = self.expect('/api/bookings', {'teacherId': user['id'],
                              'slotId': slot['slotId'], 'unitId': units[0]['id']}, self.learner)['bookingId']
        self.pay = '/api/bookings/'+self.bid+'/pay-test'

    def cleanup(self):
        if self.process and self.process.poll() is None:
            self.process.kill()
            self.process.wait(timeout=5)
        self.log.close()
        self.temp.cleanup()

    def launch(self):
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            self.port = listener.getsockname()[1]
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(('HS_', 'SUPABASE', 'STRIPE', 'DATABASE_URL'))}
        self.process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()),
                    '--child', str(self.database), str(self.port), str(self.folder)],
                    env=env, stdout=self.log, stderr=self.log)
        deadline = time.monotonic()+10
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError((self.folder/'server.log').read_text())
            try:
                if self.call('/api/units')[0] == 200:
                    return
            except OSError:
                pass
            time.sleep(.02)
        raise TimeoutError('local server did not start')

    def call(self, endpoint, data=None, cookie=''):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=12)
        try:
            conn.request('POST' if data is not None else 'GET', endpoint,
                None if data is None else json.dumps(data),
                {'Content-Type': 'application/json', 'Cookie': cookie})
            response = conn.getresponse()
            return response.status, json.loads(response.read()), response.getheader('Set-Cookie', '').split(';')[0]
        finally:
            conn.close()

    def expect(self, endpoint, data=None, cookie=''):
        status, body, _ = self.call(endpoint, data, cookie)
        self.assertEqual(200, status, body)
        return body

    def login(self, email, password):
        status, body, cookie = self.call('/api/login', {'email': email, 'password': password})
        self.assertEqual(200, status, body)
        return cookie

    def register(self, name, role):
        status, body, cookie = self.call('/api/register', {'email': name+'@example.test',
            'password': 'Local-Only-Test-12345!', 'nickname': name, 'role': role, 'adultConsent': True})
        self.assertEqual(200, status, body)
        return cookie, body['user']

    def snapshot(self):
        with sqlite3.connect(self.database) as db:
            return {table: db.execute('SELECT * FROM '+table+' ORDER BY rowid').fetchall()
                    for table in ['ledger', 'local_refund_requests', 'local_refund_adjustments', 'disputes', 'bookings', 'audit']}

    def crash(self, phase, endpoint, body, cookie):
        self.arm.write_text(json.dumps({'phase': phase, 'endpoint': endpoint}))
        oldpid = self.process.pid
        with concurrent.futures.ThreadPoolExecutor(1) as pool:
            request = pool.submit(self.call, endpoint, body, cookie)
            deadline = time.monotonic()+10
            while not self.marker.exists() and time.monotonic() < deadline:
                if request.done():
                    self.fail('request completed without reaching injection: '+str(request.result()))
                time.sleep(.01)
            self.assertTrue(self.marker.exists(), 'crash boundary was not reached')
            self.assertEqual(phase, json.loads(self.marker.read_text())['phase'])
            self.process.kill()
            self.process.wait(timeout=5)
            self.assertEqual(-9, self.process.returncode)
            with self.assertRaises((OSError, http.client.HTTPException)):
                request.result(timeout=5)
        self.arm.unlink()
        self.marker.unlink()
        self.launch()
        self.assertNotEqual(oldpid, self.process.pid)
        self.expect('/api/me', cookie=self.learner)
        with sqlite3.connect(self.database) as db:
            self.assertEqual('ok', db.execute('PRAGMA integrity_check').fetchone()[0])
            self.assertEqual([], db.execute('PRAGMA foreign_key_check').fetchall())
        print(json.dumps({'boundary': phase, 'endpoint_kind': 'refund' if '/admin/' in endpoint else 'pay-test',
                          'killed_pid': oldpid, 'new_pid': self.process.pid,
                          'exit': -9, 'integrity': 'ok', 'session_preserved': True}), flush=True)

    def test_charge_uncommitted_kill_rolls_back_then_concurrent_retry_posts_once(self):
        before = self.snapshot()
        self.crash('before_commit', self.pay, {}, self.learner)
        self.assertEqual(before, self.snapshot())
        with concurrent.futures.ThreadPoolExecutor(8) as pool:
            results = list(pool.map(lambda _: self.call(self.pay, {}, self.learner), range(8)))
        self.assertEqual([200]*8, [x[0] for x in results])
        self.assertTrue(all(x[1]['chargedRealMoney'] is False for x in results))
        self.assertEqual(1, len(self.snapshot()['ledger']))

    def test_charge_committed_lost_response_replays_without_duplicate(self):
        self.crash('after_commit_before_response', self.pay, {}, self.learner)
        before = self.snapshot()
        self.assertEqual(1, len(before['ledger']))
        self.expect(self.pay, {}, self.learner)
        self.assertEqual(before, self.snapshot())

    def prepare_refund(self):
        self.expect(self.pay, {}, self.learner)
        dispute = self.expect('/api/bookings/'+self.bid+'/dispute',
                    {'category': 'refund', 'reason': 'Crash boundary disposable refund evidence.'}, self.learner)
        self.expect('/api/bookings/'+self.bid+'/disputes/'+dispute['disputeId']+'/statements',
                    {'text': 'Actual counterpart test account statement for crash review.'}, self.teacher)
        return '/api/admin/disputes/'+dispute['disputeId'], {
            'decision': 'refund', 'reason': 'Local crash test administrator review only.'}

    def test_refund_uncommitted_kill_preserves_all_tables_then_retries_once(self):
        endpoint, body = self.prepare_refund()
        before = self.snapshot()
        self.crash('before_commit', endpoint, body, self.admin)
        self.assertEqual(before, self.snapshot())
        self.assertFalse(self.expect(endpoint, body, self.admin)['duplicate'])
        final = self.snapshot()
        self.assertEqual(1, len(final['local_refund_requests']))
        self.assertEqual(1, len(final['local_refund_adjustments']))
        self.assertEqual(0, sum(row[3] for row in final['ledger']))

    def test_refund_committed_lost_response_concurrent_replay_is_idempotent(self):
        endpoint, body = self.prepare_refund()
        self.crash('after_commit_before_response', endpoint, body, self.admin)
        before = self.snapshot()
        self.assertEqual(1, len(before['local_refund_requests']))
        with concurrent.futures.ThreadPoolExecutor(8) as pool:
            results = list(pool.map(lambda _: self.call(endpoint, body, self.admin), range(8)))
        self.assertEqual([200]*8, [x[0] for x in results])
        self.assertTrue(all(x[1]['duplicate'] and x[1]['realRefund'] is False for x in results))
        self.assertEqual(before, self.snapshot())


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--child':
        child(*sys.argv[2:])
    else:
        print('SOURCE_SERVER_SHA256='+hashlib.sha256((ROOT/'phase3/server.py').read_bytes()).hexdigest(), flush=True)
        unittest.main(verbosity=2)
