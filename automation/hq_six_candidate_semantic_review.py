"""Read-only, deterministic red flags for independently reviewing AI candidate cases.

These diagnostics never promote READY or assert educational/UX correctness.
A human/independent team15 reviewer must decide whether a case is acceptable.
"""
import re


def semantic_review_flags(artifact):
    """Return stable (case_id, issue_code) pairs for high-confidence contract risks."""
    team = str(artifact.get("team", ""))
    flags = []
    for case in artifact.get("items", []):
        if not isinstance(case, dict):
            continue
        case_id = str(case.get("id", ""))
        text = str(case.get("text", ""))
        expected = str(case.get("expected", ""))
        lower = expected.lower()
        if team == "11" and "stale" in (case_id + " " + text).lower():
            if re.search(r"allow(?:s|ed)? override|warning without blocking|default behavior is warning", lower):
                flags.append((case_id, "stale_checkout_must_block"))
        if team == "12":
            if "는" in expected and "subject" in lower and "topic" not in lower:
                flags.append((case_id, "topic_particle_mislabeled_subject"))
            if "number 'one'" in text.lower() and "native" not in text.lower() and "sino" not in text.lower():
                flags.append((case_id, "number_system_unspecified"))
        if team == "13" and "instant" in (case_id + " " + text).lower():
            if "deny" in lower and "403" not in lower:
                flags.append((case_id, "missing_exact_403_regression"))
        if team == "14" and "same teacher role" in lower:
            flags.append((case_id, "role_equality_is_not_identity"))
        if team == "15":
            if "record" in (text + " " + expected).lower() and "consent" not in (text + " " + expected).lower():
                flags.append((case_id, "recording_without_consent_condition"))
            if "lesson content" in text.lower() and "access is denied" in lower:
                flags.append((case_id, "free_lesson_access_may_be_locked"))
    if team == "14" and artifact.get("items") and all(
        "reject" in str(x.get("expected", "")).lower() or
        "disallow" in str(x.get("expected", "")).lower() or
        "denies" in str(x.get("expected", "")).lower()
        for x in artifact["items"] if isinstance(x, dict)
    ):
        flags.append(("*", "missing_valid_referral_acceptance_case"))
    if team == "16":
        flags.append(("*", "localized_labels_need_exact_source_mapping"))
    return flags
