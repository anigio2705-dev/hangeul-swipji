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
node = r'''const fs=require('fs'),vm=require('vm');const c={window:{addEventListener(){}},document:{addEventListener(){},dispatchEvent(){}},Event:function(){},fetch:async()=>({ok:true,json:async()=>({recordings:{}})})};vm.createContext(c);for(const f of ['hangul-core.js','hangul-week-data.js'])vm.runInContext(fs.readFileSync(f,'utf8'),c);const h=c.window.HSHangul;console.log(JSON.stringify({consonants:h.consonants,vowels:h.vowels,blocks:h.consonants.flatMap(([a])=>h.vowels.map(([b])=>h.compose(a,b))),days:c.window.HSWeek}));'''
data = json.loads(subprocess.check_output(['node', '-e', node], cwd=ROOT))
manifest_path = ROOT / 'hangul-audio-manifest.json'
if not manifest_path.is_file():
    raise FileNotFoundError(f"Manifest file not found: {manifest_path}")
manifest = json.loads(manifest_path.read_text())
names = {c: n for c, n, _ in data['consonants']}
vowels = dict(data['vowels'])
targets = {}

def add(word, group, label=None):
    if not isinstance(word, str):
        # Skip non-string words
        return
    sound = names.get(word, vowels.get(word, word))
    item = targets.setdefault(sound, {'text': sound, 'groups': [], 'labels': []})
    if group not in item['groups']:
        item['groups'].append(group)
    label_to_add = label or word
    if label_to_add not in item['labels']:
        item['labels'].append(label_to_add)

for c, name, _ in data['consonants']:
    if not isinstance(c, str):
        continue
    add(c, '\uc790\uc74c \uc774\ub984', c + ' \u00b7 ' + name)
for v, sound in data['vowels']:
    if not isinstance(v, str):
        continue
    add(v, '\ubaa8\uc74c', v + ' \u00b7 ' + sound)
for word in data['blocks']:
    if not isinstance(word, str):
        continue
    add(word, '\uae00\uc790\ud310 \uc74c\uc808')
for day in data['days']:
    if not isinstance(day, dict):
        continue
    for pair in day.get('practice', []) or []:
        if not (isinstance(pair, (list, tuple)) and len(pair) >= 1):
            continue
        word = pair[0]
        if not isinstance(word, str):
            continue
        add(day.get('meaning') if day.get('id') == 'H01' else word, '7\uc77c \uacfc\uc815')
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

for word, meta in manifest.get('recordings', {}).items():
    if not isinstance(meta, dict):
        raise ValueError(f"Invalid metadata for word: {word}")
    src = meta.get('src')
    if not isinstance(src, str):
        raise ValueError(f"Missing or invalid 'src' for word: {word}")
    file = ROOT / src
    if not file.is_file():
        raise FileNotFoundError(f"Audio file not found: {file}")

    # run ffmpeg and decode output with error handling
    try:
        raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(file), '-f', 's16le', '-ac', '1', '-ar', '16000', '-'], stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffmpeg failed on file {file} with error: {e.output.decode(errors='replace')}") from e

    samples = array.array('h')
    try:
        samples.frombytes(raw)
    except Exception as e:
        raise ValueError(f"Failed to decode audio raw data for {file}") from e

    if len(samples) == 0:
        raise ValueError(f"Decoded audio has zero length for {file}")

    peak = max((abs(x) for x in samples), default=0)
    rms = math.sqrt(sum(x * x for x in samples) / max(1, len(samples)))
    active = [i for i, x in enumerate(samples) if abs(x) > 184]  # approx -45 dBFS
    lead = active[0] / 16000 if active else len(samples) / 16000
    tail = (len(samples) - 1 - active[-1]) / 16000 if active else lead
    duration = len(samples) / 16000
    warnings = []
    if not active:
        warnings.append('\ubb34\uc74c')
    if lead > .5:
        warnings.append('\uc55e \ubb34\uc74c 0.5\ucd08 \ucd08\uacfc')
    if tail > .8:
        warnings.append('\ub4a4 \ubb34\uc74c 0.8\ucd08 \ucd08\uacfc')
    if peak >= 32760:
        warnings.append('\ucd5c\ub300 \uc9c4\ud3ed \ud655\uc778 \ud544\uc694')
    if tail < .02:
        warnings.append('\ub05d \uc5ec\ubc31 \ubd80\uc871: \uc798\ub9bc \uccad\ucde8 \ud655\uc778 \ud544\uc694')
    if duration < .25:
        warnings.append('\uc9e7\uc740 \ud30c\uc77c: \uc798\ub9bc \uccad\ucde8 \ud655\uc778 \ud544\uc694')
    if rms < 184:
        warnings.append('\uc791\uc740 \ud3c9\uade0 \uc74c\ub7c9')

    try:
        file_bytes = file.read_bytes()
    except Exception as e:
        raise IOError(f"Failed to read file {file}") from e
    try:
        file_hash = hashlib.sha256(file_bytes).hexdigest()
    except Exception as e:
        raise IOError(f"Failed to hash file {file}") from e

    if file_hash != meta.get('sha256'):
        raise ValueError(f"SHA256 hash mismatch for {word}")

    kind = meta.get('kind', 'human')
    if kind == 'synthetic':
        inputText = meta.get('inputText')
        modelRevision = meta.get('modelRevision')
        if not inputText or not modelRevision:
            raise ValueError(f"Missing 'inputText' or 'modelRevision' for synthetic audio {word}")
        if inputText.rstrip('.') != word:
            raise ValueError(f"Input text does not match word for synthetic {word}")
        label_status = 'generation-input-matched; listening-pending'
    elif 'segment' in meta:
        segment = meta.get('segment', {})
        if not isinstance(segment, dict):
            raise ValueError(f"Invalid segment data for {word}")
        if segment.get('text') != word:
            raise ValueError(f"Segment text does not match word for {word}")
        start = segment.get('start')
        end = segment.get('end')
        if not (isinstance(start, (int, float)) and isinstance(end, (int, float)) and 0 <= start < end):
            raise ValueError(f"Invalid segment start/end for {word}")
        label_status = 'segment-alignment-provisional; listening-pending'
    else:
        sourceTitle = meta.get('sourceTitle')
        if not isinstance(sourceTitle, str):
            raise ValueError(f"Invalid or missing sourceTitle for {word}")
        prefix_removed = sourceTitle.removeprefix('File:')
        main_part = prefix_removed.rsplit('.', 1)[0] if '.' in prefix_removed else prefix_removed
        if not main_part.endswith(word):
            raise ValueError(f"sourceTitle does not end with word for {word}")
        label_status = 'source-title-matched'

    author = meta.get('author')
    licenseUrl = meta.get('licenseUrl')
    sourceUrl = meta.get('sourceUrl')
    if not (isinstance(author, str) and isinstance(licenseUrl, str) and isinstance(sourceUrl, str)):
        raise ValueError(f"Missing or invalid required metadata (author/licenseUrl/sourceUrl) for {word}")

    recordings.append({'text': word, 'src': src, 'duration': round(duration, 3),
        'peakDbfs': round(20 * math.log10(max(1, peak) / 32768), 2),
        'rmsDbfs': round(20 * math.log10(max(1, rms) / 32768), 2),
        'leadingSilence': round(lead, 3), 'trailingSilence': round(tail, 3),
        'signalWarnings': warnings, 'alignmentObserved': meta.get('segment',{}).get('observedText',''), 'kind': kind, 'labelStatus': meta.get('labelStatus', label_status), 'stage1Candidate': bool(meta.get('stage1Candidate')), 'stage2Candidate': bool(meta.get('stage2Candidate')), 'holdReason': meta.get('holdReason', ''),
        'sourceUrl': sourceUrl, 'license': meta.get('license', ''),
        'held': bool(meta.get('disabled')), 'technicalStatus': 'decoded-and-hash-checked', 'listeningStatus': 'pending'})

