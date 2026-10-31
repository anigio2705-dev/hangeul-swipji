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
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from work_request_worker import DurableWorkStore




class DeliveryBlocked(RuntimeError):
    """Fail closed: remote side effects may have happened; do not blindly retry."""


def _github_json(url, token, payload=None):
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        url, data=body, headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        }, method="POST" if body is not None else "GET")
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.load(response)


def ensure_draft_pr(*, repo, branch, base, sha, token):
    """Idempotent draft PR handoff; never replay an ambiguous GitHub POST.

    PR creation is only a request for CI/independent QA, not QA_PASS/READY.
    A caller must supply a separate, least-privilege controller token.
    """
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise DeliveryBlocked("invalid repository")
    if not re.fullmatch(r"[A-Za-z0-9._/-]+", branch) or not branch.startswith(
            ("work/", "automation/", "agent/")):
        raise DeliveryBlocked("invalid isolated head")
    if not re.fullmatch(r"[A-Za-z0-9._/-]+", base) or base in {"main", "master"}:
        raise DeliveryBlocked("use an isolated PR base, not main")
    if not re.fullmatch(r"[0-9a-f]{40}", sha) or not token:
        raise DeliveryBlocked("missing verified SHA or controller credential")
    api = f"https://api.github.com/repos/{repo}/pulls"
    owner = repo.split("/", 1)[0]
    query = urllib.parse.urlencode({
        "state": "open", "head": f"{owner}:{branch}", "base": base,
        "per_page": 100})

    def existing():
        rows = _github_json(api + "?" + query, token)
        matches = [p for p in rows
                   if p.get("head", {}).get("ref") == branch
                   and p.get("base", {}).get("ref") == base]
        if len(matches) > 1:
            raise DeliveryBlocked("duplicate PRs require manual reconciliation")
        if not matches:
            return None
        pr = matches[0]
        if pr.get("head", {}).get("sha") != sha or not pr.get("draft"):
            raise DeliveryBlocked("existing PR SHA/draft mismatch")
        return pr["number"]

    try:
        found = existing()
        if found is not None:
            return found
        try:
            created = _github_json(api, token, {
                "title": f"Draft: AI work on {branch}",
                "head": branch, "base": base, "draft": True,
                "body": (f"Automated isolated candidate; exact SHA {sha}. "
                         "CI and independent 15-team QA pending. "
                         "No auto-merge, no READY, no production changes.")})
        except urllib.error.HTTPError as exc:
            # 503/429/403/422 may be ambiguous. Reconcile by GET exactly once;
            # do NOT replay POST when GitHub may already have created a PR.
            if exc.code not in (403, 422, 429, 500, 502, 503, 504):
                raise DeliveryBlocked(f"PR POST HTTP {exc.code}") from exc
            found = existing()
            if found is not None:
                return found
            raise DeliveryBlocked(f"ambiguous PR POST HTTP {exc.code}") from exc
        if (created.get("head", {}).get("sha") != sha
                or not created.get("draft")
                or created.get("base", {}).get("ref") != base):
            raise DeliveryBlocked("new PR SHA/draft/base mismatch")
        return created["number"]
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError,
            TypeError) as exc:
        raise DeliveryBlocked("GitHub PR API unavailable or malformed") from exc


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



def _origin_remote_status(workdir, allowed_remotes):
    """Reject Git URL rewrites and multi-push destinations before any push.

    Git's --push --all resolves pushInsteadOf and all configured pushurl
    values. A single trusted fetch URL is insufficient authorization.
    """
    def resolved_urls(*args):
        proc = subprocess.run(["git", "remote", "get-url", *args, "origin"],
                              cwd=workdir, capture_output=True, text=True,
                              check=False)
        if proc.returncode:
            return []
        return [url.strip() for url in proc.stdout.splitlines() if url.strip()]

    fetch_urls = resolved_urls("--all")
    if len(fetch_urls) != 1 or fetch_urls[0] not in allowed_remotes:
        return "UNSAFE_REMOTE"
    push_urls = resolved_urls("--push", "--all")
    if (len(push_urls) != 1 or push_urls[0] not in allowed_remotes
            or push_urls[0] != fetch_urls[0]):
        return "UNSAFE_PUSH_REMOTE"
    return None



