"""Offline TEST99 health-check tests. Never contact Render or access secrets."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from urllib.error import URLError

SOURCE = Path(__file__).with_name('verify_staging99_health.py')
spec = importlib.util.spec_from_file_location('verify_staging99_health', SOURCE)
health = importlib.util.module_from_spec(spec)
spec.loader.exec_module(health)


class FakeResponse:
    status = 200

    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def read(self, _):
        return self.body


class VerifyHealthTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / 'phase3').mkdir()
        (self.root / 'phase3' / 'staging_server.py').write_bytes(b'safe staging source')
        (self.root / 'phase3' / 'app.js').write_bytes(b'const app=1;')
        self.payload = {
            'ok': True,
            'scope': 'isolated-staging',
            'configuredOrigin': health.EXPECTED_ORIGIN,
            **health.EXPECTED_VERSIONS,
            'sourceSHA256': health.sha256_file(self.root / 'phase3' / 'staging_server.py'),
            'appSHA256': health.sha256_file(self.root / 'phase3' / 'app.js'),
        }

    def tearDown(self):
        self.tmp.cleanup()

    def test_matching_health_is_readonly_pass(self):
        result = health.probe(
            self.root,
            opener=lambda request, timeout: FakeResponse(json.dumps(self.payload).encode()),
        )
        self.assertTrue(result['pass'])
        self.assertEqual(200, result['httpStatus'])

    def test_rejects_stale_source_and_app(self):
        for key in ('sourceSHA256', 'appSHA256'):
            with self.subTest(key=key):
                payload = dict(self.payload, **{key: '0' * 64})
                self.assertFalse(health.check_health(payload, self.root)['pass'])

    def test_rejects_incorrect_versions_origin_and_scope(self):
        for key in ('gateSessionVersion', 'videoUIVersion', 'configuredOrigin', 'scope', 'ok'):
            with self.subTest(key=key):
                payload = dict(self.payload, **{key: 'WRONG'})
                self.assertFalse(health.check_health(payload, self.root)['pass'])

    def test_remote_unavailable_is_not_success(self):
        def fail(*args, **kwargs):
            raise URLError('network unavailable')
        result = health.probe(self.root, opener=fail)
        self.assertFalse(result['pass'])
        self.assertEqual('URLError', result['reason'])

    def test_malformed_json_is_not_success(self):
        result = health.probe(self.root, opener=lambda *_a, **_k: FakeResponse(b'bad-json'))
        self.assertFalse(result['pass'])

    def test_health_does_not_claim_git_commit(self):
        result = health.check_health(self.payload, self.root)
        self.assertTrue(result['pass'])
        self.assertIn('not proof of commit', result['meaning'])


if __name__ == '__main__':
    unittest.main()
