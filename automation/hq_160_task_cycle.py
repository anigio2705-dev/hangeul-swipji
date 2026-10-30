"""Executable, evidence-gated contracts for the canonical 160-item backlog.

One primary team owns each numbered item. Supporting teams can submit scoped
work, but neither AI output nor a green CI alone grants final completion.
"""
import hashlib
import json
import re
from pathlib import Path

ITEM = re.compile(r"^(\d{1,3})\. \[([ xX])\] (.+)$", re.MULTILINE)
TEAM_OWNERS = (
    (1, 10, "15", ("11",)), (11, 20, "11", ("15",)),
    (21, 30, "13", ("15",)), (31, 40, "11", ("13",)),
    (41, 50, "12", ("13",)), (51, 60, "12", ("11", "15", "16")),
    (61, 70, "12", ("16",)), (71, 80, "14", ("13",)),
    (81, 90, "13", ("14",)), (91, 100, "13", ("14", "15")),
    (101, 120, "14", ("15",)), (121, 130, "14", ("11", "15")),
    (131, 140, "11", ("13", "15")), (141, 150, "16", ("13", "15")),
    (151, 160, "15", ("11", "12", "13", "14", "16")),
)
# A gate is an actual external, browser, legal, or representative check; never
# allow an AI to replace it with an assertion.
EXTERNAL_GATES = frozenset({
    13, 14, 15, 16, 17, 18, 20, 23, 24, 25, 26, 27, 29, 30,
    55, 56, 57, 58, 60, 69, 70, 107, 121, 126, 130, 136,
    146, 150, 151, 152, 154, 155,
})
APPROVAL_GATES = frozenset({6, 14, 15, 26, 60, 70, 91, 107, 130, 150, 152, 154, 155})
# Explicit blocking dependencies, not a global serial barrier.
DEPENDENCIES = {
    15: (12, 13, 14), 16: (15,), 20: (16, 17, 18, 19),
    26: (22, 23, 24, 25), 30: (25, 26, 27, 29),
    57: (51, 52, 54, 55, 56), 58: (57,),
    110: (101, 102, 103, 104), 115: (111, 112, 114),
    130: (107, 121, 122, 124, 125, 126, 127, 128, 129),
    154: (131, 132, 133, 134, 135, 136, 137, 138, 139, 140, 151, 152, 153),
}
# Exclusive file ownership, with real backlog item numbers rather than generic
# "hardening" requests. Team 11/16 support some education-owned items.
CURATED_TARGETS = {
    # No legacy curated assignments for 11: #51/#56 are owned by team 12.
    # Team 11 may still develop independently reviewed READY items it owns.
    "11": (),
    "12": ((41, "scripts/team12_content_regression.py"),
           (52, "scripts/team12_audio_inventory.py"),
           # #49 concerns free diagnostic recommendations, implemented in
           # phase3/learning.py; unlike the rejected #47 placement mapping.
           (49, "phase3/learning.py")),
    # #47 concerns free-course progress/resume, not placement in learning.py.
    # The former team13 mapping was rejected; do not dispatch it again.
    "13": ((22, "phase3/instant_matching.py"),),
    "14": ((109, "phase3/team14_referral_store.py"),
           (115, "phase3/team14_refund_workflow.py")),
    "15": ((8, "scripts/team15_independent_gate.py"),
           (151, "scripts/team15_cross_team_smoke.py")),
    # #55 audio attribution belongs to team 12; 16 is support only.
    # Dynamic READY tasks owned by 16 remain eligible through the registry.
    "16": (),
}
STATES = frozenset({"unverified", "in_progress", "blocked", "retry", "code_verified", "complete"})

# Trusted HQ mapping: CANDIDATE/BLOCKED contracts are not dispatchable even if
# an old or incomplete evidence snapshot accidentally labels them unverified.
# Only the HQ-owned contract can change this; an AI team patch cannot.
def _semantic_dispatch_gate(number, path, failures=None):
    """Never dispatch from historical curated IDs alone.

    A previous implementation allowed missing registry entries and even
    CANDIDATE/BLOCKED repair instructions to bypass the independent READY
    gate. Those IDs are retained only for legacy tests and reporting.
    """
    return False


