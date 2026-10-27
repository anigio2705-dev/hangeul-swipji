"""Real HTTP staging-boundary regression, using only a disposable SQLite DB."""
import base64
import hashlib
import http.client
from http.cookies import SimpleCookie
import json
from pathlib import Path
import tempfile
import threading
import time
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
        h = {key:value for key,value in h.items() if value is not None}
        conn = http.client.HTTPConnection('127.0.0.1', self.http.server_port, timeout=10)
        conn.request('GET' if data is None else 'POST', path, None if data is None else json.dumps(data), h)
        response = conn.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        jar = SimpleCookie(self.cookie)
        for key, value in response.getheaders():
            if key.lower() == 'set-cookie':
                jar.load(value)
        self.cookie = '; '.join(f'{k}={v.value}' for k,v in jar.items())
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
            if path == '/': self.assertIn('Basic realm=', headers['WWW-Authenticate'])
            else: self.assertNotIn('WWW-Authenticate', headers)
            self.assertNotIn(b'teacherGuide', body)
        self.assertEqual(401, self.request('/', headers={'Authorization':'Basic !!!'})[0])

    def test_gate_cookie_keeps_navigation_and_app_login_without_basic(self):
        status, headers, _ = self.request('/speaking-platform.html')
        self.assertEqual(302,status)
        cookie=headers['Set-Cookie']
        for flag in ('hs_staging_gate=', 'Path=/', 'HttpOnly', 'Secure', 'SameSite=Strict'):
            self.assertIn(flag,cookie)
        self.assertNotIn(self.settings.gate_password,cookie)
        self.assertNotIn('Domain=',cookie)
        self.assertEqual(200,self.request('/index.html',authenticated=False)[0])
        self.assertEqual(200,self.request('/api/units',authenticated=False)[0])
        status,headers,_=self.request('/api/login',dict(email='admin@example.test',password='wrong'),authenticated=False)
        self.assertEqual(401,status)
        self.assertNotIn('WWW-Authenticate',headers)
        status,_,_=self.request('/api/login',dict(email='admin@example.test',password=self.settings.admin_password),authenticated=False)
        self.assertEqual(200,status)
        self.assertEqual(200,self.request('/api/me',authenticated=False)[0])
        self.assertEqual(200,self.request('/api/logout',{},authenticated=False)[0])
        self.assertEqual(200,self.request('/index.html',authenticated=False)[0])
        self.assertEqual(403,self.request('/api/units',headers={'Origin':'https://foreign.test'},authenticated=False)[0])

    def test_gate_cookie_expiry_tampering_and_no_background_challenges(self):
        with patch.object(staging.time,'time',return_value=1000): token=staging.gate_token(self.settings)
        with patch.object(staging.time,'time',return_value=1001):
            self.assertTrue(staging.valid_gate_cookie(self.settings,f'{staging.GATE_COOKIE}={token}'))
            self.assertFalse(staging.valid_gate_cookie(self.settings,f'{staging.GATE_COOKIE}={token[:-1]}z'))
        for now in (999,1000+staging.GATE_TTL):
            with patch.object(staging.time,'time',return_value=now):
                self.assertFalse(staging.valid_gate_cookie(self.settings,f'{staging.GATE_COOKIE}={token}'))
        other=staging.Settings.from_env(dict(self.env,HS_STAGING_PASSWORD='New-Gate-Password-123456789!'))
        self.assertFalse(staging.valid_gate_cookie(other,f'{staging.GATE_COOKIE}={staging.gate_token(self.settings)}'))
        self.cookie=f'{staging.GATE_COOKIE}=invalid'
        for path,dest in (('/api/me','empty'),('/phase3/app.js','script')):
            status,headers,body=self.request(path,headers={'Sec-Fetch-Mode':'cors','Sec-Fetch-Dest':dest},authenticated=False)
            self.assertEqual(401,status)
            self.assertNotIn('WWW-Authenticate',headers)
            self.assertEqual('STAGING_GATE_REQUIRED',json.loads(body)['code'])

    def test_gate_cookie_preserves_admission_on_speaking_redirect(self):
        status, headers, _ = self.request('/')
        self.assertEqual(200, status)
        cookie = headers['Set-Cookie'].split(';')[0]
        for flag in ('Path=/', 'Secure', 'HttpOnly', 'SameSite=Strict'):
            self.assertIn(flag, headers['Set-Cookie'])
        self.cookie = cookie
        status, headers, _ = self.request('/speaking-platform.html?lang=ko', authenticated=False)
        self.assertEqual(302, status)
        self.assertEqual('/index.html#teaching-platform', headers['Location'])
        self.assertEqual(200, self.request('/index.html', authenticated=False)[0])
        self.assertEqual(403, self.request('/api/me', authenticated=False,
            headers={'Origin':'https://attacker.test'})[0])
        self.cookie = cookie + 'tampered'
        self.assertEqual(401, self.request('/', authenticated=False)[0])
        self.cookie = cookie
        self.assertEqual(401, self.request('/', headers={'Authorization':'Basic !!!'})[0])

    def test_exact_host_origin_and_forwarded_spoofing(self):
        self.assertEqual(403, self.request('/', headers={'Host':'attacker.test','X-Forwarded-Host':'review.example.test'})[0])
        self.assertEqual(403, self.register_with_origin('https://attacker.test'))
        self.assertEqual(403, self.register_with_origin(''))
        self.assertEqual(403, self.request('/', headers={'Sec-Fetch-Site':'cross-site'})[0])

    def test_external_link_document_navigation_allowed_with_gate(self):
        navigation = {'Sec-Fetch-Site':'cross-site', 'Sec-Fetch-Mode':'navigate',
                      'Sec-Fetch-Dest':'document', 'Referer':'https://dashboard.render.com/', 'Origin':None}
        for path in ('/', '/index.html', '/learn.html', '/phase3/index.html'):
            with self.subTest(path=path):
                self.assertIn(self.request(path, headers=navigation)[0], (200,302))
        self.cookie = ''
        self.assertEqual(401, self.request('/', headers=navigation, authenticated=False)[0])

    def test_direct_navigation_and_same_origin_fetch_allowed(self):
        direct = {'Origin':None, 'Sec-Fetch-Site':'none', 'Sec-Fetch-Mode':'navigate', 'Sec-Fetch-Dest':'document'}
        self.assertEqual(200, self.request('/', headers=direct)[0])
        self.assertEqual(200, self.request('/phase3/app.js', headers={'Origin':None,
            'Referer':self.settings.origin+'/', 'Sec-Fetch-Site':'same-origin',
            'Sec-Fetch-Mode':'no-cors','Sec-Fetch-Dest':'script'})[0])
        self.assertEqual(200, self.request('/api/integrations', headers={'Origin':None,
            'Referer':self.settings.origin+'/?lang=ko', 'Sec-Fetch-Site':'same-origin',
            'Sec-Fetch-Mode':'cors','Sec-Fetch-Dest':'empty'})[0])

    def test_external_api_frames_and_mutations_still_denied(self):
        for path in ('/', '/api/integrations', '/api/me'):
            for mode,dest in (('cors','empty'),('no-cors','script'),('navigate','iframe')):
                self.assertEqual(403, self.request(path,headers={'Origin':None,'Sec-Fetch-Site':'cross-site',
                    'Sec-Fetch-Mode':mode,'Sec-Fetch-Dest':dest})[0])
        self.assertEqual(403, self.request('/api/integrations',headers={'Origin':None,
            'Sec-Fetch-Site':'cross-site','Sec-Fetch-Mode':'navigate','Sec-Fetch-Dest':'document'})[0])
        self.assertEqual(403, self.request('/api/integrations',headers={'Origin':None,
            'Sec-Fetch-Site':'same-site','Sec-Fetch-Mode':'cors','Sec-Fetch-Dest':'empty'})[0])
        self.assertEqual(403, self.request('/api/login',{},headers={'Origin':'https://attacker.test',
            'Sec-Fetch-Site':'cross-site','Sec-Fetch-Mode':'navigate','Sec-Fetch-Dest':'document'})[0])
        self.assertEqual(403, self.request('/api/login',{},headers={'Origin':None,
            'Sec-Fetch-Site':'none'})[0])

    def test_referer_validation_does_not_use_prefix_matching(self):
        for referer in ('https://attacker.test/',self.settings.origin+'.attacker.test/',
                        'https://review.example.test@attacker.test/', 'not-a-url', 'https://['):
            self.assertEqual(403, self.request('/api/login',{},headers={'Referer':referer})[0])
        self.assertEqual(200, self.request('/api/login',dict(email='admin@example.test',password=self.settings.admin_password),
            headers={'Referer':self.settings.origin+'/?lang=ko','Sec-Fetch-Site':'same-origin'})[0])

    def test_render_origin_fallback_matches_explicit_configuration(self):
        env = dict(self.env)
        env['RENDER_EXTERNAL_URL'] = env.pop('HS_STAGING_ORIGIN')
        self.assertEqual(self.settings, staging.Settings.from_env(env))

    def test_same_origin_login_booking_homework_feedback_and_second_booking(self):
        self.assertEqual(200,self.request('/')[0])  # Gate sign-in happens once.
        context = {'Origin':self.settings.origin,'Referer':self.settings.origin+'/',
                   'Sec-Fetch-Site':'same-origin','Sec-Fetch-Mode':'cors','Sec-Fetch-Dest':'empty'}
        def call(path, data=None):
            status, _, body = self.request(path,data,headers=context,authenticated=False)
            self.assertEqual(200,status,body)
            return json.loads(body)
        password = 'Disposable-Origin-Test-12345!'
        def login(email, secret=password): return call('/api/login',dict(email=email,password=secret))
        teacher = call('/api/register',dict(email='teacher@example.test',password=password,
            nickname='테스트 강사',role='teacher',adultConsent=True))['user']
        call('/api/register',dict(email='student@example.test',password=password,
            nickname='테스트 학생',role='learner',adultConsent=True))
        login('admin@example.test',self.settings.admin_password)
        call('/api/admin/verify',dict(userId=teacher['id'],approved=True,reason='Disposable local test approval only'))
        login('teacher@example.test')
        start=time.time()+120
        slot1=call('/api/availability',dict(start=start,end=start+2400))['slotId']
        slot2=call('/api/availability',dict(start=start+3600,end=start+6000))['slotId']
        login('student@example.test')
        units=call('/api/units')['units']
        bid=call('/api/bookings',dict(teacherId=teacher['id'],slotId=slot1,unitId=units[0]['id']))['bookingId']
        self.assertFalse(call('/api/bookings/'+bid+'/pay-test',{})['chargedRealMoney'])
        call('/api/bookings/'+bid+'/homework',dict(text='테스트 과제입니다.'))
        login('teacher@example.test')
        call('/api/bookings/'+bid+'/join',{})
        call('/api/bookings/'+bid+'/feedback',dict(text='테스트 피드백입니다.',score=85))
        login('student@example.test')
        call('/api/bookings',dict(teacherId=teacher['id'],slotId=slot2,unitId=units[1]['id']))
        bookings=call('/api/bookings')['bookings']
        self.assertEqual(2,len(bookings))
        first=next(b for b in bookings if b['id']==bid)
        self.assertEqual('테스트 과제입니다.',first['homework'])
        self.assertEqual(85,first['score'])

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
        health = json.loads(body)
        self.assertTrue(health['ok'])
        self.assertEqual('test',health['mode'])
        self.assertEqual('isolated-staging',health['scope'])
        self.assertEqual('document-navigation-v2',health['requestGuardVersion'])
        self.assertEqual('signed-cookie-v1',health['gateSessionVersion'])
        self.assertEqual('embedded-preview-v1',health['videoUIVersion'])
        self.assertEqual(hashlib.sha256((server.ROOT/'app.js').read_bytes()).hexdigest(),health['appSHA256'])
        self.assertEqual(self.settings.origin,health['configuredOrigin'])
        self.assertEqual(hashlib.sha256(Path(staging.__file__).read_bytes()).hexdigest(),health['sourceSHA256'])
        with patch.object(server, 'connect', side_effect=RuntimeError('private failure')):
            status, _, body = self.request('/healthz', authenticated=False)
        self.assertEqual(503, status)
        self.assertNotIn(b'private failure', body)


if __name__ == '__main__': unittest.main()
