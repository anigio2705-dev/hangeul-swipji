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
