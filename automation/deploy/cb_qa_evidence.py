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



ALLOWED_WORKFLOW = ".github/workflows/p0-host-infra-static.yml"
ALLOWED_JOB = "host-infra-static"
B_STEP = "Run independently added B QA-only regression tests (if present)"
B_COMMAND = "##[group]Run if compgen -G 'automation/deploy/test_bqa_*.py'"


def _raw_b_test_proof(log, verdict):
    """Inspect the actual B-only test step, not unrelated passing job output."""
    if not isinstance(log, str) or len(log) > 2_000_000:
        return False
    start = log.find(B_COMMAND)
    if start < 0 or log.find(B_COMMAND, start + 1) >= 0:
        return False
    group_end = log.find("##[endgroup]", start)
    if group_end < 0:
        return False
    end = log.find("##[group]", group_end + len("##[endgroup]"))
    section = log[group_end:end if end >= 0 else len(log)]
    results = re.findall(
        r"(?m)^.*?test_[A-Za-z0-9_]+ \(test_bqa_[^\r\n]+\) \.\.\. (ok|FAIL|ERROR)\s*$",
        section)
    summary = re.findall(r"(?m)^.*?Ran ([1-9][0-9]*) tests in [0-9.]+s\s*$", section)
    if not results or len(summary) != 1 or int(summary[0]) != len(results):
        return False
    if verdict == "QA_PASS":
        return (all(x == "ok" for x in results)
                and bool(re.search(r"(?m)^.*?Z OK\s*$", section))
                and not re.search(r"(?m)^.*?Z FAILED", section))
    return (any(x in ("FAIL", "ERROR") for x in results)
            and bool(re.search(r"(?m)^.*?Z FAILED \(", section)))

def _job_proof(qa_run, qa_jobs, raw_job_logs, qa_sha, verdict):
    """Bind raw B-only tests to the exact authenticated run/attempt/job."""
    if (not isinstance(qa_jobs, list) or len(qa_jobs) != 1
            or not isinstance(raw_job_logs, dict)
            or qa_run.get("path", "").split("@")[0] != ALLOWED_WORKFLOW
            or qa_run.get("name") != "P0 isolated host infrastructure static checks"
            or type(qa_run.get("id")) is not int):
        return False
    job = qa_jobs[0]
    if not isinstance(job, dict):
        return False
    if (job.get("name") != ALLOWED_JOB
            or type(job.get("id")) is not int or job["id"] < 1
            or job.get("run_id") != qa_run["id"]
            or job.get("run_attempt") != qa_run["run_attempt"]
            or job.get("head_sha") != qa_sha
            or job.get("status") != "completed"
            or job.get("conclusion") != ("success" if verdict == "QA_PASS" else "failure")):
        return False
    steps = job.get("steps")
    if not isinstance(steps, list) or not steps:
        return False
    b_steps = [st for st in steps if isinstance(st, dict) and st.get("name") == B_STEP]
    if (len(b_steps) != 1 or b_steps[0].get("conclusion") !=
            ("success" if verdict == "QA_PASS" else "failure")
            or not any(isinstance(st, dict)
                       and st.get("name") == "Run actions/checkout@v4"
                       and st.get("conclusion") == "success" for st in steps)):
        return False
    return _raw_b_test_proof(raw_job_logs.get(job["id"]), verdict)


def _ref(obj, field):
    value = obj.get(field)
    return value if isinstance(value, dict) else {}


