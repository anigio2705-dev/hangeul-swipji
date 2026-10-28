"""Read-only booking and ownership boundary for Team13/14.

Never grants access from caller-supplied roles. User rows and booking rows must
be loaded by the service from authenticated session and database.
"""
from common_contract import validate_id
from team11_shared_boundary import authorize_provider, authorize_student

def booking_access(learner, provider, booking, actor_id, action):
    """Return stable allow/error contract for existing booking participants."""
    if action not in ("view", "join", "complete", "settle"):
        return {"allowed": False, "code": "VALIDATION_ERROR"}
    try:
        actor_id = validate_id(actor_id)
        if booking["learner_id"] != learner["id"] or booking["teacher_id"] != provider["id"]:
            return {"allowed": False, "code": "CONFLICT"}
        if learner["id"] == provider["id"]:
            return {"allowed": False, "code": "CONFLICT"}
        learner_allowed = authorize_student(learner).allowed
        provider_allowed = (
            authorize_provider(provider, "professional_teacher").allowed
            if provider["role"] == "teacher" else
            authorize_provider(provider, "conversation_partner").allowed
        )
        if not learner_allowed or not provider_allowed:
            return {"allowed": False, "code": "FORBIDDEN"}
        if actor_id not in (learner["id"], provider["id"]):
            return {"allowed": False, "code": "FORBIDDEN"}
        if action == "complete" and actor_id != provider["id"]:
            return {"allowed": False, "code": "FORBIDDEN"}
        if action == "settle":
            return {"allowed": False, "code": "FORBIDDEN"}
        state = booking["status"]
        if action == "join" and state not in ("test_paid", "in_class"):
            return {"allowed": False, "code": "INVALID_STATE"}
        if action == "complete" and state != "in_class":
            return {"allowed": False, "code": "INVALID_STATE"}
        if action == "view" and state not in (
            "reserved", "test_paid", "in_class", "completed", "test_settled", "cancelled", "refunded", "expired"
        ):
            return {"allowed": False, "code": "INVALID_STATE"}
        return {"allowed": True, "code": None}
    except (ValueError, KeyError, TypeError):
        return {"allowed": False, "code": "VALIDATION_ERROR"}
