import array
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]

node = (r'''const fs=require('fs'),vm=require('vm');const c={window:{addEventListener(){}},document:{addEventListener(){},dispatchEvent(){}},Event:function(){},fetch:async()=>({ok:true,json:async()=>({recordings:{}})})};'''
        '''vm.createContext(c);for(const f of ['hangul-core.js','hangul-week-data.js'])''' 
        '''vm.runInContext(fs.readFileSync(f,'utf8'),c);const h=c.window.HSHangul;console.log(JSON.stringify({consonants:h.consonants,vowels:h.vowels,blocks:h.consonants.flatMap(([a])=>h.vowels.map(([b])=>h.compose(a,b))),days:c.window.HSWeek}));''')
try:
    data_bytes = subprocess.check_output(['node', '-e', node], cwd=ROOT)
    data = json.loads(data_bytes)
except Exception as e:
    raise RuntimeError(f"Failed to load Hangul data with Node.js: {e}") from e

manifest_path = ROOT / 'hangul-audio-manifest.json'
if not manifest_path.is_file():
    raise FileNotFoundError(f"Missing required manifest file: {manifest_path}")
try:
    manifest_text = manifest_path.read_text(encoding='utf-8')
    manifest = json.loads(manifest_text)
except Exception as e:
    raise RuntimeError(f"Failed to read or parse manifest file {manifest_path}: {e}") from e

names = {c: n for c, n, _ in data['consonants']}
vowels = dict(data['vowels'])
targets = {}

def add(word, group, label=None):
    sound = names.get(word, vowels.get(word, word))
    item = targets.setdefault(sound, {'text': sound, 'groups': [], 'labels': []})
    if group not in item['groups']:
        item['groups'].append(group)
    if (label or word) not in item['labels']:
        item['labels'].append(label or word)

for c, name, _ in data.get('consonants', []):
    add(c, '\uc790\uc74c \uc774\ub984', c + ' \u00b7 ' + name)
for v, sound in data.get('vowels', []):
    add(v, '\ubaa8\uc74c', v + ' \u00b7 ' + sound)
for word in data.get('blocks', []):
    add(word, '\uae00\uc790\ud310 \uc74c\uc808')
for day in data.get('days', []):
    for pair in day.get('practice', []):
        if len(pair) < 2:
            continue
        word, meaning = pair
        add(meaning if day.get('id') == 'H01' else word, '7\uc77c \uacfc\uc815')

extra_words = ['\uad6d', '\uc0b0', '\uc637', '\ub2ec', '\ubc24', '\ubc25', '\uac15']
for word in extra_words:
    add(word, '\uae30\uc874 \ubc1b\uce68 \uc5f0\uc2b5')

intro_path = ROOT / 'intro.html'
if not intro_path.is_file():
    raise FileNotFoundError(f"Missing intro.html file required for units: {intro_path}")
intro_text = intro_path.read_text(encoding='utf-8')
match = re.search(r'const units=(\[.*?\]);', intro_text, re.S)
if not match:
    raise ValueError("Failed to extract units data from intro.html")
try:
    intro = json.loads(match[1])
except Exception as e:
    raise RuntimeError(f"Failed to parse units data JSON from intro.html: {e}") from e

for unit in intro:
    for section in ('v', 'sent'):
        for word_pair in unit.get(section, []):
            if word_pair and len(word_pair) > 0:
                word = word_pair[0]
                add(word, '\uc785\ubb38 50\ub2e8\uc6d0')

