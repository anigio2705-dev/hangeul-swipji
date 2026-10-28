"""Team13 -> Team14 isolated, read-only booking event adapter. No provider calls."""
from team14_persistent import SimError,ident,amount

def apply_booking_event(store,event):
    """Expected: {event_id,month_id,lesson_id,booking_id,transaction_id,
    action,booking_status,currency,amount_krw}. Event source must be authenticated
    by the caller; this adapter deliberately does NOT accept arbitrary webhooks."""
    if not isinstance(event,dict): raise SimError("VALIDATION_ERROR","event object required")
    required={"event_id","month_id","lesson_id","booking_id","transaction_id","action","booking_status","currency","amount_krw"}
    if set(event)!=required: raise SimError("VALIDATION_ERROR","event fields")
    for key in ("event_id","month_id","lesson_id","booking_id","transaction_id"):
        ident(event[key])
    if event["currency"]!="KRW": raise SimError("VALIDATION_ERROR","currency mismatch")
    amount(event["amount_krw"])
    action=event["action"]
    if action not in ("complete","refund","cancel"): raise SimError("VALIDATION_ERROR","event action")
    # Team11 candidate booking states; Team13 currently persists reserved/test_paid/in_class.
    expected={"complete":"completed","refund":"refunded","cancel":"cancelled"}[action]
    if event["booking_status"]!=expected: raise SimError("INVALID_STATE","booking state mismatch")
    return store.event(event["month_id"],event["lesson_id"],event["booking_id"],
        event["transaction_id"],event["event_id"],action,event["amount_krw"],
        event["currency"],event["booking_status"])
