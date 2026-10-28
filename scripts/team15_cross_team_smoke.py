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
        # input validation: name must be a non-empty string and a relative path with no absolute or upwards traversal
        if not isinstance(name, str) or name.strip() == '':
            issues.append(f"{label}: invalid candidate filename (not a non-empty string): {repr(name)}")
            continue
        path_obj = Path(name)
        if path_obj.is_absolute() or '..' in path_obj.parts:
            issues.append(f"{label}: invalid candidate filename (absolute or parent traversal): {repr(name)}")
            continue
        # Compose full path and ensure it is normalized and within root
        path = root / team / path_obj
        try:
            resolved_path = path.resolve(strict=False)
        except RuntimeError:
            issues.append(f"{label}: invalid file path {path}")
            continue
        try:
            resolved_path.relative_to(root)
        except ValueError:
            issues.append(f"{label}: invalid file path outside of root {resolved_path}")
            continue
        try:
            if resolved_path.is_file():
                found.append(name)
        except (OSError, RuntimeError) as e:
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
    py_files = []
    try:
        resolved_folder = folder.resolve(strict=True)
        try:
            resolved_folder.relative_to(root)
        except ValueError:
            issues.append(f"{label}: invalid folder path outside of root {resolved_folder}")
            continue
    except FileNotFoundError as e:
        issues.append(f"{label}: folder does not exist {folder}: {e}")
        continue
    except RuntimeError:
        issues.append(f"{label}: invalid folder path {folder}")
        continue

    try:
        py_files = list(folder.glob("*.py"))
    except OSError as e:
        issues.append(f"{label}: error accessing folder {folder}: {e}")
        py_files = []

    pieces = []
    for p in py_files:
        try:
            resolved_file = p.resolve(strict=True)
            try:
                resolved_file.relative_to(root)
            except ValueError:
                issues.append(f"{label}: file path outside of root {resolved_file}")
                continue
        except (FileNotFoundError, RuntimeError):
            # File disappeared or invalid path; skip
            continue
        try:
            size = p.stat().st_size
        except OSError as e:
            issues.append(f"{label}: error accessing file size {p}: {e}")
            continue
        if size >= 2_000_000:
            # Skip very large files silently
            continue
        try:
            try:
                pieces.append(p.read_text(encoding="utf-8"))
            except UnicodeDecodeError:
                pieces.append(p.read_text(encoding="utf-8", errors="replace"))
        except OSError as e:
            issues.append(f"{label}: error reading file {p}: {e}")
    source = "\n".join(pieces)
    missing = [term for term in terms if term and not re.search(re.escape(term), source, re.I)]
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

# Defensive print to stdout only if JSON is valid and complete
try:
    output = json.dumps(result, ensure_ascii=False, indent=2)
except Exception as err:
    print(f"JSON serialization error: {err}", file=sys.stderr)
    sys.exit(1)
else:
    print(output)
    # Report failure with exit=1 if any issues found; else exit=0
    sys.exit(1 if issues else 0)
