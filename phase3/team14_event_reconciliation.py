"""Non-production reconciliation for server event delivery and simulated ledger.

The caller provides a trusted server-side event ID listing and DB readers.
This function never accepts browser events or transfers real money.
"""
from team14_persistent import SimError,ident
from team14_settlement_coordinator import settle_with_referral
from team14_statements import lesson_statement

def reconcile_events(settlement_store,referral_store,event_ids,read_event,
                     resolve_booking,read_referral_parent):
    if not isinstance(event_ids,(list,tuple)):
        raise SimError('VALIDATION_ERROR','server event IDs required')
    if len(event_ids)>10000:
        raise SimError('VALIDATION_ERROR','batch too large')
    seen=set();results=[]
    for event_id in event_ids:
        ident(event_id)
        if event_id in seen:
            raise SimError('CONFLICT','duplicate ID in reconciliation batch')
        seen.add(event_id)
        event=read_event(event_id)
        if not isinstance(event,dict) or event.get('event_id')!=event_id:
            raise SimError('NOT_FOUND','trusted event missing')
        result=settle_with_referral(settlement_store,referral_store,event_id,
                                   read_event,resolve_booking,read_referral_parent)
        statement=lesson_statement(settlement_store,event['month_id'],event['lesson_id'])
        if event['action']=='complete':
            award=referral_store.awards_for_lesson(event['lesson_id'])
            if result['referral_award']!=award:
                raise AssertionError('referral award mismatch')
        results.append(dict(event_id=event_id,state=result['settlement']['state'],
                            ledger_entries=len(statement['ledger']),
                            refunded_krw=statement['refunded_krw'],
                            real_money=False))
    return results
