"""Durable review-only refund requests, separate from external payment/provider APIs."""
import json
from team14_persistent import SimError, ident, amount


def _init(store):
    store.db.execute("""CREATE TABLE IF NOT EXISTS refund_requests(
        request_id TEXT PRIMARY KEY, booking_id TEXT NOT NULL, actor_id TEXT NOT NULL,
        amount_krw INTEGER NOT NULL CHECK(amount_krw>0),
        state TEXT NOT NULL CHECK(state IN ('requested','approved','rejected','cancelled','applied')),
        reason TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")


def request_refund(server_db, store, booking_id, request_id, actor_id, amount_krw, reason=''):
    for value in (booking_id, request_id, actor_id):
        ident(value)
    amount(amount_krw, True)
    if not isinstance(reason, str):
        raise SimError('VALIDATION_ERROR', 'reason must be a string')
    # Validate reason length and strip here to fail early and store clean data
    reason_clean = reason.strip() if isinstance(reason, str) else ''
    if reason != '' and not reason_clean:
        raise SimError('VALIDATION_ERROR', 'reason must not be only whitespace')

    booking = server_db.execute(
        'SELECT learner_id,teacher_id,price,status FROM bookings WHERE id=?',
        (booking_id,)).fetchone()
    if booking is None:
        raise SimError('NOT_FOUND', 'booking missing')
    if actor_id != booking['learner_id']:
        raise SimError('FORBIDDEN', 'only booking learner can request refund')
    if booking['status'] not in ('completed', 'test_settled', 'refunded'):
        raise SimError('INVALID_STATE', 'booking not completed')
    lesson = store.db.execute('SELECT amount FROM lessons WHERE booking_id=?', (booking_id,)).fetchone()
    if lesson is None or lesson['amount'] != booking['price']:
        raise SimError('CONFLICT', 'booking price mismatch')
    _init(store)
    with store.atomic():
        previous = store.db.execute('SELECT * FROM refund_requests WHERE request_id=?', (request_id,)).fetchone()
        if previous is not None:
            if (previous['booking_id'], previous['actor_id'], previous['amount_krw']) != (booking_id, actor_id, amount_krw):
                raise SimError('CONFLICT', 'refund request reused')
            return dict(previous)
        store.db.execute(
            "INSERT INTO refund_requests(request_id,booking_id,actor_id,amount_krw,state,reason) VALUES(?,?,?,?,?,?)",
            (request_id, booking_id, actor_id, amount_krw, 'requested', reason_clean))
    return dict(store.db.execute('SELECT * FROM refund_requests WHERE request_id=?', (request_id,)).fetchone())


def decide_refund(store, request_id, decision, reviewer):
    ident(request_id)
    ident(reviewer)
    if reviewer != 'test_reviewer':
        raise SimError('FORBIDDEN', 'internal test reviewer only')
    if decision not in ('approved', 'rejected', 'cancelled'):
        raise SimError('VALIDATION_ERROR', 'refund decision')
    _init(store)
    with store.atomic():
        row = store.db.execute('SELECT * FROM refund_requests WHERE request_id=?', (request_id,)).fetchone()
        if row is None:
            raise SimError('NOT_FOUND', 'refund request missing')
        if row['state'] == decision:
            return dict(row)
        if row['state'] != 'requested':
            raise SimError('INVALID_STATE', 'refund decision locked')

        # Additional stricter validation to ensure refund event integrity
        if decision == 'approved':
            # Validate amount_krw is positive integer
            if not isinstance(row['amount_krw'], int) or row['amount_krw'] <= 0:
                raise SimError('VALIDATION_ERROR', 'invalid refund amount')

            # Verify 'reason' is a non-empty string trimmed of whitespace
            if not isinstance(row['reason'], str):
                raise SimError('VALIDATION_ERROR', 'refund reason must be a string')
            reason_clean = row['reason'].strip()
            if not reason_clean:
                raise SimError('VALIDATION_ERROR', 'refund reason required')

            # Also ensure reason field stored in DB is stripped of extra whitespace
            if reason_clean != row['reason']:
                # update trimmed reason to db
                store.db.execute('UPDATE refund_requests SET reason=? WHERE request_id=?', (reason_clean, request_id))

        store.db.execute('UPDATE refund_requests SET state=?, updated_at=CURRENT_TIMESTAMP WHERE request_id=?',
                         (decision, request_id))
    return dict(store.db.execute('SELECT * FROM refund_requests WHERE request_id=?', (request_id,)).fetchone())


def apply_approved_refund(server_db, store, request_id):
    """Transactionally post adjustment and transition refund request in one SQLite file."""
    import team14_persistent
    ident(request_id)
    _init(store)
    with store.atomic():
        row = store.db.execute('SELECT * FROM refund_requests WHERE request_id=?', (request_id,)).fetchone()
        if row is None:
            raise SimError('NOT_FOUND', 'refund request missing')
        if row['state'] == 'applied':
            return json.loads(store.db.execute('SELECT result FROM operations WHERE id=?', (request_id,)).fetchone()['result'])
        if row['state'] != 'approved':
            raise SimError('INVALID_STATE', 'refund not approved')
        booking = server_db.execute('SELECT price,status,learner_id FROM bookings WHERE id=?',
                                    (row['booking_id'],)).fetchone()
        if booking is None or booking['learner_id'] != row['actor_id']:
            raise SimError('FORBIDDEN', 'server booking owner changed')
        if booking['status'] not in ('completed', 'test_settled', 'refunded'):
            raise SimError('INVALID_STATE', 'booking no longer refundable')
        lesson = store.db.execute('SELECT id,month_id,amount,state,refunded FROM lessons WHERE booking_id=?',
                                (row['booking_id'],)).fetchone()
        if lesson is None or lesson['amount'] != booking['price']:
            raise SimError('CONFLICT', 'booking amount mismatch')
        if lesson['state'] not in ('completed', 'completed_partially_refunded'):
            raise SimError('INVALID_STATE', 'no completed settlement to refund')
        month = store.db.execute('SELECT commission,referral FROM months WHERE id=?',
                               (lesson['month_id'],)).fetchone()
        price = lesson['amount']
        old = lesson['refunded']
        new = old + row['amount_krw']
        if new > price:
            raise SimError('INVALID_STATE', 'refund exceeds balance')
        teacher = price * (10000 - month['commission']) // 10000
        referral = price * month['referral'] // 10000
        tdelta = teacher * new // price - teacher * old // price
        rdelta = referral * new // price - referral * old // price
        entries = [('refund_reversal', -row['amount_krw']),
                   ('teacher_reversal', -tdelta), ('referral_reversal', -rdelta),
                   ('platform_reversal', -(row['amount_krw'] - tdelta - rdelta))]
        signature = json.dumps(['event', lesson['month_id'], lesson['id'], row['booking_id'],
                              request_id, 'refund_completed', row['amount_krw'], 'KRW', 'refunded'],
                             sort_keys=True)
        for kind, value in entries:
            store.db.execute('INSERT INTO ledger(transaction_id,lesson_id,kind,amount) VALUES(?,?,?,?)',
                             (request_id, lesson['id'], kind, value))
            team14_persistent._fault('after_' + kind)
        state = 'refunded' if new == price else 'completed_partially_refunded'
        store.db.execute('UPDATE lessons SET state=?,refunded=? WHERE id=?', (state, new, lesson['id']))
        result = dict(transaction_id=request_id, state=state, real_money=False)
        store.db.execute('INSERT INTO operations VALUES(?,?,?)', (request_id, signature, json.dumps(result)))
        store.db.execute("UPDATE refund_requests SET state='applied',updated_at=CURRENT_TIMESTAMP WHERE request_id=?",
                         (request_id,))
        team14_persistent._fault('before_refund_commit')
    return result
