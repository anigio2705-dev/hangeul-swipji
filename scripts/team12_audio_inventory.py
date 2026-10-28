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

    try:
        manifest_text = manifest_path.read_text(encoding="utf-8")
    except Exception as e:
        raise IOError(f"Failed to read manifest file: {manifest_path}, error: {e}")

    try:
        manifest = json.loads(manifest_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in manifest file: {e}")

    if not isinstance(manifest, dict):
        raise ValueError("Manifest file root must be a JSON object")

    records = manifest.get("recordings")
    if not isinstance(records, dict):
        raise ValueError("Manifest 'recordings' entry missing or invalid")

    problems, inventory = [], []
    # Path regex must match exactly relative path starting with './assets/hangul-audio/'
    # Strict pattern: ./assets/hangul-audio/<filename>.mp3 with filename [a-zA-Z0-9_-]+ only
    path_regex = re.compile(r"\./assets/hangul-audio/[a-zA-Z0-9\-_]+\.mp3$")

    root_resolved = root.resolve(strict=False)

    for word, entry in records.items():
        if not isinstance(word, str) or not isinstance(entry, dict):
            problems.append({"word": word, "issue": "invalid_record_entry"})
            continue

        src = entry.get("src", "")
        # Use safe regex matching for valid path
        if not isinstance(src, str) or not path_regex.fullmatch(src):
            problems.append({"word": word, "issue": "invalid_source_path", "path": src})
            continue

        # Immediate escape for extremely long src
        if len(src) > 260:
            problems.append({"word": word, "issue": "source_path_too_long", "path": src})
            continue

        # Normalize and validate src path to prevent path traversal
        try:
            # Must start exactly with './'
            if not src.startswith("./"):
                problems.append({"word": word, "issue": "source_path_missing_dot_slash", "path": src})
                continue

            # clean src removing leading './'
            cleaned_src = src[2:]

            # Prevent suspicious path components like .. or empty parts (including //)
            parts = cleaned_src.split('/')
            if any(p == '..' or p == '' for p in parts):
                problems.append({"word": word, "issue": "path_contains_invalid_components", "path": src})
                continue

            # Prevent absolute path use
            if Path(cleaned_src).is_absolute():
                problems.append({"word": word, "issue": "path_is_absolute", "path": src})
                continue

            # Reject paths with symbolic links in components within root
            src_path = (root / cleaned_src).resolve(strict=False)

            # root_resolved may not exist, check by parts prefix
            # Ensure src_path is inside root directory
            try:
                # Use parts comparison for robustness
                if not src_path.is_absolute():
                    problems.append({"word": word, "issue": "path_not_absolute_after_resolve", "path": src})
                    continue

                root_parts = root_resolved.parts
                src_parts = src_path.parts

                if len(src_parts) < len(root_parts) or src_parts[:len(root_parts)] != root_parts:
                    problems.append({"word": word, "issue": "invalid_path_outside_root", "path": src})
                    continue

                # Check for any '..' after resolve (should not happen, but extra safety)
                if '..' in src_parts:
                    problems.append({"word": word, "issue": "resolved_path_contains_parent", "path": src})
                    continue

                # Additional check to deny any symlink components on resolved path parts inside root
                # Slightly slower but more secure
                current_path = root_resolved
                # We check path components after root_parts
                for part in src_parts[len(root_parts):]:
                    current_path = current_path / part
                    try:
                        # is_symlink call can raise if broken symlink
                        if current_path.is_symlink():
                            problems.append({"word": word, "issue": "path_component_is_symlink", "path": str(current_path)})
                            raise StopIteration  # break outer loops
                    except Exception:
                        # Stat failed or inaccessible
                        problems.append({"word": word, "issue": "cannot_stat_symlink_check", "path": str(current_path)})
                        raise StopIteration
            except StopIteration:
                continue
            except Exception as ex:
                problems.append({"word": word, "issue": "invalid_path_outside_root_check_failed", "path": src, "detail": str(ex)})
                continue

            # Extra check, path must start with root/assets/hangul-audio
            rel_path = None
            try:
                rel_path = src_path.relative_to(root_resolved)
            except Exception:
                rel_path = None

            if rel_path is None or not str(rel_path).startswith("assets/hangul-audio/"):
                problems.append({"word": word, "issue": "invalid_path_subdir", "path": src})
                continue

            # Validate the filename component strictly
            if src_path.is_file():
                filename = src_path.name
                # Validate that filename matches the pattern exactly
                if not re.fullmatch(r"[a-zA-Z0-9\-_]+\.mp3", filename):
                    problems.append({"word": word, "issue": "invalid_filename", "filename": filename})
                    continue
            else:
                problems.append({"word": word, "issue": "file_missing", "path": src})
                continue

        except Exception as e:
            problems.append({"word": word, "issue": "invalid_path", "path": src, "detail": str(e)})
            continue

        path = root / cleaned_src

        try:
            # Prevent reading unexpectedly large files (> 100MB)
            filesize = path.stat().st_size
            if filesize > 100 * 1024 * 1024:
                problems.append({"word": word, "issue": "file_too_large", "path": src, "size": filesize})
                continue
            if filesize == 0:
                problems.append({"word": word, "issue": "file_empty", "path": src})
                continue

            # Limit read size to filesize (already known and safe)
            data_bytes = path.read_bytes()

            # Safety check: Verify data_bytes is likely a valid mp3 header (not foolproof but better than nothing)
            if len(data_bytes) < 10 or not (data_bytes.startswith(b'ID3') or (data_bytes[0] & 0xFF) == 0xFF):
                problems.append({"word": word, "issue": "invalid_file_content", "path": src})
                continue
        except Exception as e:
            problems.append({"word": word, "issue": "file_read_error", "path": src, "detail": str(e)})
            continue

        digest = hashlib.sha256(data_bytes).hexdigest()
        if entry.get("sha256"):
            sha256_val = entry.get("sha256")
            if not isinstance(sha256_val, str) or len(sha256_val) != 64 or not re.fullmatch(r"[a-fA-F0-9]{64}", sha256_val):
                problems.append({"word": word, "issue": "invalid_sha256_format", "path": src})
            elif digest != sha256_val.lower():
                problems.append({"word": word, "issue": "hash_mismatch", "path": src})

        # Run ffmpeg to check for decode errors
        try:
            probe = subprocess.run([
                "ffmpeg", "-v", "error", "-i", str(path), "-f", "null", "-"
            ], capture_output=True, text=True, timeout=10)
            # Treat non-zero exit code and stderr as decode failure
            if probe.returncode != 0 or probe.stderr.strip():
                problems.append({"word": word, "issue": "decode_failed", "path": src, "detail": probe.stderr[:300]})
        except subprocess.SubprocessError as e:
            problems.append({"word": word, "issue": "ffmpeg_error", "path": src, "detail": str(e)})

        if entry.get("kind") != "human":
            problems.append({"word": word, "issue": "not_verified_human", "path": src})

        for key in ("sourceUrl", "author", "license"):
            val = entry.get(key)
            if not isinstance(val, str) or not val.strip():
                problems.append({"word": word, "issue": "missing_provenance", "path": src})
                break

    # Prepare inventory for 399 syllables
    for i, c in enumerate(CONSONANTS):
        for j, v in enumerate(VOWELS):
            # Compose Hangul syllable code point
            cp = 0xAC00 + (i * 21 + j) * 28
            # Validate cp is valid (within Unicode Hangul Syllables block)
            if cp > 0xD7A3:
                continue
            word = chr(cp)
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
        # Ensure only string error message is dumped
        err_msg = str(e) if e else "Unknown error"
        print(json.dumps({"error": err_msg}))
        raise SystemExit(1)

    data = json.dumps(result, ensure_ascii=False, indent=2)

    if args.output:
        try:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(data + "\n", encoding="utf-8")
        except Exception as e:
            print(json.dumps({"error": f"Failed writing output file: {e}"}))
            raise SystemExit(1)

    print(json.dumps({
        "counts": result["counts"],
        "file_issues": result["file_issues"],
        "browser_playback": result["browser_playback"]
    }, ensure_ascii=False))

    raise SystemExit(bool(result["file_issues"]))
