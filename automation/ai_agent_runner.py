"""Run a real authenticated Codex CLI worker against a leased queue item.

Requires an always-on host, durable SQLite path, installed Codex CLI and
OPENAI_API_KEY. This module never runs from the hourly ChatGPT automation.
It does not deploy, merge, approve QA or touch production.
"""
import json
import os
import subprocess
import time
from pathlib import Path

from work_request_worker import DurableWorkStore


def run_once(store, *, workdir, agent_command=("codex", "exec"), timeout=2400):
    claim = store.claim("central-ai", lease_seconds=3600)
    if claim is None:
        return {"status": "IDLE"}
    issue, owner = claim["issue"], claim["owner"]
    if not os.environ.get("OPENAI_API_KEY"):
        store.fail(issue, owner)
        return {"status": "BLOCKED_AUTH", "issue": issue}
    prompt = (
        "You are central developer for Hangeul Swipji. Work only on an isolated "
        "branch; never modify main, production databases, payments or deployments. "
        f"Work request GitHub issue #{issue}: {claim['title']}. "
        "Inspect the 160-item ledger and Issue #34. Implement only the authorized "
        "task, run relevant tests, commit on isolated branch, and report exact SHA "
        "and CI/QA pending. Do not self-approve READY or QA."
    )
    try:
        result = subprocess.run([*agent_command, prompt], cwd=workdir,
                                capture_output=True, text=True, timeout=timeout,
                                check=False)
        if result.returncode:
            store.fail(issue, owner)
            return {"status": "AGENT_FAILED", "issue": issue,
                    "exit_code": result.returncode}
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=workdir,
                             capture_output=True, text=True, check=True).stdout.strip()
        branch = subprocess.run(["git", "branch", "--show-current"], cwd=workdir,
                                capture_output=True, text=True, check=True).stdout.strip()
        if not branch or branch in {"main", "master"}:
            store.fail(issue, owner)
            return {"status": "UNSAFE_BRANCH", "issue": issue}
        proof = f"issue={issue} branch={branch} sha={sha} agent=codex"
        if not store.finish(issue, owner, proof):
            return {"status": "LEASE_LOST", "issue": issue}
        return {"status": "REPORTED_QA_PENDING", "issue": issue, "proof": proof}
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError):
        store.fail(issue, owner)
        return {"status": "AGENT_ERROR", "issue": issue}


def main():
    path = os.environ["HS_DURABLE_WORKER_DB"]
    workdir = Path(os.environ["HS_WORKTREE"]).resolve()
    if not path.startswith("/") or path.startswith(("/tmp/", "/home/runner/")):
        raise RuntimeError("persistent worker database required")
    if not workdir.is_dir() or not (workdir / ".git").exists():
        raise RuntimeError("isolated git worktree required")
    with_store = DurableWorkStore(path)
    try:
        while True:
            print(json.dumps(run_once(with_store, workdir=str(workdir)), flush=True))
            time.sleep(5)
    finally:
        with_store.close()


if __name__ == "__main__":
    main()
