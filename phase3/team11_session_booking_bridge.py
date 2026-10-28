"""Team11 trusted session-to-booking authorization bridge.

No route, deployment, database schema or Team13 matching code is changed.
"""
import hashlib
import time

from team11_server_booking_adapter import authenticated_booking_access

def authenticated_session_booking_access(db, raw_session_token, booking_id, action, now=None):
    """Resolve the *server cookie token* to a live DB session, then authorize.

    Callers must extract hs3 from the HTTP Cookie header, never request JSON.
    Returns a deny-by-default decision; does not disclose room URLs.
    """
    if not isinstance(raw_session_token, str) or not 16 <= len(raw_session_token) <= 512:
        return {"allowed": False, "code": "UNAUTHENTICATED"}
    digest = hashlib.sha256(raw_session_token.encode("utf-8")).hexdigest()
    clock = time.time() if now is None else now
    row = db.execute(
        "SELECT s.user_id FROM sessions s JOIN users u ON u.id=s.user_id "
        "WHERE s.token=? AND s.expires>?", (digest, clock)
    ).fetchone()
    if row is None:
        return {"allowed": False, "code": "UNAUTHENTICATED"}
    return authenticated_booking_access(db, row["user_id"], booking_id, action)
