#!/usr/bin/env python3
"""Team15 D2 evidence gates. CI success is NEVER a Render/browser PASS."""
import argparse
import json
import pathlib
import re
import sys

REQUIRED = ("11", "12", "13", "14", "15", "16")
STATES = ("not_started", "code_ready", "ci_pass", "server_verified", "blocked")
FIELDS = ("team", "feature", "code_sha", "ci_run_url", "render_sha",
          "http_evidence", "browser_evidence", "state", "blockers")
SHA = re.compile(r"^[a-f0-9]{40}$")
ACTIONS = re.compile(r"^https://github[.]com/[^/]+/[^/]+/actions/runs/[0-9]+$")
def validate(rows):
    errors = []
    seen = set()
    for n, row in enumerate(rows, 1):
        tag = f"row {n}"
        for field in FIELDS:
            if field not in row:
                errors.append(f"{tag}: missing {field}")
        team, feature = row.get("team"), row.get("feature")
        if team not in REQUIRED or not isinstance(feature, str) or not feature.strip():
            errors.append(f"{tag}: invalid team or feature")
        key = (team, feature)
        if key in seen:
            errors.append(f"{tag}: duplicate team/feature")
        seen.add(key)
        state = row.get("state")
        if state not in STATES:
            errors.append(f"{tag}: invalid state {state}")
        code = row.get("code_sha")
        render = row.get("render_sha")
        if code and not SHA.fullmatch(code):
            errors.append(f"{tag}: invalid code SHA")
        if render and not SHA.fullmatch(render):
            errors.append(f"{tag}: invalid Render SHA")
        ci = row.get("ci_run_url")
        if ci and not ACTIONS.fullmatch(ci):
            errors.append(f"{tag}: invalid CI URL")
        if state in ("code_ready", "ci_pass", "server_verified") and not code:
            errors.append(f"{tag}: code evidence required")
        if state in ("ci_pass", "server_verified") and not ci:
            errors.append(f"{tag}: actual Actions run URL required")
        if state == "server_verified":
            if not (render and row.get("http_evidence") and row.get("browser_evidence")):
                errors.append(f"{tag}: Render SHA + HTTP + browser evidence required")
            if not row.get("verification_time"):
                errors.append(f"{tag}: verification timestamp required")
    return errors

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    args = ap.parse_args()
    data = json.loads(pathlib.Path(args.file).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise SystemExit("Expected a JSON array")
    errors = validate(data)
    for e in errors:
        print("FAIL", e)
    print(f"Validated {len(data)} entries; server-verified={sum(r.get('state') == 'server_verified' for r in data)}; errors={len(errors)}")
    return bool(errors)

if __name__ == "__main__":
    sys.exit(main())
