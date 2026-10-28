#!/usr/bin/env python3
"""Read-only physical audio and 399-cell recording inventory. No TTS."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

CONSONANTS = "\u3131\u3132\u3134\u3137\u3138\u3139\u3141\u3142\u3143\u3145\u3146\u3147\u3148\u3149\u314a\u314b\u314c\u314d\u314e"
VOWELS = "\u314f\u3150\u3151\u3152\u3153\u3154\u3155\u3156\u3157\u3158\u3159\u315a\u315b\u315c\u315d\u315e\u315f\u3160\u3161\u3162\u3163"


def inspect(root):
    manifest_path = root / "hangul-audio-manifest.json"
    # Validate manifest file existence and readability
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Manifest file not found: {manifest_path}")

    manifest_text = manifest_path.read_text(encoding="utf-8")

    try:
        manifest = json.loads(manifest_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in manifest file: {e}")

    records = manifest.get("recordings")
    if not isinstance(records, dict):
        raise ValueError("Manifest 'recordings' entry missing or invalid")

    problems, inventory = [], []
    for word, entry in records.items():
        if not isinstance(word, str) or not isinstance(entry, dict):
            problems.append({"word": word, "issue": "invalid_record_entry"})
            continue

        src = entry.get("src", "")
        if not isinstance(src, str) or not re.fullmatch(r"\./assets/hangul-audio/[\w-]+\.mp3", src):
            problems.append({"word": word, "issue": "invalid_source_path", "path": src})
            continue

        path = root / src[2:]
        if not path.is_file():
            problems.append({"word": word, "issue": "file_missing", "path": src})
            continue

        try:
            data_bytes = path.read_bytes()
        except Exception as e:
            problems.append({"word": word, "issue": "file_read_error", "path": src, "detail": str(e)})
            continue

        digest = hashlib.sha256(data_bytes).hexdigest()
        if entry.get("sha256") and digest != entry["sha256"]:
            problems.append({"word": word, "issue": "hash_mismatch", "path": src})

        probe = subprocess.run([
            "ffmpeg", "-v", "error", "-i", str(path), "-f", "null", "-"
        ], capture_output=True, text=True)
        if probe.returncode:
            problems.append({"word": word, "issue": "decode_failed", "path": src, "detail": probe.stderr[:300]})

        if entry.get("kind") != "human":
            problems.append({"word": word, "issue": "not_verified_human", "path": src})

        if not all(isinstance(entry.get(k), str) and entry.get(k).strip() for k in ("sourceUrl", "author", "license")):
            problems.append({"word": word, "issue": "missing_provenance", "path": src})

    for i, c in enumerate(CONSONANTS):
        for j, v in enumerate(VOWELS):
            word = chr(0xAC00 + (i * 21 + j) * 28)
            entry = records.get(word)
            state = "missing"
            if entry is not None and isinstance(entry, dict):
                if entry.get("disabled"):
                    state = "held"
                else:
                    state = "ready_unapproved"
            inventory.append({
                "character": word, "consonant": c, "vowel": v,
                "recording_script": word, "required_filename": f"{ord(word):04x}.mp3",
                "usage": "Hangul board composed syllable button",
                "status": state, "human_listening_approval": "pending"
            })

    counts = {key: sum(x["status"] == key for x in inventory) for key in ("ready_unapproved", "held", "missing")}

    return {
        "counts": counts,
        "file_issues": problems,
        "recording_inventory": inventory,
        "browser_playback": "NOT_TESTED",
        "human_listening": "NOT_APPROVED"
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    try:
        result = inspect(args.root)
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        raise SystemExit(1)

    data = json.dumps(result, ensure_ascii=False, indent=2)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(data + "\n", encoding="utf-8")

    print(json.dumps({
        "counts": result["counts"],
        "file_issues": result["file_issues"],
        "browser_playback": result["browser_playback"]
    }, ensure_ascii=False))

    raise SystemExit(bool(result["file_issues"]))
