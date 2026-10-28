#!/usr/bin/env python3
"""Bounded Commons discovery for missing *human* Hangul syllables.

Only creates a provenance-review queue. Never downloads, publishes, or
claims that a candidate is human-verified or listening-approved.
"""
import argparse
import html
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://commons.wikimedia.org/w/api.php"
PRIORITY = ("고", "노", "누", "도", "라", "마", "바", "자", "카", "타", "파", "하")
LICENSES = {"CC0", "CC BY 4.0", "CC BY-SA 4.0", "CC BY 3.0", "CC BY-SA 3.0"}


def exact_target(title, character):
    """Exclude unrelated words, partial matches, and arbitrary uploads."""
    if not isinstance(title, str):
        return False
    suffix = re.escape(character)
    return bool(re.fullmatch(r"File:Ko-" + suffix + r"\.(ogg|oga|wav)", title)
                or re.fullmatch(r"File:LL-Q9176 \(kor\)-[^/]+-" + suffix + r"\.(ogg|oga|wav)", title))


def candidate(page, character):
    if not exact_target(page.get("title"), character):
        return None
    info = (page.get("imageinfo") or [{}])[0]
    meta = info.get("extmetadata") or {}
    license_name = meta.get("LicenseShortName", {}).get("value", "")
    url = info.get("url", "")
    page_url = info.get("descriptionurl", "")
    if (license_name not in LICENSES
            or not url.startswith("https://upload.wikimedia.org/")
            or not page_url.startswith("https://commons.wikimedia.org/")):
        return None
    artist = re.sub(r"<[^>]+>", "", html.unescape(meta.get("Artist", {}).get("value", ""))).strip()
    if not artist:
        return None
    return {"character": character, "title": page["title"], "source_url": page_url,
            "download_url": url, "author": artist, "license": license_name,
            "license_url": meta.get("LicenseUrl", {}).get("value", ""),
            "status": "LICENSE_CANDIDATE_NOT_LISTENING_APPROVED",
            "required_action": "Verify spoken syllable, speaker provenance, license attribution, and playback before importing"}


def query_commons(character, opener=urllib.request.urlopen, timeout=12):
    params = {"action": "query", "format": "json", "generator": "search",
              "gsrsearch": 'intitle:"' + character + '" filetype:audio',
              "gsrnamespace": 6, "gsrlimit": 30, "prop": "imageinfo",
              "iiprop": "url|extmetadata"}
    request = urllib.request.Request(API + "?" + urllib.parse.urlencode(params),
        headers={"User-Agent": "HangeulSwipjiHumanAudioAudit/1.1 (https://github.com/anigio2705-dev/hangeul-swipji)"})
    with opener(request, timeout=timeout) as response:
        data = json.load(response)
    if "error" in data:
        raise ValueError("Commons API returned an error")
    pages = (data.get("query") or {}).get("pages") or {}
    return [item for page in pages.values() if (item := candidate(page, character))]


def discover(inventory, max_targets=12, query=query_commons):
    if not 1 <= max_targets <= 40:
        raise ValueError("bounded target count required")
    entries = inventory["recording_inventory"]
    missing = {item["character"] for item in entries if item["status"] == "missing"}
    ordered = [ch for ch in PRIORITY if ch in missing]
    ordered += [item["character"] for item in entries
                if item["character"] in missing and item["character"] not in PRIORITY]
    targets = ordered[:max_targets]
    results, errors = [], []
    for ch in targets:
        try:
            results.extend(query(ch))
        except (OSError, ValueError, KeyError, TimeoutError) as exc:
            errors.append({"character": ch, "error": type(exc).__name__})
    return {"inventory_missing": len(missing), "searched": targets,
            "candidate_count": len(results), "candidates": results,
            "failed_queries": errors, "new_recordings_imported": 0,
            "listening_approved": 0, "note": "Search candidates only; never enable playback from this report."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-targets", type=int, default=12)
    args = parser.parse_args()
    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    result = discover(inventory, args.max_targets)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"searched": len(result["searched"]), "candidate_count": result["candidate_count"],
                      "failed_queries": len(result["failed_queries"]), "imported": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
