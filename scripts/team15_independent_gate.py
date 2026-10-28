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
        failures.append(f"{team}: checkout missing or path not a directory")
        continue
    try:
        sha = subprocess.check_output(["git", "-C", str(directory), "rev-parse", "HEAD"], text=True, stderr=subprocess.PIPE).strip()
    except subprocess.CalledProcessError as e:
        failures.append(f"{team}: git rev-parse failed: {e}")
        continue
    except FileNotFoundError:
        failures.append(f"{team}: git command not found")
        continue
    print(f"{team} SHA={sha}")
    for path in paths:
        # Normalize path to prevent directory traversal
        try:
            normalized_path = Path(path)
        except Exception as e:
            failures.append(f"{team}: invalid path {path}: {e}")
            continue
        file_path = directory / normalized_path
        try:
            # Resolve to absolute and check within team's directory
            resolved_file_path = file_path.resolve(strict=False)
        except Exception as e:
            failures.append(f"{team}: path resolution error for {file_path}: {e}")
            continue
        if ROOT not in resolved_file_path.parents and resolved_file_path != ROOT:
            failures.append(f"{team}: file {path} escapes expected root directory")
            continue
        if not resolved_file_path.is_file():
            failures.append(f"{team}: missing file {path}")

    if team != "integration":
        # We cannot rely on the disabled git diff in original, skip
        try:
            tracked = subprocess.check_output(["git", "-C", str(directory), "ls-files"], text=True, stderr=subprocess.PIPE).splitlines()
        except subprocess.CalledProcessError as e:
            failures.append(f"{team}: git ls-files failed: {e}")
            tracked = []
        except FileNotFoundError:
            failures.append(f"{team}: git command not found")
            tracked = []

        changed_files = set()
        for p in tracked:
            # Defensive path normalization
            try:
                p_path = Path(p)
            except Exception as e:
                failures.append(f"{team}: invalid tracked path {p}: {e}")
                continue
            integration_file = ROOT / "integration" / p_path
            team_file = directory / p_path
            try:
                resolved_team_file = team_file.resolve(strict=False)
                resolved_integration_file = integration_file.resolve(strict=False)
            except Exception as e:
                failures.append(f"{team}: path resolution error for tracked files {team_file} or {integration_file}: {e}")
                changed_files.add(p)
                continue
            # Confirm both files are inside expected directories
            if ROOT not in resolved_team_file.parents and resolved_team_file != ROOT:
                failures.append(f"{team}: tracked file {p} escapes expected root directory")
                changed_files.add(p)
                continue
            if ROOT not in resolved_integration_file.parents and resolved_integration_file != ROOT:
                failures.append(f"{team}: integration file {p} escapes expected root directory")
                changed_files.add(p)
                continue
            if not resolved_team_file.is_file():
                # If tracked but no file, consider changed (possibly deleted)
                changed_files.add(p)
                continue
            if not resolved_integration_file.is_file():
                # File does not exist in integration, count as changed
                changed_files.add(p)
                continue
            try:
                team_bytes = resolved_team_file.read_bytes()
                integration_bytes = resolved_integration_file.read_bytes()
            except (OSError, IOError) as e:
                failures.append(f"{team}: error reading files {resolved_team_file} or {resolved_integration_file}: {e}")
                changed_files.add(p)
                continue
            if team_bytes != integration_bytes:
                changed_files.add(p)

        changes[team] = changed_files

# Check for overlaps across teams
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
