#!/usr/bin/env python3
"""Rebuild the 359-target human recording script from audited board/name inventories."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/team12/missing-recording-script-359.json"

def generate():
    board = json.loads((ROOT / "docs/team12/recording-plan-399.json").read_text(encoding="utf-8"))
    names = json.loads((ROOT / "docs/team12/consonant-name-plan-19.json").read_text(encoding="utf-8"))
    if board["manifest_version"] != names["manifest_version"]:
        raise ValueError("Inventory versions do not match")
    cells = [c for c in board["cells"] if c["status"] == "missing"]
    missing_names = [n for n in names["names"] if n["status"] == "missing"]
    targets = []
    for cell in cells:
        text = cell["syllable"]
        targets.append({
            "id": "syllable:" + text, "kind": "syllable",
            "text": text, "spoken_text": text, "repeat": 2, "pause_ms": 700,
            "context": cell["consonant"] + " + " + cell["vowel"] + " = " + text,
        })
    for item in missing_names:
        text = item["name"]
        targets.append({
            "id": "consonant_name:" + text, "kind": "consonant_name",
            "text": text, "spoken_text": text, "repeat": 2, "pause_ms": 700,
            "context": item["letter"] + " 자음의 이름",
        })
    counts = {"syllables": len(cells), "consonant_names": len(missing_names),
              "total": len(targets)}
    if len({x["id"] for x in targets}) != len(targets):
        raise ValueError("Duplicate recording target")
    return {
        "schema": 1,
        "purpose": "Human-only recording script for 359 currently missing targets; no audio files created",
        "source_manifest_version": board["manifest_version"],
        "counts": counts,
        "protocol": "Human speaker reads spoken_text twice with a short pause; review pronunciation, rights, noise and file quality separately.",
        "targets": targets,
    }

def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    args = parser.parse_args()
    actual = generate()
    if args.write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(actual, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    else:
        if not OUT.is_file():
            raise SystemExit("FAIL: recording script is missing")
        if json.loads(OUT.read_text(encoding="utf-8")) != actual:
            raise SystemExit("FAIL: recording script differs from audited missing targets")
    print("PASS: human recording script targets:", actual["counts"])
    print("NOT VERIFIED: audio creation, listening quality, license, website playback")

if __name__ == "__main__":
    main()
