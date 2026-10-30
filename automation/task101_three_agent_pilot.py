#!/usr/bin/env python3
"""Bounded, read-only Task #101 real-model handoff experiment.

Each role runs in a distinct GitHub Actions job and makes ONE authenticated
model API call. This never edits source, dispatches READY, merges or deploys.
A missing key, invalid prior artifact, malformed model output, or API failure
fails closed. The artifact is evidence of a call, NOT team15/HQ2 approval.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen

PRODUCT_SHA = "13f87f5410028e9e606904b901b036df6da0a1e6"
MODEL = "gpt-4.1-mini"
ROLES = ("11", "14", "15")
KEYS = {"consumed_handoff_id", "hypothesis", "challenge", "next_experiment", "evidence_boundary"}


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def validate_prior(path, team, run_id, workflow_sha):
    expected = {"14": "11", "15": "14"}[team]
    item = json.loads(Path(path).read_text(encoding="utf-8"))
    digest = item.pop("handoff_id", None)
    if (item.get("team") != expected or item.get("run_id") != run_id
            or item.get("workflow_sha") != workflow_sha
            or item.get("product_sha") != PRODUCT_SHA
            or not isinstance(digest, str)
            or hashlib.sha256(canonical(item)).hexdigest() != digest
            or not str(item.get("api_response_id", "")).startswith("chatcmpl-")):
        raise ValueError("Prior artifact failed provenance or handoff integrity")
    item["handoff_id"] = digest
    return item


def model_call(team, previous, key):
    previous_id = previous["handoff_id"] if previous else ""
    context = {
        "task": 101, "product_sha": PRODUCT_SHA,
        "observed": "Four teacher/learner referral directions pass targeted CI; "
                    "historical inviter role revocation must not block normal booking. "
                    "Root index.html preservation CI remains failing; READY=0.",
        "prior_handoff_id": previous_id,
        "prior_analysis": previous["analysis"] if previous else None,
    }
    roles = {
        "11": "Security/infrastructure reviewer. Identify one falsifiable source/CI trust-boundary risk.",
        "14": "Business product owner. Challenge the previous security hypothesis and independently choose a policy acceptance experiment.",
        "15": "Independent quality critic. Challenge the business owner's conclusion with a concrete counterexample and a distinct falsifying experiment. Never approve READY.",
    }
    payload = {
        "model": MODEL,
        "temperature": 0.2,
        "max_completion_tokens": 320,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": roles[team] +
             " Respond ONLY with a JSON object containing strings: consumed_handoff_id, hypothesis, challenge, next_experiment, evidence_boundary. "
             "Do not claim any code/CI/API evidence you did not actually execute."},
            {"role": "user", "content": json.dumps(context, ensure_ascii=False) +
             "\nEcho consumed_handoff_id EXACTLY. Select a falsifiable experiment of your own, not a preselected answer."},
        ],
    }
    req = Request("https://api.openai.com/v1/chat/completions",
                  data=json.dumps(payload).encode(),
                  headers={"Authorization": "Bearer " + key,
                           "Content-Type": "application/json"},
                  method="POST")
    with urlopen(req, timeout=65) as response:
        result = json.load(response)
    if not str(result.get("id", "")).startswith("chatcmpl-"):
        raise ValueError("No verifiable model response ID")
    usage = result.get("usage") or {}
    if not (usage.get("prompt_tokens", 0) > 0 and usage.get("completion_tokens", 0) > 0):
        raise ValueError("Missing actual API token usage")
    answer = json.loads(result["choices"][0]["message"]["content"])
    if (set(answer) != KEYS or any(not isinstance(v, str) for v in answer.values())
            or answer["consumed_handoff_id"] != previous_id
            or any(not answer[k].strip() for k in KEYS - {"consumed_handoff_id"})):
        raise ValueError("Model did not consume the exact prior handoff")
    if previous and answer["next_experiment"].strip() == previous["analysis"]["next_experiment"].strip():
        raise ValueError("Repeated prior experiment instead of choosing a distinct hypothesis")
    return result["id"], usage, answer


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--team", required=True, choices=ROLES)
    parser.add_argument("--prior")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if (args.team == "11") != (args.prior is None):
        raise ValueError("Only team11 starts without a prior artifact")
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        raise RuntimeError("MISSING_API_KEY: no model calls were made")
    run_id, workflow_sha = os.environ["GITHUB_RUN_ID"], os.environ["GITHUB_SHA"]
    previous = validate_prior(args.prior, args.team, run_id, workflow_sha) if args.prior else None
    response_id, usage, answer = model_call(args.team, previous, key)
    record = {
        "schema": 1, "task_id": 101, "team": args.team,
        "run_id": run_id, "job": os.environ["GITHUB_JOB"],
        "workflow_sha": workflow_sha, "product_sha": PRODUCT_SHA,
        "model": MODEL, "api_response_id": response_id,
        "usage": usage, "previous_handoff_id": previous["handoff_id"] if previous else "",
        "analysis": answer, "ready_approval": False,
    }
    record["handoff_id"] = hashlib.sha256(canonical(record)).hexdigest()
    Path(args.output).write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"team": args.team, "api_response_id": response_id,
                      "prompt_tokens": usage["prompt_tokens"],
                      "completion_tokens": usage["completion_tokens"],
                      "consumed_handoff": record["previous_handoff_id"][:16],
                      "produced_handoff": record["handoff_id"][:16],
                      "ready_promotions": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