for word, item in targets.items():
    recs = manifest.get('recordings', {})
    item['recordingAvailable'] = word in recs
    item['playbackAvailable'] = item['recordingAvailable'] and not recs.get(word, {}).get('disabled', False)
    item['listeningStatus'] = 'pending' if item['recordingAvailable'] else 'no-recording'
    if item['recordingAvailable']:
        item['src'] = recs[word].get('src', '')

report = {'version': '20261026-human-only', 'scope': '\uae00\uc790\ud310\u00b77\uc77c \uacfc\uc815\u00b7\uc785\ubb38 50\ub2e8\uc6d0\uc758 \uc7ac\uc0dd \ub300\uc0c1',
    'note': '\ud30c\uc77c\u00b7\ubb38\uc790 \uc5f0\ucb60 \uac80\uc0ac\ub294 \uc2e4\uc81c \uc18c\ub9ac\uc758 \uc815\ud655\uc131\uc774\ub098 \uc798\ub9bc \uc5ec\ubd80\ub97c \uccad\ucde8 \uc2b9\uc778\ud55c \uac83\uc774 \uc544\ub2d9\ub2c8\ub2e4. \uae30\uae30 TTS\ub294 \uc74c\uc131\uc774 \ub2ec\ub77c \uc804\uc218 \ud488\uc9c8 \uc778\uc99d \ub300\uc0c1\uc774 \ub420 \uc218 \uc5c6\uc2b5\ub2c8\ub2e4.',
    'counts': {'targets': len(targets), 'available': sum(x['recordingAvailable'] for x in targets.values()),
        'missing': sum(not x['recordingAvailable'] for x in targets.values()), 'decodedFiles': len(recordings),
        'playbackAvailable': sum(x['playbackAvailable'] for x in targets.values()),
        'humanFiles': sum(x.get('kind','human') == 'human' for x in manifest.get('recordings', {}).values()),
        'syntheticFiles': sum(x.get('kind') == 'synthetic' for x in manifest.get('recordings', {}).values()),
        'excludedSynthetic': len(manifest.get('retiredSynthetic',{})),
        'held': sum(bool(x.get('disabled')) for x in manifest.get('recordings', {}).values()), 'listeningApproved': 0, 'signalWarnings': sum(bool(x['signalWarnings']) for x in recordings)},
    'week': {'targets': sum('7\uc77c \uacfc\uc815' in x['groups'] for x in targets.values()), 'available': sum('7\uc77c \uacfc\uc815' in x['groups'] and x['recordingAvailable'] for x in targets.values()), 'missing': sum('7\uc77c \uacfc\uc815' in x['groups'] and not x['recordingAvailable'] for x in targets.values()), 'listeningApproved': 0},
    'recordings': recordings, 'targets': list(targets.values())}

output_path = ROOT / 'hangul-audio-audit.json'
output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

print(json.dumps(report['counts'], ensure_ascii=False))
for x in recordings:
    if x['signalWarnings']:
        print(x['text'], ', '.join(x['signalWarnings']))
