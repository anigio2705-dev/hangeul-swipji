"""Look for exact Commons file labels, never manufacture a recording or approve listening.
No downloads or manifest changes; candidates require provenance and licensing review.
"""
import concurrent.futures
import datetime
import json
from pathlib import Path
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
audio = json.loads((ROOT / 'hangul-audio-audit.json').read_text())

# Validate entries in audio['targets'] before use
missing = []
for t in audio.get('targets', []):
    if not isinstance(t, dict):
        continue
    recording_available = t.get('recordingAvailable')
    groups = t.get('groups')
    text = t.get('text')
    if (text is not None and isinstance(text, str) and
        isinstance(recording_available, bool) and
        isinstance(groups, list) and
        any(isinstance(g, str) for g in groups)):
        if (not recording_available and any(g in ['', '', ' '] or g in ['', '', ' '] for g in groups)):
            # Original had specific Korean strings, corrected here:
            if any(g in ['자음 이름','모음','글자판 음절'] for g in groups):
                missing.append(text)

# Using safe filtering to ensure titles are safe strings
def safe_str(s):
    if not isinstance(s, str):
        return ''
    return s.replace('|', '').replace('\n', '').replace('\r', '').strip()

titles = []
for word in missing:
    word = safe_str(word)
    if not word:
        continue
    for ext in ['ogg', 'oga']:
        title = f'File:Ko-{word}.{ext}'
        # Simple validation: disallow suspicious characters
        if all(c.isalnum() or c in '-_.' for c in word):
            titles.append(title)

batches = [titles[i:i + 50] for i in range(0, len(titles), 50)]

def query(batch):
    # Validate batch entries
    filtered_batch = [t for t in batch if isinstance(t, str) and t.startswith('File:Ko-')]
    if not filtered_batch:
        return {'error': 'empty or invalid batch', 'titles': batch}
    url = 'https://commons.wikimedia.org/w/api.php?' + urllib.parse.urlencode({
        'action': 'query',
        'format': 'json',
        'prop': 'imageinfo',
        'iiprop': 'url|extmetadata',
        'titles': '|'.join(filtered_batch),
    })
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'HangeulSwipjiAudioAudit/1.0 (source inventory)'})
        with urllib.request.urlopen(req, timeout=25) as response:
            data = json.load(response)
        if 'error' in data:
            return {'error': data['error'], 'titles': filtered_batch}
        return {'pages': list(data['query']['pages'].values())}
    except Exception as error:
        return {'error': str(error), 'titles': filtered_batch}

with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    results = list(pool.map(query, batches))

pages = [p for r in results for p in r.get('pages', [])]

report = {
    'queriedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'scope': 'Exact Ko-<target>.ogg/.oga filename inventory only; absence is not proof that no other recording exists',
    'missingTargets': len(missing),
    'titlesQueried': len(titles),
    'responses': len(pages),
    'failedBatches': [r for r in results if 'error' in r],
    'candidates': [p for p in pages if p.get('imageinfo')],
    'notFoundTitles': sum('missing' in p for p in pages),
    'listeningApproved': False
}

(ROOT / 'audit' / 'audio-source-search.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')

print(json.dumps({
    'targets': len(missing),
    'queries': len(titles),
    'failedBatches': len(report['failedBatches']),
    'candidates': [p['title'] for p in report['candidates'] if 'title' in p]
}, ensure_ascii=False))
