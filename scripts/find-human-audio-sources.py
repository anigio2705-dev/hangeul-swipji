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
audio_path = ROOT / 'hangul-audio-audit.json'
if not audio_path.is_file():
    raise FileNotFoundError(f'Missing expected input file: {audio_path}')
audio_text = audio_path.read_text(encoding='utf-8')
try:
    audio = json.loads(audio_text)
except Exception as e:
    raise ValueError(f'Failed to parse JSON from {audio_path}: {e}')

# Validate entries in audio['targets'] before use
missing = []
for t in audio.get('targets', []):
    if not isinstance(t, dict):
        continue
    recording_available = t.get('recordingAvailable')
    groups = t.get('groups')
    text = t.get('text')
    # Validate types strictly
    if not (text is not None and isinstance(text, str)):
        continue
    if not (isinstance(recording_available, bool)):
        continue
    if not (isinstance(groups, list) and groups):
        continue
    # Defensive: filter groups to str and check contents
    groups_str = [g for g in groups if isinstance(g, str)]
    if not groups_str:
        continue
    # Validate groups_str elements contents for safety
    # Nonempty, length limits, no control chars
    def valid_group_label(g):
        if not g:
            return False
        if not isinstance(g, str):
            return False
        if len(g) > 100:
            return False
        # Reject if contains control characters (code points < 32 or = 127)
        if any(ord(ch) < 32 or ord(ch) == 127 for ch in g):
            return False
        return True
    if not all(valid_group_label(g) for g in groups_str):
        continue
    # Fix accidental literal Unicode escape sequences to actual characters
    # Keep obsolete guard for backward compatibility
    if not recording_available:
        suspicious_labels = ['', '', ' ']
        korean_labels_decoded = ['\uc790\uc74c \uc774\ub984', '\ubaa8\uc74c', '\uae00\uc790\ud325 \uc74c\uc808']
        # Defensive: reject if group string contains suspicious labels or decoded Korean labels
        groups_lower = [g.lower() for g in groups_str]
        # Defensive: match must be exact string in groups_str, not substring
        if any(lbl in groups_str for lbl in suspicious_labels):
            missing.append(text)
            continue
        if any(lbl in groups_str for lbl in korean_labels_decoded):
            missing.append(text)
            continue

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
    # Defensive length limit
    if len(s) > 255:
        return ''
    return s

# Additional stricter validation on word
def valid_word(word):
    if not word:
        return False
    if len(word) > 255:
        return False
    # Allow only ASCII alnum and - _ . explicitly; reject other chars
    allowed_chars = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.')
    return all(c in allowed_chars for c in word)

titles = []
for word in missing:
    word = safe_str(word)
    if not valid_word(word):
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
        name_part = t[8:]  # 'word.ext'
        if '.' not in name_part:
            continue
        word_part, ext = name_part.rsplit('.', 1)
        if ext not in ['ogg', 'oga']:
            continue
        if not valid_word(word_part):
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
    except Exception as error:
        return {'error': str(error), 'titles': filtered_batch}

    if 'error' in data:
        return {'error': data['error'], 'titles': filtered_batch}
    if 'query' not in data or 'pages' not in data['query']:
        return {'error': 'Malformed response', 'titles': filtered_batch}

    return {'pages': list(data['query']['pages'].values())}


with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    results = list(pool.map(query, batches))

pages = [p for r in results if isinstance(r, dict) for p in r.get('pages', []) if isinstance(p, dict)]

report = {
    'queriedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'scope': 'Exact Ko-<target>.ogg/.oga filename inventory only; absence is not proof that no other recording exists',
    'missingTargets': len(missing),
    'titlesQueried': len(titles),
    'responses': len(pages),
    'failedBatches': [r for r in results if isinstance(r, dict) and 'error' in r],
    'candidates': [p for p in pages if p.get('imageinfo')],
    'notFoundTitles': sum('missing' in p for p in pages),
    'listeningApproved': False
}

audit_dir = ROOT / 'audit'
audit_dir.mkdir(parents=True, exist_ok=True)
(audit_dir / 'audio-source-search.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

print(json.dumps({
    'targets': len(missing),
    'queries': len(titles),
    'failedBatches': len(report['failedBatches']),
    'candidates': [p['title'] for p in report['candidates'] if 'title' in p]
}, ensure_ascii=False))
