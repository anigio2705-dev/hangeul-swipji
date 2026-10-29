"""Independent six-team cycle gate: real commits, tests, repair and bounded dispatch.

Never counts controller WAIT cycles as development, and never marks a final
backlog item complete. Only the approved HQ isolation ref may dispatch.
"""
import base64
import io
import json
import os
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen, build_opener, HTTPRedirectHandler

from hq_160_task_cycle import CURATED_TARGETS, load_catalog, next_assignment

REPO = "anigio2705-dev/hangeul-swipji"
HQ_REF = "automation/hq-pilot-13-14-15-20261029"
WORKFLOW = "hq-six-developers.yml"
FOUR_REVIEW_RUN = 40782295178
# Only known, concrete patch-format failures qualify for one additional
# AI attempt. Unknown failures stop rather than endlessly dispatching teams.
PATCH_REPAIR_HINTS = {
    "Patch must make one unambiguous real change":
        "The previous old text did not occur exactly once, or old == new. "
        "Copy an exact unique 12-2400 character substring from the provided source "
        "and replace it with a genuinely different, meaningful 12-3200 character fix.",
    "Patch too small or large":
        "Your old text must be 12-2400 characters and new text 12-3200 characters. "
        "Select one focused, unique source fragment; do not return the entire file.",
    "New imports are forbidden":
        "Do not add imports; implement a focused fix using existing imports.",
    "Regression or unexpected changes":
        "Preserve existing tests and all other files; fix the precise regression "
        "shown in the developer feedback before proposing another patch.",
}
REGRESSIONS = {
    ("12", 41): ["python", "scripts/team12_content_regression.py"],
    ("12", 49): ["python", "-m", "unittest", "discover", "-s", "phase3", "-p", "test_global_learning.py"],
    ("13", 22): ["python", "-m", "unittest", "discover", "-s", "phase3", "-p", "test_instant_matching.py"],
    ("14", 109): ["python", "-m", "unittest", "discover", "-s", "phase3", "-p", "test_team14_referral_store.py"],
    ("16", 55): ["python", "scripts/render-audio-credits.py"],
}

def api(path, token, method="GET", payload=None, raw=False):
    body = None if payload is None else json.dumps(payload).encode()
    req = Request("https://api.github.com/repos/" + REPO + path, data=body,
                  method=method, headers={
                      "Authorization": "Bearer " + token,
                      "Accept": "application/vnd.github+json",
                      "Content-Type": "application/json",
                      "User-Agent": "hq-six-cycle-gate"})
    if raw:
        class NoRedirect(HTTPRedirectHandler):
            def redirect_request(self, request, fp, code, msg, headers, newurl):
                return None
        try:
            with build_opener(NoRedirect()).open(req, timeout=35) as response:
                return response.read()
        except HTTPError as exc:
            if exc.code not in (302, 303) or not exc.headers.get("Location"):
                raise
            location = exc.headers["Location"]
            host = urlsplit(location).hostname or ""
            if urlsplit(location).scheme != "https" or not (
                host.endswith(".githubusercontent.com") or
                host.endswith(".blob.core.windows.net")
            ):
                raise ValueError("Untrusted artifact redirect")
            # Signed artifact URL must never receive the GitHub token.
            with urlopen(Request(location, headers={"User-Agent": "hq-six-cycle-gate"}), timeout=35) as response:
                return response.read()
    with urlopen(req, timeout=35) as response:
        data = response.read()
        return json.loads(data) if data else {}

def cmd(args, cwd=None, timeout=120):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout)

def load_team_results(root):
    result = {}
    for team in CURATED_TARGETS:
        file = Path(root) / ("team-" + team + "-development") / "team-result.json"
        if not file.exists():
            result[team] = {"team": team, "tasks": [], "missing_artifact": True}
            continue
        record = json.loads(file.read_text(encoding="utf-8"))
        if record.get("team") != team or not isinstance(record.get("tasks"), list):
            raise ValueError("Invalid team result artifact " + team)
        result[team] = record
    return result

