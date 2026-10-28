"""D1 test-only product/pricing policy for 15/25-minute and four-session lessons.

75% teacher / 25% combined platform+referral allocation is approved as an
INITIAL simulated split, not a live payment policy. Prices are not approved.
Callers must supply positive integer KRW prices from a trusted server catalog.
"""
from team14_persistent import SimError, ident, amount

TEACHER_BPS = 7500
PLATFORM_GROSS_BPS = 2500
MAX_REFERRAL_BPS = PLATFORM_GROSS_BPS

def validate_product(duration_minutes, sessions, unit_price_krw, referral_bps=0):
    if type(duration_minutes) is not int or duration_minutes not in (15, 25):
        raise SimError('VALIDATION_ERROR', 'supported lesson duration: 15 or 25 minutes')
    if type(sessions) is not int or sessions not in (1, 4):
        raise SimError('VALIDATION_ERROR', 'supported package: 1 or 4 sessions')
    amount(unit_price_krw, positive=True)
    if type(referral_bps) is not int or not 0 <= referral_bps <= MAX_REFERRAL_BPS:
        raise SimError('VALIDATION_ERROR', 'referral exceeds platform share')
    total = unit_price_krw * sessions
    amount(total, positive=True)
    return dict(duration_minutes=duration_minutes, sessions=sessions,
                unit_price_krw=unit_price_krw, total_price_krw=total,
                teacher_bps=TEACHER_BPS, platform_gross_bps=PLATFORM_GROSS_BPS,
                referral_bps=referral_bps, prices_approved=False,
                real_money=False, payout_eligible=False)

def create_simulated_package(store, month_id, booking_ids, duration_minutes,
                             unit_price_krw, referral_bps=0):
    """Server-side only: booking IDs and trusted catalog price, never client totals.

    The four-session package creates FOUR distinct lesson/booking mappings,
    avoiding a fake single 'completed' event paying all four sessions.
    Existing MonthStore behavior and legacy policy remain unchanged.
    """
    ident(month_id)
    if not isinstance(booking_ids, (list, tuple)) or len(booking_ids) not in (1, 4):
        raise SimError('VALIDATION_ERROR', '1 or 4 booking IDs required')
    bookings = [ident(x) for x in booking_ids]
    if len(set(bookings)) != len(bookings):
        raise SimError('CONFLICT', 'duplicate booking ID')
    product = validate_product(duration_minutes, len(bookings),
                               unit_price_krw, referral_bps)
    lesson_rows = [(ident('lesson_' + booking), booking, unit_price_krw)
                   for booking in bookings]
    result = store.create_month(month_id, lesson_rows, commission_bps=2500,
                                referral_bps=referral_bps)
    return dict(result, product=product)

def expected_split(total_krw, referral_bps=0):
    """Calculate ledger-compatible integer split, referral WITHIN platform 25%."""
    amount(total_krw, positive=True)
    if type(referral_bps) is not int or not 0 <= referral_bps <= 2500:
        raise SimError('VALIDATION_ERROR', 'referral exceeds platform share')
    teacher = total_krw * 7500 // 10000
    referral = total_krw * referral_bps // 10000
    platform = total_krw - teacher - referral
    return dict(gross=total_krw, teacher=teacher, referral=referral,
                platform=platform, platform_including_referral=platform + referral,
                real_money=False, payout_eligible=False)

# D2 prices approved for TEST-ONLY simulation; production PG and price approval
# remain separate. A completed event must match the server booking price.
TEST_CATALOG = {
    'trial_15': (15, 6000),
    'partner_25': (25, 10000),
    'professional_25': (25, 15000),
}

def bind_server_booking_product(server_db, store, month_id, booking_id, product_code,
                                referral_bps=0):
    """Create a single trusted mapping only when server booking price matches catalog.

    Never edits Team13 bookings or emits a completion event. The existing
    verified-event bridge is the sole path to simulate earned allocations.
    """
    ident(month_id)
    ident(booking_id)
    if product_code not in TEST_CATALOG:
        raise SimError('VALIDATION_ERROR', 'unknown test product')
    duration, price = TEST_CATALOG[product_code]
    row = server_db.execute(
        'SELECT b.price,b.status,u.role,u.approved FROM bookings b '
        'JOIN users u ON u.id=b.teacher_id WHERE b.id=?', (booking_id,)
    ).fetchone()
    if row is None:
        raise SimError('NOT_FOUND', 'server booking not found')
    if row['price'] != price:
        raise SimError('CONFLICT', 'server booking price differs from test catalog')
    if row['role'] not in ('teacher', 'partner') or row['approved'] != 1:
        raise SimError('FORBIDDEN', 'teacher is not approved')
    if product_code == 'professional_25' and row['role'] != 'teacher':
        raise SimError('FORBIDDEN', 'professional product requires teacher role')
    if product_code == 'partner_25' and row['role'] != 'partner':
        raise SimError('FORBIDDEN', 'partner product requires partner role')
    if row['status'] not in ('test_paid', 'in_class', 'completed', 'test_settled'):
        raise SimError('INVALID_STATE', 'booking not eligible')
    result = create_simulated_package(store, month_id, [booking_id], duration,
                                      price, referral_bps)
    return dict(result, product_code=product_code, test_price_krw=price,
                real_money=False, payment_executed=False, payout_eligible=False)