def contracts(backlog_text):
    matches = [(int(n), flag.lower() == "x", title.strip())
               for n, flag, title in ITEM.findall(backlog_text)]
    if [number for number, _, _ in matches] != list(range(1, 161)):
        raise ValueError("Master backlog must contain exactly 160 ordered, unique items")
    result = {}
    for number, checked, criterion in matches:
        if not criterion:
            raise ValueError("Empty acceptance criterion: " + str(number))
        owner, helpers = next((owner, helpers) for lo, hi, owner, helpers
                              in TEAM_OWNERS if lo <= number <= hi)
        result[number] = {
            "number": number, "criterion": criterion,
            "owner": owner, "support": list(helpers),
            "dependencies": list(DEPENDENCIES.get(number, ())),
            "external_gate": number in EXTERNAL_GATES,
            "approval_gate": number in APPROVAL_GATES,
            "master_checked": checked,
            "evidence_required": [
                "actual_changed_file_and_commit", "independent_test_result",
                "successful_relevant_CI", "backlog_specific_review",
            ] + (["real_world_evidence"] if number in EXTERNAL_GATES else [])
              + (["representative_approval"] if number in APPROVAL_GATES else []),
        }
    return result

def load_catalog(backlog_path):
    return contracts(Path(backlog_path).read_text(encoding="utf-8"))

def _reviewed_ready_assignment(team, catalog, evidence, failures, registry=None, root=None):
    """Dispatch a new *independently reviewed* READY item, not only curated IDs.

    hq_traffic_lights.readiness is the single conservative path/owner/dependency/
    collision gate. This is static eligibility; the runner must still verify the
    live CI conclusion, exact SHA and task-specific regression before accepting
    any developer patch. No automatic READY promotion occurs here.
    """
    from hq_traffic_lights import readiness

    if registry is None:
        file = Path(__file__).with_name("hq_semantic_contract_paths.json")
        if not file.is_file():
            return None  # fail closed; never guess a contract
        registry = json.loads(file.read_text(encoding="utf-8"))
    base = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    queue = readiness(catalog, evidence, registry, base)["dispatchable"]
    for candidate in queue:
        number = candidate["task"]
        task = catalog[number]
        # Only the canonical owner may develop a new READY item; support teams
        # can review but must not independently produce duplicate patches.
        if candidate["owner"] != team or task["owner"] != team:
            continue
        state = evidence.get(str(number), {}).get("status", "unverified")
        if state not in STATES:
            raise ValueError("Invalid task state")
        if state not in ("unverified", "retry"):
            continue  # no duplicate AI calls for pending CI or verified work
        source_paths = candidate["source_paths"]
        # Read-only source context may span files, but the developer may edit
        # exactly one explicitly reviewed file. Never infer a target from order.
        editable = candidate.get("editable_path")
        if editable is None:
            if len(source_paths) != 1:
                continue
            editable = source_paths[0]
        if editable not in source_paths:
            continue
        retry = failures.get(str(number), {})
        attempts = retry.get("attempts", 0)
        if not isinstance(attempts, int) or attempts < 0:
            raise ValueError("Invalid retry count")
        if attempts >= 2:
            continue
        instruction = retry.get("repair_instruction", "")
        if not isinstance(instruction, str) or len(instruction) > 1200:
            raise ValueError("Invalid repair instruction")
        return {
            "team": team, "task_number": number, "path": editable,
            "owner": task["owner"], "support": task["support"],
            "acceptance_criterion": task["criterion"],
            "required_evidence": task["evidence_required"],
            "attempt": attempts + 1,
            "repair_instruction": instruction,
            "mode": "repair" if instruction else "develop",
            "source": "independently_reviewed_READY_registry",
            "independent_test_paths": registry["items"][str(number)]["test_paths"],
        }
    return None


def next_assignment(team, catalog, evidence=None, failures=None, registry=None, root=None):
    """Skip already code-verified work and repeat failures; keep tasks isolated."""
    if team not in CURATED_TARGETS:
        raise ValueError("Unknown team")
    evidence, failures = evidence or {}, failures or {}
    reviewed = _reviewed_ready_assignment(team, catalog, evidence, failures, registry, root)
    if reviewed is not None:
        return reviewed
    for number, path in CURATED_TARGETS[team]:
        if not _semantic_dispatch_gate(number, path, failures):
            continue
        task = catalog[number]
        if team != task["owner"] and team not in task["support"]:
            raise ValueError("Team has no authority for item " + str(number))
        state = evidence.get(str(number), {}).get("status", "unverified")
        if state not in STATES:
            raise ValueError("Invalid task state")
        if state in ("code_verified", "complete", "blocked"):
            continue
        # A separately reviewed commit is awaiting its own CI; do not spend
        # another AI call rewriting it while that exact verification is pending.
        if state == "in_progress" and evidence.get(str(number), {}).get("independent_review") == "pass":
            # A previous review using the WRONG task regression (e.g. #47
            # learning.py checked with matching tests) is not a valid gate.
            # Re-queue that exact item for task-specific verification; keep
            # correctly verified, CI-pending items out of the AI queue.
            if evidence[str(number)].get("task_specific_verified") is not False:
                continue
        if any(evidence.get(str(dep), {}).get("status") != "complete"
               for dep in task["dependencies"]):
            continue
        retry = failures.get(str(number), {})
        attempts = retry.get("attempts", 0)
        if not isinstance(attempts, int) or attempts < 0:
            raise ValueError("Invalid retry count")
        if attempts >= 2:
            continue
        instruction = retry.get("repair_instruction", "")
        if instruction and (not isinstance(instruction, str) or len(instruction) > 1200):
            raise ValueError("Invalid repair instruction")
        return {
            "team": team, "task_number": number, "path": path,
            "owner": task["owner"], "support": task["support"],
            "acceptance_criterion": task["criterion"],
            "required_evidence": task["evidence_required"],
            "attempt": attempts + 1,
            "repair_instruction": instruction,
            "mode": ("repair" if instruction else "verify_existing"
                     if state == "in_progress" and evidence.get(str(number), {}).get("task_specific_verified") is False
                     else "develop"),
        }
    return None

