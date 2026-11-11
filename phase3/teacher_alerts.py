"""Account-owned test search registrations. No commits or external delivery."""
import datetime as dt
import json
import re
import secrets
import time


def initialize(db) -> None:
    db.execute('''CREATE TABLE IF NOT EXISTS teacher_search_alerts (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id),
        filters_json TEXT NOT NULL,
        created_at REAL NOT NULL
    )''')
    db.execute('''CREATE UNIQUE INDEX IF NOT EXISTS teacher_search_alerts_owner_filters
                  ON teacher_search_alerts(user_id, filters_json)''')


def _normalize(filters):
    if not isinstance(filters, dict):
        raise ValueError('검색 조건 객체가 필요합니다')
    result = {}
    for key in ('q', 'role', 'language', 'level', 'purpose'):
        value = filters.get(key, '')
        if not isinstance(value, str) or len(value.strip()) > 200:
            raise ValueError('문자열 검색 조건은 200자 이하여야 합니다')
        result[key] = value.strip()
    if result['role'] not in ('', 'teacher', 'partner'):
        raise ValueError('참여 유형을 확인하세요')
    price = filters.get('maxPrice', '')
    if price == '' and isinstance(price, str):
        result['maxPrice'] = ''
    else:
        if isinstance(price, str):
            if not re.fullmatch(r'[0-9]+', price.strip()):
                raise ValueError('가격은 정수여야 합니다')
            try:
                price = int(price.strip())
            except ValueError:
                raise ValueError('가격 범위를 확인하세요') from None
        if type(price) is not int or not 1000 <= price <= 1000000:
            raise ValueError('가격은 1000~1000000 정수여야 합니다')
        result['maxPrice'] = price
    endpoints = []
    for key in ('from', 'to'):
        value = filters.get(key, '')
        if not isinstance(value, str):
            raise ValueError('시간대가 포함된 ISO 일시가 필요합니다')
        if not value:
            endpoints.append(None)
            result[key] = ''
            continue
        try:
            parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
            if parsed.tzinfo is None or parsed.utcoffset() is None:
                raise ValueError()
            parsed = parsed.astimezone(dt.timezone.utc)
        except (ValueError, OverflowError):
            raise ValueError('시간대가 포함된 유효한 ISO 일시가 필요합니다') from None
        endpoints.append(parsed)
        result[key] = parsed.isoformat()
    start, end = endpoints
    if (start is None) != (end is None):
        raise ValueError('검색 시작과 종료 시각이 모두 필요합니다')
    if start is not None and end <= start:
        raise ValueError('검색 종료는 시작 이후여야 합니다')
    return result


def register(db, user_id, filters, *, now=None) -> dict:
    normalized = _normalize(filters)
    encoded = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    alert_id = secrets.token_hex(16)
    inserted = db.execute('''INSERT INTO teacher_search_alerts(id,user_id,filters_json,created_at)
                             VALUES(?,?,?,?)
                             ON CONFLICT(user_id,filters_json) DO NOTHING''',
                          (alert_id, user_id, encoded, time.time() if now is None else now)).rowcount
    saved = db.execute('SELECT id FROM teacher_search_alerts WHERE user_id=? AND filters_json=?',
                       (user_id, encoded)).fetchone()
    return dict(alertId=saved[0], status='registered', duplicate=not bool(inserted), deliveryEnabled=False)
