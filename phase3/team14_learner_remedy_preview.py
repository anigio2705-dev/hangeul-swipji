"""#119 policy-gated learner remedy review: simulation only, no actual entitlement.

A real student-facing selection requires an authenticated booking, approved
country-specific policy, verified dispute decision and a separate server API.
This module NEVER creates bookings, refunds, replacement sessions or payouts.
"""
import re

ID = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")
OPTIONS = ("makeup_lesson", "change_tutor", "unused_lessons_refund")
STATES = ("unverified", "review_pending", "manual_review_recorded")


def remedy_preview(*, case_ref, remaining_lessons, dispute_state,
                   policy_fixture=None):
    if type(case_ref) is not str or not ID.fullmatch(case_ref):
        raise ValueError("invalid case reference")
    if type(remaining_lessons) is not int or not 0 <= remaining_lessons <= 1000:
        raise ValueError("invalid remaining lesson count")
    if type(dispute_state) is not str or dispute_state not in STATES:
        raise ValueError("invalid dispute state")
    if policy_fixture is not None:
        if type(policy_fixture) is not dict or set(policy_fixture) != {
                "version", "enabled_options"}:
            raise ValueError("invalid policy test fixture")
        version = policy_fixture["version"]
        allowed = policy_fixture["enabled_options"]
        if type(version) is not str or not ID.fullmatch(version):
            raise ValueError("invalid policy fixture version")
        if type(allowed) not in (list, tuple) or any(
                type(o) is not str or o not in OPTIONS for o in allowed):
            raise ValueError("invalid fixture options")
        if len(set(allowed)) != len(allowed):
            raise ValueError("duplicate fixture option")
    else:
        allowed = ()
        version = None
    options = []
    for option in OPTIONS:
        no_lessons = remaining_lessons == 0
        fixture_enabled = option in allowed and not no_lessons
        options.append({
            "id": option,
            "shown": not no_lessons,
            "fixture_eligible": fixture_enabled,
            "status": ("SIMULATION_ONLY" if fixture_enabled else
                       "NO_REMAINING_LESSONS" if no_lessons else
                       "POLICY_NOT_APPROVED"),
            "student_can_select": False,
            "refund_executed": False,
            "booking_modified": False,
            "teacher_reassigned": False,
        })
    return {
        "case_ref": case_ref,
        "remaining_lessons": remaining_lessons,
        "dispute_state": dispute_state,
        "policy_fixture_version": version,
        "options": options,
        "manual_review_required": True,
        "authenticated_booking_verified": False,
        "policy_approved": False,
        "real_money": False,
        "refund_executed": False,
        "booking_modified": False,
        "payout_authorized": False,
        "operating_db_connected": False,
    }
