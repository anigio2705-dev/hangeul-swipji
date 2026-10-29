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

def check(source, allow_unsafe_baseline=False):
    with tempfile.TemporaryDirectory(prefix="hq56-") as temp:
        root = Path(temp)
        (root / "scripts").mkdir()
        (root / "audit").mkdir()
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
            sample = {"query": {"pages": {"123": {
                "title": "File:Ko-가.ogg",
                "imageinfo": [{"url": "https://example.invalid/recording.ogg",
                               "extmetadata": {"LicenseShortName": {"value": "CC BY-SA 4.0"},
                                               "LicenseUrl": {"value": "https://example.invalid/license"},
                                               "Artist": {"value": "Sample human speaker"}}}]
            }}}}
            return io.BytesIO(json.dumps(sample, ensure_ascii=False).encode("utf-8"))
        with patch.object(urllib.request, "urlopen", side_effect=fake_urlopen):
            runpy.run_path(str(script), run_name="__main__")
        report = json.loads((root / "audit/audio-source-search.json").read_text(encoding="utf-8"))
        names = []
        for url in urls:
            names += urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)["titles"][0].split("|")
        expected = {"File:Ko-" + word + "." + ext
                    for word in ("가", "ㄱ", "ㅏ") for ext in ("ogg", "oga")}
        if (not expected.issubset(set(names)) if allow_unsafe_baseline
            else set(names) != expected or len(names) != 6):
            raise AssertionError("Task #56 regression: Korean Hangul targets dropped or invalid titles queried; "
                                 + repr({"actual": names, "expected": sorted(expected)}))
        if (report.get("titlesQueried") != len(names) or report.get("listeningApproved") is not False
            or (not allow_unsafe_baseline and len(names) != 6)):
            raise AssertionError("Task #56 report must preserve all six candidates without approving audio")
        if report.get("failedBatches"):
            raise AssertionError("Mocked source lookup should not have failed")
        if not allow_unsafe_baseline:
            reviews = report.get("candidateReview", [])
            if len(reviews) != 1 or reviews[0].get("title") != "File:Ko-가.ogg":
                raise AssertionError("Task #56 must emit one independently reviewable source candidate")
            item = reviews[0]
            if not all(item.get(k) is True for k in ("has_license_name", "has_license_url", "has_author")):
                raise AssertionError("Task #56 candidate provenance metadata was lost")
            if item.get("review_status") != "pending_independent_license_and_listening_review":
                raise AssertionError("Task #56 must not auto-approve candidate license or listening")
            if item.get("rightsApproved") is not False or item.get("listeningApproved") is not False:
                raise AssertionError("Task #56 candidate rights and listening approval must stay false")
        print("PASS: #56 six Hangul candidate titles, malicious title excluded, no listening approval")

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--source", required=True)
    p.add_argument("--allow-unsafe-baseline", action="store_true")
    args = p.parse_args()
    check(Path(args.source).resolve(), args.allow_unsafe_baseline)
