"""Fail-closed test99 acceptance evidence. No credentials, deployment or production writes."""
from __future__ import annotations
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
TEST99 = "https://hangeul-swipji99-test.onrender.com"
PRODUCTION = "https://anigio2705-dev.github.io/hangeul-swipji/"
HISTORICAL = ROOT / "audit/staging99-deployment.json"
CONFIG = ROOT / "deploy/render-staging.yaml"
SOURCE = ROOT / "phase3/staging_server.py"


def static_evidence():
    historic = json.loads(HISTORICAL.read_text(encoding="utf-8"))
    config = CONFIG.read_text(encoding="utf-8")
    safe = all((
        historic.get("url") == TEST99,
        historic.get("provider") == "Render",
        historic.get("autoDeploy") == "off",
        historic.get("productionDatabaseUsed") is False,
        historic.get("realPaymentsEnabled") is False,
        "autoDeployTrigger: 'off'" in config,
        "plan: free" in config,
        "HS_STAGING_DB" in config,
        "/tmp/hangeul-swipji-staging/" in config,
        "branch: main" not in config,
        TEST99 != PRODUCTION.rstrip("/"),
    ))
    return {
        "url": TEST99,
        "production_url": PRODUCTION,
        "historical_deploy_sha": historic.get("deployedCommit"),
        "historical_deploy_at": historic.get("dateKST"),
        "historical_only": True,
        "static_isolation_configuration_pass": safe,
        "local_staging_source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "hosting_configuration_verified_live": False,
    }


def acceptance_gate(evidence, desired_sha):
    """Static/HTTP evidence never substitutes for hosted browser and deploy SHA."""
    failures = []
    if not evidence.get("static_isolation_configuration_pass"):
        failures.append("STATIC_ISOLATION_UNVERIFIED")
    if evidence.get("health_status") != 200 or evidence.get("health_mode") != "test" or evidence.get("health_scope") != "isolated-staging":
        failures.append("HOSTED_HEALTH_UNVERIFIED")
    if evidence.get("hosted_source_sha256") != evidence.get("local_staging_source_sha256"):
        failures.append("HOSTED_SOURCE_MISMATCH_OR_UNKNOWN")
    if not desired_sha or evidence.get("verified_deploy_sha") != desired_sha:
        failures.append("DEPLOY_SHA_UNVERIFIED")
    if evidence.get("hosting_configuration_verified_live") is not True:
        failures.append("HOSTING_ISOLATION_UNVERIFIED")
    if evidence.get("authenticated_browser_pass") is not True:
        failures.append("AUTHENTICATED_BROWSER_UNVERIFIED")
    if evidence.get("mobile_browser_pass") is not True:
        failures.append("MOBILE_BROWSER_UNVERIFIED")
    if evidence.get("owner_approval") is not True:
        failures.append("OWNER_APPROVAL_PENDING")
    return {"status": "ACCEPTED" if not failures else "BLOCKED", "reasons": failures}


def request_public(url):
    """GET only; no auth, no cookies, no POST, no redirects to another host."""
    from urllib.request import build_opener, HTTPRedirectHandler
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None
    opener = build_opener(NoRedirect())
    req = Request(url, headers={"User-Agent": "HangeulSwipji-Test99-ReadOnly-Evidence/1"})
    try:
        with opener.open(req, timeout=12) as response:
            body = response.read(8192)
            return response.status, body
    except HTTPError as exc:
        return exc.code, b""
    except (URLError, TimeoutError, OSError) as exc:
        return None, str(type(exc).__name__).encode("ascii", "ignore")


def probe():
    result = static_evidence()
    status, body = request_public(TEST99 + "/healthz")
    result["health_status"] = status
    try:
        health = json.loads(body) if status == 200 else {}
    except (ValueError, UnicodeDecodeError):
        health = {}
    result["health_mode"] = health.get("mode")
    result["health_scope"] = health.get("scope")
    result["hosted_source_sha256"] = health.get("sourceSHA256")
    result["health_origin_matches"] = health.get("configuredOrigin") == TEST99
    result["unauthenticated_home_status"] = request_public(TEST99 + "/")[0]
    result["checked_at_utc"] = datetime.now(timezone.utc).isoformat()
    result["verified_deploy_sha"] = None  # Never infer SHA from old audit or HTTP hash.
    result["authenticated_browser_pass"] = False
    result["mobile_browser_pass"] = False
    result["owner_approval"] = False
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--desired-sha", default="")
    args = parser.parse_args()
    result = probe() if args.probe else static_evidence()
    result["acceptance"] = acceptance_gate(result, args.desired_sha)
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
