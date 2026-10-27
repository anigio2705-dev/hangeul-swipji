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