def independent_check(team, task, token, catalog, ledger=None, registry=None, root=None):
    """Accept only curated or independently reviewed READY task/file contracts.

    A developer's assignment_source flag is untrusted: the HQ-owned registry
    must independently resolve the same owner, number, editable file and tests.
    """
    number, path, sha = task.get("task_number"), task.get("path"), task.get("commit", "")
    if team not in CURATED_TARGETS or not isinstance(number, int) or number not in catalog:
        return "RETRY", "Commit lacks a valid assigned backlog number and owned path", {}
    reviewed_tests = []
    if (number, path) not in CURATED_TARGETS[team]:
        if task.get("assignment_source") != "reviewed_READY":
            return "RETRY", "Commit lacks a valid assigned backlog number and owned path", {}
        assignment = next_assignment(team, catalog, ledger or {}, {},
                                     registry=registry, root=root)
        if (not assignment or assignment.get("source") != "independently_reviewed_READY_registry"
                or assignment.get("task_number") != number or assignment.get("path") != path):
            return "RETRY", "Unreviewed or mismatched READY task/file contract", {}
        reviewed_tests = assignment.get("independent_test_paths", [])
        if (not reviewed_tests or not all(
                isinstance(p, str) and p.endswith(".py")
                and Path(p).name.startswith("test_")
                and ".." not in Path(p).parts and not Path(p).is_absolute()
                for p in reviewed_tests)):
            return "RETRY", "READY requires independently reviewed Python unittest paths", {}
    if not isinstance(sha, str) or not re.fullmatch(r"[a-f0-9]{40}", sha):
        return "RETRY", "Missing valid commit SHA", {}
    contract = catalog[number]
    if team != contract["owner"] and team not in contract["support"]:
        return "RETRY", "Team is not assigned to this numbered item", {}
    branch = "automation/hq-team-" + team + "-autodev-20261029"
    head = api("/branches/" + branch, token)["commit"]["sha"]
    if head != sha:
        return "RETRY", "Reported commit is not current isolated team branch HEAD", {"head": head}
    commit = api("/commits/" + sha, token)
    files = [x["filename"] for x in commit.get("files", [])]
    if files != [path]:
        return "RETRY", "Independent GitHub diff does not match assigned file: " + str(files)[:300], {}
    if "task #" + str(number) not in commit["commit"]["message"]:
        return "RETRY", "Commit message does not identify assigned backlog item", {}
    with tempfile.TemporaryDirectory(prefix="hq-team-verify-") as temp:
        fetched = cmd(["git", "fetch", "--depth=1", "origin", sha], timeout=80)
        if fetched.returncode:
            return "RETRY", "Cannot fetch committed code for independent testing", {}
        added = cmd(["git", "worktree", "add", "--detach", temp, sha], timeout=80)
        if added.returncode:
            return "RETRY", "Cannot independently check out committed code", {}
        try:
            syntax = cmd(["python", "-m", "py_compile", path], cwd=temp)
            if syntax.returncode:
                return "RETRY", "Independent syntax check failed: " + syntax.stderr[-350:], {}
            command = REGRESSIONS.get((team, number))
            commands = ([command] if command else [
                ["python", "-m", "unittest", "discover", "-s", str(Path(p).parent),
                 "-p", Path(p).name] for p in reviewed_tests])
            if not commands:
                return "PROVISIONAL", "Syntax verified; independent functional regression not configured", {
                    "commit": sha, "changed_files": files, "syntax": "success"}
            for check_command in commands:
                checked = cmd(check_command, cwd=temp, timeout=180)
                output = checked.stdout + checked.stderr
                if checked.returncode or ("Ran 0 tests" in output or "Ran 0 test " in output):
                    return "RETRY", "Independent regression failed or ran zero tests: " + output[-500:], {}
            if (team, number) == ("12", 41):
                # The AI may edit its own regression file. Run an immutable HQ
                # verifier OUTSIDE the candidate worktree as an independent gate.
                trusted_check = cmd(
                    ["python", str(Path(__file__).resolve().parent / "verify_task41.py"), temp],
                    cwd=temp, timeout=120)
                if trusted_check.returncode:
                    return "RETRY", "Trusted #41 source audit failed: " + (
                        trusted_check.stdout + trusted_check.stderr)[-500:], {}
            if (team, number) == ("12", 49):
                trusted_check = cmd(
                    ["python", str(Path(__file__).resolve().parent / "verify_task49.py"), temp],
                    cwd=temp, timeout=120)
                if trusted_check.returncode:
                    return "RETRY", "Trusted #49 recommendation semantics failed: " + (
                        trusted_check.stdout + trusted_check.stderr)[-500:], {}
            if (team, number) == ("16", 55):
                rendered = Path(temp) / "hangul-audio-credits.html"
                manifest = Path(temp) / "hangul-audio-manifest.json"
                if not rendered.is_file() or not manifest.is_file():
                    return "RETRY", "Audio attribution renderer did not produce expected evidence", {}
                entries = json.loads(manifest.read_text(encoding="utf-8"))["recordings"]
                if rendered.read_text(encoding="utf-8").count("<tr>") != len(entries) + 1:
                    return "RETRY", "Audio attribution rows do not match manifest", {}
            return "TEST_PASS_PENDING_CI", "Independent diff and functional regression passed; final backlog gate remains", {
                "commit": sha, "changed_files": files, "independent_test": "success",
                "test_command": " && ".join(" ".join(c) for c in commands) + (
                    " + trusted automation/verify_task41.py" if (team, number) == ("12", 41) else
                    " + trusted automation/verify_task49.py" if (team, number) == ("12", 49) else "")}
        finally:
            cmd(["git", "worktree", "remove", "--force", temp], timeout=45)

