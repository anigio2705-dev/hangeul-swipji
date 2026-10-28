#!/usr/bin/env python3
"""Four *separate* bounded, read-only AI calls to evaluate HQ work allocation.

Each GitHub Actions matrix job has its own prompt, context and output artifact.
No code edits, deployment, payment calls or automatic policy selection.
"""
import json
import os
from pathlib import Path
import sys
from urllib.request import Request, urlopen

ROLES = {
    "development": "Prioritize measurable working features, exclusive file ownership, integration and avoidance of repeated refactors.",
    "quality": "Prioritize independent regression, code evidence, CI success vs actual functionality, failure recovery and review gates.",
    "operations": "Prioritize branch isolation, workflow concurrency, safe deployments, external blockers and sustainable operations.",
    "cost": "Prioritize token cost, calls, measured validated tasks/hour, collision/rework cost and realistic 50x claims.",
}
MODEL = "gpt-4.1-mini"
REPO = "anigio2705-dev/hangeul-swipji"


def evidence():
    """Small, explicit baseline. No inference of task completion from a green job."""
    return {
        "backlog_total": 160, "final_completed": 0,
        "six_team_example": {"run_id": 40778383849, "job_count": 6,
                             "job_conclusions": "6 success; success is not a verified backlog completion",
                             "observed": "Bot commits exist on team 11-16 branches; file edits recur across rounds"},
        "focused_example": {"business_ci": 40782053380, "audio_ci": 40782148907,
                            "observation": "Focused isolated bug fixes with tests; CI may be pending"},
        "audio_inventory": {"cells": 399, "ready_unapproved": 19, "held": 26,
                            "missing": 354, "listening_approved": 0},
        "comparison_limits": "No controlled same-task A/B timing, rework or API billing baseline available.",
        "scope": "Only isolated branches. main, production DB, live payments and deployment forbidden.",
    }


def messages(role):
    if role not in ROLES:
        raise ValueError("invalid role")
    system = ("You are one independent review call. You cannot see other reviewers. "
              "Return a concise JSON object with keys choice, evidence, dissent, "
              "controlled_pilot, metrics_missing, confidence. Choose among six_parallel, "
              "four_roles_one_task, hybrid. Treat CI as partial evidence, not production completion. "
              "Do not assert 50x speedup or invent token costs, timestamps or independent experiments.")
    user = json.dumps({"reviewer": role, "priority": ROLES[role], "same_evidence": evidence(),
                       "evaluation": ["code-verified backlog items per hour", "functional completeness",
                                      "CI pass rate", "rework", "file conflicts", "API costs",
                                      "external approval waits"]}, ensure_ascii=False)
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def evaluate(role, key, opener=urlopen):
    payload = {"model": MODEL, "max_completion_tokens": 850,
               "response_format": {"type": "json_object"}, "messages": messages(role)}
    request = Request("https://api.openai.com/v1/chat/completions",
                      data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                      headers={"Authorization": "Bearer " + key,
                               "Content-Type": "application/json"})
    with opener(request, timeout=65) as response:
        result = json.load(response)
    review = json.loads(result["choices"][0]["message"]["content"])
    return {"role": role, "status": "independent_api_call_completed", "model": MODEL,
            "review": review, "usage_tokens": result.get("usage", {}),
            "cost_usd": "NOT_VERIFIED", "backlog_completed": 0}


def main():
    role = os.environ.get("HQ_REVIEW_ROLE", "")
    if role not in ROLES or os.environ.get("GITHUB_REF_NAME") != "automation/hq-pilot-13-14-15-20261029":
        raise SystemExit("invalid role or branch")
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        result = {"role": role, "status": "not_run_missing_api_key",
                  "note": "No independent AI evaluation occurred; do not count as a reviewer."}
    else:
        try:
            result = evaluate(role, key)
        except (OSError, ValueError, KeyError, IndexError) as exc:
            result = {"role": role, "status": "api_call_failed",
                      "error_type": type(exc).__name__, "note": "No review claim or retry."}
    out = Path("/tmp/hq-review-" + role + ".json")
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"role": role, "status": result["status"],
                      "usage_tokens": result.get("usage_tokens", {})}, ensure_ascii=False))


if __name__ == "__main__":
    main()