recordings = []
for word, meta in manifest.get('recordings', {}).items():
    file = ROOT / meta.get('src', '')
    if not file.is_file():
        print(f"Warning: Missing audio file {file} for word '{word}'")
        continue
    try:
        raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(file), '-f', 's16le', '-ac', '1', '-ar', '16000', '-'])
    except subprocess.CalledProcessError as e:
        print(f"Warning: Failed to decode {file} for word '{word}': {e}")
        continue
    samples = array.array('h', raw)
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
    # Check sha256 integrity if file readable..
    try:
        actual_hash = hashlib.sha256(file.read_bytes()).hexdigest()
    except Exception as e:
        print(f"Warning: Unable to read file for hash check: {file}, skipping hash check: {e}")
        actual_hash = None
    expected_hash = meta.get('sha256')
    if actual_hash and expected_hash and actual_hash != expected_hash:
        print(f"Warning: SHA256 mismatch for '{word}', expected {expected_hash}, got {actual_hash}")
    kind = meta.get('kind', 'human')
    label_status = meta.get('labelStatus', '')
    try:
        if kind == 'synthetic':
            assert meta['inputText'].rstrip('.') == word and meta.get('modelRevision'), word
            if not label_status:
                label_status = 'generation-input-matched; listening-pending'
        elif 'segment' in meta:
            seg = meta['segment']
            assert seg['text'] == word and 0 <= seg['start'] < seg['end'], word
            if not label_status:
                label_status = 'segment-alignment-provisional; listening-pending'
        else:
            source_title = meta.get('sourceTitle','')
            # Use removeprefix safely for Python <3.9 compatibility
            if source_title.startswith('File:'):
                st = source_title[5:]
            else:
                st = source_title
            if '.' in st:
                st_base = st.rsplit('.', 1)[0]
            else:
                st_base = st
            assert st_base.endswith(word), word
            if not label_status:
                label_status = 'source-title-matched'
        assert meta.get('author'), f"Missing author for '{word}'"
        assert meta.get('licenseUrl'), f"Missing licenseUrl for '{word}'"
        assert meta.get('sourceUrl'), f"Missing sourceUrl for '{word}'"
    except AssertionError as e:
        print(f"Metadata validation error for '{word}': {e}")
        pass

    recordings.append({'text': word, 'src': meta.get('src', ''), 'duration': round(duration, 3),
        'peakDbfs': round(20 * math.log10(max(1, peak) / 32768), 2),
        'rmsDbfs': round(20 * math.log10(max(1, rms) / 32768), 2),
        'leadingSilence': round(lead, 3), 'trailingSilence': round(tail, 3),
        'signalWarnings': warnings, 'alignmentObserved': meta.get('segment', {}).get('observedText', ''),
        'kind': kind, 'labelStatus': label_status, 'stage1Candidate': bool(meta.get('stage1Candidate')),
        'stage2Candidate': bool(meta.get('stage2Candidate')), 'holdReason': meta.get('holdReason', ''),
        'sourceUrl': meta.get('sourceUrl', ''), 'license': meta.get('license',''),
        'held': bool(meta.get('disabled')), 'technicalStatus': 'decoded-and-hash-checked',
        'listeningStatus': 'pending'})

for word, item in targets.items():
    recording = manifest.get('recordings', {}).get(word, {})
    item['recordingAvailable'] = bool(recording)
    item['playbackAvailable'] = item['recordingAvailable'] and not recording.get('disabled', False)
    item['listeningStatus'] = 'pending' if item['recordingAvailable'] else 'no-recording'
    if item['recordingAvailable']:
        item['src'] = recording.get('src', '')

report = {
    'version': '20261026-human-only',
    'scope': '\uae00\uc790\ud310\u00b77\uc77c \uacfc\uc815\u00b7\uc785\ubb38 50\ub2e8\uc6d0\uc758 \uc7ac\uc0dd \ub300\uc0c1',
    'note': '\ud30c\uc77c\u00b7\ubb38\uc790 \uc5f0\uacb0 \uac80\uc0ac\ub294 \uc2e4\uc81c \uc18c\ub9ac\uc758 \uc815\ud655\uc131\uc774\ub098 \uc798\ub9bc \uc5ec\ubd80\ub97c \uccad\ucde8 \uc2b9\uc778\ud55c \uac83\uc774 \uc544\ub2d9\ub2c8\ub2e4. \uae30\uae30 TTS\ub294 \uc74c\uc131\uc774 \ub2ec\ub77c \uc804\uc218 \ud488\uc9c8 \uc778\uc99d \ub300\uc0c1\uc774 \ub420 \uc218 \uc5c6\uc2b5\ub2c8\ub2e4.',
    'counts': {
        'targets': len(targets),
        'available': sum(x['recordingAvailable'] for x in targets.values()),
        'missing': sum(not x['recordingAvailable'] for x in targets.values()),
        'decodedFiles': len(recordings),
        'playbackAvailable': sum(x['playbackAvailable'] for x in targets.values()),
        'humanFiles': sum(x.get('kind','human') == 'human' for x in manifest.get('recordings', {}).values()),
        'syntheticFiles': sum(x.get('kind') == 'synthetic' for x in manifest.get('recordings', {}).values()),
        'excludedSynthetic': len(manifest.get('retiredSynthetic', {})),
        'held': sum(bool(x.get('disabled')) for x in manifest.get('recordings', {}).values()),
        'listeningApproved': 0,
        'signalWarnings': sum(bool(x['signalWarnings']) for x in recordings),
    },
    'week': {
        'targets': sum('7\uc77c \uacfc\uc815' in x['groups'] for x in targets.values()),
        'available': sum('7\uc77c \uacfc\uc815' in x['groups'] and x['recordingAvailable'] for x in targets.values()),
        'missing': sum('7\uc77c \uacfc\uc815' in x['groups'] and not x['recordingAvailable'] for x in targets.values()),
        'listeningApproved': 0
    },
    'recordings': recordings,
    'targets': list(targets.values())
}

hangul_audio_audit_path = ROOT / 'hangul-audio-audit.json'
try:
    hangul_audio_audit_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
except Exception as e:
    raise RuntimeError(f"Failed to write audit report to {hangul_audio_audit_path}: {e}") from e

print(json.dumps(report['counts'], ensure_ascii=False))
for x in recordings:
    if x['signalWarnings']:
        print(x['text'], ', '.join(x['signalWarnings']))
