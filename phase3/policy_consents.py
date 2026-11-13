"""Explicit synthetic local-test acknowledgements; no approved live policies.

privacy_notice records acknowledgement of a notice, not blanket legal consent
for personal-data processing. Callers own transactions and authentication.
Tests may replace catalog() with an in-memory synthetic catalogue.
"""
import hashlib
import math
import secrets
import sqlite3


_KINDS = frozenset(('learner_terms', 'provider_terms', 'privacy_notice',
                    'cancellation_refund', 'referral_conditions'))
_ROLES = frozenset(('learner', 'teacher', 'partner', 'admin'))
_MODE = 'synthetic-test-only'


class PolicyConsentError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message, self.status = message, status


def catalog(role) -> list[dict]:
    if not isinstance(role, str) or role not in _ROLES:
        raise PolicyConsentError('Unknown policy role')
    texts = [
        ('learner_terms', '이용약관: 로컬 테스트 참여 조건을 확인합니다.'),
        ('privacy_notice', '개인정보 고지: 모의 확인 기록의 사용자·역할·시각 연결을 확인합니다. 모든 개인정보 처리에 대한 포괄 동의가 아닙니다.'),
        ('cancellation_refund', '취소·환불: 기존 테스트 취소·환불 조건 검토를 위한 확인이며 요율이나 환불 권리를 변경하지 않습니다.'),
        ('referral_conditions', '소개 보상: 기존 테스트 소개 보상 조건 검토를 위한 확인이며 실제 지급을 약속하지 않습니다.'),
    ]
    if role in ('teacher', 'partner'):
        texts.append(('provider_terms', '강사 계약: 강사·파트너의 로컬 테스트 참여 조건을 확인합니다.'))
    result = []
    for policy_id, body in texts:
        text = '미승인 모의 문안·모의 확인 전용. 실제 약관 승인·공표·법적 동의가 아닙니다. 기존 정책 초안을 실제 약관으로 사용하지 않습니다. ' + body
        result.append(dict(policyId=policy_id, version='synthetic-v1', text=text,
                           sha256=hashlib.sha256(text.encode('utf-8')).hexdigest(),
                           acknowledgementKind=('notice_acknowledgement' if policy_id == 'privacy_notice' else 'synthetic_acknowledgement'),
                           simulated=True, legallyApproved=False))
    return result


