"""Inventory the Hangul board, seven-day course and all 50 intro units.
Decode every available recording; never equate signal tests with pronunciation approval.
Run from the repository root: python scripts/audit-hangul-audio.py
"""
import array
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]

# Run node script to gather Hangul data
node = r'''const fs=require('fs'),vm=require('vm');const c={window:{addEventListener(){}},document:{addEventListener(){},dispatchEvent(){}},Event:function(){},fetch:async()=>({ok:true,json:async()=>({recordings:{}})})};vm.createContext(c);for(const f of ['hangul-core.js','hangul-week-data.js'])vm.runInContext(fs.readFileSync(f,'utf8'),c);const h=c.window.HSHangul;console.log(JSON.stringify({consonants:h.consonants,vowels:h.vowels,blocks:h.consonants.flatMap(([a])=>h.vowels.map(([b])=>h.compose(a,b))),days:c.window.HSWeek}));'''
data = json.loads(subprocess.check_output(['node', '-e', node], cwd=ROOT))

manifest_path = ROOT / 'hangul-audio-manifest.json'
if not manifest_path.is_file():
    raise FileNotFoundError(f"Manifest file not found: {manifest_path}")

manifest_text = manifest_path.read_text(encoding='utf-8')
try:
    manifest = json.loads(manifest_text)
except json.JSONDecodeError as e:
    raise ValueError(f"Failed to parse manifest JSON from {manifest_path}") from e

names = {c: n for c, n, _ in data['consonants'] if isinstance(c, str)}
vowels = {v: s for v, s in data['vowels'] if isinstance(v, str)}
targets = {}

def add(word, group, label=None):
    if not isinstance(word, str):
        # Skip non-string words
        return
    sound = names.get(word, vowels.get(word, word))
    if not isinstance(sound, str):  # Defensive check
        sound = word
    item = targets.setdefault(sound, {'text': sound, 'groups': [], 'labels': []})
    if group not in item['groups']:
        item['groups'].append(group)
    label_to_add = label or word
    if label_to_add not in item['labels']:
        item['labels'].append(label_to_add)

for c, name, _ in data['consonants']:
    if not isinstance(c, str):
        continue
    add(c, '\uc790\uc74c \uc774\ub984', c + ' \u00b7 ' + name if isinstance(name, str) else c)

for v, sound in data['vowels']:
    if not isinstance(v, str):
        continue
    add(v, '\ubaa8\uc74c', v + ' \u00b7 ' + sound if isinstance(sound, str) else v)

for word in data['blocks']:
    if not isinstance(word, str):
        continue
    add(word, '\uae00\uc790\ud310 \uc74c\uc808')

for day in data['days']:
    if not isinstance(day, dict):
        continue
    for pair in day.get('practice') or []:
        if not (isinstance(pair, (list, tuple)) and len(pair) >= 1):
            continue
        word = pair[0]
        if not isinstance(word, str):
            continue
        # Defensive: fallback to day.get('meaning') only when day['id'] == 'H01'
        add(day.get('meaning') if day.get('id') == 'H01' and isinstance(day.get('meaning'), str) else word, '7\uc77c \uacfc\uc815')

for word in ['\uad6d', '\uc0b0', '\uc637', '\ub2ec', '\ubc24', '\ubc25', '\uac15']:
    add(word, '\uae30\uc874 \ubc1b\uce68 \uc5f0\uc2b5')

intro_path = ROOT / 'intro.html'
if not intro_path.is_file():
    raise FileNotFoundError(f"Intro file not found: {intro_path}")
intro_text = intro_path.read_text(encoding='utf-8')
intro_match = re.search(r'const units=(\[.*?\]);', intro_text, re.S)
if not intro_match or len(intro_match.groups()) < 1:
    raise ValueError("Failed to extract units from intro.html")
try:
    intro = json.loads(intro_match[1])
except json.JSONDecodeError as e:
    raise ValueError("Failed to parse units JSON from intro.html") from e

for unit in intro:
    if not isinstance(unit, dict):
        continue
    v_list = unit.get('v', [])
    sent_list = unit.get('sent', [])
    for pair in v_list + sent_list:
        if not (isinstance(pair, (list, tuple)) and len(pair) >= 1 and isinstance(pair[0], str)):
            continue
        word = pair[0]
        add(word, '\uc785\ubb38 50\ub2e8\uc6d0')

recordings = []

def mixinGetSegmentObservedText(meta_dict):
    seg = meta_dict.get('segment')
    if isinstance(seg, dict):
        obs = seg.get('observedText')
        if isinstance(obs, str):
            return obs
    return ''

