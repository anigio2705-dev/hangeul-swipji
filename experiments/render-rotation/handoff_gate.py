"""Read-only C/B handoff gate for Render rotation. No network writes or AI calls.

This is a pure adapter to the existing rotation, not a replacement for the
trusted persistent controller in PR #168 and QA receipt storage in PR #248.
"""
import json
import re
from pathlib import Path
from rotation_dryrun import slot

SHA = re.compile(r"^[0-9a-f]{40}$")
ALLOWED = {"CODE_READY", "CI_PASS", "QA_REQUESTED", "QA_RUNNING",
           "QA_PASS", "QA_FAIL", "FIX_REQUESTED", "C_FIXING", "NEW_SHA"}
REQUIRED = ("REQUEST_ID", "TASK_ID", "SOURCE_ROLE", "TARGET_ROLE",
            "PR_NUMBER", "PRODUCT_SHA", "QA_SHA", "CI_RUN_URL", "QA_STATUS",
            "FAILURE_EVIDENCE", "RETRY_COUNT", "NEXT_ACTION", "UPDATED_AT")


def plan_tick(at, record):
    seq, team, _ = slot(at)
    if not isinstance(record, dict) or any(k not in record for k in REQUIRED):
        return {"seq": seq, "team": team, "action": "HOLD_INVALID_CONTRACT"}
    if (type(record["PR_NUMBER"]) is not int or record["PR_NUMBER"] < 1
            or not isinstance(record["PRODUCT_SHA"], str)
            or not SHA.fullmatch(record["PRODUCT_SHA"])
            or record["QA_STATUS"] not in ALLOWED
            or type(record["RETRY_COUNT"]) is not int
            or record["RETRY_COUNT"] < 0):
        return {"seq": seq, "team": team, "action": "HOLD_INVALID_CONTRACT"}
    status = record["QA_STATUS"]
    if team == "B" and status == "CI_PASS":
        action = "REQUEST_B_QA_VIA_TRUSTED_OUTBOX"
    elif team == "C" and status == "QA_FAIL":
        action = ("ESCALATE_245" if record["RETRY_COUNT"] >= 3
                  else "FETCH_VERIFIED_FAILURE_AND_REPAIR")
    elif team == "C" and status == "QA_PASS":
        action = "NO_C_FIX_A_REVIEW_ONLY"
    else:
        action = "NOOP"
    return {"seq": seq, "team": team, "action": action,
            "request_id": record["REQUEST_ID"], "product_sha": record["PRODUCT_SHA"]}


def plan_from_file(at, path):
    # File is a fixture/snapshot only. Render ephemeral filesystem cannot
    # prove persistence or authority for B verdicts.
    return plan_tick(at, json.loads(Path(path).read_text(encoding="utf-8")))
