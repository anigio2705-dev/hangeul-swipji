#!/usr/bin/env python3
"""Independent Hangul board audit; read-only, no audio synthesis."""
import argparse
import json
from pathlib import Path

def audit(report):
    counts = report.get("counts", {})
    ready, held, missing = (counts.get(k, -1) for k in ("ready", "held", "missing"))
    issues = []
    if min(ready, held, missing) < 0:
        issues.append("missing_or_negative_count")
    if ready + held + missing != 399:
        issues.append("syllable_total_mismatch")
    recordings = report.get("recordingFiles", [])
    seen = set()
    for item in recordings:
        word = item.get("word")
        if not word or word in seen:
            issues.append("missing_or_duplicate_recording_word:" + str(word))
        seen.add(word)
        if item.get("exists") and not item.get("decodeOK"):
            issues.append("undecodable:" + str(word))
        if item.get("held") and item.get("playable") is True:
            issues.append("held_marked_playable:" + str(word))
    return {"counts": counts, "recording_entries": len(recordings),
            "issues": issues, "status": "PASS" if not issues else "FAIL",
            "limits": "Checks audit report consistency only; does not verify current browser playback or human pronunciation."}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    result = audit(json.loads(args.report.read_text(encoding="utf-8")))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(bool(result["issues"]))

if __name__ == "__main__":
    main()
