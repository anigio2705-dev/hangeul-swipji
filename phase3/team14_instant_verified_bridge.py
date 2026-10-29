"""Team13 verified instant event -> Team14 simulated settlement, no money transfers.

Only trusted internal code may call this adapter.  It resolves the event afresh
from the actual Team13 SQLite records and uses an existing booking-to-lesson
mapping in the Team14 ledger; neither IDs nor amounts come from client JSON.
"""
from team14_persistent import SimError,ident
from team14_settlement_coordinator import settle_with_referral

def settle_verified_instant_event(server_db, settlement_store, referral_store, event_id):
    import instant_matching
    ident(event_id)
    # The Team13 resolver checks the stored event, booking, current approval and price.
    try:
        verified=instant_matching.verified_event_for_team14(server_db,event_id)
    except Exception as exc:
        if isinstance(exc,instant_matching.server.Error):
            raise SimError('FORBIDDEN',exc.message) from exc
        raise
    if verified.get('verifiedByServer') is not True:
        raise SimError('FORBIDDEN','unverified event')
    if verified.get('type')!='lesson.completed' or verified.get('status') not in ('completed','test_settled'):
        raise SimError('INVALID_STATE','only verified lesson completions can be settled')
    booking_id=ident(verified['bookingId'])
    binding=settlement_store.db.execute(
        'SELECT id,month_id,amount FROM lessons WHERE booking_id=?',
        (booking_id,)).fetchone()
    if binding is None:
        raise SimError('NOT_FOUND','no trusted booking-to-month mapping')
    if binding['amount']!=verified['amount']:
        raise SimError('CONFLICT','server booking price mismatch')
    # Team13 product snapshots must be verified at the product-aware binding boundary.
    # Legacy instant bookings without snapshots remain eligible for the older
    # verified-event simulation path; do not infer or rewrite their product codes.
    month_id=ident(binding['month_id'])
    lesson_id=ident(binding['id'])
    # Stable transaction/event identifiers.  Both are constrained by the
    # settlement SQLite operations and ledger unique indexes.
    event={'event_id':event_id,'booking_id':booking_id,'month_id':month_id,
           'lesson_id':lesson_id,'transaction_id':event_id,'action':'complete',
           'booking_status':'completed','currency':'KRW','amount_krw':0,
           'learner_id':ident(verified['learnerId']),
           'teacher_id':ident(verified['teacherId'])}
    # Preserve current server booking evidence, not an HTTP request payload.
    booking=server_db.execute(
        """SELECT b.id,b.learner_id,b.teacher_id,b.status,b.price,
                  u.role,u.approved
           FROM bookings b JOIN users u ON u.id=b.teacher_id WHERE b.id=?""",
        (booking_id,)).fetchone()
    if (not booking or booking['learner_id']!=event['learner_id']
        or booking['teacher_id']!=event['teacher_id']
        or booking['status'] not in ('completed','test_settled')
        or booking['price']!=binding['amount']
        or booking['role'] not in ('teacher','partner') or booking['approved']!=1):
        raise SimError('FORBIDDEN','booking changed or actor approval revoked')
    record={'booking_id':booking_id,'month_id':month_id,'lesson_id':lesson_id,
            'learner_id':booking['learner_id'],'teacher_id':booking['teacher_id'],
            'teacher_approved':True,'authenticated_event':True,
            'booking_status':'completed'}
    def resolve_booking(requested):
        if requested!=booking_id:raise SimError('FORBIDDEN','booking mismatch')
        return record
    def parent_of(uid):
        row=server_db.execute('SELECT referred_by FROM users WHERE id=?',(uid,)).fetchone()
        if row is None:raise SimError('NOT_FOUND','learner missing')
        return row['referred_by']
    from team14_recovery import settle_recoverably
    result=settle_recoverably(settlement_store,referral_store,event_id,
                                lambda eid:event if eid==event_id else None,
                                resolve_booking,parent_of)
    return dict(event_id=event_id,booking_id=booking_id,month_id=month_id,
                lesson_id=lesson_id,result=result,real_money=False,
                payment_executed=False,payout_eligible=False,
                verified_session_kind='simulated')

def refund_verified_instant_settlement(server_db,settlement_store,booking_id,
                                       refund_id,amount_krw,actor_id):
    """Internal simulated adjustment; actor must be a booking participant.

    A refund is a separate ledger operation; a repeated refund_id is idempotent.
    It does not modify the original Team13 completed event or execute money APIs.
    """
    from team14_persistent import amount as check_amount
    ident(booking_id);ident(refund_id);ident(actor_id)
    check_amount(amount_krw,True)
    booking=server_db.execute(
        'SELECT learner_id,teacher_id,status,price FROM bookings WHERE id=?',
        (booking_id,)).fetchone()
    if booking is None:raise SimError('NOT_FOUND','booking missing')
    if actor_id not in (booking['learner_id'],booking['teacher_id']):
        raise SimError('FORBIDDEN','not a booking participant')
    if booking['status'] not in ('completed','test_settled','refunded'):
        raise SimError('INVALID_STATE','booking not completed')
    binding=settlement_store.db.execute(
        'SELECT id,month_id,amount,state FROM lessons WHERE booking_id=?',
        (booking_id,)).fetchone()
    if binding is None or binding['amount']!=booking['price']:
        raise SimError('CONFLICT','booking price or settlement mapping mismatch')
    return settlement_store.event(binding['month_id'],binding['id'],booking_id,
                                  refund_id,refund_id,'refund_completed',
                                  amount_krw,'KRW','refunded')
