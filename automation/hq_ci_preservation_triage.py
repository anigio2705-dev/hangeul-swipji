"""Read-only original-source drift evidence; never restores or edits production files.

This is a diagnostic supplement, not a replacement for the existing fail-closed
professional96 audit or the 15-team READY/representative approval gates.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

BASE_COMMIT = "7418e325f0833604249e5170c2531a103b31ff1c"
ORIGINAL_PATHS = (
    "intro.html", "beginner1.html", "beginner2.html",
    "intermediate1.html", "intermediate2.html",
    "advanced1.html", "advanced2.html", "reading.html",
    "reading-curriculum.js", "reading-alternates.js",
    "hangul-audio-manifest.json", "index.html",
    "phase3/content.json", "phase3/content-expansion.json",
)


def inspect(root, base=BASE_COMMIT, paths=None, git_show=None):
    """Return exact per-file evidence, preserving a failure on unavailable history."""
    paths = ORIGINAL_PATHS if paths is None else paths
    if not re.fullmatch(r"[0-9a-f]{7,40}", base):
        raise ValueError("base must be a Git commit SHA")
    root = Path(root).resolve()
    git_show = git_show or subprocess.check_output
    records = []
    for rel in paths:
        if rel not in ORIGINAL_PATHS:
            raise ValueError("unapproved original-source path")
        try:
            original = git_show(["git", "show", f"{base}:{rel}"], cwd=root)
        except (subprocess.CalledProcessError, FileNotFoundError, OSError):
            records.append({"path": rel, "status": "BASE_UNAVAILABLE"})
            continue
        path = root / rel
        if not path.is_file():
            records.append({"path": rel, "status": "MISSING",
                            "baseline_sha256": hashlib.sha256(original).hexdigest()})
            continue
        current = path.read_bytes()
        records.append({
            "path": rel,
            "status": "PRESERVED" if current == original else "MODIFIED",
            "baseline_sha256": hashlib.sha256(original).hexdigest(),
            "current_sha256": hashlib.sha256(current).hexdigest(),
        })
    return {"base_commit": base, "checked": len(records),
            "all_preserved": all(x["status"] == "PRESERVED" for x in records),
            "files": records}


def main(argv=None):
    p = argparse.ArgumentParser(description="Read-only source preservation triage")
    p.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument("--base", default=BASE_COMMIT)
    p.add_argument("--strict", action="store_true",
                   help="Exit 2 if ANY source changed, missing, or history unavailable")
    args = p.parse_args(argv)
    report = inspect(args.root, args.base)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 2 if args.strict and not report["all_preserved"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
