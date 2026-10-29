#!/usr/bin/env python3
"""Independent #54 semantic test: derive missing targets from live board + manifest."""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NODE = r"""
const fs=require('fs'),vm=require('vm');
const sandbox={window:{addEventListener(){}},document:{addEventListener(){},dispatchEvent(){}},
  Event:function(){},fetch:async()=>({ok:true,json:async()=>({recordings:{}})})};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync('hangul-core.js','utf8'),sandbox);
const h=sandbox.window.HSHangul;
process.stdout.write(JSON.stringify({syllables:h.consonants.flatMap(([c])=>h.vowels.map(([v])=>h.compose(c,v))),
  names:h.consonants.map(([,name])=>name)}));
"""

def main():
    live = json.loads(subprocess.check_output(["node", "-e", NODE], cwd=ROOT, text=True, timeout=30))
    manifest = json.loads((ROOT / "hangul-audio-manifest.json").read_text(encoding="utf-8"))
    script = json.loads((ROOT / "docs/team12/missing-recording-script-359.json").read_text(encoding="utf-8"))
    recordings = manifest["recordings"]
    expected = {("syllable", x) for x in live["syllables"] if x not in recordings}
    expected |= {("consonant_name", x) for x in live["names"] if x not in recordings}
    actual = {(x["kind"], x["text"]) for x in script["targets"]}
    assert len(live["syllables"]) == 399 and len(live["names"]) == 19
    assert len(expected) == 359, "Current missing count changed; update script and baseline"
    assert len(actual) == len(script["targets"]) == 359, "Duplicate or missing script entry"
    assert actual == expected, "Script contains held/available/wrong targets or misses a required item"
    assert script["counts"] == {"syllables": 354, "consonant_names": 5, "total": 359}
    assert script["source_manifest_version"] == manifest["version"]
    for item in script["targets"]:
        assert item["spoken_text"] == item["text"] and item["repeat"] == 2
        assert item["pause_ms"] == 700 and item["context"]
        assert item["id"] == item["kind"] + ":" + item["text"]
    print("PASS: independent live-code+manifest semantic audit of 359 human recording prompts")
    print("NOT VERIFIED: actual human recordings, playback, rights or listening")

if __name__ == "__main__":
    main()
