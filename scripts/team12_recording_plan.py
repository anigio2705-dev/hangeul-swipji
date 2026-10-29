#!/usr/bin/env python3
"""Reconcile the real Hangul board with the human-audio manifest.

This is an inventory generator/checker, NOT a pronunciation or listening approval.
399 composed board syllables and 19 consonant-name targets are distinct scopes.
"""
import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "docs/team12/recording-plan-399.json"
NODE = r"""
const fs = require('fs'), vm = require('vm');
const sandbox = {
  window: {addEventListener() {}},
  document: {addEventListener() {}, dispatchEvent() {}},
  Event: function Event() {},
  fetch: async () => ({ok: true, json: async () => ({recordings: {}})})
};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync('hangul-core.js', 'utf8'), sandbox);
const h = sandbox.window.HSHangul;
if (!h) throw new Error('Missing live Hangul board implementation');
const cells = h.consonants.flatMap(([c]) =>
  h.vowels.map(([v]) => ({consonant:c, vowel:v, syllable:h.compose(c,v)})));
process.stdout.write(JSON.stringify({
  consonants: h.consonants.map(([c])=>c),
  vowels: h.vowels.map(([v])=>v),
  cells
}));
"""

def generate():
    board = json.loads(subprocess.check_output(
        ["node", "-e", NODE], cwd=ROOT, text=True, timeout=30))
    if len(board["consonants"]) != 19 or len(set(board["consonants"])) != 19:
        raise ValueError("Board must have 19 distinct initial consonants")
    if len(board["vowels"]) != 21 or len(set(board["vowels"])) != 21:
        raise ValueError("Board must have 21 distinct medial vowels")
    cells = board["cells"]
    if len(cells) != 399 or len({cell["syllable"] for cell in cells}) != 399:
        raise ValueError("Board must have 399 distinct composed syllables")
    manifest = json.loads((ROOT / "hangul-audio-manifest.json").read_text(encoding="utf-8"))
    recordings = manifest["recordings"]
    counts = {"ready_unapproved": 0, "held": 0, "missing": 0}
    result = []
    for cell in cells:
        entry = recordings.get(cell["syllable"])
        state = "missing" if entry is None else "held" if entry.get("disabled") else "ready_unapproved"
        counts[state] += 1
        result.append({**cell, "status": state, "src": entry.get("src") if entry else None})
    return {
        "schema": 1,
        "scope": "399 composed board syllables; 19 consonant-name targets are separate (418 inventory targets, not 418 approved recordings)",
        "manifest_version": manifest.get("version"),
        "counts": counts,
        "cells": result,
    }

def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true")
    group.add_argument("--write", action="store_true")
    args = parser.parse_args()
    actual = generate()
    if args.write:
        PLAN.parent.mkdir(parents=True, exist_ok=True)
        PLAN.write_text(json.dumps(actual, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("Updated board inventory:", actual["counts"])
        return
    if not PLAN.is_file():
        raise SystemExit("FAIL: missing board inventory " + str(PLAN))
    stored = json.loads(PLAN.read_text(encoding="utf-8"))
    if stored != actual:
        raise SystemExit("FAIL: board inventory differs from live code/manifest; regenerate and review")
    print("PASS: 399 board syllables + 19 distinct consonant-name targets; statuses:", actual["counts"])
    print("NOT VERIFIED: human listening, browser playback, rights approval, 418 distinct audio files")

if __name__ == "__main__":
    main()
