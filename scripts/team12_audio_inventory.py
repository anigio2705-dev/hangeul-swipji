#!/usr/bin/env python3
"""Read-only physical audio and 399-cell recording inventory. No TTS."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

CONSONANTS = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
VOWELS = "ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ"

def inspect(root):
    manifest = json.loads((root / "hangul-audio-manifest.json").read_text(encoding="utf-8"))
    records = manifest.get("recordings")
    if not isinstance(records, dict):
        raise ValueError("audio manifest recordings must be an object")
    problems, inventory = [], []
    seen_sources, seen_digests = {}, {}
    for word, entry in records.items():
        if not isinstance(entry, dict):
            problems.append({"word": word, "issue": "invalid_recording_entry"})
            continue
        src = entry.get("src", "")
        if not isinstance(src, str) or not re.fullmatch(r"\./assets/hangul-audio/[A-Za-z0-9_-]+\.mp3", src):
            problems.append({"word": word, "issue": "invalid_source_path", "path": src})
            continue
        if src in seen_sources:
            problems.append({"word": word, "issue": "duplicate_source_path",
                             "other_word": seen_sources[src], "path": src})
        else:
            seen_sources[src] = word
        path = root / src[2:]
        if not path.is_file():
            problems.append({"word": word, "issue": "file_missing", "path": src})
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        declared = entry.get("sha256")
        if not isinstance(declared, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", declared):
            problems.append({"word": word, "issue": "missing_or_invalid_sha256", "path": src})
        elif digest != declared.lower():
            problems.append({"word": word, "issue": "hash_mismatch", "path": src})
        if digest in seen_digests:
            problems.append({"word": word, "issue": "duplicate_audio_bytes",
                             "other_word": seen_digests[digest], "path": src})
        else:
            seen_digests[digest] = word
        probe = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "null", "-"],
                               capture_output=True, text=True)
        if probe.returncode:
            problems.append({"word": word, "issue": "decode_failed",
                             "path": src, "detail": probe.stderr[:300]})
        if entry.get("kind") != "human":
            problems.append({"word": word, "issue": "not_verified_human", "path": src})
        if (not isinstance(entry.get("sourceUrl"), str)
                or not entry["sourceUrl"].startswith("https://")
                or not all(isinstance(entry.get(k), str) and entry[k].strip()
                           for k in ("author", "license"))):
            problems.append({"word": word, "issue": "missing_provenance", "path": src})
    invalid_words = {item["word"] for item in problems}
    for i, c in enumerate(CONSONANTS):
        for j, v in enumerate(VOWELS):
            word = chr(0xAC00 + (i * 21 + j) * 28)
            entry = records.get(word)
            state = ("missing" if word not in records else
                     "held" if word in invalid_words or (isinstance(entry, dict) and entry.get("disabled")) else
                     "ready_unapproved")
            inventory.append({"character": word, "consonant": c, "vowel": v,
                              "recording_script": word, "required_filename": f"{ord(word):04x}.mp3",
                              "usage": "Hangul board composed syllable button",
                              "status": state, "human_listening_approval": "pending"})
    counts = {key: sum(x["status"] == key for x in inventory)
              for key in ("ready_unapproved", "held", "missing")}
    return {"counts": counts, "file_issues": problems, "recording_inventory": inventory,
            "browser_playback": "NOT_TESTED", "human_listening": "NOT_APPROVED"}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = inspect(args.root)
    data = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(data + "\n", encoding="utf-8")
    print(json.dumps({"counts": result["counts"], "file_issues": result["file_issues"],
                      "browser_playback": result["browser_playback"]}, ensure_ascii=False))
    raise SystemExit(bool(result["file_issues"]))
