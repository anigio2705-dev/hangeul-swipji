"""Durable GitHub issue queue watchdog. Does not invoke ChatGPT or approve READY."""
import json
import os
import urllib.request
from urllib.error import HTTPError

API = "https://api.github.com"
MARKER = "[HS-AUTONOMOUS-WORK-REQUEST]"
def request(path, token, method="GET", payload=None):
    body = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(API + path, data=body, method=method,
        headers={"Authorization": "Bearer " + token,
                 "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28",
                 "User-Agent": "hangeul-swipji-watchdog"})
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.load(response)

def pending(issues):
    # Pull requests also appear in GitHub issues API; exclude them.
    return [i for i in issues if "pull_request" not in i
            and i.get("title", "").startswith(MARKER)
            and i.get("state") == "open"]

def plan(issues):
    if pending(issues):
        return {"action": "wait", "reason": "existing unacknowledged work request"}
    return {"action": "create", "title": MARKER + " Central: inspect backlog and continue",
            "body": ("Central HQ: inspect Issue #34 and 160-item ledger; develop the next "
                     "eligible task; request separate team15 QA; central decides READY. "
                     "Support team only unblocks central. Close this request after "
                     "a verifiable run, not merely after reading. This issue is a "
                     "queue signal, NOT evidence that a ChatGPT worker started. "
                     "Do not deploy, pay, or change production data.")}

def main():
    repo = os.environ["GITHUB_REPOSITORY"]
    token = os.environ["GH_TOKEN"]
    if not repo.replace("-", "").replace("_", "").replace("/", "").isalnum() or repo.count("/") != 1:
        raise ValueError("invalid repository")
    issues = request("/repos/" + repo + "/issues?state=open&per_page=100", token)
    result = plan(issues)
    print(json.dumps(result, ensure_ascii=False))
    if result["action"] == "create" and os.environ.get("APPLY_QUEUE") == "true":
        created = request("/repos/" + repo + "/issues", token, "POST",
                          {"title": result["title"], "body": result["body"]})
        print("QUEUED_ISSUE=" + str(created["number"]))
    elif result["action"] == "create":
        print("DRY_RUN: no issue created")
if __name__ == "__main__":
    main()
