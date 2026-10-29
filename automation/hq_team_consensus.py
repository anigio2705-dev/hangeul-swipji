"""Fail-closed six-team agreement gate; no synthetic votes or deployments."""
import argparse
import json
from pathlib import Path
TEAMS = ("11", "12", "13", "14", "15", "16")
EDGES = (("11","12"),("11","13"),("11","14"),("11","15"),("11","16"),("12","13"),("12","15"),("13","14"),("13","15"),("13","16"),("14","15"),("14","16"),("15","16"))
FIELDS = ("team", "decision", "deliverables", "dependencies", "risks", "evidence")
def review(replies):
    issues = []
    for team in TEAMS:
        r = replies.get(team)
        if not isinstance(r, dict):
            issues.append(f"{team}: missing independent response")
            continue
        for field in FIELDS:
            if field not in r or r[field] in ("", [], None):
                issues.append(f"{team}: missing {field}")
        if r.get("team") != team:
            issues.append(f"{team}: identity mismatch")
        if r.get("decision") != "ACCEPT":
            issues.append(f"{team}: not accepted")
        evidence = r.get("evidence")
        if not isinstance(evidence, dict) or not evidence.get("run_id"):
            issues.append(f"{team}: missing execution evidence")
    for a,b in EDGES:
        if a in replies and b in replies:
            if b not in replies[a].get("acknowledges", []) or a not in replies[b].get("acknowledges", []):
                issues.append(f"{a}<->{b}: missing bilateral acknowledgement")
    return {"status": "PASS" if not issues else "BLOCKED", "issues": issues, "received": sorted(set(replies).intersection(TEAMS))}
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    replies = {}
    for team in TEAMS:
        path = args.directory / f"team-{team}.json"
        if path.is_file():
            replies[team] = json.loads(path.read_text(encoding="utf-8"))
    result = review(replies)
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if result["status"] == "PASS" else 2
if __name__ == "__main__":
    raise SystemExit(main())
