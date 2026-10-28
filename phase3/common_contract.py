"""Pure shared contract validation. No database access or production side effects."""
import re

ROLES = frozenset(("learner", "partner", "teacher", "admin"))
TEACHING_ROLES = frozenset(("partner", "teacher"))
KINDS = frozenset(("conversation_partner", "professional_teacher"))
STATES = frozenset(("requested", "approved", "suspended", "rejected"))
ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,128}$")


def validate_id(value):
    if not isinstance(value, str) or not ID_PATTERN.fullmatch(value):
        raise ValueError("invalid opaque identifier")
    return value


def validate_roles(roles):
    if not isinstance(roles, (list, tuple, set, frozenset)) or not roles:
        raise ValueError("roles must be a nonempty collection")
    if any(not isinstance(role, str) or role not in ROLES for role in roles):
        raise ValueError("unknown role")
    if len(roles) != len(set(roles)):
        raise ValueError("duplicate roles")
    return frozenset(roles)


def can_teach(roles, kind, approval):
    validated = validate_roles(roles)
    if kind not in KINDS or approval not in STATES:
        raise ValueError("invalid teaching profile")
    required = "partner" if kind == "conversation_partner" else "teacher"
    return required in validated and approval == "approved"


def validate_referral_edge(referrer_id, referred_id):
    validate_id(referrer_id)
    validate_id(referred_id)
    if referrer_id == referred_id:
        raise ValueError("self-referral prohibited")
    return (referrer_id, referred_id)


def validate_amount_minor(value):
    if type(value) is not int or value < 0 or value > 10**15:
        raise ValueError("invalid minor-unit amount")
    return value

# Candidate v1 contract: these names do not change legacy persisted states.
BOOKING_STATES = frozenset(("reserved", "expired", "cancelled", "test_paid", "in_class", "completed", "refunded"))
MATCH_STATES = frozenset(("idle", "waiting", "offered", "active", "ended"))
TRANSACTION_STATES = frozenset(("pending", "authorized", "captured", "failed", "refunded", "partially_refunded"))
ERROR_CODES = frozenset(("UNAUTHENTICATED", "FORBIDDEN", "NOT_FOUND", "VALIDATION_ERROR", "CONFLICT", "INVALID_STATE"))


def roles_from_legacy(role):
    """Read-only projection. Does not grant learner role to existing teachers."""
    if not isinstance(role, str) or role not in ROLES:
        raise ValueError("unknown legacy role")
    return frozenset((role,))


def legacy_role_for(roles):
    """Only singleton roles round-trip without losing permissions."""
    validated = validate_roles(roles)
    if len(validated) != 1:
        raise ValueError("multi-role account cannot be stored in legacy role column")
    return next(iter(validated))


def validate_state(value, domain):
    allowed = {"booking": BOOKING_STATES, "match": MATCH_STATES,
               "transaction": TRANSACTION_STATES}
    if domain not in allowed or not isinstance(value, str) or value not in allowed[domain]:
        raise ValueError("invalid state")
    return value


def validate_error_code(value):
    if not isinstance(value, str) or value not in ERROR_CODES:
        raise ValueError("invalid error code")
    return value