def initialize(db) -> None:
    # Individual execute calls deliberately avoid executescript's implicit commit.
    statements = (
        '''CREATE TABLE IF NOT EXISTS policy_consents (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
            policy_id TEXT NOT NULL,
            version TEXT NOT NULL,
            kind TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            body TEXT NOT NULL,
            role TEXT,
            created_at REAL NOT NULL,
            mode TEXT NOT NULL CHECK(mode='synthetic-test-only'),
            UNIQUE(user_id, policy_id, version, sha256)
        )''',
        '''CREATE TABLE IF NOT EXISTS booking_policy_consents (
            booking_id TEXT NOT NULL REFERENCES bookings(id) ON DELETE RESTRICT,
            consent_id TEXT NOT NULL REFERENCES policy_consents(id) ON DELETE RESTRICT,
            created_at REAL NOT NULL,
            PRIMARY KEY(booking_id, consent_id)
        )''',
    )
    for statement in statements:
        db.execute(statement)
    if 'role' not in {row[1] for row in db.execute('PRAGMA table_info(policy_consents)')}:
        db.execute('ALTER TABLE policy_consents ADD COLUMN role TEXT')
    db.execute('''CREATE TABLE IF NOT EXISTS policy_snapshots (
        policy_id TEXT NOT NULL, version TEXT NOT NULL,
        body TEXT NOT NULL, sha256 TEXT NOT NULL, kind TEXT NOT NULL,
        PRIMARY KEY(policy_id, version)
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS booking_policy_seals (
        booking_id TEXT PRIMARY KEY REFERENCES bookings(id) ON DELETE RESTRICT,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT
    )''')
    db.execute('''CREATE TRIGGER IF NOT EXISTS policy_consents_snapshot_fk
        BEFORE INSERT ON policy_consents WHEN NOT EXISTS (
            SELECT 1 FROM policy_snapshots s WHERE s.policy_id=NEW.policy_id
            AND s.version=NEW.version AND s.body=NEW.body
            AND s.sha256=NEW.sha256 AND s.kind=NEW.kind)
        BEGIN SELECT RAISE(ABORT, 'invalid policy snapshot'); END''')
    db.execute('''CREATE TRIGGER IF NOT EXISTS booking_policy_seals_fk
        BEFORE INSERT ON booking_policy_seals WHEN NOT EXISTS (
            SELECT 1 FROM bookings WHERE id=NEW.booking_id AND learner_id=NEW.user_id)
        BEGIN SELECT RAISE(ABORT, 'invalid booking seal'); END''')
    db.execute('''CREATE TRIGGER IF NOT EXISTS booking_policy_seals_booking_delete
        BEFORE DELETE ON bookings WHEN EXISTS (
            SELECT 1 FROM booking_policy_seals WHERE booking_id=OLD.id)
        BEGIN SELECT RAISE(ABORT, 'referenced policy booking'); END''')
    db.execute('''CREATE TRIGGER IF NOT EXISTS booking_policy_seals_booking_update
        BEFORE UPDATE OF id, learner_id ON bookings
        WHEN (NEW.id IS NOT OLD.id OR NEW.learner_id IS NOT OLD.learner_id)
        AND EXISTS (SELECT 1 FROM booking_policy_seals WHERE booking_id=OLD.id)
        BEGIN SELECT RAISE(ABORT, 'referenced policy booking'); END''')
    for table in ('policy_consents', 'booking_policy_consents', 'policy_snapshots', 'booking_policy_seals'):
        for operation in ('UPDATE', 'DELETE'):
            db.execute(
                f'CREATE TRIGGER IF NOT EXISTS {table}_no_{operation.lower()} '
                f'BEFORE {operation} ON {table} BEGIN '
                "SELECT RAISE(ABORT, 'immutable policy record'); END"
            )
    # These also enforce references when a caller has not enabled SQLite FKs.
    db.execute('''CREATE TRIGGER IF NOT EXISTS policy_consents_user_fk
        BEFORE INSERT ON policy_consents
        WHEN NOT EXISTS (SELECT 1 FROM users WHERE id=NEW.user_id)
        BEGIN SELECT RAISE(ABORT, 'unknown policy user'); END''')
    db.execute('''CREATE TRIGGER IF NOT EXISTS booking_policy_consents_fk
        BEFORE INSERT ON booking_policy_consents
        WHEN NOT EXISTS (
            SELECT 1 FROM bookings b JOIN policy_consents c
            ON c.user_id=b.learner_id
            WHERE b.id=NEW.booking_id AND c.id=NEW.consent_id
        )
        BEGIN SELECT RAISE(ABORT, 'invalid booking consent'); END''')
    db.execute('''CREATE TRIGGER IF NOT EXISTS policy_consents_user_delete
        BEFORE DELETE ON users
        WHEN EXISTS (SELECT 1 FROM policy_consents WHERE user_id=OLD.id)
        BEGIN SELECT RAISE(ABORT, 'referenced policy user'); END''')
    db.execute('''CREATE TRIGGER IF NOT EXISTS policy_consents_user_update
        BEFORE UPDATE OF id ON users
        WHEN NEW.id IS NOT OLD.id AND EXISTS (
            SELECT 1 FROM policy_consents WHERE user_id=OLD.id)
        BEGIN SELECT RAISE(ABORT, 'referenced policy user'); END''')
    db.execute('''CREATE TRIGGER IF NOT EXISTS booking_policy_consents_booking_delete
        BEFORE DELETE ON bookings
        WHEN EXISTS (SELECT 1 FROM booking_policy_consents WHERE booking_id=OLD.id)
        BEGIN SELECT RAISE(ABORT, 'referenced policy booking'); END''')
    db.execute('''CREATE TRIGGER IF NOT EXISTS booking_policy_consents_booking_update
        BEFORE UPDATE OF id, learner_id ON bookings
        WHEN (NEW.id IS NOT OLD.id OR NEW.learner_id IS NOT OLD.learner_id)
        AND EXISTS (SELECT 1 FROM booking_policy_consents WHERE booking_id=OLD.id)
        BEGIN SELECT RAISE(ABORT, 'referenced policy booking'); END''')


