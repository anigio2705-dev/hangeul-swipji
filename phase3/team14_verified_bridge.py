"""Fail-closed integration boundary for trusted Team13 internal events; TEST ONLY.

The trusted resolver MUST query authenticated Team13 server-side booking/role data.
Never expose this entry point as a public endpoint or accept client-supplied trust.
"""
from team14_persistent import SimError,ident
from team14_booking_events import apply_booking_event

def apply_verified_booking_event(store,event,resolve_booking):
    """Resolver(booking_id) -> server-side dict:
    {booking_id,month_id,lesson_id,learner_id,teacher_id,
     teacher_approved,booking_status,authenticated_event}.
    Caller owns server authentication and event provenance.
    """
    if not callable(resolve_booking):
        raise SimError('FORBIDDEN','trusted server resolver required')
    if not isinstance(event,dict):
        raise SimError('VALIDATION_ERROR','event object required')
    booking_id=ident(event.get('booking_id'))
    record=resolve_booking(booking_id)
    if not isinstance(record,dict):
        raise SimError('NOT_FOUND','server booking unavailable')
    keys=('booking_id','month_id','lesson_id','learner_id','teacher_id')
    for key in keys:
        ident(record.get(key))
    if not record.get('authenticated_event') is True:
        raise SimError('FORBIDDEN','unverified event source')
    if record.get('teacher_approved') is not True:
        raise SimError('FORBIDDEN','teacher not approved')
    if any(record[k]!=event.get(k) for k in ('booking_id','month_id','lesson_id')):
        raise SimError('FORBIDDEN','booking ownership mismatch')
    if record.get('booking_status')!=event.get('booking_status'):
        raise SimError('INVALID_STATE','stale or forged booking status')
    return apply_booking_event(store,event)
