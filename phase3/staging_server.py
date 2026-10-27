#!/usr/bin/env python3
"""Password-protected TEST host behind a provider's HTTPS proxy, never production."""
import base64
import binascii
import hashlib
from dataclasses import dataclass
import hmac
from http.cookies import SimpleCookie, CookieError
import os
from pathlib import Path
import re
import time
from urllib.parse import urlsplit

import server
import instant_matching

GATE_COOKIE = 'hs_staging_gate'
GATE_TTL = 8 * 60 * 60


def gate_signature(settings, expiry):
    # Preserve the cookie format introduced by concurrent integration commit339b418.
    message = settings.origin + ':' + settings.gate_user + ':' + expiry
    return hmac.new(settings.gate_password.encode(), message.encode(), hashlib.sha256).hexdigest()


def gate_token(settings):
    expiry = str(int(time.time()) + GATE_TTL)
    return expiry + '.' + gate_signature(settings, expiry)


def valid_gate_cookie(settings, header):
    try:
        cookies = SimpleCookie(header)
        token = cookies[GATE_COOKIE].value
        if not re.fullmatch(r'[0-9]{1,12}\.[a-f0-9]{64}', token): return False
        expiry, signature = token.split('.')
        if not time.time() < int(expiry) <= time.time() + GATE_TTL: return False
        return hmac.compare_digest(signature, gate_signature(settings, expiry))
    except (KeyError, ValueError, CookieError):
        return False


@dataclass(frozen=True)
class Settings:
    origin: str
    gate_user: str
    gate_password: str
    db_path: Path
    admin_password: str

    @classmethod
    def from_env(cls, env):
        # No credentials for Auth/PG or other DBs may enter this review deployment.
        forbidden = ('HS_SUPABASE_', 'HS_STRIPE_', 'SUPABASE_', 'STRIPE_')
        if any(v and (k.startswith(forbidden) or k in ('DATABASE_URL', 'HS_PHASE3_DB')) for k, v in env.items()):
            raise ValueError('Remove external integration/DB settings from the staging service')
        origin = env.get('HS_STAGING_ORIGIN') or env.get('RENDER_EXTERNAL_URL', '')
        parts = urlsplit(origin)
        if (parts.scheme != 'https' or not parts.hostname or parts.username or parts.password
                or parts.path or parts.query or parts.fragment
                or not re.fullmatch(r'[A-Za-z0-9.-]+(?::[0-9]+)?', parts.netloc)):
            raise ValueError('HS_STAGING_ORIGIN must be an exact HTTPS origin without a trailing slash')
        user = env.get('HS_STAGING_USER', '')
        password = env.get('HS_STAGING_PASSWORD', '')
        admin = env.get('HS_STAGING_ADMIN_PASSWORD', '')
        if not re.fullmatch(r'[A-Za-z0-9_-]{3,40}', user) or len(password) < 24 or len(admin) < 24:
            raise ValueError('Set a staging username and two independent secrets of at least 24 characters')
        if hmac.compare_digest(password.encode(), admin.encode()):
            raise ValueError('Gate and admin passwords must differ')
        path = Path(env.get('HS_STAGING_DB', '/tmp/hangeul-swipji-staging/platform.sqlite3'))
        if (not path.is_absolute() or path.suffix != '.sqlite3' or path.is_symlink()
                or path.resolve().is_relative_to(server.ROOT.parent)
                or path.resolve().parent.name != 'hangeul-swipji-staging'):
            raise ValueError('Use a separate absolute hangeul-swipji-staging/*.sqlite3 path outside the repository')
        return cls(origin, user, password, path.resolve(), admin)


