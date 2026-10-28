"""Read-only HQ pilot decision engine. No tokens, network, or writes required."""
from dataclasses import dataclass
from typing import Mapping

TEAM_OWNERS = {
    "test_instant_matching.py": "13",
    "instant_matching.py": "13",
    "team14_initial_products.py": "14",
    "test_team14_d2_catalog_http.py": "13+14",
    "team14_recovery.py": "14",
    "team15": "15",
}
BLOCKED = {"failure", "cancelled", "timed_out", "action_required", "startup_failure"}

@dataclass(frozen=True)
class Decision:
    state: str
    next_action: str
    owner: str
    approval_required: bool = False

def decide(checks: Mapping[str, str], staging_verified: bool = False) -> Decision:
    """Only explicit successes pass; missing and pending evidence never passes."""
    required = ("team13", "team14", "cross_contract")
    for name in required:
        result = checks.get(name, "missing")
        if result in BLOCKED:
            owner = "13+14" if name == "cross_contract" else name.replace("team", "")
            return Decision("blocked", "Fix failed check, then rerun unchanged tests", owner)
        if result != "success":
            return Decision("waiting", "Wait for verified CI evidence", "15")
    if not staging_verified:
        return Decision("code_passed", "Request separate Render 99 verification; do not deploy", "11+15", True)
    return Decision("ready_for_review", "Request representative approval for D2 progression", "HQ", True)

def route_failure(log: str) -> str:
    if "booking_product_snapshots" in log or "CONTRACT_MISSING" in log:
        return "13+14"
    for token, owner in TEAM_OWNERS.items():
        if token in log:
            return owner
    return "15"
