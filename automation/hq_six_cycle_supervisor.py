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

from hq_160_task_cycle import CURATED_TARGETS, load_catalog

REPO = "anigio2705-dev/hangeul-swipji"
HQ_REF = "automation/hq-pilot-13-14-15-20261029"
WORKFLOW = "hq-six-developers.yml"
FOUR_REVIEW_RUN = 40782295178
REGRESSIONS = {
    "13": ["python", "-m", "unittest", "discover", "-s", "phase3", "-p", "test_instant_matching.py"],
    "14": ["python", "-m", "unittest", "discover", "-s", "phase3", "-p", "test_team14_referral_store.py"],
    "16": ["python", "scripts/render-audio-credits.py"],
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

def independent_check(team, task, token, catalog):
    number, path, sha = task.get("task_number"), task.get("path"), task.get("commit", "")
    if not isinstance(number, int) or (number, path) not in CURATED_TARGETS[team]:
        return "RETRY", "Commit lacks a valid assigned backlog number and owned path", {}
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
            command = REGRESSIONS.get(team)
            if not command:
                return "PROVISIONAL", "Syntax verified; independent functional regression not configured", {
                    "commit": sha, "changed_files": files, "syntax": "success"}
            checked = cmd(command, cwd=temp, timeout=180)
            if checked.returncode:
                return "RETRY", "Independent regression failed: " + (checked.stdout + checked.stderr)[-500:], {}
            if team == "16":
                rendered = Path(temp) / "hangul-audio-credits.html"
                manifest = Path(temp) / "hangul-audio-manifest.json"
                if not rendered.is_file() or not manifest.is_file():
                    return "RETRY", "Audio attribution renderer did not produce expected evidence", {}
                entries = json.loads(manifest.read_text(encoding="utf-8"))["recordings"]
                if rendered.read_text(encoding="utf-8").count("<tr>") != len(entries) + 1:
                    return "RETRY", "Audio attribution rows do not match manifest", {}
            return "TEST_PASS_PENDING_CI", "Independent diff and functional regression passed; final backlog gate remains", {
                "commit": sha, "changed_files": files, "independent_test": "success",
                "test_command": " ".join(command)}
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
                              (json.dumps(ledger, ensure_ascii=False, indent=2) + "\\n").encode()).decode()})
    return result.get("commit", {}).get("sha")

def promote_prior(ledger, token):
    promoted = []
    for number, record in ledger.items():
        if record.get("status") != "in_progress" or record.get("independent_review") != "pass":
            continue
        match = re.fullmatch(
            r"https://github\\.com/anigio2705-dev/hangeul-swipji/actions/runs/([0-9]+)",
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
    for team, result in teams.items():
        verdicts[team] = []
        for task in result["tasks"]:
            number = task.get("task_number")
            status = task.get("status")
            if status in ("committed", "verification_requested"):
                try:
                    verdict, reason, evidence = independent_check(team, task, token, catalog)
                except Exception as exc:
                    verdict, reason, evidence = "RETRY", "Independent verification error: " + type(exc).__name__, {}
                verdicts[team].append({"task_number": number, "verdict": verdict,
                                       "reason": reason, "evidence": evidence})
                if verdict == "TEST_PASS_PENDING_CI":
                    if ledger.get(str(number), {}).get("status") not in ("complete", "code_verified"):
                        ledger[str(number)] = {
                            "status": "in_progress", "commit": evidence["commit"],
                            "ci_url": "https://github.com/" + REPO + "/actions/runs/" + os.environ["GITHUB_RUN_ID"],
                            "ci_result": "pending", "independent_review": "pass",
                            "scope": "Independent source diff and functional regression passed; final CI run and public site still pending",
                            "owner": team, "path": task["path"]}
                        staged.append(number)
                    if status == "committed":
                        passed += 1
                elif verdict == "RETRY" and isinstance(number, int):
                    prev = next_repairs.setdefault(team, {}).get(str(number), {})
                    attempts = prev.get("attempts", 0) + 1
                    next_repairs[team][str(number)] = {
                        "attempts": attempts, "repair_instruction": reason[:1200]}
                    if attempts < 2:
                        repairable += 1
            elif status in ("blocked", "retry", "baseline_failed", "unavailable", "no_change"):
                verdicts[team].append({"task_number": number, "verdict": "BLOCKED",
                                       "reason": task.get("feedback", task.get("error", status))})
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
              "test_site_verified": False, "dispatched_next": False}
    # No progress and no precise fix -> do not repeat identical six-team calls.
    if depth < 2 and (passed > 0 or repairable > 0 or promoted or staged):
        try:
            api("/actions/workflows/" + WORKFLOW + "/dispatches", token, method="POST",
                payload={"ref": HQ_REF, "inputs": {
                    "chain_depth": str(depth + 1),
                    "repair_instructions_json": json.dumps(next_repairs, ensure_ascii=False)}})
            report["dispatched_next"] = True
            report["next_reason"] = ("independently tested code or prior CI promotion" if (passed or promoted or staged) else "specific bounded repair")
        except Exception as exc:
            report["next_reason"] = "DISPATCH_FAILED: " + type(exc).__name__
            report["dispatch_error"] = str(exc)[:240]
    else:
        report["next_reason"] = "STOP: no independently tested progress or bounded depth reached"
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