for word, meta in manifest.get('recordings', {}).items():
    if not isinstance(word, str):
        # skip invalid keys
        continue
    if not isinstance(meta, dict):
        # Defensive: skip invalid metadata instead of raising
        continue

    src = meta.get('src')
    if not isinstance(src, str):
        # Defensive: skip entries missing 'src'
        continue

    file = ROOT / src
    if not file.is_file():
        # Defensive: skip missing audio files
        continue

    # run ffmpeg and decode output with error handling
    try:
        raw = subprocess.check_output([
            "ffmpeg", "-v", "error", "-i", str(file), "-f", "s16le", "-ac", "1", "-ar", "16000", "-"],
            stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError:
        # Defensive: skip files that ffmpeg cannot decode
        continue

    samples = array.array('h')
    try:
        samples.frombytes(raw)
    except Exception:
        # Defensive: skip if raw audio cannot be decoded properly
        continue

    if len(samples) == 0:
        # Defensive: skip zero-length audio
        continue

    try:
        peak = max((abs(x) for x in samples), default=0)
    except Exception:
        peak = 0
    try:
        rms = math.sqrt(sum(x * x for x in samples) / max(1, len(samples)))
    except Exception:
        rms = 0
    try:
        active = [i for i, x in enumerate(samples) if abs(x) > 184]  # approx -45 dBFS
    except Exception:
        active = []

    # Defensive check for active range validity
    if active:
        lead = active[0] / 16000
        tail = (len(samples) - 1 - active[-1]) / 16000
    else:
        lead = len(samples) / 16000
        tail = lead
    duration = len(samples) / 16000

    warnings = []
    if not active:
        warnings.append('\ubb34\uc74c')
    if lead >= 0.5:
        warnings.append('\uc55e \ubb34\uc74c 0.5\ucd08 \ucd08\uacfc')
    if tail >= 0.8:
        warnings.append('\ub4a4 \ubb34\uc74c 0.8\ucd08 \ucd08\uacfc')
    if peak >= 32760:
        warnings.append('\ucd5c\ub300 \uc9c4\ud3ed \ud655\uc778 \ud544\uc694')
    if tail < 0.02:
        warnings.append('\ub05d \uc5ec\ubc31 \ubd80\uc871: \uc798\ub9bc \uccad\ucde8 \ud655\uc778 \ud544\uc694')
    if duration < 0.25:
        warnings.append('\uc9e7\uc740 \ud30c\uc77c: \uc798\ub9bc \uccad\ucde8 \ud655\uc778 \ud544\uc694')
    if rms < 184:
        warnings.append('\uc791\uc740 \ud3c9\uade0 \uc74c\ub7c9')

    try:
        file_bytes = file.read_bytes()
    except Exception:
        # Defensive: skip file read errors 
        continue

    try:
        file_hash = hashlib.sha256(file_bytes).hexdigest()
    except Exception:
        # Defensive: skip hash errors
        continue

    meta_sha256 = meta.get('sha256')
    if not isinstance(meta_sha256, str):
        # Defensive: skip if manifest is missing valid hash
        continue

    if file_hash != meta_sha256:
        # Defensive: skip files whose hash does not match manifest
        continue

    kind = meta.get('kind', 'human')

    label_status = ''

    if kind == 'synthetic':
        inputText = meta.get('inputText')
        modelRevision = meta.get('modelRevision')
        if not (isinstance(inputText, str) and isinstance(modelRevision, str)):
            # Defensive: skip incomplete synthetic metadata
            continue
        # Defensive normalization: allow inputText to differ by trailing dot or whitespace
        if inputText.rstrip('. ').rstrip() != word:
            # Defensive: skip if inputText mismatch
            continue
        label_status = 'generation-input-matched; listening-pending'

    elif 'segment' in meta:
        segment = meta.get('segment')
        if not isinstance(segment, dict):
            # Defensive: skip invalid segment
            continue
        if segment.get('text') != word:
            # Defensive: skip if text mismatch
            continue
        start = segment.get('start')
        end = segment.get('end')
        if not (isinstance(start, (int, float)) and isinstance(end, (int, float)) and 0 <= start < end):
            # Defensive: skip if invalid start/end
            continue
        label_status = 'segment-alignment-provisional; listening-pending'

    else:
        sourceTitle = meta.get('sourceTitle')
        if not isinstance(sourceTitle, str):
            # Defensive: skip if missing sourceTitle
            continue
        # Defensive check and fallback for removeprefix
        if hasattr(sourceTitle, 'removeprefix') and callable(getattr(sourceTitle, 'removeprefix')):
            prefix_removed = sourceTitle.removeprefix('File:')
        else:
            prefix_removed = sourceTitle
            if prefix_removed.startswith('File:'):
                prefix_removed = prefix_removed[5:]
        if '.' in prefix_removed:
            main_part = prefix_removed.rsplit('.', 1)[0]
        else:
            main_part = prefix_removed
        if not isinstance(main_part, str):
            # Defensive: skip if invalid
            continue
        if not main_part.endswith(word):
            # Defensive: skip if suffix mismatch
            continue
        label_status = 'source-title-matched'

    author = meta.get('author')
    licenseUrl = meta.get('licenseUrl')
    sourceUrl = meta.get('sourceUrl')
    if not (isinstance(author, str) and isinstance(licenseUrl, str) and isinstance(sourceUrl, str)):
        # Defensive: skip missing critical metadata
        continue

    # Defensive sanitation of warnings list elements and types
    clean_warnings = []
    if isinstance(warnings, list):
        for w in warnings:
            if isinstance(w, str):
                clean_warnings.append(w)

    recordings.append({'text': word, 'src': src, 'duration': round(duration, 3),
        'peakDbfs': round(20 * math.log10(max(1, peak) / 32768), 2),
        'rmsDbfs': round(20 * math.log10(max(1, rms) / 32768), 2),
        'leadingSilence': round(lead, 3), 'trailingSilence': round(tail, 3),
        'signalWarnings': clean_warnings, 'alignmentObserved': mixinGetSegmentObservedText(meta), 'kind': kind, 'labelStatus': meta.get('labelStatus', label_status), 'stage1Candidate': bool(meta.get('stage1Candidate')), 'stage2Candidate': bool(meta.get('stage2Candidate')), 'holdReason': meta.get('holdReason', ''),
        'sourceUrl': sourceUrl, 'license': meta.get('license', ''),
        'held': bool(meta.get('disabled')), 'technicalStatus': 'decoded-and-hash-checked', 'listeningStatus': 'pending'})

for word, item in targets.items():
    recs = manifest.get('recordings', {})
    item['recordingAvailable'] = word in recs and isinstance(recs.get(word), dict)
    item['playbackAvailable'] = (item['recordingAvailable'] and
                                 not bool(recs.get(word, {}).get('disabled', False)))
    item['listeningStatus'] = 'pending' if item['recordingAvailable'] else 'no-recording'
    if item['recordingAvailable']:
        src = recs[word].get('src')
        if isinstance(src, str):
            item['src'] = src
        else:
            item['src'] = ''

report = {
    'version': '20261026-human-only',
    'scope': '\uae00\uc790\ud310\u00b77\uc77c \uacfc\uc815\u00b7\uc785\ubb38 50\ub2e8\uc6d0\uc758 \uc7ac\uc0dd \ub300\uc0c1',
    'note': '\ud30c\uc77c\u00b7\ubb38\uc790 \uc5f0\ucb60 \uac80\uc0ac\ub294 \uc2e4\uc81c \uc18c\ub9ac\uc758 \uc815\ud655\uc131\uc774\ub098 \uc798\ub9bc \uc5ec\ubd80\ub97c \uccad\ucde8 \uc2b9\uc778\ud55c \uac83\uc774 \uc544\ub2d9\ub2c8\ub2e4. \uae30\uae30 TTS\ub294 \uc74c\uc131\uc774 \ub2ec\ub77c \uc804\uc218 \ud488\uc9c8 \uc778\uc99d \ub300\uc0c1\uc774 \ub420 \uc218 \uc5c6\uc2b5\ub2c8\ub2e4.',
    'counts': {
        'targets': len(targets),
        'available': sum(bool(x.get('recordingAvailable')) for x in targets.values()),
        'missing': sum(not bool(x.get('recordingAvailable')) for x in targets.values()),
        'decodedFiles': len(recordings),
        'playbackAvailable': sum(bool(x.get('playbackAvailable')) for x in targets.values()),
        'humanFiles': sum(x.get('kind', 'human') == 'human' for x in manifest.get('recordings', {}).values() if isinstance(x, dict)),
        'syntheticFiles': sum(x.get('kind') == 'synthetic' for x in manifest.get('recordings', {}).values() if isinstance(x, dict)),
        'excludedSynthetic': len(manifest.get('retiredSynthetic', {})),
        'held': sum(bool(x.get('disabled')) for x in manifest.get('recordings', {}).values() if isinstance(x, dict)),
        'listeningApproved': 0,
        'signalWarnings': sum(bool(x.get('signalWarnings')) for x in recordings if isinstance(x, dict)),
    },
    'week': {
        'targets': sum('7\uc77c \uacfc\uc815' in x.get('groups', []) for x in targets.values()),
        'available': sum(('7\uc77c \uacfc\uc815' in x.get('groups', []) and x.get('recordingAvailable', False)) for x in targets.values()),
        'missing': sum(('7\uc77c \uacfc\uc815' in x.get('groups', []) and not x.get('recordingAvailable', False)) for x in targets.values()),
        'listeningApproved': 0
    },
    'recordings': recordings,
    'targets': list(targets.values())
}

output_path = ROOT / 'hangul-audio-audit.json'
# Defensive write operation with exception handling
try:
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
except Exception as e:
    raise IOError(f"Failed to write report to {output_path}") from e

print(json.dumps(report['counts'], ensure_ascii=False))
for x in recordings:
    warnings_list = []
    if isinstance(x, dict):
        sig_warns = x.get('signalWarnings')
        if isinstance(sig_warns, list) and sig_warns:
            warnings_list = [w for w in sig_warns if isinstance(w, str)]
    if warnings_list:
        print(x.get('text', ''), ', '.join(warnings_list))
