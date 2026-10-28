"""Non-production wiring: server booking/referral SQLite -> Team14 ledger.

Team13 must provide an authenticated internal read_event(event_id) function.
No public HTTP endpoint, payment gateway, or client supplied event objects.
"""
from team14_persistent import SimError,ident
from team14_settlement_coordinator import settle_with_referral
from team14_team11_db_adapter import read_server_booking,read_server_referral_parent

def settle_from_server_db(settlement_store,referral_store,server_db_path,event_id,read_event):
    ident(event_id)
    if not callable(read_event):
        raise SimError('FORBIDDEN','Team13 authenticated event reader required')
    event=read_event(event_id)
    if not isinstance(event,dict) or event.get('event_id')!=event_id:
        raise SimError('NOT_FOUND','server event missing')
    month=ident(event.get('month_id'))
    lesson=ident(event.get('lesson_id'))
    booking_id=ident(event.get('booking_id'))
    def booking_reader(requested_booking_id):
        if requested_booking_id!=booking_id:
            raise SimError('FORBIDDEN','booking ID mismatch')
        # Authentication is established by Team13's internal reader, never HTTP input.
        booking=read_server_booking(server_db_path,booking_id,month,lesson,
                                   authenticated_event=True)
        lesson_row=settlement_store.db.execute(
            'SELECT amount FROM lessons WHERE id=? AND month_id=? AND booking_id=?',
            (lesson,month,booking_id)).fetchone()
        if lesson_row is None:
            raise SimError('NOT_FOUND','settlement lesson not found')
        if lesson_row['amount']!=booking['booking_price_krw']:
            raise SimError('CONFLICT','server booking price and settlement amount differ')
        return booking
    def referral_reader(learner_id):
        return read_server_referral_parent(server_db_path,learner_id)
    # Freeze one server-owned event snapshot; do not re-read mutable event data.
    return settle_with_referral(settlement_store,referral_store,event_id,
                                lambda requested: event if requested==event_id else None,
                                booking_reader,referral_reader)
