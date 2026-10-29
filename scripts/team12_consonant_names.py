#!/usr/bin/env python3
"""Independent inventory of 19 consonant-name buttons, not listening approval."""
import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "docs/team12/consonant-name-plan-19.json"
NODE = r"""
const fs=require('fs'),vm=require('vm');
const sandbox={
  window:{addEventListener(){}},
  document:{addEventListener(){},dispatchEvent(){}},
  Event:function(){},
  fetch:async()=>({ok:true,json:async()=>({recordings:{}})})
};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync('hangul-core.js','utf8'),sandbox);
const h=sandbox.window.HSHangul;
if(!h)throw Error('Missing real board');
process.stdout.write(JSON.stringify(h.consonants.map(([letter,name])=>({letter,name}))));
"""

def generate():
    names = json.loads(subprocess.check_output(
        ["node", "-e", NODE], cwd=ROOT, text=True, timeout=30))
    if len(names) != 19 or len({x["letter"] for x in names}) != 19:
        raise ValueError("Expected 19 distinct consonant letters")
    if len({x["name"] for x in names}) != 19:
        raise ValueError("Expected 19 distinct consonant names")
    board = json.loads((ROOT / "docs/team12/recording-plan-399.json").read_text(encoding="utf-8"))
    if len(board["cells"]) != 399 or len({c["syllable"] for c in board["cells"]}) != 399:
        raise ValueError("Expected 399 distinct board syllables")
    if {x["letter"] for x in names} != {c["consonant"] for c in board["cells"]}:
        raise ValueError("Names do not match the 399-cell board")
    if len({x["name"] for x in names} | {c["syllable"] for c in board["cells"]}) != 418:
        raise ValueError("418 target collision")
    manifest = json.loads((ROOT / "hangul-audio-manifest.json").read_text(encoding="utf-8"))
    if board["manifest_version"] != manifest.get("version"):
        raise ValueError("Board and name inventories use different manifest versions")
    counts = {"ready_unapproved": 0, "held": 0, "missing": 0}
    targets = []
    for item in names:
        record = manifest["recordings"].get(item["name"])
        state = "missing" if record is None else "held" if record.get("disabled") else "ready_unapproved"
        counts[state] += 1
        targets.append({**item, "status": state, "src": record.get("src") if record else None})
    return {
        "schema": 1,
        "scope": "19 consonant names from live hangul-core.js; not approved recordings",
        "manifest_version": manifest.get("version"),
        "counts": counts,
        "names": targets,
    }

def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    actual = generate()
    if args.write:
        PLAN.parent.mkdir(parents=True, exist_ok=True)
        PLAN.write_text(json.dumps(actual, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    else:
        if not PLAN.is_file():
            raise SystemExit("FAIL: missing 19-name inventory")
        if json.loads(PLAN.read_text(encoding="utf-8")) != actual:
            raise SystemExit("FAIL: 19-name inventory differs from live board or manifest")
    print("PASS: 19 consonant names independently reconciled:", actual["counts"])
    print("NOT VERIFIED: listening accuracy, rights approval, browser playback, 418 audio files")

if __name__ == "__main__":
    main()