class StagingHandler(server.Handler):
    def setup(self):
        self.request.settimeout(15)
        super().setup()

    def check_request_context(self):
        settings = self.server.staging
        # Do not trust arbitrary Forwarded/X-Forwarded-* headers for host or origin.
        if self.headers.get_all('Host', []) != [urlsplit(settings.origin).netloc]:
            raise server.Error('허용되지 않은 테스트 호스트', 403)
        origins = self.headers.get_all('Origin', [])
        if (origins and origins != [settings.origin]) or (self.command != 'GET' and origins != [settings.origin]):
            raise server.Error('테스트 주소에서만 요청할 수 있습니다', 403)
        # Clicking a link from Render/another site is a legitimate document navigation.
        # It still needs Basic Auth. Never extend this exception to API reads or writes.
        path = urlsplit(self.path).path
        document_navigation = (self.command == 'GET'
            and self.headers.get('Sec-Fetch-Mode') == 'navigate'
            and self.headers.get('Sec-Fetch-Dest') == 'document'
            and not server.unquote(path).startswith('/api/'))
        if self.headers.get('Sec-Fetch-Site') in ('cross-site', 'same-site') and not document_navigation:
            raise server.Error('다른 사이트 요청 거부', 403)
        referers = self.headers.get_all('Referer', [])
        if referers and not document_navigation:
            try:
                ref = urlsplit(referers[0])
                valid_referer = (len(referers) == 1 and not ref.username and not ref.password
                    and f'{ref.scheme}://{ref.netloc}' == settings.origin)
            except ValueError:
                valid_referer = False
            if not valid_referer:
                raise server.Error('다른 출처 Referer 요청 거부', 403)
        # A successful gate sign-in survives navigation/API requests without relying
        # on the browser's path-scoped HTTP-auth cache. Never contains a password.
        self.gate_denied = False
        self.new_gate_token = None
        if not self.headers.get('Authorization') and valid_gate_cookie(settings, self.headers.get('Cookie', '')):
            return
        try:
            scheme, encoded = self.headers.get('Authorization', '').split(' ', 1)
            if scheme.lower() != 'basic': raise ValueError()
            supplied = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error):
            supplied = b''
        expected = (settings.gate_user + ':' + settings.gate_password).encode()
        if not hmac.compare_digest(supplied, expected):
            self.gate_denied = True
            raise server.Error('비공개 테스트 접속 비밀번호가 필요합니다', 401)
        self.new_gate_token = gate_token(settings)

    def send(self, status, value, cookie=None):
        # Only the outer gate's 401 triggers the browser's Basic Auth prompt.
        if getattr(self, 'gate_denied', False):
            value = dict(error='테스트 서버 접속 인증이 필요합니다. 수업 계정 또는 Jitsi 로그인과는 별개입니다.',
                         code='STAGING_GATE_REQUIRED')
        super().send(status, value, cookie)

    def end_headers(self):
        # A background fetch/asset must never trigger a native password dialog loop.
        # Retain the normal Basic challenge only for top-level document navigation.
        path = server.unquote(urlsplit(self.path).path)
        document_request = (self.command == 'GET' and (path == '/' or path.endswith('.html')
            or path.startswith('/free/') or path == '/phase3/') and not path.startswith('/api/')
            and self.headers.get('Sec-Fetch-Mode') in (None, 'navigate')
            and self.headers.get('Sec-Fetch-Dest') in (None, 'document'))
        if getattr(self, 'gate_denied', False) and document_request:
            self.send_header('WWW-Authenticate', 'Basic realm="Hangeul Swipji TEST", charset="UTF-8"')
        if getattr(self, 'new_gate_token', None):
            self.send_header('Set-Cookie', f'{GATE_COOKIE}={self.new_gate_token}; Path=/; Max-Age={GATE_TTL}; Secure; HttpOnly; SameSite=Strict')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Robots-Tag', 'noindex, nofollow, noarchive')
        # Legacy static pages must not contact the existing hosted database either.
        self.send_header('Content-Security-Policy', "connect-src 'self'; form-action 'self'; base-uri 'self'; object-src 'none'")
        super().end_headers()

    def static(self, path):
        name = server.unquote(path.lstrip('/'))
        if name == 'speaking-platform.html':
            # Keep instant conversation separate from paid/booked lessons, without
            # reconnecting the original page's hosted production database.
            body = (server.ROOT / 'instant-speaking.html').read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Referrer-Policy', 'no-referrer')
            self.end_headers()
            self.wfile.write(body)
            return
        if name == 'speaking-config.js':
            body = b'window.HS_CONFIG = {}; // Isolated staging: external DB disabled.\n'
            self.send_response(200)
            self.send_header('Content-Type', 'text/javascript; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().static(path)

    def route(self, db, path, data, query):
        if path.startswith('/api/instant/'):
            return instant_matching.route(self, db, path, data)
        if path.startswith(('/api/auth/', '/api/payments/')):
            raise server.Error('이 테스트 서버는 외부 인증·결제를 연결하지 않습니다', 403)
        if path == '/api/register' and not re.fullmatch(r'[^\s@]+@[^\s@]+\.test', str(data.get('email', '')), re.I):
            raise server.Error('실제 이메일 대신 name@example.test 형식을 사용하세요')
        return super().route(db, path, data, query)

    def do_GET(self):
        # Provider probes disclose no users/content and do not require the outer gate.
        if self.path == '/healthz':
            try:
                with server.connect() as db: db.execute('SELECT 1 FROM users LIMIT 1')
                return self.send(200, {'ok': True, 'scope': 'isolated-staging',
                    'requestGuardVersion': 'document-navigation-v2',
                    'gateSessionVersion': 'signed-cookie-v1',
                    'videoUIVersion': 'embedded-preview-v1',
                    'appSHA256': hashlib.sha256((server.ROOT/'app.js').read_bytes()).hexdigest(),
                    'configuredOrigin': self.server.staging.origin,
                    'sourceSHA256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
            except Exception:
                return self.send(503, {'ok': False})
        super().do_GET()


def prepare_database(settings):
    settings.db_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    server.DB_PATH = str(settings.db_path)
    server.init_db()
    with server.connect() as db:
        instant_matching.initialize(db)
    with server.connect() as db:
        admins = list(db.execute("SELECT email FROM users WHERE role='admin'"))
        if admins and [r['email'] for r in admins] != ['admin@example.test']:
            raise ValueError('Unexpected admin in staging DB; refusing to reuse it')
    if not admins:
        server.create_admin('admin@example.test', settings.admin_password)
    elif not server.password_ok(settings.admin_password, _admin_hash()):
        raise ValueError('Existing admin password differs; use the original secret or a new staging DB')


def _admin_hash():
    with server.connect() as db:
        return db.execute("SELECT password FROM users WHERE email='admin@example.test'").fetchone()[0]


def main():
    settings = Settings.from_env(os.environ)
    port = int(os.environ.get('PORT', '8765'))
    if not 1 <= port <= 65535: raise ValueError('Invalid PORT')
    prepare_database(settings)
    http = server.ThreadingHTTPServer(('0.0.0.0', port), StagingHandler)
    http.staging = settings
    http.secure_cookies = True
    http.failures = {}
    print('ISOLATED STAGING: existing homepage + Python API; mock money only', flush=True)
    print(f'STAGING HTTPS ORIGIN: {settings.origin}', flush=True)
    try: http.serve_forever()
    finally: http.server_close()


if __name__ == '__main__':
    main()
