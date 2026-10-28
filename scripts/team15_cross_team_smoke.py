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
        try:
            # Ensure path is within root directory to avoid unexpected issues
            path.resolve(strict=False)
        except RuntimeError:
            issues.append(f"{label}: invalid file path {path}")
            continue
        try:
            if path.is_file():
                found.append(name)
        except OSError as e:
            issues.append(f"{label}: error accessing file {path}: {e}")
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
    try:
        folder.resolve(strict=True)
    except FileNotFoundError as e:
        issues.append(f"{label}: folder does not exist {folder}: {e}")
        py_files = []
    except RuntimeError:
        issues.append(f"{label}: invalid folder path {folder}")
        py_files = []
    else:
        try:
            py_files = list(folder.glob("*.py"))
        except OSError as e:
            issues.append(f"{label}: error accessing folder {folder}: {e}")
            py_files = []
    pieces = []
    for p in py_files:
        try:
            if p.stat().st_size < 2_000_000:
                # Read text with strict UTF-8 decoding; fallback silently if error
                try:
                    pieces.append(p.read_text(encoding="utf-8"))
                except UnicodeDecodeError:
                    pieces.append(p.read_text(encoding="utf-8", errors="replace"))
        except OSError as e:
            issues.append(f"{label}: error reading file {p}: {e}")
    source = "\n".join(pieces)
    missing = [term for term in terms if not re.search(re.escape(term), source, re.I)]
    evidence[label] = {"terms": terms, "missing": missing,
                       "status": "source_terms_present" if not missing else "missing"}
    if missing:
        issues.append(f"{label}: missing source terms {missing}")

result = {
    "gate": "source-interface-smoke-only",
    "runtime_integration_verified": False,
    "actual_two_person_av_verified": False,
    "live_payments_executed": False,
    "checks": evidence,
    "issues": issues
}

print(json.dumps(result, ensure_ascii=False, indent=2))
sys.exit(1 if issues else 0)
