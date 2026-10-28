"""Non-production lesson-event settlement and referral coordination.

Trusted internal callers only. The booking/event resolvers MUST be server-owned;
the learner ID and referral parent relationships MUST come from server DB.
No payout is ever performed. Referral awards are recorded only after settlement.
"""
from team14_persistent import SimError,ident
from team14_internal_event_consumer import consume_internal_lesson_event
from team14_statements import lesson_statement

def settle_with_referral(settlement_store,referral_store,event_id,read_event,
                         resolve_booking,read_referral_parent=None):
    """Return simulated settlement and eligible referral award.

    read_referral_parent(learner_id) -> trusted server DB parent ID or None.
    ReferralStore.link is immutable, and a conflicting parent is rejected.
    For non-completion actions, only the settlement ledger is updated.
    """
    ident(event_id)
    if not callable(read_event) or not callable(resolve_booking):
        raise SimError('FORBIDDEN','trusted server callbacks required')
    event=read_event(event_id)
    if not isinstance(event,dict) or event.get('event_id')!=event_id:
        raise SimError('NOT_FOUND','server event missing')
    action=event.get('action')
    if action not in ('complete','refund','refund_completed','cancel'):
        raise SimError('VALIDATION_ERROR','unsupported event action')
    if action=='complete':
        if not callable(read_referral_parent):
            raise SimError('FORBIDDEN','trusted referral parent lookup required')
        learner=ident(event.get('learner_id'))
        # Validate the server-owned booking BEFORE mutating referral relationships.
        booking=resolve_booking(ident(event.get('booking_id')))
        if not isinstance(booking,dict):
            raise SimError('NOT_FOUND','server booking unavailable')
        if (booking.get('learner_id')!=learner or
            booking.get('teacher_id')!=event.get('teacher_id') or
            booking.get('teacher_approved') is not True or
            booking.get('authenticated_event') is not True or
            booking.get('booking_status')!=event.get('booking_status') or
            any(booking.get(k)!=event.get(k) for k in ('booking_id','month_id','lesson_id'))):
            raise SimError('FORBIDDEN','unverified booking or event')
        parent=read_referral_parent(learner)
        if parent is not None:
            referral_store.link(learner,ident(parent))
    # Pin the authenticated server event snapshot for the entire operation.
    # A second mutable DB read could otherwise change participants, action or amount
    # between referral verification and settlement application.
    result=consume_internal_lesson_event(
        settlement_store,event_id,lambda requested_id: event if requested_id==event_id else None,
        resolve_booking)
    if action=='complete':
        gross=lesson_statement(settlement_store,event['month_id'],event['lesson_id'])['gross_krw']
        award=referral_store.award(event_id,learner,event['lesson_id'],gross)
    else:
        award=None
    return dict(settlement=result,referral_award=award,real_money=False)
