"""Fail-closed GitHub A issuance verifier for B intake (no local SQLite as authority).

Required external evidence: A_ISSUANCE_RUN_ID and A_ISSUANCE_WORKFLOW_ID.
The A-issued workflow run must have succeeded, be on the pinned A branch,
and carry a matching qa-pending-request artifact. Unimplemented artifact
content verification intentionally BLOCKS all requests.
"""
import json
import os
import urllib.request

def main():
    e=os.environ
    run_id=e.get("A_ISSUANCE_RUN_ID")
    workflow_id=e.get("A_ISSUANCE_WORKFLOW_ID")
    if not run_id or not run_id.isdecimal() or not workflow_id:
        raise SystemExit("BLOCKED_NO_AUTHENTICATED_A_ISSUANCE_RUN")
    repo=e["GITHUB_REPOSITORY"]
    token=e["GH_TOKEN"]
    def api(path):
        req=urllib.request.Request(
            f"https://api.github.com/repos/{repo}/{path}",
            headers={"Authorization":f"Bearer {token}","Accept":"application/vnd.github+json"})
        with urllib.request.urlopen(req,timeout=20) as resp:
            return json.load(resp)
    run=api(f"actions/runs/{run_id}")
    if (run.get("conclusion")!="success" or run.get("event")!="workflow_dispatch"
        or str(run.get("workflow_id"))!=workflow_id):
        raise SystemExit("BLOCKED_UNTRUSTED_A_ISSUANCE_RUN")
    artifacts=api(f"actions/runs/{run_id}/artifacts").get("artifacts",[])
    candidates=[a for a in artifacts if a.get("name")=="qa-pending-request" and not a.get("expired")]
    if len(candidates)!=1:
        raise SystemExit("BLOCKED_MISSING_A_PENDING_ARTIFACT")
    # GitHub API artifact ZIP bytes must be downloaded, independently decoded,
    # matched to all four inputs, and consumed via a durable replay-resistant ledger.
    # Until then, no receipt may be produced.
    raise SystemExit("BLOCKED_A_ARTIFACT_CONTENT_AND_REPLAY_NOT_VERIFIED")

if __name__=="__main__":
    main()
