"""Pure compatibility adapter; never mutates legacy users, DB or service state."""
from dataclasses import dataclass
from typing import Mapping

from common_contract import ROLES, validate_roles, roles_from_legacy, can_teach, validate_state, validate_error_code

@dataclass(frozen=True)
class IdentityView:
    roles: frozenset
    provider_approvals: Mapping

    def may_learn(self):
        return "learner" in self.roles

    def may_provide(self, kind):
        approval = self.provider_approvals.get(kind, "requested")
        return can_teach(self.roles, kind, approval)


def from_legacy_user(user):
    """Project actual users.role/approved without silently granting extra roles."""
    role = user["role"]
    approved = user["approved"]
    if type(approved) not in (bool, int) or approved not in (0, 1):
        raise ValueError("invalid legacy approved flag")
    roles = roles_from_legacy(role)
    approval = "approved" if approved else "requested"
    return IdentityView(roles, {
        "conversation_partner": approval if role in ("partner", "teacher") else "requested",
        "professional_teacher": approval if role == "teacher" else "requested",
    })


def from_candidate(roles, approvals):
    """Candidate roles require explicit per-profile approvals, never implicit grant."""
    valid = validate_roles(roles)
    if not isinstance(approvals, Mapping):
        raise ValueError("approval map required")
    if any(k not in ("conversation_partner", "professional_teacher") or
           v not in ("requested", "approved", "suspended", "rejected")
           for k, v in approvals.items()):
        raise ValueError("invalid approval map")
    return IdentityView(valid, dict(approvals))


def matching_side(view, requested_side):
    """Explicit intent prevents provider accounts silently becoming learners."""
    if requested_side == "learner":
        return view.may_learn()
    if requested_side == "provider":
        return (view.may_provide("conversation_partner") or
                view.may_provide("professional_teacher"))
    raise ValueError("invalid requested side")


def normalize_match_state(state):
    """API-only idle/waiting and persisted offered/active/ended remain distinct."""
    validate_state(state, "match")
    return {"state": state, "persisted": state in ("offered", "active", "ended")}


def normalize_error(status):
    """Read-only status mapping; no legacy response shape modification."""
    if type(status) is not int:
        raise ValueError("invalid HTTP status")
    code = {400:"VALIDATION_ERROR",401:"UNAUTHENTICATED",403:"FORBIDDEN",
            404:"NOT_FOUND",409:"CONFLICT"}.get(status)
    if code is None:
        raise ValueError("unmapped HTTP status")
    return validate_error_code(code)


def month_lesson_reference(month_id, lesson_index, currency):
    """Reject invented transaction/booking IDs; keep simulation references scoped."""
    if not isinstance(month_id, str) or not month_id:
        raise ValueError("month id required")
    if type(lesson_index) is not int or lesson_index < 0:
        raise ValueError("invalid lesson index")
    if currency != "KRW":
        raise ValueError("monthly simulation only supports KRW")
    return {"month_id":month_id, "lesson_index":lesson_index, "currency":"KRW"}