def _text(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError('A nonempty string is required')
    return value


def _time(now):
    if type(now) not in (int, float):
        raise ValueError('A finite server timestamp is required')
    try:
        valid = math.isfinite(now) and now >= 0
    except (OverflowError, ValueError):
        valid = False
    if not valid:
        raise ValueError('A finite server timestamp is required')
    return now


def _user(db, user_id):
    _text(user_id)
    row = db.execute('SELECT role FROM users WHERE id=?', (user_id,)).fetchone()
    if row is None:
        raise ValueError('Unknown user')
    return row[0]


def _policies():
    entries = catalog()
    if not isinstance(entries, list):
        raise ValueError('Invalid synthetic catalogue')
    result = {}
    fields = {'policyId', 'version', 'kind', 'applicableRoles', 'body', 'sha256', 'mode'}
    for item in entries:
        if not isinstance(item, dict) or set(item) != fields:
            raise ValueError('Invalid synthetic policy fields')
        p = dict(item)
        for key in ('policyId', 'version', 'kind', 'sha256', 'mode'):
            _text(p[key])
        roles = p['applicableRoles']
        if (not isinstance(roles, list) or not roles
                or any(not isinstance(role, str) or role not in _ROLES for role in roles)
                or len(set(roles)) != len(roles)):
            raise ValueError('Invalid policy roles')
        if p['kind'] not in _KINDS or p['mode'] != _MODE or not isinstance(p['body'], str):
            raise ValueError('Only synthetic test policies are supported')
        try:
            digest = hashlib.sha256(p['body'].encode('utf-8')).hexdigest()
        except UnicodeError as exc:
            raise ValueError('Invalid UTF-8 policy body') from exc
        if p['sha256'] != digest or p['policyId'] in result:
            raise ValueError('Invalid hash or duplicate active policy')
        p['applicableRoles'] = list(roles)
        result[p['policyId']] = p
    return result


def _records(cursor):
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


_SELECT = '''SELECT id, user_id AS userId, policy_id AS policyId,
    version, kind, sha256, body, created_at AS createdAt, mode
    FROM policy_consents'''


def _accept(db, user_id, *, policy_id, version, sha256, consent, now) -> dict:
    role = _user(db, user_id)
    _time(now)
    for value in (policy_id, version, sha256):
        _text(value)
    if consent is not True:
        raise ValueError('Explicit true consent is required')
    policy = _policies().get(policy_id)
    if (policy is None or policy['version'] != version or policy['sha256'] != sha256
            or role not in policy['applicableRoles']):
        raise ValueError('Policy, version, hash or role does not match')
    params = (user_id, policy_id, version, sha256)
    query = _SELECT + ' WHERE user_id=? AND policy_id=? AND version=? AND sha256=?'
    existing = _records(db.execute(query, params))
    if existing:
        return existing[0]
    try:
        db.execute('''INSERT INTO policy_consents
            (id,user_id,policy_id,version,kind,sha256,body,created_at,mode)
            VALUES (?,?,?,?,?,?,?,?,?)
            ON CONFLICT(user_id,policy_id,version,sha256) DO NOTHING''',
            (secrets.token_hex(16), user_id, policy_id, version, policy['kind'],
             sha256, policy['body'], now, _MODE))
    except sqlite3.IntegrityError as exc:
        raise ValueError('Invalid policy consent') from exc
    return _records(db.execute(query, params))[0]


def _list_consents(db, user_id) -> list[dict]:
    _user(db, user_id)
    return _records(db.execute(_SELECT + ' WHERE user_id=? ORDER BY created_at,id', (user_id,)))


def _bind_booking(db, booking_id, user_id, *, consent_ids, now) -> list[dict]:
    role = _user(db, user_id)
    _text(booking_id)
    _time(now)
    if (not isinstance(consent_ids, list)
            or any(not isinstance(value, str) or not value.strip() for value in consent_ids)):
        raise ValueError('Consent IDs must be a list of nonempty strings')
    if len(set(consent_ids)) != len(consent_ids):
        raise ValueError('Duplicate consent IDs')
    booking = db.execute('SELECT learner_id FROM bookings WHERE id=?', (booking_id,)).fetchone()
    if booking is None or booking[0] != user_id or role != 'learner':
        raise ValueError('Booking must belong to the learner')
    policies = _policies()
    required = {key for key, p in policies.items() if 'learner' in p['applicableRoles']}
    owned = {record['id']: record for record in _list_consents(db, user_id)}
    selected = []
    seen = set()
    for consent_id in consent_ids:
        record = owned.get(consent_id)
        if record is None:
            raise ValueError('Unknown or other user consent')
        policy = policies.get(record['policyId'])
        if (policy is None or 'learner' not in policy['applicableRoles']
                or record['version'] != policy['version']
                or record['sha256'] != policy['sha256']
                or record['body'] != policy['body']
                or record['kind'] != policy['kind'] or record['mode'] != _MODE):
            raise ValueError('Consent is not for the current learner policy')
        if record['policyId'] in seen:
            raise ValueError('Duplicate policy consent')
        seen.add(record['policyId'])
        selected.append(record)
    if seen != required:
        raise ValueError('Current learner policy consents are required')
    existing = _records(db.execute('''SELECT consent_id AS id, created_at AS linkedAt
        FROM booking_policy_consents WHERE booking_id=?''', (booking_id,)))
    if existing:
        if {row['id'] for row in existing} != set(consent_ids):
            raise ValueError('Booking policy links are immutable')
        linked = {row['id']: row['linkedAt'] for row in existing}
    else:
        # A savepoint prevents partial links without committing the caller's transaction.
        # Start an outer transaction first: releasing an outermost savepoint commits.
        if not db.in_transaction:
            db.execute('BEGIN')
        db.execute('SAVEPOINT bind_policy_consents')
        try:
            for record in selected:
                db.execute('''INSERT INTO booking_policy_consents
                    (booking_id,consent_id,created_at) VALUES (?,?,?)''',
                    (booking_id, record['id'], now))
        except Exception as exc:
            db.execute('ROLLBACK TO bind_policy_consents')
            db.execute('RELEASE bind_policy_consents')
            if isinstance(exc, sqlite3.IntegrityError):
                raise ValueError('Invalid booking policy link') from exc
            raise
        db.execute('RELEASE bind_policy_consents')
        linked = {record['id']: now for record in selected}
    return [dict(record, bookingId=booking_id, linkedAt=linked[record['id']])
            for record in selected]


def _checked_user(db, user_id):
    try:
        return _user(db, user_id)
    except ValueError as exc:
        raise PolicyConsentError(str(exc)) from exc


def _atomic(db, name, action):
    # Keep an outer transaction open even for callers using autocommit.
    if not db.in_transaction:
        db.execute('BEGIN')
    db.execute('SAVEPOINT ' + name)
    try:
        result = action()
    except Exception as exc:
        db.execute('ROLLBACK TO ' + name)
        db.execute('RELEASE ' + name)
        if isinstance(exc, sqlite3.IntegrityError):
            raise PolicyConsentError('Conflicting immutable policy record', 409) from exc
        raise
    db.execute('RELEASE ' + name)
    return result


def list_records(db, *, user_id):
    _checked_user(db, user_id)
    records = _records(db.execute(
        _SELECT.replace('version, kind,', 'version, role, kind,') +
        ' WHERE user_id=? ORDER BY created_at,id', (user_id,)))
    for item in records:
        item['text'] = item['body']
        item['acknowledgementKind'] = item['kind']
        item['simulated'] = True
        item['legallyApproved'] = False
        item['bookingIds'] = [row[0] for row in db.execute(
            'SELECT booking_id FROM booking_policy_consents WHERE consent_id=? ORDER BY booking_id',
            (item['id'],))]
    return records


def record(db, *, user_id, acknowledgements, simulated, now):
    role = _checked_user(db, user_id)
    try:
        _time(now)
    except ValueError as exc:
        raise PolicyConsentError(str(exc)) from exc
    if simulated is not True or not isinstance(acknowledgements, list):
        raise PolicyConsentError('Explicit simulated acknowledgements are required')
    policies = {item['policyId']: item for item in catalog(role)}
    seen = set()
    mismatch = False
    fields = {'policyId', 'version', 'sha256', 'acknowledged'}
    for item in acknowledgements:
        if not isinstance(item, dict) or set(item) != fields:
            raise PolicyConsentError('Invalid acknowledgement fields')
        if any(not isinstance(item[key], str) or not item[key].strip()
               for key in ('policyId', 'version', 'sha256')) or item['acknowledged'] is not True:
            raise PolicyConsentError('Invalid acknowledgement values')
        key = item['policyId']
        if key not in policies or key in seen:
            raise PolicyConsentError('Unknown or duplicate policy')
        seen.add(key)
        policy = policies[key]
        mismatch |= item['version'] != policy['version'] or item['sha256'] != policy['sha256']
    if seen != set(policies):
        raise PolicyConsentError('All role policies must be acknowledged exactly once')
    if mismatch:
        raise PolicyConsentError('Current policy version or hash does not match', 409)

    def save():
        for policy in policies.values():
            values = (policy['policyId'], policy['version'], policy['text'],
                      policy['sha256'], policy['acknowledgementKind'])
            snapshot = db.execute('''SELECT body,sha256,kind FROM policy_snapshots
                WHERE policy_id=? AND version=?''', values[:2]).fetchone()
            if snapshot is not None and tuple(snapshot) != values[2:]:
                raise PolicyConsentError('Policy version content is immutable', 409)
            if snapshot is None:
                db.execute('''INSERT INTO policy_snapshots
                    (policy_id,version,body,sha256,kind) VALUES (?,?,?,?,?)''', values)
            db.execute('''INSERT INTO policy_consents
                (id,user_id,policy_id,version,kind,sha256,body,role,created_at,mode)
                VALUES (?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(user_id,policy_id,version,sha256) DO NOTHING''',
                (secrets.token_hex(16), user_id, policy['policyId'], policy['version'],
                 policy['acknowledgementKind'], policy['sha256'], policy['text'], role, now, _MODE))
        current = {(p['policyId'], p['version'], p['sha256']) for p in policies.values()}
        return [item for item in list_records(db, user_id=user_id)
                if (item['policyId'], item['version'], item['sha256']) in current]
    return _atomic(db, 'record_policy_batch', save)


def link_booking(db, *, booking_id, user_id):
    role = _checked_user(db, user_id)
    if not isinstance(booking_id, str) or not booking_id.strip():
        raise PolicyConsentError('Invalid booking ID')
    booking = db.execute('SELECT learner_id,created_at FROM bookings WHERE id=?',
                         (booking_id,)).fetchone()
    if booking is None or booking[0] != user_id or role != 'learner':
        raise PolicyConsentError('Booking must belong to the learner')

    def link():
        sealed = db.execute('SELECT 1 FROM booking_policy_seals WHERE booking_id=?',
                            (booking_id,)).fetchone()
        if sealed is None:
            # A seal also freezes an empty selection. The timestamp excludes
            # confirmations obtained after a pre-existing booking was created.
            current = {(p['policyId'], p['version'], p['sha256'], p['text'],
                        p['acknowledgementKind']) for p in catalog(role)}
            selected = [item for item in list_records(db, user_id=user_id)
                        if item['createdAt'] <= booking[1]
                        and (item['policyId'], item['version'], item['sha256'],
                             item['text'], item['kind']) in current]
            db.execute('INSERT INTO booking_policy_seals (booking_id,user_id) VALUES (?,?)',
                       (booking_id, user_id))
            for item in selected:
                db.execute('''INSERT INTO booking_policy_consents
                    (booking_id,consent_id,created_at) VALUES (?,?,?)''',
                    (booking_id, item['id'], booking[1]))
        return [item for item in list_records(db, user_id=user_id)
                if booking_id in item['bookingIds']]
    return _atomic(db, 'link_policy_booking', link)