def inspect_evidence(*, repo, source_pr, qa_pr, qa_files, qa_run, qa_reviews,
                     source_sha, qa_sha, trusted_b_login, qa_jobs=None, raw_job_logs=None):
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
    run_prs = qa_run.get("pull_requests")
    if not isinstance(run_prs, list):
        return deny("Actions run PR list missing")
    if (qa_run.get("head_sha") != qa_sha or qa_run.get("event") != "pull_request"
            or qa_run.get("status") != "completed"
            or qa_run.get("conclusion") not in ("success", "failure")
            or _ref(qa_run, "head_repository").get("full_name") != repo
            or type(qa_run.get("run_attempt")) is not int
            or qa_run["run_attempt"] < 1
            or not any(isinstance(p, dict) and p.get("number") == qa_pr.get("number")
                       for p in run_prs)):
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
    if not _job_proof(qa_run, qa_jobs, raw_job_logs, qa_sha, verdicts[0]):
        return deny("missing or invalid raw B-only Actions job evidence")
    return {"status": verdicts[0], "reason": "independent B exact-SHA review and raw B-only Actions job proof"}


def collect_github_evidence(*, token, source_pr_number, qa_pr_number, run_id,
                            source_sha, qa_sha, trusted_b_login, get_json=None, get_text=None):
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


    def default_get_text(path):
        # GitHub returns a temporary HTTPS redirect for Actions job logs.
        # Never forward the GitHub token to a different host.
        from urllib.parse import urlsplit
        class SafeRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                target = urlsplit(newurl)
                if target.scheme != "https":
                    raise ValueError("unsafe Actions log redirect")
                next_req = super().redirect_request(req, fp, code, msg, headers, newurl)
                if next_req is not None and target.netloc != urlsplit(req.full_url).netloc:
                    next_req.remove_header("Authorization")
                return next_req
        req = urllib.request.Request(
            "https://api.github.com/repos/" + REPO + path,
            headers={"Authorization": "Bearer " + token,
                     "Accept": "application/vnd.github+json",
                     "X-GitHub-Api-Version": "2022-11-28"})
        with urllib.request.build_opener(SafeRedirect()).open(req, timeout=15) as response:
            raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ValueError("Actions job log exceeds bounded size")
        return raw.decode("utf-8", errors="replace")

    get = get_json if get_json is not None else default_get
    get_log = get_text if get_text is not None else default_get_text
    source = get(f"/pulls/{source_pr_number}")
    qa = get(f"/pulls/{qa_pr_number}")
    files = get(f"/pulls/{qa_pr_number}/files?per_page=100&page=1")
    run = get(f"/actions/runs/{run_id}")
    if (not isinstance(files, list) or len(files) > 50
            or not isinstance(source, dict) or not isinstance(qa, dict)
            or not isinstance(run, dict)):
        return {"status": "UNVERIFIED", "reason": "incomplete GitHub evidence"}
    # Reject unrelated workflow runs before requesting logs.
    if (run.get("path", "").split("@")[0] != ALLOWED_WORKFLOW
            or run.get("name") != "P0 isolated host infrastructure static checks"
            or run.get("head_sha") != qa_sha
            or run.get("status") != "completed"
            or run.get("conclusion") not in ("success", "failure")
            or type(run.get("id")) is not int or run["id"] != run_id):
        return {"status": "UNVERIFIED", "reason": "untrusted QA workflow or run"}
    jobs_payload = get(f"/actions/runs/{run_id}/jobs?per_page=100&page=1")
    if (not isinstance(jobs_payload, dict)
            or type(jobs_payload.get("total_count")) is not int
            or jobs_payload["total_count"] != 1
            or not isinstance(jobs_payload.get("jobs"), list)
            or len(jobs_payload["jobs"]) != 1):
        return {"status": "UNVERIFIED", "reason": "missing or paginated QA job evidence"}
    jobs = jobs_payload["jobs"]
    job_id = jobs[0].get("id") if isinstance(jobs[0], dict) else None
    if type(job_id) is not int or job_id < 1:
        return {"status": "UNVERIFIED", "reason": "invalid QA job id"}
    raw_logs = {job_id: get_log(f"/actions/jobs/{job_id}/logs")}
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
        qa_sha=qa_sha, trusted_b_login=trusted_b_login,
        qa_jobs=jobs, raw_job_logs=raw_logs)
