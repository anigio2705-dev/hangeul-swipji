"""Run a real authenticated Codex CLI worker against a leased queue item.

Requires an always-on host, durable SQLite path, installed Codex CLI and
OPENAI_API_KEY. This module never runs from the hourly ChatGPT automation.
It does not deploy, merge, approve QA or touch production.
"""
import json
import os
import re
import signal
import subprocess
import time
from pathlib import Path

from work_request_worker import DurableWorkStore



def _run_with_lease(command, *, cwd, store, issue, owner, timeout,
                    heartbeat_interval=5, env=None):
    """Keep the exact fencing token live while a subprocess is running.

    Reconciliation/lease loss aborts the process group, including child tools.
    A completed subprocess is NOT authorization for READY or a new task.
    """
    if heartbeat_interval <= 0:
        raise ValueError("heartbeat interval must be positive")
    if not store.heartbeat(issue, owner, lease_seconds=3600):
        return None
    process = subprocess.Popen(command, cwd=cwd, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True,
                               start_new_session=True, env=env)
    started = time.monotonic()
    try:
        while True:
            remaining = timeout - (time.monotonic() - started)
            if remaining <= 0:
                raise subprocess.TimeoutExpired(command, timeout)
            try:
                stdout, stderr = process.communicate(
                    timeout=min(heartbeat_interval, remaining))
                if not store.heartbeat(issue, owner, lease_seconds=3600):
                    return None
                return subprocess.CompletedProcess(command, process.returncode,
                                                   stdout, stderr)
            except subprocess.TimeoutExpired:
                if not store.heartbeat(issue, owner, lease_seconds=3600):
                    return None
    finally:
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.communicate()


def run_once(store, *, workdir, agent_command=("codex", "exec", "--full-auto"),
             timeout=2400, heartbeat_interval=5):
    before = subprocess.run(["git", "branch", "--show-current"], cwd=workdir,
                            capture_output=True, text=True, check=True).stdout.strip()
    # No protected, user-facing, or unscoped branch may be written by the agent.
    if (not re.fullmatch(r"(?:work|automation|agent)/[A-Za-z0-9][A-Za-z0-9._/-]{0,100}", before)
            or ".." in before or "//" in before or before.endswith(("/", "."))):
        return {"status": "UNSAFE_BRANCH"}
    remote = subprocess.run(["git", "remote", "get-url", "origin"], cwd=workdir,
                            capture_output=True, text=True, check=True).stdout.strip()
    expected = os.environ.get("GITHUB_REPOSITORY", "anigio2705-dev/hangeul-swipji")
    allowed_remotes = {f"https://github.com/{expected}", f"https://github.com/{expected}.git",
                       f"git@github.com:{expected}", f"git@github.com:{expected}.git"}
    if remote not in allowed_remotes:
        return {"status": "UNSAFE_REMOTE"}
    if subprocess.run(["git", "status", "--porcelain"], cwd=workdir,
                      capture_output=True, text=True, check=True).stdout.strip():
        return {"status": "DIRTY_WORKTREE"}
    previous_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=workdir,
                                  capture_output=True, text=True, check=True).stdout.strip()
    claim = store.claim("central-ai", lease_seconds=3600)
    if claim is None:
        return {"status": "IDLE"}
    issue, owner = claim["issue"], claim["owner"]
    if timeout <= 0 or timeout >= 3600 or heartbeat_interval <= 0:
        store.fail(issue, owner)
        return {"status": "UNSAFE_TIMEOUT", "issue": issue}
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
        # The coding agent must not inherit GitHub write credentials. The
        # controller alone performs the separately fenced push.
        agent_env = os.environ.copy()
        for secret in ("GH_TOKEN", "GITHUB_TOKEN", "GIT_ASKPASS",
                       "SSH_ASKPASS", "SSH_AUTH_SOCK"):
            agent_env.pop(secret, None)
        result = _run_with_lease(
            [*agent_command, prompt], cwd=workdir, store=store,
            issue=issue, owner=owner, timeout=timeout,
            heartbeat_interval=heartbeat_interval, env=agent_env)
        if result is None:
            return {"status": "LEASE_LOST", "issue": issue}
        if result.returncode:
            store.fail(issue, owner)
            return {"status": "AGENT_FAILED", "issue": issue,
                    "exit_code": result.returncode}
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=workdir,
                             capture_output=True, text=True, check=True).stdout.strip()
        branch = subprocess.run(["git", "branch", "--show-current"], cwd=workdir,
                                capture_output=True, text=True, check=True).stdout.strip()
        if not branch or branch != before or branch in {"main", "master"}:
            store.fail(issue, owner)
            return {"status": "UNSAFE_BRANCH", "issue": issue}
        if sha == previous_sha:
            store.fail(issue, owner)
            return {"status": "NO_COMMIT", "issue": issue}
        if subprocess.run(["git", "status", "--porcelain"], cwd=workdir,
                          capture_output=True, text=True, check=True).stdout.strip():
            store.fail(issue, owner)
            return {"status": "UNCOMMITTED_CHANGES", "issue": issue}
        ancestry = subprocess.run(["git", "merge-base", "--is-ancestor", previous_sha, sha],
                                  cwd=workdir, capture_output=True, text=True, check=False)
        if ancestry.returncode:
            store.fail(issue, owner)
            return {"status": "NON_FAST_FORWARD", "issue": issue}
        # Revalidate the remote after the agent: it may have changed config.
        remote_after = subprocess.run(
            ["git", "remote", "get-url", "origin"], cwd=workdir,
            capture_output=True, text=True, check=True).stdout.strip()
        if remote_after not in allowed_remotes:
            store.fail(issue, owner)
            return {"status": "UNSAFE_REMOTE", "issue": issue}
        # Monitor the push itself; a lost lease must kill its process group.
        # GitHub cannot guarantee rollback of a push already accepted before
        # cancellation, so downstream delivery still needs idempotency.
        try:
            pushed = _run_with_lease(
                ["git", "push", "origin", f"HEAD:refs/heads/{branch}"],
                cwd=workdir, store=store, issue=issue, owner=owner,
                timeout=120, heartbeat_interval=heartbeat_interval)
            if pushed is None:
                return {"status": "LEASE_LOST", "issue": issue}
            if pushed.returncode:
                store.fail(issue, owner)
                return {"status": "PUSH_FAILED", "issue": issue}
            advertised = subprocess.run(
                ["git", "ls-remote", "origin", f"refs/heads/{branch}"],
                cwd=workdir, capture_output=True, text=True, check=True,
                timeout=60).stdout.strip()
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
            store.fail(issue, owner)
            return {"status": "PUSH_FAILED", "issue": issue}
        if advertised.split() != [sha, f"refs/heads/{branch}"]:
            store.fail(issue, owner)
            return {"status": "REMOTE_SHA_MISMATCH", "issue": issue}
        proof = f"issue={issue} branch={branch} remote_sha={sha} agent=codex QA_PENDING"
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
            print(json.dumps(run_once(with_store, workdir=str(workdir))), flush=True)
            time.sleep(5)
    finally:
        with_store.close()


if __name__ == "__main__":
    main()