def _controller_git_env():
    """Never give an agent-influenced Git subprocess controller credentials.

    The Git transport has no need for the Codex key or GitHub API bearer token.
    A dedicated least-privilege credential broker is required for authenticated
    pushes; credentials must not be present in an agent-controlled Git process.
    """
    env = os.environ.copy()
    for key in list(env):
        # Remove all Git/SSH overrides, including GIT_DIR and Git executables.
        if (key.startswith(("GIT_", "SSH_"))
                or key in {"GH_TOKEN", "GITHUB_TOKEN", "OPENAI_API_KEY"}):
            env.pop(key, None)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    return env


def _unsafe_git_execution_config(workdir):
    """Fail closed on Git configuration capable of launching agent code.

    Agent-owned .git/config and includeIf files must never be allowed to select
    SSH commands, credential helpers, upload/receive-pack, or hooks in a
    controller process. These checks supplement (not replace) OS isolation.
    """
    forbidden = (
        "core.sshcommand", "credential.helper", "core.hookspath",
        "core.fsmonitor", "remote.origin.receivepack",
        "remote.origin.uploadpack",
    )
    env = _controller_git_env()
    for key in forbidden:
        proc = subprocess.run(["git", "config", "--get-all", key],
                              cwd=workdir, capture_output=True, text=True,
                              check=False, env=env)
        if proc.returncode not in (0, 1):
            return "UNSAFE_GIT_CONFIG"
        if proc.returncode == 0 and proc.stdout.strip():
            return "UNSAFE_GIT_CONFIG"
    return None


def _trusted_push_destination(repo):
    """Controller-selected fixed destination; never agent-owned origin config."""
    return f"https://github.com/{repo}.git"


def _push_from_trusted_repo(*, workdir, branch, sha, repo, store, issue,
                            owner, heartbeat_interval):
    """Transport through a new bare Git database, not the agent's .git.

    Defense in depth against pushurl TOCTOU. The same-UID temporary repository
    is not a substitute for OS-separated controller credentials or a broker.
    """
    trusted_url = _trusted_push_destination(repo)
    # P0 crash-fencing quarantine: the local SQLite lock cannot revoke an
    # orphaned Git transport after SIGKILL. No real GitHub push is authorized
    # until a separately supervised, credential-owning OS broker with remote
    # cancellation reconciliation has passed independent B QA.
    # Local bare-remotes remain available for isolated regression tests.
    if trusted_url.startswith(("https://github.com/", "git@github.com:")):
        return "PUSH_BROKER_REQUIRED"
    env = _controller_git_env()
    with tempfile.TemporaryDirectory(prefix="hs-controller-transport-") as tmp:
        subprocess.run(["git", "init", "--bare", "-q", tmp], check=True,
                       capture_output=True, text=True, env=env)
        subprocess.run(["git", "fetch", "--no-tags", "--no-recurse-submodules",
                        str(Path(workdir).resolve()), branch], cwd=tmp,
                       check=True, capture_output=True, text=True, env=env)
        fetched = subprocess.run(["git", "rev-parse", "FETCH_HEAD"], cwd=tmp,
                                 check=True, capture_output=True, text=True,
                                 env=env).stdout.strip()
        if fetched != sha:
            return "SOURCE_SHA_CHANGED"
        # Preserve failure on a removed origin; this does not select a remote.
        configured = subprocess.run(["git", "remote"], cwd=workdir,
                                    capture_output=True, text=True, env=env,
                                    check=True).stdout.splitlines()
        if "origin" not in configured:
            return "PUSH_FAILED"
        # A heartbeat followed by Popen has a revocation TOCTOU window.
        # Serialize the entire bounded remote write with durable cancellation
        # using the same SQLite write fence as reconcile_open/claim/finish.
        # This guarantees no write AFTER cancellation commits; a concurrent
        # cancellation request waits for an in-flight push to finish.
        pushed = store.fenced_remote_write(
            issue, owner,
            lambda: subprocess.run(
                ["git", "push", "--no-verify", trusted_url,
                 f"{sha}:refs/heads/{branch}"],
                cwd=tmp, capture_output=True, text=True, check=False,
                timeout=120, env=env),
            minimum_seconds=150)
        if pushed is None:
            return "LEASE_LOST"
        if pushed.returncode:
            return "PUSH_FAILED"
        advertised = subprocess.run(
            ["git", "ls-remote", trusted_url, f"refs/heads/{branch}"],
            cwd=tmp, capture_output=True, text=True, check=True,
            timeout=60, env=env).stdout.strip()
        if advertised.split() != [sha, f"refs/heads/{branch}"]:
            return "REMOTE_SHA_MISMATCH"
    return None


