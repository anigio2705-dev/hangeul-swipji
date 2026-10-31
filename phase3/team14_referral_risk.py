"""#109 server-side referral abuse risk signals; review only, never payouts.

All edges, account-cluster findings and booking evidence MUST come from trusted
server records, never from client-supplied identifiers. An absent signal is
UNKNOWN, not proof of legitimacy. This does not perform identity verification.
"""
from team14_persistent import SimError, ident

MAX_EDGES = 10000
MAX_CLUSTERS = 1000


def screen_referral_risk(*, referred_id, inviter_id, stored_edges,
                         verified_account_clusters=(), booking=None):
    """Inspect a proposed relation and optional trusted booking snapshot.

    Returns deterministic review flags. Does not create links, block bookings,
    credit points or authorize any real/simulated transfer.
    """
    ident(referred_id)
    ident(inviter_id)
    if not isinstance(stored_edges, (tuple, list)) or len(stored_edges) > MAX_EDGES:
        raise SimError("VALIDATION_ERROR", "bounded trusted edges required")
    if not isinstance(verified_account_clusters, (tuple, list)) or len(verified_account_clusters) > MAX_CLUSTERS:
        raise SimError("VALIDATION_ERROR", "bounded trusted duplicate-account findings required")

    flags = set()
    graph = {}
    for edge in stored_edges:
        if not isinstance(edge, (tuple, list)) or len(edge) != 2:
            raise SimError("VALIDATION_ERROR", "invalid trusted referral edge")
        child, parent = edge
        ident(child)
        ident(parent)
        if child == parent:
            flags.add("SELF_REFERRAL")
        if child in graph:
            flags.add("DUPLICATE_OR_CHANGED_PARENT")
        else:
            graph[child] = parent
    if referred_id == inviter_id:
        flags.add("SELF_REFERRAL")
    if referred_id in graph:
        if graph[referred_id] != inviter_id:
            flags.add("IMMUTABLE_PARENT_CONFLICT")
        else:
            flags.add("EXISTING_RELATION_REPLAY")
    else:
        graph[referred_id] = inviter_id

    # Check all graph paths, including imported historical rows.
    resolved = set()
    for start in graph:
        if start in resolved:
            continue
        visiting = set()
        current = start
        while current in graph and current not in resolved:
            if current in visiting:
                flags.add("CYCLE_OR_RECIPROCAL")
                break
            visiting.add(current)
            current = graph[current]
        resolved.update(visiting)

    for group in verified_account_clusters:
        if not isinstance(group, (tuple, list, set, frozenset)) or len(group) > 100:
            raise SimError("VALIDATION_ERROR", "invalid trusted account cluster")
        checked = set()
        for user_id in group:
            ident(user_id)
            checked.add(user_id)
        if referred_id in checked and inviter_id in checked:
            flags.add("POSSIBLE_MULTI_ACCOUNT")

    if booking is None:
        flags.add("TRANSACTION_NOT_ASSESSED")
    else:
        if not isinstance(booking, dict):
            raise SimError("VALIDATION_ERROR", "trusted booking snapshot required")
        student_id = ident(booking.get("student_id"))
        teacher_id = ident(booking.get("teacher_id"))
        if student_id != referred_id:
            flags.add("BOOKING_OWNER_MISMATCH")
        if student_id == teacher_id:
            flags.add("SELF_TRADE")
        if (booking.get("payment_verified") is not True
                or booking.get("lesson_completed") is not True
                or booking.get("attendance_verified") is not True):
            flags.add("TRANSACTION_EVIDENCE_MISSING")

    return {
        "flags": sorted(flags),
        "review_required": bool(flags),
        "account_identity_assessed": bool(verified_account_clusters),
        "real_money": False,
        "payment_enabled": False,
        "reward_authorized": False,
        "policy_approved": False,
    }
