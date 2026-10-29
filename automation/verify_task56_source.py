#!/usr/bin/env python3
"""Trusted task #56 source regression: Hangul audio candidates survive filtering.

Runs candidate script in an isolated temporary directory with mocked HTTP;
never downloads audio, changes production manifests or approves listening.
"""
import argparse
import io
import json
import runpy
import shutil
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path
from unittest.mock import patch

def check(source):
    with tempfile.TemporaryDirectory(prefix="hq56-") as temp:
        root = Path(temp)
        (root / "scripts").mkdir()
        script = root / "scripts" / "find-human-audio-sources.py"
        shutil.copyfile(source, script)
        targets = [
            {"text": "가", "recordingAvailable": False, "groups": ["글자판 음절"]},
            {"text": "ㄱ", "recordingAvailable": False, "groups": ["자음 이름"]},
            {"text": "ㅏ", "recordingAvailable": False, "groups": ["모음"]},
            {"text": "나", "recordingAvailable": True, "groups": ["글자판 음절"]},
            {"text": "../bad", "recordingAvailable": False, "groups": ["글자판 음절"]},
        ]
        (root / "hangul-audio-audit.json").write_text(
            json.dumps({"targets": targets}, ensure_ascii=False), encoding="utf-8")
        urls = []
        def fake_urlopen(request, timeout=25):
            urls.append(request.full_url)
            return io.BytesIO(b'{"query":{"pages":{}}}')
        with patch.object(urllib.request, "urlopen", side_effect=fake_urlopen):
            runpy.run_path(str(script), run_name="__main__")
        report = json.loads((root / "audit/audio-source-search.json").read_text(encoding="utf-8"))
        names = []
        for url in urls:
            names += urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)["titles"][0].split("|")
        expected = {"File:Ko-" + word + "." + ext
                    for word in ("가", "ㄱ", "ㅏ") for ext in ("ogg", "oga")}
        if set(names) != expected or len(names) != 6:
            raise AssertionError("Task #56 regression: Korean Hangul targets dropped or invalid titles queried; "
                                 + repr({"actual": names, "expected": sorted(expected)}))
        if report.get("titlesQueried") != 6 or report.get("listeningApproved") is not False:
            raise AssertionError("Task #56 report must preserve all six candidates without approving audio")
        if report.get("failedBatches"):
            raise AssertionError("Mocked source lookup should not have failed")
        print("PASS: #56 six Hangul candidate titles, malicious title excluded, no listening approval")

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--source", required=True)
    args = p.parse_args()
    check(Path(args.source).resolve())
