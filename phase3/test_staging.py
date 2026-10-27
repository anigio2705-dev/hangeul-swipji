"""Real HTTP staging-boundary regression, using only a disposable SQLite DB."""
import base64
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

import server
import staging_server as staging


class StagingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = dict(HS_STAGING_ORIGIN='https://review.example.test', HS_STAGING_USER='review',
                        HS_STAGING_PASSWORD='Gate-Only-Test-Password-12345!',
                        HS_STAGING_ADMIN_PASSWORD='Admin-Only-Test-Password-12345!',
                        HS_STAGING_DB=str(Path(self.temp.name)/'hangeul-swipji-staging/platform.sqlite3'))
        self.settings = staging.Settings.from_env(self.env)
        self.old_db = server.DB_PATH
        staging.prepare_database(self.settings)
        self.http = server.ThreadingHTTPServer(('127.0.0.1', 0), staging.StagingHandler)
        self.http.staging = self.settings
        self.http.secure_cookies = True
        self.http.failures = {}
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        self.cookie = ''

    def tearDown(self):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join()
        server.DB_PATH = self.old_db
        self.temp.cleanup()

    def request(self, path, data=None, headers=None, authenticated=True):
        h = {'Host': 'review.example.test', 'Origin': self.settings.origin,
             'Content-Type': 'application/json', 'Cookie': self.cookie}
        if authenticated:
            h['Authorization'] = 'Basic '+base64.b64encode(('review:'+self.settings.gate_password).encode()).decode()
        h.update(headers or {})
        conn = http.client.HTTPConnection('127.0.0.1', self.http.server_port, timeout=10)
        conn.request('GET' if data is None else 'POST', path, None if data is None else json.dumps(data), h)
        response = conn.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        if response.getheader('Set-Cookie'): self.cookie = response.getheader('Set-Cookie').split(';')[0]
        conn.close()
        return result

    def register(self, email='learner@example.test'):
        return self.request('/api/register', dict(email=email, password='Learner-Password-12345!',
                            nickname='테스트 학생', role='learner', adultConsent=True))

    def test_config_fails_closed(self):
        for change in ({'HS_STAGING_ORIGIN':'http://review.example.test'}, {'HS_STAGING_ORIGIN':'https://review.example.test/'},
                       {'HS_STAGING_PASSWORD':'short'}, {'HS_STAGING_DB':'relative.sqlite3'},
                       {'HS_STAGING_DB':str(server.ROOT/'hangeul-swipji-staging/a.sqlite3')},
                       {'HS_STAGING_ADMIN_PASSWORD':self.settings.gate_password},
                       {'HS_SUPABASE_TEST_PROJECT_REF':'some-project'}, {'STRIPE_SECRET_KEY':'sk_live_forbidden'},
                       {'DATABASE_URL':'postgres://forbidden'}, {'HS_PHASE3_DB':'/tmp/old.sqlite3'}):
            with self.subTest(change=list(change)), self.assertRaises(ValueError):
                staging.Settings.from_env(dict(self.env, **change))

    def test_gate_covers_home_assets_and_api(self):
        for path in ('/', '/phase3/app.js', '/api/units'):
            status, headers, body = self.request(path, authenticated=False)
            self.assertEqual(401, status)
            self.assertIn('Basic realm=', headers['WWW-Authenticate'])
            self.assertNotIn(b'teacherGuide', body)
        self.assertEqual(401, self.request('/', headers={'Authorization':'Basic !!!'})[0])

    def test_exact_host_origin_and_forwarded_spoofing(self):
        self.assertEqual(403, self.request('/', headers={'Host':'attacker.test','X-Forwarded-Host':'review.example.test'})[0])
        self.assertEqual(403, self.register_with_origin('https://attacker.test'))
        self.assertEqual(403, self.register_with_origin(''))
        self.assertEqual(403, self.request('/', headers={'Sec-Fetch-Site':'cross-site'})[0])

    def register_with_origin(self, origin):
        return self.request('/api/login', {}, headers={'Origin':origin, 'X-Forwarded-Proto':'https'})[0]

    def test_home_unchanged_and_private_files_blocked(self):
        status, headers, body = self.request('/')
        self.assertEqual(200, status)
        self.assertEqual((server.ROOT.parent/'index.html').read_bytes(), body)
        self.assertIn('noindex', headers['X-Robots-Tag'])
        self.assertIn("connect-src 'self'", headers['Content-Security-Policy'])
        for path in ('/phase3/staging_server.py','/phase3/content-remaining72.json','/.git/config','/phase3/schema.sql'):
            self.assertEqual(404, self.request(path)[0])
        self.assertEqual('/index.html#teaching-platform', self.request('/phase3/index.html')[1]['Location'])

    def test_legacy_links_cannot_reach_existing_hosted_database(self):
        for path in ('/speaking-platform.html', '/speaking%2dplatform.html'):
            self.assertEqual('/index.html#teaching-platform', self.request(path)[1]['Location'])
        status, _, body = self.request('/speaking-config.js')
        self.assertEqual(200, status)
        self.assertNotIn(b'supabase.co', body)
        self.assertNotIn(b'sb_publishable_', body)
        self.assertIn(b'window.HS_CONFIG = {};', body)

    def test_signup_secure_cookie_96_units_and_logout(self):
        self.assertEqual(400, self.register('real@example.com')[0])
        status, headers, body = self.register()
        self.assertEqual(200, status)
        self.assertIn('; Secure', headers['Set-Cookie'])
        self.assertIn('HttpOnly', headers['Set-Cookie'])
        self.assertEqual(200, self.request('/api/me')[0])
        status, _, body = self.request('/api/units')
        self.assertEqual(200, status)
        self.assertEqual(96, len(json.loads(body)['units']))
        self.assertNotIn(b'teacherGuide', body)
        status, headers, _ = self.request('/api/logout', {})
        self.assertEqual(200, status)
        self.assertIn('; Secure', headers['Set-Cookie'])

    def test_external_integrations_blocked_and_mock_only(self):
        for path in ('/api/auth/supabase', '/api/payments/stripe-test/webhook'):
            self.assertEqual(403, self.request(path, {})[0])
        body = json.loads(self.request('/api/integrations')[2])
        self.assertFalse(body['realMoneyEnabled'])
        self.assertFalse(body['productionDatabaseUsed'])

    def test_admin_bootstrap_idempotent_and_no_password_reset(self):
        staging.prepare_database(self.settings)
        with server.connect() as db:
            self.assertEqual(1, db.execute("SELECT count(*) FROM users WHERE role='admin'").fetchone()[0])
        wrong = staging.Settings.from_env(dict(self.env, HS_STAGING_ADMIN_PASSWORD='Other-Admin-Password-123456!'))
        with self.assertRaises(ValueError): staging.prepare_database(wrong)
        self.assertEqual(200, self.request('/api/login',dict(email='admin@example.test',password=self.settings.admin_password))[0])

    def test_health_only_without_gate_and_db_failure(self):
        status, _, body = self.request('/healthz', authenticated=False)
        self.assertEqual(200, status)
        self.assertEqual({'mode':'test','ok':True,'scope':'isolated-staging'}, json.loads(body))
        with patch.object(server, 'connect', side_effect=RuntimeError('private failure')):
            status, _, body = self.request('/healthz', authenticated=False)
        self.assertEqual(503, status)
        self.assertNotIn(b'private failure', body)


if __name__ == '__main__': unittest.main()