def four_role_evidence(token):
    """Read original four independent reviewer ZIP artifacts, not a summary."""
    roles = {}
    try:
        listing = api("/actions/runs/" + str(FOUR_REVIEW_RUN) + "/artifacts", token)
        for artifact in listing.get("artifacts", []):
            name = artifact.get("name", "")
            if not name.startswith("hq-independent-review-") or artifact.get("expired"):
                continue
            role = name.removeprefix("hq-independent-review-")
            if role not in ("development", "quality", "operations", "cost"):
                continue
            raw = api("/actions/artifacts/" + str(artifact["id"]) + "/zip", token, raw=True)
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                names = [n for n in archive.namelist() if n.endswith(".json")]
                if not names:
                    continue
                payload = json.loads(archive.read(names[0]))
                roles[role] = payload
    except Exception as exc:
        return {"status": "unavailable", "error_type": type(exc).__name__, "roles_read": list(roles)}
    if set(roles) != {"development", "quality", "operations", "cost"}:
        return {"status": "partial", "roles_read": list(roles)}
    # Conservative hybrid: use parallelism only for non-overlapping files;
    # a single writer and independent verifier for every risky item.
    return {"status": "read_four_independent_artifacts", "roles_read": list(roles),
            "opinions": roles, "provisional_choice": "hybrid_nonoverlap_plus_independent_gate"}

def load_ledger(token):
    data = api("/contents/automation/task-evidence.json?ref=" + HQ_REF.replace("/", "%2F"), token)
    raw = base64.b64decode(data["content"])
    return json.loads(raw), data["sha"]

def save_ledger(token, ledger, blob_sha, changed):
    if not changed:
        return None
    result = api("/contents/automation/task-evidence.json", token, method="PUT",
                 payload={"branch": HQ_REF, "sha": blob_sha,
                          "message": "chore(hq): preserve independent numbered code verification evidence",
                          "content": base64.b64encode(
                              (json.dumps(ledger, ensure_ascii=False, indent=2) + "\n").encode()).decode()})
    return result.get("commit", {}).get("sha")

def promote_prior(ledger, token):
    promoted = []
    for number, record in ledger.items():
        if (record.get("status") != "in_progress"
                or record.get("independent_review") != "pass"
                or record.get("task_specific_verified") is not True):
            # An unrelated green test (e.g. matching tests for learning.py)
            # must never promote a numbered task to code_verified.
            continue
        match = re.fullmatch(
            r"https://github\.com/anigio2705-dev/hangeul-swipji/actions/runs/([0-9]+)",
            record.get("ci_url", ""))
        if not match:
            continue
        run = api("/actions/runs/" + match.group(1), token)
        if run.get("status") != "completed":
            continue
        if run.get("conclusion") == "success":
            record["status"] = "code_verified"
            record["ci_result"] = "success"
            promoted.append(int(number))
        elif run.get("conclusion") in ("failure", "cancelled", "timed_out"):
            record["status"] = "unverified"
            record["ci_result"] = run["conclusion"]
            record["independent_review"] = "CI_failed_after_local_test"
    return promoted

