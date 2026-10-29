"""Bounded six-team candidate artifacts when no independently reviewed READY exists.

This does NOT promote READY or edit product files. One real model call per team
may create an isolated, schema-checked exploratory artifact for later team15 QA.
No production source, secrets, payment, deployment, or CI safety gate changes.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.request import Request, urlopen

TEAM_TASKS = {
    "11": (11, 3, "Create three precise clean/dirty/stale-checkout preflight cases, with expected blocking behavior."),
    "12": (45, 3, "Create three original beginner Korean quiz questions. Each expected field must include the correct answer and an educational explanation."),
    "13": (22, 3, "Create three booking-to-video authorization scenarios, including existing-booking instant-join denial and a legitimate participant case. No real room tokens."),
    "14": (101, 4, "Return exactly FOUR role-pair items with ids teacher_teacher, teacher_student, student_teacher, student_student (one each, no aliases, no extra IDs). For each item, use TWO DISTINCT PERSON IDENTITIES with the specified introducer and introduced roles. Expected must describe VALID ACCEPTANCE of a permitted non-self, non-cyclic mock referral, subject to existing role and authorization rules. Do NOT reject merely because both people have the same role. Separately explain that self-identity and cyclic introductions are REJECTED. No real payouts, no invented API behavior. These are candidate scenarios only; independent team15 QA must verify against source and tests."),
    "15": (151, 5, "Create five concrete independent user-journey QA cases covering learner, tutor, speaking partner, admin, and unauthorized visitor."),
    "16": (143, 8, "Create eight locale-specific UI label checks with ids ko,en,ja,es,zh,ru,mn,vi; include localized Learn/Watch/Speak labels in text."),
}
ROLE_IDS = {"teacher_teacher", "teacher_student", "student_teacher", "student_student"}
LOCALE_IDS = {"ko", "en", "ja", "es", "zh", "ru", "mn", "vi"}
ROOT = Path("experiments/hq-six-candidate-artifacts")


def validate_artifact(data, team):
    number, minimum, _ = TEAM_TASKS[team]
    if not isinstance(data, dict) or set(data) != {"team", "task_number", "items"}:
        raise ValueError("invalid artifact envelope")
    if data["team"] != team or data["task_number"] != number:
        raise ValueError("wrong owner or numbered contract")
    items = data["items"]
    if not isinstance(items, list) or not minimum <= len(items) <= 12:
        raise ValueError("invalid item count")
    ids = []
    for item in items:
        if not isinstance(item, dict) or set(item) != {"id", "text", "expected"}:
            raise ValueError("invalid case fields")
        for field in ("id", "text", "expected"):
            value = item[field]
            if not isinstance(value, str) or not value.strip() or len(value) > 1600:
                raise ValueError("invalid case value")
            if re.search(r"(?i)(api[_-]?key|bearer\s+|ghp_[a-z0-9]+)", value):
                raise ValueError("possible secret in generated content")
        if not re.fullmatch(r"[a-z][a-z0-9_]{1,45}", item["id"]):
            raise ValueError("invalid case id")
        ids.append(item["id"])
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate case id")
    if team == "14" and not ROLE_IDS.issubset(ids):
        raise ValueError("four referral roles missing")
    if team == "16" and set(ids) != LOCALE_IDS:
        raise ValueError("eight supported locales missing")
    return True


def shell(*args):
    return subprocess.run(args, text=True, capture_output=True, timeout=90)


def generated_python_cache(path):
    """Only untracked .pyc inside a __pycache__ directory may be discarded."""
    p = Path(path)
    return (not p.is_absolute() and ".." not in p.parts
            and "__pycache__" in p.parts and p.suffix == ".pyc")


def require_clean_checkout():
    status = shell("git", "status", "--porcelain", "-uall")
    if status.returncode:
        raise ValueError("git status unavailable")
    # Pre-call unit tests create untracked Python bytecode on older team
    # branches without .gitignore. Never remove tracked or arbitrary files.
    for line in status.stdout.splitlines():
        if line.startswith("?? ") and generated_python_cache(line[3:]):
            Path(line[3:]).unlink(missing_ok=True)
    again = shell("git", "status", "--porcelain", "-uall")
    if again.returncode or again.stdout.strip():
        names = [line[:2] + " " + Path(line[3:]).name
                 for line in again.stdout.splitlines()[:6]]
        raise ValueError("dirty checkout remains after safe cache cleanup: " + repr(names))


def main():
    team = os.environ.get("HQ_TEAM", "")
    if team not in TEAM_TASKS:
        raise ValueError("unknown team")
    if os.environ.get("GITHUB_REF_NAME") != "automation/hq-pilot-13-14-15-20261029":
        raise ValueError("not isolated pilot")
    branch = "automation/hq-team-" + team + "-autodev-20261029"
    current = shell("git", "branch", "--show-current")
    if current.returncode or current.stdout.strip() != branch:
        raise ValueError("team checkout mismatch")
    result_path = Path("/tmp/team-result.json")
    if not result_path.is_file():
        raise ValueError("missing trusted developer result")
    report = json.loads(result_path.read_text())
    if report.get("team") != team or report.get("calls") != 0:
        print("Candidate bootstrap skipped: developer already called model or result mismatch")
        return
    if any(t.get("status") == "committed" for t in report.get("tasks", [])):
        return
    require_clean_checkout()
    number, minimum, goal = TEAM_TASKS[team]
    path = ROOT / ("team" + team) / ("task" + str(number) + ".json")
    if path.exists():
        print("Existing candidate artifact; do not spend again")
        return
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        report["tasks"].append({"task_number": number, "status": "prototype_blocked", "reason": "missing API key"})
        result_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
        return
    body = {
        "model": "gpt-4.1-mini", "max_completion_tokens": 1700,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": (
                "You are an independent Korean-learning platform specialist. Return ONLY JSON "
                "with exactly team (string), task_number (integer), items (array). "
                "Each item has exactly id (lowercase snake_case), text (concrete original "
                "feature/content/test case), expected (specific correct outcome and rationale). "
                "No code execution, deployment, API calls, personal data, payment, secrets, "
                "For team 14, use exactly these four literal id strings: teacher_teacher, teacher_student, student_teacher, student_student. "
                "Do not change underscores or add prefixes. "
                "or claims of testing. These are experimental candidate artifacts, NOT "
                "approved production changes or a claim of backlog completion.")},
            {"role": "user", "content": json.dumps({
                "team": team, "backlog_number": number, "minimum_items": minimum,
                "goal": goal, "strict_role_ids": sorted(ROLE_IDS) if team == "14" else None,
                "strict_locale_ids": sorted(LOCALE_IDS) if team == "16" else None
            }, ensure_ascii=False)}
        ]
    }
    report["calls"] = 1  # Count the attempted real API request, not an invented success.
    try:
        request = Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(body, ensure_ascii=False).encode(),
            headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
        with urlopen(request, timeout=110) as response:
            response_body = json.load(response)
        raw = response_body["choices"][0]["message"]["content"]
        artifact = json.loads(raw)
        validate_artifact(artifact, team)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n")
        added = shell("git", "add", "--", str(path))
        committed = shell("git", "commit", "-m",
                          "bot(team" + team + "): exploratory task #" + str(number) + " candidate artifact")
        if added.returncode or committed.returncode:
            raise RuntimeError("candidate artifact commit failed")
        pushed = shell("git", "push", "origin", "HEAD:refs/heads/" + branch)
        if pushed.returncode:
            raise RuntimeError("candidate artifact push failed")
        sha = shell("git", "rev-parse", "HEAD").stdout.strip()
        report["tasks"].append({
            "task_number": number, "path": str(path), "status": "prototype_committed",
            "commit": sha, "source": "independent_model_candidate",
            "validation": "strict JSON schema and per-team item coverage",
            "next_instruction": "Independent team15 semantic QA and READY gate remain mandatory"})
        print("Candidate artifact committed: team", team, "task", number, "sha", sha)
    except Exception as exc:
        report["tasks"].append({"task_number": number, "status": "prototype_failed",
                                "reason": type(exc).__name__, "detail": str(exc)[:220]})
        print("Candidate artifact BLOCKED:", type(exc).__name__)
    finally:
        result_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--validate-file":
        team = sys.argv[2]
        validate_artifact(json.loads(Path(sys.argv[3]).read_text()), team)
        print("Candidate artifact schema PASS; semantic review still pending")
    else:
        main()
