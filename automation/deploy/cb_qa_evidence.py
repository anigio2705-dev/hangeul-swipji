"""Read-only GitHub B QA evidence verification; never trusts a comment/boolean.

This verifier deliberately requires a distinct allowlisted B reviewer account.
If A/B/C share the same GitHub account, independent provenance is NOT proven
and no receipt is accepted. It never posts, pushes, or grants READY.
"""
import re

SHA = re.compile(r"^[0-9a-f]{40}$")
REPO = "anigio2705-dev/hangeul-swipji"
MARKER = re.compile(
    r"(?m)^HS_B_QA_VERDICT status=(QA_PASS|QA_FAIL) product_sha=([0-9a-f]{40}) qa_sha=([0-9a-f]{40})$"
)


def _ref(obj, field):
    value = obj.get(field)
    return value if isinstance(value, dict) else {}


def inspect_evidence(*, repo, source_pr, qa_pr, qa_files, qa_run, qa_reviews,
                     source_sha, qa_sha, trusted_b_login):
    """Return a verified verdict only with independent B review + CI provenance.

    Inputs MUST come from authenticated GitHub REST responses fetched by the
    credential-owning controller, never from a C-authored JSON/comment.
    This pure validator does not authenticate its caller or perform HTTP.
    """
    deny = lambda reason: {"status": "UNVERIFIED", "reason": reason}
    if (repo != REPO or not SHA.fullmatch(str(source_sha))
            or not SHA.fullmatch(str(qa_sha)) or source_sha == qa_sha):
        return deny("invalid repo or SHA")
    if not trusted_b_login or not isinstance(trusted_b_login, str):
        return deny("no independent B reviewer configured")
    if not all(isinstance(x, dict) for x in (source_pr, qa_pr, qa_run)):
        return deny("malformed GitHub payload")
    source_author = _ref(source_pr, "user").get("login")
    qa_author = _ref(qa_pr, "user").get("login")
    if (not source_author or not qa_author
            or trusted_b_login in (source_author, qa_author)):
        return deny("B reviewer not independent of PR authors")
    src_head = _ref(source_pr, "head")
    qa_head = _ref(qa_pr, "head")
    qa_base = _ref(qa_pr, "base")
    if (src_head.get("sha") != source_sha or qa_base.get("sha") != source_sha
            or qa_head.get("sha") != qa_sha
            or qa_base.get("ref") != src_head.get("ref")
            or not str(qa_head.get("ref", "")).startswith(("qa/", "bqa/"))
            or source_pr.get("state") != "open" or qa_pr.get("state") != "open"
            or qa_pr.get("merged") is not False):
        return deny("source or B QA PR exact SHA/base mismatch")
    if (not isinstance(qa_files, list) or not qa_files
            or len(qa_files) > 50 or not all(isinstance(f, dict) for f in qa_files)):
        return deny("missing QA-only changed file evidence")
    paths = [f.get("filename") for f in qa_files]
    if (not all(isinstance(p, str) and p.startswith(("automation/deploy/test_bqa_",
                                                  "automation/deploy/test_b15_",
                                                  "phase3/test_bqa_")) and p.endswith(".py")
                for p in paths)
            or not all(f.get("status") == "added" for f in qa_files)):
        return deny("QA PR changes more than new independent tests")
    if (qa_run.get("head_sha") != qa_sha or qa_run.get("event") != "pull_request"
            or qa_run.get("status") != "completed"
            or qa_run.get("conclusion") not in ("success", "failure")
            or _ref(qa_run, "head_repository").get("full_name") != repo
            or type(qa_run.get("run_attempt")) is not int
            or qa_run["run_attempt"] < 1
            or not any(isinstance(p, dict) and p.get("number") == qa_pr.get("number")
                       for p in qa_run.get("pull_requests", [])
                       if isinstance(qa_run.get("pull_requests"), list))):
        return deny("Actions run does not belong to exact B QA PR/SHA")
    if not isinstance(qa_reviews, list) or len(qa_reviews) > 200:
        return deny("review evidence incomplete")
    verdicts = []
    for review in qa_reviews:
        if not isinstance(review, dict):
            return deny("malformed review")
        if (_ref(review, "user").get("login") != trusted_b_login
                or review.get("commit_id") != qa_sha
                or review.get("state") not in ("APPROVED", "CHANGES_REQUESTED")
                or not review.get("submitted_at")):
            continue
        for match in MARKER.finditer(str(review.get("body") or "")):
            verdict, product, qa = match.groups()
            if product == source_sha and qa == qa_sha:
                if (review["state"] == "APPROVED" and verdict == "QA_PASS"
                        and qa_run["conclusion"] == "success"):
                    verdicts.append(verdict)
                elif (review["state"] == "CHANGES_REQUESTED" and verdict == "QA_FAIL"):
                    verdicts.append(verdict)
    if len(set(verdicts)) != 1 or not verdicts:
        return deny("missing or conflicting independent B exact-SHA review")
    return {"status": verdicts[0], "reason": "distinct B reviewer + exact QA-only PR + Actions"}


def collect_github_evidence(*, token, source_pr_number, qa_pr_number, run_id,
                            source_sha, qa_sha, trusted_b_login, get_json=None):
    """Read-only authenticated GitHub evidence collection, never an approval.

    Caller must supply trusted_b_login from a protected controller setting,
    not from an issue comment or AI-edited file. No POST, token logging, or
    automatic receipt write. API failures raise; missing evidence fails closed.
    """
    import json
    import urllib.request

    if (not token or any(type(n) is not int or n < 1
                         for n in (source_pr_number, qa_pr_number, run_id))
            or not SHA.fullmatch(str(source_sha))
            or not SHA.fullmatch(str(qa_sha))):
        return {"status": "UNVERIFIED", "reason": "invalid collection parameters"}

    def default_get(path):
        req = urllib.request.Request(
            "https://api.github.com/repos/" + REPO + path,
            headers={"Authorization": "Bearer " + token,
                     "Accept": "application/vnd.github+json",
                     "X-GitHub-Api-Version": "2022-11-28"})
        with urllib.request.urlopen(req, timeout=15) as response:
            return json.load(response)

    get = get_json if get_json is not None else default_get
    source = get(f"/pulls/{source_pr_number}")
    qa = get(f"/pulls/{qa_pr_number}")
    files = get(f"/pulls/{qa_pr_number}/files?per_page=100&page=1")
    run = get(f"/actions/runs/{run_id}")
    if (not isinstance(files, list) or len(files) > 50
            or not isinstance(source, dict) or not isinstance(qa, dict)
            or not isinstance(run, dict)):
        return {"status": "UNVERIFIED", "reason": "incomplete GitHub evidence"}
    reviews = []
    for page in range(1, 4):
        batch = get(f"/pulls/{qa_pr_number}/reviews?per_page=100&page={page}")
        if not isinstance(batch, list) or len(batch) > 100:
            return {"status": "UNVERIFIED", "reason": "malformed reviews page"}
        reviews.extend(batch)
        if len(reviews) > 200:
            return {"status": "UNVERIFIED", "reason": "reviews exceed safe bound"}
        if len(batch) < 100:
            break
    else:
        return {"status": "UNVERIFIED", "reason": "reviews pagination incomplete"}
    return inspect_evidence(
        repo=REPO, source_pr=source, qa_pr=qa, qa_files=files,
        qa_run=run, qa_reviews=reviews, source_sha=source_sha,
        qa_sha=qa_sha, trusted_b_login=trusted_b_login)
