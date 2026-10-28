#!/usr/bin/env python3
"""Read-only physical audio and 399-cell recording inventory. No TTS."""
import argparse
import hashlib
import json
import re
from pathlib import Path

CONSONANTS = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
VOWELS = "ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ"

def inspect(root):
    manifest = json.loads((root / "hangul-audio-manifest.json").read_text(encoding="utf-8"))
    records = manifest["recordings"]
    problems, inventory = [], []
    for word, entry in records.items():
        src = entry.get("src", "")
        if not re.fullmatch(r"\./assets/hangul-audio/[\w-]+\.mp3", src):
            problems.append({"word": word, "issue": "invalid_source_path", "path": src})
            continue
        path = root / src[2:]
        if not path.is_file():
            problems.append({"word": word, "issue": "file_missing", "path": src})
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if entry.get("sha256") and digest != entry["sha256"]:
            problems.append({"word": word, "issue": "hash_mismatch", "path": src})
        if entry.get("kind") != "human":
            problems.append({"word": word, "issue": "not_verified_human", "path": src})
        if not all(entry.get(k) for k in ("sourceUrl", "author", "license")):
            problems.append({"word": word, "issue": "missing_provenance", "path": src})
    for i, c in enumerate(CONSONANTS):
        for j, v in enumerate(VOWELS):
            word = chr(0xAC00 + (i * 21 + j) * 28)
            entry = records.get(word)
            state = "missing" if entry is None else ("held" if entry.get("disabled") else "ready_unapproved")
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
