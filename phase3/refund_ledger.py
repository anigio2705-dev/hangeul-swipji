"""Local test-ledger refunds; all writes belong to the caller's transaction."""
import json
import uuid


class RefundError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


def initialize(db) -> None:
    # Do not use executescript: it can commit the caller's transaction.
    db.execute('''CREATE TABLE IF NOT EXISTS local_refund_requests (
        booking_id TEXT NOT NULL,
        request_id TEXT NOT NULL,
        amount INTEGER NOT NULL CHECK(amount > 0),
        allocations TEXT NOT NULL,
        cumulative_refunded INTEGER NOT NULL,
        actor_id TEXT NOT NULL,
        PRIMARY KEY (booking_id, request_id)
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS local_refund_adjustments (
        booking_id TEXT NOT NULL,
        request_id TEXT NOT NULL,
        original_id TEXT NOT NULL,
        reversal_id TEXT NOT NULL UNIQUE,
        amount INTEGER NOT NULL CHECK(amount > 0),
        PRIMARY KEY (booking_id, request_id, original_id),
        FOREIGN KEY (booking_id, request_id)
            REFERENCES local_refund_requests(booking_id, request_id)
    )''')


def _rows(cursor):
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def _positive(value):
    return type(value) is int and 0 < value <= 9223372036854775807


def _quoted(name):
    return '"' + name.replace('"', '""') + '"'


def _layout(db):
    columns = _rows(db.execute('PRAGMA table_info(ledger)'))
    names = {column['name'] for column in columns}
    kind = next((name for name in ('kind', 'type', 'entry_type') if name in names), None)
    if not kind or not {'id', 'booking_id', 'amount'} <= names:
        raise RefundError('지원하지 않는 원장 스키마입니다', 409)
    return columns, kind


def _result(request_id, amount, cumulative, duplicate):
    return dict(requestId=request_id, refundedAmount=amount,
                cumulativeRefunded=cumulative, duplicate=duplicate,
                realRefund=False)


def apply_refund(db, *, booking_id, request_id, amount, allocations, actor_id) -> dict:
    if not db.in_transaction:
        raise RefundError('호출자의 트랜잭션이 필요합니다', 409)
    if not isinstance(request_id, str) or not request_id.strip():
        raise RefundError('requestId가 필요합니다')
    if not _positive(amount):
        raise RefundError('환불액은 양의 정수여야 합니다')
    if not isinstance(allocations, dict) or not allocations:
        raise RefundError('원본 항목별 배분이 필요합니다')
    if any(not isinstance(key, str) or not key or not _positive(value)
           for key, value in allocations.items()):
        raise RefundError('배분은 원본 ID와 양의 정수여야 합니다')
    normalized = json.dumps(allocations, sort_keys=True, separators=(',', ':'))
    savepoint = 'refund_' + uuid.uuid4().hex
    db.execute('SAVEPOINT ' + savepoint)
    try:
        initialize(db)
        users = _rows(db.execute('SELECT role FROM users WHERE id=?', (actor_id,)))
        if not users or users[0]['role'] != 'admin':
            raise RefundError('관리자 권한이 필요합니다', 403)
        previous = _rows(db.execute(
            'SELECT amount, allocations, cumulative_refunded '
            'FROM local_refund_requests WHERE booking_id=? AND request_id=?',
            (booking_id, request_id)))
        if previous:
            old = previous[0]
            if old['amount'] != amount or old['allocations'] != normalized:
                raise RefundError('같은 요청 ID의 환불 입력이 다릅니다', 409)
            result = _result(request_id, amount, old['cumulative_refunded'], True)
        else:
            result = _apply(db, booking_id, request_id, amount, allocations,
                            normalized, actor_id)
        db.execute('RELEASE SAVEPOINT ' + savepoint)
        return result
    except BaseException:
        db.execute('ROLLBACK TO SAVEPOINT ' + savepoint)
        db.execute('RELEASE SAVEPOINT ' + savepoint)
        raise


