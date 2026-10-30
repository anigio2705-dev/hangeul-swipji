"""Read-only audit of task #101's protected ROOT index.html drift.

This report does NOT authorize the drift or replace the existing byte-for-byte
protection gate. Only 12/15/HQ2 independent review can decide an approved
baseline/migration; the original test must continue to fail until then.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

BASE = "7418e32"
PROTECTED = ("phase3/content.json", "phase3/content-expansion.json",
             "index.html", "hangul-audio-manifest.json")
# Exact observed changes, not an authorization to change protected originals.
OBSERVED = (
    (".editorial-landing{position:relative;min-height:760px;",
     ".editorial-landing{position:relative;min-height:640px;"),
    (".editorial-image{position:relative;min-height:760px;",
     ".editorial-image{position:relative;min-height:640px;"),
    (".editorial-content{padding:90px clamp(28px,5vw,100px) 65px;",
     ".editorial-content{padding:56px clamp(28px,5vw,100px) 50px;"),
    (".editorial-steps{margin-top:65px;padding-top:24px;",
     ".editorial-steps{margin-top:38px;padding-top:24px;"),
    ('</section><section id="teaching-platform"',
     '</section><div class="shell" data-team12-handoff></div>'
     '<script src="./scripts/team12_learning_handoff.js" defer></script>'
     '<section id="teaching-platform"'),
)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def observed_delta(baseline, candidate):
    """Classify ONLY the five exact changes; fail closed on any other drift."""
    try:
        old = baseline.decode("utf-8")
        new = candidate.decode("utf-8")
    except UnicodeDecodeError:
        return False, "non_utf8"
    expected = old
    for before, after in OBSERVED:
        if expected.count(before) != 1:
            return False, "baseline_anchor_missing_or_ambiguous"
        expected = expected.replace(before, after, 1)
    return expected == new, "exact_five_observed_changes" if expected == new else "unrecognized_root_change"


def audit(root, baseline_reader):
    root = Path(root)
    files = []
    for path in PROTECTED:
        original = baseline_reader(path)
        actual = (root / path).read_bytes()
        equal = original == actual
        known, classification = observed_delta(original, actual) if path == "index.html" else (False, "exact_preservation" if equal else "unexpected_change")
        files.append({"path": path, "baseline_sha256": sha256(original),
                      "current_sha256": sha256(actual), "byte_identical": equal,
                      "observed_delta_only": known, "classification": classification})
    index = next(x for x in files if x["path"] == "index.html")
    others_intact = all(x["byte_identical"] for x in files if x["path"] != "index.html")
    handoff_exists = (root / "scripts/team12_learning_handoff.js").is_file()
    return {
        "schema": 1, "task": 101, "baseline_ref": BASE,
        "baseline_review_status": "PENDING_12_15_HQ2",
        "approved": False, "ready": False,
        "original_protection_pass": all(x["byte_identical"] for x in files),
        "known_delta_only": bool(index["observed_delta_only"] and others_intact and handoff_exists),
        "handoff_script_exists": handoff_exists,
        "files": files,
        "next_action": "Independent 12/15/HQ2 review of root index UI and learning handoff; do not weaken original test.",
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", default=".")
    p.add_argument("--output", required=True)
    args = p.parse_args()
    root = Path(args.root).resolve()
    def baseline(path):
        return subprocess.check_output(["git", "show", BASE + ":" + path], cwd=root)
    report = audit(root, baseline)
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("known_delta_only", "approved", "ready", "original_protection_pass")}))
    # The audit may succeed while the original, unchanged protection test fails.
    return 0 if report["known_delta_only"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