def verify_submission(assignment, submission, trusted):
    """Trusted evidence must come from independent CI/GitHub inspection.

    The developer's own 'passed' flag is intentionally ignored.
    """
    number, path = assignment["task_number"], assignment["path"]
    sha = submission.get("commit", "")
    if not isinstance(sha, str) or not re.fullmatch(r"[a-f0-9]{40}", sha):
        return {"number": number, "verdict": "RETRY", "repair_instruction": "Submit actual 40-character commit SHA."}
    if trusted.get("branch_head") != sha:
        return {"number": number, "verdict": "RETRY", "repair_instruction": "Commit is not verified at isolated branch HEAD; fetch and reconcile."}
    if trusted.get("changed_files") != [path]:
        return {"number": number, "verdict": "RETRY", "repair_instruction": "Limit change to assigned file; independently inspect git diff."}
    if trusted.get("independent_test") != "success":
        return {"number": number, "verdict": "RETRY", "repair_instruction": "Fix independent regression failure: " + str(trusted.get("test_error", "unknown"))[:400]}
    if trusted.get("ci_conclusion") != "success" or trusted.get("ci_head_sha") != sha:
        return {"number": number, "verdict": "RETRY", "repair_instruction": "Obtain successful relevant CI whose verified head SHA matches this exact commit; do not reuse older green runs."}
    if not trusted.get("ci_url", "").startswith("https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/"):
        return {"number": number, "verdict": "RETRY", "repair_instruction": "Supply verified GitHub Actions run URL."}
    return {"number": number, "verdict": "CODE_VERIFIED",
            "note": "Requires separate backlog review and external/approval gates before final completion.",
            "commit": sha, "ci_url": trusted["ci_url"]}

def make_report(backlog_text, evidence=None, failures=None):
    catalog = contracts(backlog_text)
    evidence, failures = evidence or {}, failures or {}
    def is_final(number):
        record = evidence.get(str(number), {})
        task = catalog[number]
        return (record.get("status") == "complete"
                and task["master_checked"]
                and isinstance(record.get("commit"), str)
                and bool(re.fullmatch(r"[a-f0-9]{40}", record["commit"]))
                and record.get("ci_conclusion") == "success"
                and record.get("independent_review") == "pass"
                and bool(re.fullmatch(
                    r"https://github\.com/anigio2705-dev/hangeul-swipji/actions/runs/[0-9]+",
                    record.get("ci_url", "")))
                and (not task["external_gate"] or bool(record.get("external_evidence")))
                and (not task["approval_gate"] or bool(record.get("approval_evidence"))))
    return {
        "schema": 1,
        "backlog_sha256": hashlib.sha256(backlog_text.encode()).hexdigest(),
        "total": 160,
        "final_complete": sum(bool(is_final(n)) for n in catalog),
        "assignments": {team: next_assignment(team, catalog, evidence, failures)
                        for team in CURATED_TARGETS},
        "contracts": list(catalog.values()),
        "warning": "An assignment or successful code check is not a finished public feature.",
    }

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--backlog", required=True)
    parser.add_argument("--evidence")
    parser.add_argument("--failures")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    evidence = json.loads(Path(args.evidence).read_text()) if args.evidence else {}
    failures = json.loads(Path(args.failures).read_text()) if args.failures else {}
    report = make_report(Path(args.backlog).read_text(encoding="utf-8"), evidence, failures)
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"final_complete": report["final_complete"], "assignments": report["assignments"]}, ensure_ascii=False))

if __name__ == "__main__":
    main()