def supervise(root, token, depth, repairs, output):
    if os.environ.get("GITHUB_REF_NAME") != HQ_REF:
        raise RuntimeError("Supervisor restricted to approved isolated branch")
    if not (0 <= depth <= 2) or not isinstance(repairs, dict):
        raise ValueError("Unsafe dispatch budget")
    catalog = load_catalog("automation/hq_backlog_160.md")
    ledger, ledger_sha = load_ledger(token)
    original_ledger = json.dumps(ledger, sort_keys=True)
    promoted = promote_prior(ledger, token)
    teams = load_team_results(root)
    verdicts, next_repairs = {}, json.loads(json.dumps(repairs))
    passed, repairable, staged = 0, 0, []
    progress_teams, repair_teams = set(), set()
    for team, result in teams.items():
        verdicts[team] = []
        for task in result["tasks"]:
            number = task.get("task_number")
            status = task.get("status")
            if status in ("committed", "verification_requested"):
                try:
                    verdict, reason, evidence = independent_check(team, task, token, catalog, ledger=ledger)
                except Exception as exc:
                    verdict, reason, evidence = "RETRY", "Independent verification error: " + type(exc).__name__, {}
                verdicts[team].append({"task_number": number, "verdict": verdict,
                                       "reason": reason, "evidence": evidence})
                if verdict == "TEST_PASS_PENDING_CI":
                    previous = ledger.get(str(number), {})
                    # A previously reviewed SHA is not new development, even
                    # if a developer artifact is replayed in another workflow.
                    # Do not dispatch more AI work or count it twice.
                    new_commit = (
                        previous.get("status") not in ("complete", "code_verified")
                        and previous.get("commit") != evidence["commit"]
                    )
                    if new_commit:
                        ledger[str(number)] = {
                            "status": "in_progress", "commit": evidence["commit"],
                            "ci_url": "https://github.com/" + REPO + "/actions/runs/" + os.environ["GITHUB_RUN_ID"],
                            "ci_result": "pending", "independent_review": "pass",
                            "task_specific_verified": True,
                            "test_command": evidence["test_command"],
                            "scope": "Independent source diff and task-specific functional regression passed; final CI run and public site still pending",
                            "owner": team, "path": task["path"]}
                        staged.append(number)
                    if new_commit:
                        # A newly verified pre-existing candidate also unlocks
                        # the next safe item, but is NOT a new code commit in
                        # this workflow (avoid inflating throughput).
                        progress_teams.add(team)
                        if status == "committed":
                            passed += 1
                elif verdict == "RETRY" and isinstance(number, int):
                    # A previously submitted test-file commit that fails its
                    # own regression needs diagnosis, not an AI rewriting the
                    # failing test to green. No blind repair dispatch.
                    if status == "verification_requested" and task.get("path", "").startswith("scripts/team12_content_regression"):
                        verdicts[team][-1]["verdict"] = "BLOCKED"
                        verdicts[team][-1]["reason"] = (
                            "Existing #41 candidate regression failed; inspect full test log "
                            "and fix the actual assertion/source mismatch before redispatch.")
                        continue
                    prev = next_repairs.setdefault(team, {}).get(str(number), {})
                    attempts = prev.get("attempts", 0) + 1
                    next_repairs[team][str(number)] = {
                        "attempts": attempts, "repair_instruction": reason[:1200]}
                    if attempts < 2:
                        repairable += 1
                        repair_teams.add(team)
            elif status in ("blocked", "retry", "baseline_failed", "unavailable", "no_change"):
                detail = str(task.get("feedback", task.get("error", status)))[:700]
                hint = next((guidance for error, guidance in PATCH_REPAIR_HINTS.items()
                             if error in detail), None)
                # A failed AI patch is not a verified change. One *different*,
                # specifically instructed repair is permitted, then stop.
                allowed = (status in ("blocked", "retry") and hint is not None
                           and isinstance(number, int)
                           and (number, task.get("path")) in CURATED_TARGETS[team])
                previous = next_repairs.get(team, {}).get(str(number), {}) if allowed else {}
                attempts = previous.get("attempts", 0) if isinstance(previous, dict) else 2
                if allowed and isinstance(attempts, int) and 0 <= attempts < 1:
                    next_repairs.setdefault(team, {})[str(number)] = {
                        "attempts": attempts + 1,
                        "repair_instruction": (hint + " Previous failure: " + detail)[:1200],
                    }
                    repairable += 1
                    repair_teams.add(team)
                    verdicts[team].append({"task_number": number, "verdict": "RETRY",
                                           "reason": hint})
                else:
                    verdicts[team].append({"task_number": number, "verdict": "BLOCKED",
                                           "reason": detail})
                    # A deterministic patch/regression failure after its one
                    # permitted repair must persist across hourly invocations.
                    # Otherwise every new workflow forgets the failure and
                    # spends API budget on the same rejected backlog number.
                    exhausted = (
                        status in ("blocked", "retry")
                        and hint is not None and isinstance(number, int)
                        and (number, task.get("path")) in CURATED_TARGETS[team]
                        and isinstance(attempts, int) and attempts >= 1
                    )
                    if exhausted and ledger.get(str(number), {}).get("status") not in ("complete", "code_verified", "blocked"):
                        ledger[str(number)] = {
                            "status": "blocked", "owner": team,
                            "path": task["path"], "block_reason": detail,
                            "repair_attempts": attempts,
                            "scope": "Exhausted deterministic repair; requires distinct root-cause fix before retry"
                        }
                        # A newly blocked item releases the team to its next
                        # independent safe assignment, not the same failed item.
                        progress_teams.add(team)
            elif status in ("already_verified_or_blocked", "dependency_blocked", "awaiting_independent_verification"):
                verdicts[team].append({"task_number": number, "verdict": "WAIT",
                                       "reason": status})
    ledger_commit = save_ledger(token, ledger, ledger_sha,
                                json.dumps(ledger, sort_keys=True) != original_ledger)
    review = four_role_evidence(token)
    report = {"schema": 1, "depth": depth, "team_verdicts": verdicts,
              "verified_new_functional_code": passed, "repairable": repairable,
              "staged_pending_CI": staged, "promoted_code_verified": promoted,
              "evidence_commit": ledger_commit,
              "independent_review": review,
              "completed_160": "not established; never inferred from CI",
              "code_verified_count": sum(record.get("status") == "code_verified" for record in ledger.values()),
              "team_runner_elapsed_seconds": {
                  team: result.get("team_runner_elapsed_seconds") for team, result in teams.items()},
              "manual_site_review_seconds": None,
              "representative_review_seconds": None,
              "time_measurement_note": "Runner elapsed time is measured; site/manual review is separate and not yet measured.",
              "test_site_verified": False, "dispatched_next": False}
    # Dispatch only teams with an actual safe next assignment. This prevents
    # six repeated AI calls after a team has no remaining eligible work.
    for number in promoted:
        owner = ledger.get(str(number), {}).get("owner")
        if owner in CURATED_TARGETS:
            progress_teams.add(owner)
    candidates = sorted(progress_teams | repair_teams)
    eligible = [team for team in candidates
                if next_assignment(team, catalog, ledger, next_repairs.get(team, {})) is not None]
    report["dispatched_teams"] = []
    if depth < 2 and eligible:
        try:
            api("/actions/workflows/" + WORKFLOW + "/dispatches", token, method="POST",
                payload={"ref": HQ_REF, "inputs": {
                    "chain_depth": str(depth + 1),
                    "repair_instructions_json": json.dumps(next_repairs, ensure_ascii=False),
                    "teams_json": json.dumps(eligible)}})
            report["dispatched_next"] = True
            report["dispatched_teams"] = eligible
            report["next_reason"] = ("targeted bounded repair" if repair_teams else
                                     "next safe backlog assignment after independent verification")
        except Exception as exc:
            report["next_reason"] = "DISPATCH_FAILED: " + type(exc).__name__
            report["dispatch_error"] = str(exc)[:240]
    else:
        report["next_reason"] = ("STOP: bounded depth reached" if depth >= 2 else
                                 "STOP: no safe new assignment or actionable one-time repair")
    Path(output).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "independent_review"}, ensure_ascii=False))
    return report

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--depth", type=int, default=0)
    parser.add_argument("--repairs", default="{}")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    supervise(args.root, os.environ["GITHUB_TOKEN"], args.depth,
              json.loads(args.repairs), args.output)
