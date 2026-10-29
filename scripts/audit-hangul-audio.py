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
manifest = json.loads((ROOT / 'hangul-audio-manifest.json').read_text())
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

for c, name, _ in data['consonants']:
    add(c, '자음 이름', c + ' · ' + name)
for v, sound in data['vowels']:
    add(v, '모음', v + ' · ' + sound)
for word in data['blocks']:
    add(word, '글자판 음절')
for day in data['days']:
    for word, meaning in day['practice']:
        add(meaning if day['id'] == 'H01' else word, '7일 과정')
for word in ['국', '산', '옷', '달', '밤', '밥', '강']:
    add(word, '기존 받침 연습')
intro = json.loads(re.search(r'const units=(\[.*?\]);', (ROOT / 'intro.html').read_text(), re.S)[1])
for unit in intro:
    for word, _ in unit['v'] + unit['sent']:
        add(word, '입문 50단원')

recordings = []
for word, meta in manifest['recordings'].items():
    file = (ROOT / meta['src']).resolve()
    if not file.is_relative_to(ROOT.resolve()) or not file.is_file():
        raise ValueError(f'Audio source missing or outside repository: {word}')
    raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(file), '-f', 's16le', '-ac', '1', '-ar', '16000', '-'])
    samples = array.array('h', raw)
    peak = max((abs(x) for x in samples), default=0)
    rms = math.sqrt(sum(x * x for x in samples) / max(1, len(samples)))
    active = [i for i, x in enumerate(samples) if abs(x) > 184]  # approx -45 dBFS
    lead = active[0] / 16000 if active else len(samples) / 16000
    tail = (len(samples) - 1 - active[-1]) / 16000 if active else lead
    duration = len(samples) / 16000
    warnings = []
    if not active:
        warnings.append('무음')
    if lead > .5:
        warnings.append('앞 무음 0.5초 초과')
    if tail > .8:
        warnings.append('뒤 무음 0.8초 초과')
    if peak >= 32760:
        warnings.append('최대 진폭 확인 필요')
    if tail < .02:
        warnings.append('끝 여백 부족: 잘림 청취 확인 필요')
    if duration < .25:
        warnings.append('짧은 파일: 잘림 청취 확인 필요')
    if rms < 184:
        warnings.append('작은 평균 음량')
    assert hashlib.sha256(file.read_bytes()).hexdigest() == meta['sha256'], word
    kind = meta.get('kind', 'human')
    if kind == 'synthetic':
        assert meta['inputText'].rstrip('.') == word and meta['modelRevision'], word
        label_status = 'generation-input-matched; listening-pending'
    elif 'segment' in meta:
        assert meta['segment']['text'] == word and 0 <= meta['segment']['start'] < meta['segment']['end'], word
        label_status = 'segment-alignment-provisional; listening-pending'
    else:
        assert meta['sourceTitle'].removeprefix('File:').rsplit('.', 1)[0].endswith(word), word
        label_status = 'source-title-matched'
    assert meta['author'] and meta['licenseUrl'] and meta['sourceUrl'], word
    recordings.append({'text': word, 'src': meta['src'], 'duration': round(duration, 3),
        'peakDbfs': round(20 * math.log10(max(1, peak) / 32768), 2),
        'rmsDbfs': round(20 * math.log10(max(1, rms) / 32768), 2),
        'leadingSilence': round(lead, 3), 'trailingSilence': round(tail, 3),
        'signalWarnings': warnings, 'alignmentObserved': meta.get('segment',{}).get('observedText',''), 'kind': kind, 'labelStatus': meta.get('labelStatus', label_status), 'stage1Candidate': bool(meta.get('stage1Candidate')), 'stage2Candidate': bool(meta.get('stage2Candidate')), 'holdReason': meta.get('holdReason', ''),
        'sourceUrl': meta['sourceUrl'], 'license': meta['license'],
        'held': bool(meta.get('disabled')), 'technicalStatus': 'decoded-and-hash-checked', 'listeningStatus': 'pending'})
for word, item in targets.items():
    item['recordingAvailable'] = word in manifest['recordings']
    item['playbackAvailable'] = item['recordingAvailable'] and not manifest['recordings'][word].get('disabled', False)
    item['listeningStatus'] = 'pending' if item['recordingAvailable'] else 'no-recording'
    if item['recordingAvailable']:
        item['src'] = manifest['recordings'][word]['src']
report = {'version': '20261026-human-only', 'scope': '글자판·7일 과정·입문 50단원의 재생 대상',
    'note': '파일·문자 연결 검사는 실제 소리의 정확성이나 잘림 여부를 청취 승인한 것이 아닙니다. 기기 TTS는 음성이 달라 전수 품질 인증 대상이 될 수 없습니다.',
    'counts': {'targets': len(targets), 'available': sum(x['recordingAvailable'] for x in targets.values()),
        'missing': sum(not x['recordingAvailable'] for x in targets.values()), 'decodedFiles': len(recordings),
        'playbackAvailable': sum(x['playbackAvailable'] for x in targets.values()),
        'humanFiles': sum(x.get('kind','human') == 'human' for x in manifest['recordings'].values()),
        'syntheticFiles': sum(x.get('kind') == 'synthetic' for x in manifest['recordings'].values()),
        'excludedSynthetic': len(manifest.get('retiredSynthetic',{})),
        'held': sum(bool(x.get('disabled')) for x in manifest['recordings'].values()), 'listeningApproved': 0, 'signalWarnings': sum(bool(x['signalWarnings']) for x in recordings)},
    'week': {'targets': sum('7일 과정' in x['groups'] for x in targets.values()), 'available': sum('7일 과정' in x['groups'] and x['recordingAvailable'] for x in targets.values()), 'missing': sum('7일 과정' in x['groups'] and not x['recordingAvailable'] for x in targets.values()), 'listeningApproved': 0},
    'recordings': recordings, 'targets': list(targets.values())}
(ROOT / 'hangul-audio-audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(report['counts'], ensure_ascii=False))
for x in recordings:
    if x['signalWarnings']:
        print(x['text'], ', '.join(x['signalWarnings']))