def _apply(db, booking_id, request_id, amount, allocations, normalized, actor_id):
    bookings = _rows(db.execute('SELECT status FROM bookings WHERE id=?', (booking_id,)))
    if not bookings:
        raise RefundError('예약이 없습니다', 404)
    columns, kind = _layout(db)
    entries = _rows(db.execute('SELECT * FROM ledger WHERE booking_id=?', (booking_id,)))
    originals = {}
    reversals = {}
    for row in entries:
        entry_kind = row[kind]
        if not isinstance(entry_kind, str) or type(row['amount']) is not int:
            raise RefundError('잘못된 원장 항목입니다', 409)
        if '_reversal__refund_' in entry_kind or entry_kind.endswith('_reversal'):
            if '_reversal__refund_' in entry_kind:
                base = entry_kind.split('_reversal__refund_', 1)[0]
            else:
                base = entry_kind[:-len('_reversal')].split('__refund_', 1)[0]
            reversals[base] = reversals.get(base, 0) + abs(row['amount'])
        else:
            originals[str(row['id'])] = row
    charges = [row for row in originals.values() if row[kind] == 'test_charge']
    total = sum(abs(row['amount']) for row in charges)
    refunded = reversals.get('test_charge', 0)
    if not total or refunded + amount > total:
        raise RefundError('누적 환불 한도를 초과합니다', 409)
    if bookings[0]['status'] in ('reserved', 'expired', 'cancelled', 'refunded'):
        raise RefundError('환불할 수 없는 예약 상태입니다', 409)
    selected = []
    for key, value in allocations.items():
        row = originals.get(key)
        if row is None:
            raise RefundError('이 예약의 원본 원장 ID가 필요합니다')
        if not row['amount']:
            raise RefundError('금액이 없는 원장 항목입니다')
        selected.append((key, row, value))
    if sum(value for _, row, value in selected if row[kind] == 'test_charge') != amount:
        raise RefundError('test_charge 배분 합계가 환불액과 다릅니다')
    # Every original non-charge posting is an existing settlement component.
    # This preserves its recorded kind and beneficiary without inventing rates.
    settlement = [row for row in originals.values() if row[kind] != 'test_charge']
    settlement_sum = sum(value for _, row, value in selected if row[kind] != 'test_charge')
    if settlement and settlement_sum != amount:
        raise RefundError('정산 배분 합계가 환불액과 다릅니다')
    links = _rows(db.execute(
        'SELECT original_id, SUM(amount) AS used FROM local_refund_adjustments '
        'WHERE booking_id=? GROUP BY original_id', (booking_id,)))
    used = {row['original_id']: row['used'] for row in links}
    linked_by_kind = {}
    for key, value in used.items():
        if key not in originals:
            raise RefundError('원장 연결이 손상되었습니다', 409)
        base = originals[key][kind]
        linked_by_kind[base] = linked_by_kind.get(base, 0) + value
    for key, row, value in selected:
        base = row[kind]
        # Legacy reversals have no original-row link. Attribute them only when
        # the original is unambiguous; otherwise reject rather than over-refund.
        legacy = reversals.get(base, 0) - linked_by_kind.get(base, 0)
        if legacy < 0:
            raise RefundError('역분개 연결 합계가 원장과 다릅니다', 409)
        peers = [entry for entry in originals.values() if entry[kind] == base]
        if legacy and len(peers) != 1:
            raise RefundError('기존 역분개의 원본 연결 확인이 필요합니다', 409)
        if used.get(key, 0) + legacy + value > abs(row['amount']):
            raise RefundError('원본 항목의 누적 역분개 한도를 초과합니다', 409)
    db.execute(
        'INSERT INTO local_refund_requests '
        '(booking_id,request_id,amount,allocations,cumulative_refunded,actor_id) '
        'VALUES(?,?,?,?,?,?)',
        (booking_id, request_id, amount, normalized, refunded + amount, actor_id))
    for key, original, value in selected:
        posting = dict(original)
        reversal_kind = original[kind] + '_reversal'
        if any(entry[kind] == reversal_kind for entry in entries):
            reversal_kind = original[kind] + '_reversal__refund_' + uuid.uuid4().hex + '_reversal'
        posting[kind] = reversal_kind
        posting['amount'] = -value if original['amount'] > 0 else value
        id_column = next(column for column in columns if column['name'] == 'id')
        integer_id = id_column['type'].upper() == 'INTEGER' and id_column['pk'] == 1
        if integer_id:
            posting.pop('id')
        else:
            posting['id'] = uuid.uuid4().hex
        # Let the schema supply fresh timestamps, preserving all beneficiary fields.
        for column in columns:
            if column['name'] in ('created_at', 'updated_at') and column['dflt_value'] is not None:
                posting.pop(column['name'], None)
        names = list(posting)
        cursor = db.execute(
            'INSERT INTO ledger (' + ','.join(_quoted(name) for name in names) + ') '
            'VALUES (' + ','.join('?' for _ in names) + ')',
            tuple(posting[name] for name in names))
        reversal_id = cursor.lastrowid if integer_id else posting['id']
        db.execute(
            'INSERT INTO local_refund_adjustments '
            '(booking_id,request_id,original_id,reversal_id,amount) VALUES(?,?,?,?,?)',
            (booking_id, request_id, key, str(reversal_id), value))
    if refunded + amount == total:
        db.execute("UPDATE bookings SET status='refunded' WHERE id=?", (booking_id,))
    return _result(request_id, amount, refunded + amount, False)
