#!/usr/bin/env python3
"""Independent read-only source gate for separately checked-out team branches."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
EXPECT = {
    "integration": ["phase3/test_content.py", "phase3/test_instant_matching.py", "phase3/test_payments.py"],
    "team11": ["phase3/common_contract.py", "phase3/test_common_contract.py", "phase3/test_common_compatibility.py", "phase3/test_common_legacy_db.py"],
    "team12": ["scripts/team12_audio_inventory.py", "scripts/team12_audit_hangul_report.py"],
    "team13": ["phase3/test_instant_matching.py", "phase3/instant-browser-test.cjs"],
    "team14": ["phase3/team14_monthly_sim.py", "phase3/test_team14_monthly_sim.py", "phase3/test_team14_monthly_boundaries.py"],
}
failures = []
changes = {}
for team, paths in EXPECT.items():
    directory = ROOT / team
    if not directory.is_dir():
        failures.append(f"{team}: checkout missing")
        continue
    sha = subprocess.check_output(["git", "-C", str(directory), "rev-parse", "HEAD"], text=True).strip()
    print(f"{team} SHA={sha}")
    for path in paths:
        if not (directory / path).is_file():
            failures.append(f"{team}: missing {path}")
    if team != "integration":
        out = subprocess.check_output(["git", "-C", str(directory), "diff", "--name-only", "integration/phase2-phase3-20261027"], text=True, stderr=subprocess.DEVNULL) if False else None
        # Compare branch contents against the separately checked-out integration tree,
        # not local branch refs (which may be absent in shallow Actions checkouts).
        tracked = subprocess.check_output(["git", "-C", str(directory), "ls-files"], text=True).splitlines()
        changes[team] = {p for p in tracked if (ROOT / "integration" / p).is_file() and (directory / p).read_bytes() != (ROOT / "integration" / p).read_bytes()} | {p for p in tracked if not (ROOT / "integration" / p).exists()}
for left in changes:
    for right in changes:
        if left >= right:
            continue
        common = sorted(changes[left] & changes[right])
        if common:
            print(f"POTENTIAL OVERLAP {left}/{right}: {common}")
            failures.append(f"overlap {left}/{right}: {len(common)}")
if failures:
    print("FAIL:", *failures, sep="\n- ")
    sys.exit(1)
print("PASS: required test sources present; no cross-team changed-file overlap")
