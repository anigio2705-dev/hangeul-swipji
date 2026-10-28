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
        # Defensive: discard groups with non-str elements, filter only str
        groups_str = [g for g in groups if isinstance(g, str)]
        if (not recording_available and any(g in ['\u007f\u007f\u007f', '\u007f\u007f', '\u007f\u007f\u007f\u007f \u007f\u007f\u007f'] for g in groups_str)):
            # Original had specific Korean strings, corrected here:
            if any(g in ['\uc790\uc74c \uc774\ub984','\ubaa8\uc74c','\uae00\uc790\ud310 \uc74c\uc808'] for g in groups_str):
                missing.append(text)

# Using safe filtering to ensure titles are safe strings
def safe_str(s):
    if not isinstance(s, str):
        return ''
    # Strip whitespace and remove pipe and control characters
    s = s.strip()
    s = s.replace('|', '')
    s = s.replace('\n', '').replace('\r', '')
    # Remove any control characters
    s = ''.join(ch for ch in s if ch.isprintable())
    return s

titles = []
for word in missing:
    word = safe_str(word)
    if not word:
        continue
    # Safety check: only allow alnum and dash, underscore, dot
    if not all(c.isalnum() or c in '-_.' for c in word):
        continue
    # Defensive: reject words that are too long or empty after cleaning
    if len(word) > 255 or len(word) == 0:
        continue
    for ext in ['ogg', 'oga']:
        title = f'File:Ko-{word}.{ext}'
        titles.append(title)

batches = [titles[i:i + 50] for i in range(0, len(titles), 50)]

def query(batch):
    # Validate batch entries strictly
    filtered_batch = []
    for t in batch:
        if not isinstance(t, str):
            continue
        if not t.startswith('File:Ko-'):
            continue
        # Extract name portion and validate characters
        name_part = t[8:]  # remove 'File:Ko-'
        # name_part should be something like 'word.ext', check word part
        if '.' not in name_part:
            continue
        word_part, ext = name_part.rsplit('.', 1)
        if ext not in ['ogg', 'oga']:
            continue
        if not word_part:
            continue
        # Validate characters in word_part
        if not all(c.isalnum() or c in '-_.' for c in word_part):
            continue
        # Defensive length check
        if len(word_part) > 255 or len(word_part) == 0:
            continue
        filtered_batch.append(t)

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
