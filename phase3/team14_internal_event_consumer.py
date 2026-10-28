"""Trusted internal Team13 event-store consumer; simulation only, no HTTP/payment API.

The Team13 integration layer supplies a server-owned read_event(event_id) callback.
Never accept an event payload or an authenticated flag from a browser/client.
"""
from team14_persistent import SimError,ident
from team14_verified_bridge import apply_verified_booking_event

def consume_internal_lesson_event(store,event_id,read_event,resolve_booking):
    """Read and apply one authenticated event from Team13's persistent server store.

    read_event(event_id) must read the server DB and return:
      {event_id,month_id,lesson_id,booking_id,transaction_id,action,
       booking_status,currency,amount_krw,learner_id,teacher_id}
    resolve_booking(booking_id) must read server-owned booking/teacher DB data.
    Both callbacks must be provided by the trusted internal server layer.
    """
    ident(event_id)
    if not callable(read_event) or not callable(resolve_booking):
        raise SimError('FORBIDDEN','trusted server callbacks required')
    event=read_event(event_id)
    if not isinstance(event,dict):
        raise SimError('NOT_FOUND','server event not found')
    if event.get('event_id')!=event_id:
        raise SimError('FORBIDDEN','server event identity mismatch')
    learner=ident(event.get('learner_id'))
    teacher=ident(event.get('teacher_id'))
    record=resolve_booking(ident(event.get('booking_id')))
    if not isinstance(record,dict):
        raise SimError('NOT_FOUND','server booking unavailable')
    if record.get('learner_id')!=learner or record.get('teacher_id')!=teacher:
        raise SimError('FORBIDDEN','event participant mismatch')
    if record.get('authenticated_event') is not True:
        raise SimError('FORBIDDEN','unverified internal event')
    payload={k:v for k,v in event.items() if k not in ('learner_id','teacher_id')}
    return apply_verified_booking_event(store,payload,lambda booking_id:record)
