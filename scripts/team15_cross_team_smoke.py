#!/usr/bin/env python3
"""Read-only cross-team integration evidence gate; never implies runtime E2E."""
import json
import re
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[2]
issues = []
evidence = {}
checks = {
    "11_auth": ("team11", ["phase3/common_contract.py", "phase3/server.py"], ["session", "booking"]),
    "12_learning": ("team12", ["phase3/content.json"], [""]),
    "13_room": ("team13", ["phase3/server.py"], ["booking", "room"]),
    "14_refund": ("team14", ["phase3/team14_monthly_sim.py"], ["refund", "event"]),
}
for label, (team, candidates, tokens) in checks.items():
    found = []
    for name in candidates:
        path = root / team / name
        if path.is_file():
            found.append(name)
    if not found:
        issues.append(f"{label}: no candidate source found")
    evidence[label] = {"files": found, "status": "source_present" if found else "missing"}
# Verify that expected key integration identifiers are represented in the actual
# source tree. This is an interface smoke gate, not a claim of executable wiring.
for label, team, terms in [
    ("11_to_13", "team13", ["booking", "session"]),
    ("13_to_14", "team14", ["refund", "booking"]),
]:
    folder = root / team / "phase3"
    source = "\n".join(p.read_text(encoding="utf-8", errors="replace")
                       for p in folder.glob("*.py") if p.stat().st_size < 2_000_000)
    missing = [term for term in terms if not re.search(re.escape(term), source, re.I)]
    evidence[label] = {"terms": terms, "missing": missing,
                       "status": "source_terms_present" if not missing else "missing"}
    if missing:
        issues.append(f"{label}: missing source terms {missing}")
result = {"gate": "source-interface-smoke-only", "runtime_integration_verified": False,
          "actual_two_person_av_verified": False, "live_payments_executed": False,
          "checks": evidence, "issues": issues}
print(json.dumps(result, ensure_ascii=False, indent=2))
sys.exit(1 if issues else 0)
