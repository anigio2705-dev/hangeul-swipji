def classify_inventory(manifest, targets):
    """Classify recordings without modifying inputs or approving pronunciation."""
    import re

    recordings = manifest.get("recordings", manifest) if isinstance(manifest, dict) else manifest
    if isinstance(recordings, list):
        recordings = {
            entry["text"]: entry
            for entry in recordings
            if isinstance(entry, dict) and isinstance(entry.get("text"), str)
        }
    if not isinstance(recordings, dict):
        recordings = {}

    items = []
    counts = {"total": 0, "ready": 0, "held": 0, "invalid": 0, "missing": 0}
    for text in targets:
        recording = recordings.get(text)
        quality = "pending"
        if recording is None:
            state = "missing"
            quality = "no-recording"
        elif not isinstance(recording, dict):
            state = "invalid"
        elif recording.get("disabled") is True or recording.get("enabled") is False:
            state = "held"
        else:
            src = recording.get("src")
            human = recording.get("type", recording.get("kind")) == "human"
            provenance = all(
                isinstance(recording.get(field), str) and recording[field].strip()
                for field in ("author", "sourceUrl", "license")
            )
            valid_src = isinstance(src, str) and re.fullmatch(
                r"\./assets/hangul-audio/[\w-]+\.mp3", src
            ) is not None
            state = "ready" if human and valid_src and provenance else "invalid"
        items.append({"text": text, "state": state, "quality": quality})
        counts["total"] += 1
        counts[state] += 1
    return {"items": items, "counts": counts}
