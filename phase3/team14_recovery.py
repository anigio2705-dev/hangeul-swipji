"""Durable mock-settlement recovery journal with explicit non-payment semantics.

The settlement and referral SQLite databases remain distinct. A durable prepare
record precedes settlement; after a crash, deterministic event replay completes
missing referral awards. No external payment or payout is ever performed.
"""
import json
from team14_persistent import SimError,ident
from team14_settlement_coordinator import settle_with_referral

FAULT_HOOK=None

def _fault(point):
    if FAULT_HOOK is not None:
        FAULT_HOOK(point)

def _initialize(store):
    store.db.execute("""CREATE TABLE IF NOT EXISTS recovery_events(
       event_id TEXT PRIMARY KEY, booking_id TEXT NOT NULL,
       payload TEXT NOT NULL, status TEXT NOT NULL
       CHECK(status IN ('prepared','settled')), updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")

def settle_recoverably(store,referrals,event_id,read_event,resolve_booking,read_referral_parent):
    ident(event_id)
    if not callable(read_event):raise SimError('FORBIDDEN','trusted read_event required')
    event=read_event(event_id)
    if not isinstance(event,dict) or event.get('event_id')!=event_id:
        raise SimError('NOT_FOUND','verified server event not found')
    booking_id=ident(event.get('booking_id'))
    _initialize(store)
    # Prepare durable intent before any money *simulation* mutations.
    serialized=json.dumps(event,sort_keys=True,separators=(',',':'))
    with store.atomic():
        old=store.db.execute('SELECT payload FROM recovery_events WHERE event_id=?',
                             (event_id,)).fetchone()
        if old is not None and old['payload']!=serialized:
            raise SimError('CONFLICT','event identity reused with changed payload')
        if old is None:
            store.db.execute("INSERT INTO recovery_events(event_id,booking_id,payload,status) VALUES(?,?,?,'prepared')",
                             (event_id,booking_id,serialized))
    _fault('after_event_received')
    _fault('before_settlement')
    result=settle_with_referral(store,referrals,event_id,
                                 lambda key:event if key==event_id else None,
                                 resolve_booking,read_referral_parent)
    _fault('after_referral_award')
    _fault('before_settlement_done')
    with store.atomic():
        store.db.execute("UPDATE recovery_events SET status='settled',updated_at=CURRENT_TIMESTAMP WHERE event_id=?",
                         (event_id,))
    return result

def recovery_status(store,event_id):
    ident(event_id)
    _initialize(store)
    row=store.db.execute('SELECT status,booking_id FROM recovery_events WHERE event_id=?',
                         (event_id,)).fetchone()
    return None if row is None else dict(row)

def unfinished_events(store):
    _initialize(store)
    return [row['event_id'] for row in store.db.execute(
        "SELECT event_id FROM recovery_events WHERE status='prepared' ORDER BY event_id")]

def recover_prepared(store,referrals,read_event,resolve_booking,read_referral_parent):
    """Replay pending IDs using current trusted server-owned callbacks.
    Do not reconstruct authentication solely from persisted payload.
    """
    results=[]
    for event_id in unfinished_events(store):
        results.append(settle_recoverably(store,referrals,event_id,read_event,
                                         resolve_booking,read_referral_parent))
    return results
