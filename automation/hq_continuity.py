"""Bounded, resumable HQ validation worker; no production writes or API charges."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time

BRANCH = "automation/hq-pilot-13-14-15-20261029"
TASKS = [
    ("queue", ["python", "-m", "unittest", "automation.test_backlog_queue", "-v"]),
    ("hq", ["python", "-m", "unittest", "automation.test_hq_pilot", "-v"]),
    ("sandbox", ["python", "-m", "unittest", "discover", "-s", "automation/worker_sandbox", "-p", "test_*.py", "-v"]),
]
def run_cycle(tasks=TASKS, runner=subprocess.run):
    results = []
    for name, command in tasks:
        try:
            p = runner(command, capture_output=True, text=True, timeout=180)
            results.append({"task": name, "status": "passed" if p.returncode == 0 else "failed",
                            "exit_code": p.returncode, "output_tail": (p.stdout + p.stderr)[-2000:]})
        except subprocess.TimeoutExpired:
            results.append({"task": name, "status": "timeout", "exit_code": None})
    return results

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-seconds", type=int, default=3000)
    parser.add_argument("--cycles", type=int, default=1)
    args = parser.parse_args()
    if os.environ.get("GITHUB_REF_NAME") != BRANCH:
        raise SystemExit("Isolated branch only")
    if not (1 <= args.max_seconds <= 3300 and 1 <= args.cycles <= 100):
        raise SystemExit("Invalid bounded execution limits")
    started = time.monotonic()
    output = []
    # Never idle or repeat green checks merely to consume time.
    for cycle in range(args.cycles):
        if time.monotonic() - started > args.max_seconds - 200:
            break
        results = run_cycle()
        output.append({"cycle": cycle + 1, "checks": results})
        if all(r["status"] == "passed" for r in results):
            break
        # A failing check needs a separate authorized code repair, not an infinite rerun.
        break
    Path("automation/continuity-result.json").write_text(
        json.dumps({"cycles": output, "elapsed_seconds": round(time.monotonic()-started, 2),
                    "note": "Validation only; no autonomous production feature edits"}, ensure_ascii=False, indent=2))
    if any(r["status"] != "passed" for item in output for r in item["checks"]):
        raise SystemExit("Validation failed; evidence saved")

if __name__ == "__main__":
    main()