def run_once(store, *, workdir, agent_command=("codex", "exec", "--full-auto"),
             timeout=2400, heartbeat_interval=5):
    # Before even reading status, reject untrusted executable Git settings.
    # In particular fsmonitor may run while querying a dirty worktree.
    config_status = _unsafe_git_execution_config(workdir)
    if config_status:
        return {"status": config_status}
    before = subprocess.run(["git", "branch", "--show-current"], cwd=workdir,
                            capture_output=True, text=True, check=True).stdout.strip()
    # No protected, user-facing, or unscoped branch may be written by the agent.
    if (not re.fullmatch(r"(?:work|automation|agent)/[A-Za-z0-9][A-Za-z0-9._/-]{0,100}", before)
            or ".." in before or "//" in before or before.endswith(("/", "."))):
        return {"status": "UNSAFE_BRANCH"}
    expected = os.environ.get("GITHUB_REPOSITORY", "anigio2705-dev/hangeul-swipji")
    allowed_remotes = {f"https://github.com/{expected}", f"https://github.com/{expected}.git",
                       f"git@github.com:{expected}", f"git@github.com:{expected}.git"}
    remote_status = _origin_remote_status(workdir, allowed_remotes)
    if remote_status:
        return {"status": remote_status}
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
        # The agent may rewrite local Git config after initial validation.
        # Refuse all further Git operations if executable settings appeared.
        config_status = _unsafe_git_execution_config(workdir)
        if config_status:
            store.fail(issue, owner)
            return {"status": config_status, "issue": issue}
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
        # The agent may change remote.origin.pushurl or url.*.pushInsteadOf
        # after the initial check. Re-resolve all effective destinations.
        remote_status = _origin_remote_status(workdir, allowed_remotes)
        if remote_status:
            store.fail(issue, owner)
            return {"status": remote_status, "issue": issue}
        # Never consult agent-owned Git config for the actual transport.
        try:
            push_status = _push_from_trusted_repo(
                workdir=workdir, branch=branch, sha=sha, repo=expected,
                store=store, issue=issue, owner=owner,
                heartbeat_interval=heartbeat_interval)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired,
                OSError):
            push_status = "PUSH_FAILED"
        if push_status:
            if push_status != "LEASE_LOST":
                store.fail(issue, owner)
            return {"status": push_status, "issue": issue}
        # Optional strict PR gate for a real always-on controller. Without it
        # the queue records a push-only candidate, NEVER completed delivery.
        pr_number = None
        if os.environ.get("HS_REQUIRE_DRAFT_PR") == "1":
            token = os.environ.get("GH_TOKEN", "")
            if not token:
                store.fail(issue, owner)
                return {"status": "BLOCKED_GITHUB_AUTH", "issue": issue}
            try:
                pr_number = ensure_draft_pr(
                    repo=expected, branch=branch,
                    base=os.environ.get("HS_PR_BASE", "automation/event-driven-ready-gate-20261031"),
                    sha=sha, token=token)
            except DeliveryBlocked:
                store.fail(issue, owner)
                return {"status": "PR_DELIVERY_BLOCKED", "issue": issue}
            if not store.heartbeat(issue, owner, lease_seconds=3600):
                return {"status": "LEASE_LOST", "issue": issue}
        proof = f"issue={issue} branch={branch} remote_sha={sha} agent=codex QA_PENDING"
        if pr_number is not None:
            proof += f" draft_pr={pr_number} CI_PENDING"
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
