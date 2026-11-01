"""Original 160 task #140: explicit-assumption growth, infrastructure cost and margin scenarios.

Isolated, deterministic review-only model. Inputs are hypothetical, not vendor
quotes, platform prices, a fee policy, or authorization to charge or pay.
No network, database, credentials, payments or provider APIs.
"""
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_HALF_UP

_MONEY = Decimal("0.01")
_MAX_COUNT = 1_000_000
_MAX_RATE = Decimal("1000000")
_REQUIRED = frozenset({
    "fixed_server_monthly", "server_per_active_user_monthly",
    "video_per_minute", "storage_gb_per_active_user",
    "storage_per_gb_monthly", "notification_per_message",
    "messages_per_completed_lesson", "minutes_per_completed_lesson",
    "lessons_per_learner_monthly", "completion_rate",
    "platform_revenue_per_completed_lesson",
})


def _decimal(value, key, *, unit_interval=False):
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise ValueError("invalid " + key)
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError("invalid " + key) from None
    if not number.is_finite() or number < 0 or number > _MAX_RATE:
        raise ValueError("invalid " + key)
    if unit_interval and number > 1:
        raise ValueError("invalid " + key)
    return number


def _count(value, key):
    if type(value) is not int or value < 0 or value > _MAX_COUNT:
        raise ValueError("invalid " + key)
    return value


def _money(value):
    return str(value.quantize(_MONEY, rounding=ROUND_HALF_UP))


def _break_even(fixed, margin):
    if margin <= 0:
        return 0 if fixed == 0 else None
    return int((fixed / margin).to_integral_value(rounding=ROUND_CEILING))


def compare_growth_economics(*, assumptions, scenarios):
    """Return isolated monthly costs and break-even lesson counts for growth cases.

    Only completed lessons produce modeled revenue, video minutes and messages.
    Infrastructure/storage cost scales with learner+teacher active accounts.
    All rates are explicit inputs; no platform policy is inferred.
    """
    if type(assumptions) is not dict or set(assumptions) != _REQUIRED:
        raise ValueError("assumptions must contain exactly the required fields")
    rates = {k: _decimal(v, k, unit_interval=(k == "completion_rate"))
             for k, v in assumptions.items()}
    if type(scenarios) not in (list, tuple) or not (1 <= len(scenarios) <= 30):
        raise ValueError("scenarios must contain 1..30 cases")

    rows = []
    for case in scenarios:
        if type(case) is not dict or set(case) != {"learners", "teachers"}:
            raise ValueError("scenario must contain learners and teachers")
        learners = _count(case["learners"], "learners")
        teachers = _count(case["teachers"], "teachers")
        active = learners + teachers
        lessons = (Decimal(learners) * rates["lessons_per_learner_monthly"]
                   * rates["completion_rate"])
        video_minutes = lessons * rates["minutes_per_completed_lesson"]
        storage_gb = Decimal(active) * rates["storage_gb_per_active_user"]
        messages = lessons * rates["messages_per_completed_lesson"]
        server_cost = (rates["fixed_server_monthly"]
                       + Decimal(active) * rates["server_per_active_user_monthly"])
        video_cost = video_minutes * rates["video_per_minute"]
        storage_cost = storage_gb * rates["storage_per_gb_monthly"]
        notification_cost = messages * rates["notification_per_message"]
        total_cost = server_cost + video_cost + storage_cost + notification_cost
        revenue = lessons * rates["platform_revenue_per_completed_lesson"]
        fixed = server_cost + storage_cost
        contribution = (rates["platform_revenue_per_completed_lesson"]
                        - rates["minutes_per_completed_lesson"] * rates["video_per_minute"]
                        - rates["messages_per_completed_lesson"] * rates["notification_per_message"])
        # Reconcile the *displayed* two-decimal components. Rounding the
        # unrounded aggregate independently creates contradictory UI totals
        # when individual components contain sub-cent values.
        display_server = Decimal(_money(server_cost))
        display_video = Decimal(_money(video_cost))
        display_storage = Decimal(_money(storage_cost))
        display_notifications = Decimal(_money(notification_cost))
        display_total = (display_server + display_video + display_storage
                         + display_notifications)
        display_revenue = Decimal(_money(revenue))
        display_profit = display_revenue - display_total
        rows.append({
            "learners": learners, "teachers": teachers, "active_users": active,
            "completed_lessons": str(lessons),
            "video_minutes": str(video_minutes),
            "storage_gb": str(storage_gb),
            "notification_messages": str(messages),
            "server_cost": _money(display_server),
            "video_cost": _money(display_video),
            "storage_cost": _money(display_storage),
            "notification_cost": _money(display_notifications),
            "total_cost": _money(display_total),
            "platform_revenue": _money(display_revenue),
            "platform_profit_loss": _money(display_profit),
            "break_even_completed_lessons": _break_even(fixed, contribution),
            "contribution_per_completed_lesson": _money(contribution),
        })
    return {
        "task": 140, "status": "HYPOTHETICAL_REVIEW_ONLY",
        "currency": "ASSUMPTION_UNITS", "assumptions": {k: str(rates[k]) for k in sorted(rates)},
        "scenarios": rows,
        "provider_quotes_verified": False, "pricing_policy_approved": False,
        "real_money_enabled": False, "operating_db_connected": False,
        "external_api_called": False, "deployment_approved": False,
    }
