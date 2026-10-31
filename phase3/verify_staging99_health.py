#!/usr/bin/env python3
"""Read-only TEST99 /healthz fingerprint check; no credentials or deployment.

Run: python3 phase3/verify_staging99_health.py
Compares a public TEST99 health response with the selected checkout's exact bytes.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

HEALTH_URL = 'https://hangeul-swipji99-test.onrender.com/healthz'
EXPECTED_ORIGIN = 'https://hangeul-swipji99-test.onrender.com'
EXPECTED_VERSIONS = {
    'gateSessionVersion': 'signed-cookie-v1',
    'videoUIVersion': 'embedded-preview-v1',
}


def sha256_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_health(payload, root):
    """A matching byte digest is NOT evidence of a particular Git commit."""
    expected = {
        'ok': True,
        'scope': 'isolated-staging',
        'configuredOrigin': EXPECTED_ORIGIN,
        **EXPECTED_VERSIONS,
        'sourceSHA256': sha256_file(root / 'phase3' / 'staging_server.py'),
        'appSHA256': sha256_file(root / 'phase3' / 'app.js'),
    }
    if not isinstance(payload, dict):
        return {'pass': False, 'reason': 'invalid-json-object', 'checks': {}}
    checks = {
        name: {'pass': payload.get(name) == value,
               'expected': value, 'observed': payload.get(name)}
        for name, value in expected.items()
    }
    return {
        'pass': all(item['pass'] for item in checks.values()),
        'checks': checks,
        'meaning': 'byte-level checkout match only; not proof of commit, login, media, or database persistence',
    }


def probe(root, timeout=15, opener=urlopen):
    request = Request(HEALTH_URL, headers={
        'Accept': 'application/json',
        'User-Agent': 'HangeulSwipji-TEST99-readonly-check/1',
    })
    try:
        with opener(request, timeout=timeout) as response:
            status = response.status
            raw = response.read(32769)
            if status != 200 or len(raw) > 32768:
                return {'pass': False, 'httpStatus': status, 'reason': 'unexpected-status-or-size'}
        payload = json.loads(raw.decode('utf-8'))
    except (HTTPError, URLError, TimeoutError, OSError, UnicodeError, ValueError) as exc:
        # Do not echo any response body, Authorization header, or secret.
        return {'pass': False, 'reason': type(exc).__name__,
                'httpStatus': getattr(exc, 'code', None)}
    return {'httpStatus': status, **check_health(payload, root)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument('--timeout', type=float, default=15)
    args = parser.parse_args(argv)
    if not 0 < args.timeout <= 60:
        parser.error('timeout must be in (0,60]')
    result = probe(args.root.resolve(), args.timeout)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result['pass'] else 1


if __name__ == '__main__':
    sys.exit(main())
