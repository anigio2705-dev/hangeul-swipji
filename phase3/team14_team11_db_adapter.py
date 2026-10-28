"""Read-only Team11 phase3 SQLite adapters for trusted Team14 simulation.

Only call from the authenticated internal server process. Never expose these
functions as public HTTP handlers or accept caller-supplied identity claims.
"""
import sqlite3
from team14_persistent import SimError,ident

def _db(path):
    if not isinstance(path,str) or not path or path==':memory:':
        raise SimError('VALIDATION_ERROR','persistent server database path required')
    con=sqlite3.connect('file:'+path+'?mode=ro',uri=True)
    con.row_factory=sqlite3.Row
    return con

def read_server_booking(path,booking_id,month_id,lesson_id,authenticated_event=False):
    """Query Team11 users/bookings DB. Caller establishes event authentication.

    month_id and lesson_id are internal settlement identifiers, not Team11
    booking columns. The caller must bind them to the authenticated event.
    """
    for x in (booking_id,month_id,lesson_id):ident(x)
    with _db(path) as con:
        row=con.execute("""SELECT b.id,b.learner_id,b.teacher_id,b.status,
                            u.role,u.approved
                            FROM bookings b JOIN users u ON u.id=b.teacher_id
                            WHERE b.id=?""",(booking_id,)).fetchone()
        if row is None:raise SimError('NOT_FOUND','server booking unavailable')
        if row['role'] not in ('teacher','partner'):
            raise SimError('FORBIDDEN','booking teacher role invalid')
        return dict(booking_id=row['id'],month_id=month_id,lesson_id=lesson_id,
                    learner_id=row['learner_id'],teacher_id=row['teacher_id'],
                    teacher_approved=bool(row['approved']),
                    booking_status=row['status'],
                    authenticated_event=authenticated_event)

def read_server_referral_parent(path,learner_id):
    ident(learner_id)
    with _db(path) as con:
        row=con.execute('SELECT referred_by FROM users WHERE id=?',(learner_id,)).fetchone()
        if row is None:raise SimError('NOT_FOUND','server learner unavailable')
        return row['referred_by']
