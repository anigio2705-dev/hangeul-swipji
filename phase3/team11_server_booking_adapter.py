"""Team11 server-side adapter: load identity and booking from trusted SQLite rows.

Team13 can call this from authenticated handlers. Caller must supply user_id
from verified server session, never from request JSON. No schema mutation.
"""
from team11_booking_access import booking_access
from common_contract import validate_id

def authenticated_booking_access(db, session_user_id, booking_id, action):
    try:
        validate_id(session_user_id)
        validate_id(booking_id)
    except ValueError:
        return {"allowed": False, "code": "VALIDATION_ERROR"}
    booking = db.execute("SELECT * FROM bookings WHERE id=?", (booking_id,)).fetchone()
    if booking is None:
        return {"allowed": False, "code": "NOT_FOUND"}
    user = db.execute("SELECT * FROM users WHERE id=?", (session_user_id,)).fetchone()
    if user is None:
        return {"allowed": False, "code": "UNAUTHENTICATED"}
    if session_user_id not in (booking["learner_id"], booking["teacher_id"]):
        return {"allowed": False, "code": "FORBIDDEN"}
    learner = db.execute("SELECT * FROM users WHERE id=?", (booking["learner_id"],)).fetchone()
    provider = db.execute("SELECT * FROM users WHERE id=?", (booking["teacher_id"],)).fetchone()
    if learner is None or provider is None:
        return {"allowed": False, "code": "NOT_FOUND"}
    return booking_access(learner, provider, booking, session_user_id, action)
