"""Render attribution and the current acquisition status from the manifest."""
import html
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
manifest_path = root / 'hangul-audio-manifest.json'

# Validate the manifest file exists and is readable
if not manifest_path.is_file():
    raise FileNotFoundError(f'Manifest file not found: {manifest_path}')

manifest_text = manifest_path.read_text(encoding='utf-8')
try:
    manifest = json.loads(manifest_text)
except json.JSONDecodeError as e:
    raise ValueError(f'Failed to parse JSON manifest: {e}') from e

entries = manifest.get('recordings', {})
if not isinstance(entries, dict):
    raise ValueError('Manifest recordings entry must be a dictionary')

human = sum(a.get('kind', 'human') == 'human' for a in entries.values())
synthetic = len(entries) - human
held = sum(bool(a.get('disabled')) for a in entries.values())
esc = html.escape
rows = []
for word, a in entries.items():
    kind_val = a.get('kind')
    if kind_val == 'synthetic':
        kind = '\ud569\uc131 \uc74c\uc131 \ud6c4\ubcf4'
    else:
        kind = '\uc0ac\ub78c \ub179\uc74c'

    state = '\uac80\uc218 \uc804 \ubcf4\ub958' if a.get('disabled') else '\uc7ac\uc0dd \uac00\ub2a5 \u00b7 \uccad\ucde8 \uc2b9\uc778 \uc804'

    author = a.get('author', '')
    source_url = a.get('sourceUrl', '#')
    license_url = a.get('licenseUrl', '#')
    license_name = a.get('license', '')

    # Sanitize all string inputs before inserting into HTML
    author_esc = esc(str(author))
    source_url_esc = esc(str(source_url))
    license_url_esc = esc(str(license_url))
    license_name_esc = esc(str(license_name))
    word_esc = esc(str(word))

    rows.append(
        f'<tr><td class="notranslate" translate="no">{word_esc}</td><td>{kind}<br>{state}</td><td>{author_esc}</td><td><a href="{source_url_esc}">\ucd9c\ucc98</a></td><td><a href="{license_url_esc}">{license_name_esc}</a></td></tr>'
    )

page = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>\uc0ac\ub78c \ub179\uc74c \ucd9c\ucc98\u00b7\uac80\uc218 \uc0c1\ud0dc | \ud55c\uae00\uc27d\uc9c0</title><link rel="stylesheet" href="./hangul-foundations.css?v=20261026-foundations"></head><body><header><div class="wrap"><a class="brand" href="./hangul-basics.html">\u2190 \uc804\uccb4 \uae00\uc790\ud310</a><a href="./hangul-week.html">7\uc77c \uacfc\uc815</a></div></header><main class="wrap"><div class="intro"><h1>\uc2e4\uc81c \uc0ac\ub78c\uc758 \ub179\uc74c\ub9cc \uc0ac\uc6a9\ud569\ub2c8\ub2e4.</h1><p>\ud569\uc131 \uc74c\uc131\uacfc \uae30\uae30 TTS\ub294 \ud55c\uae00 \uae30\ucd08 \ud559\uc2b5\u00b7\uac80\uc218 \uc7ac\uc0dd\uc5d0\uc11c \uc81c\uc678\ud588\uc2b5\ub2c8\ub2e4.</p></div><section class="panel"><h2>7\uc77c \uacfc\uc815 \uc0ac\ub78c \ub179\uc74c \ud6c4\ubcf4 51/63\uac1c</h2><p>\uae30\uc874 \uc0ac\ub78c \ub179\uc74c37\uac1c\uc5d0 \uc790\uc74c \uc774\ub984 \uc5f0\uc18d \ub179\uc74c\uc5d0\uc11c \ubd84\ub9ac\ud55c \ud6c4\ubcf414\uac1c\ub97c \ucd94\uac00\ud588\uc2b5\ub2c8\ub2e4. 12\uac1c \uae30\ubcf8 \uc74c\uc808\uc740 \uc2e4\uc81c \ub179\uc74c\uc774 \ud544\uc694\ud569\ub2c8\ub2e4. \uc0ac\ub78c\uc758 \ub179\uc74c\uc774\ub77c\ub294 \uc0ac\uc2e4\uc640 \ubc1c\uc74c\u00b7\uae00\uc790 \ub300\uc751\uc774 \ub9de\ub294\ub2e4\ub294 \uccad\ucde8 \uc2b9\uc778\uc740 \ub2e4\ub985\ub2c8\ub2e4.</p><p class="note">\uc0c8 \uc790\uc74c \uc774\ub98414\uac1c\ub294 \uc21c\uc11c\ub85c \uc784\uc2dc \ub300\uc751\ud55c \ud6c4\ubcf4\uc785\ub2c8\ub2e4. \uc2e4\uc81c \uc774\ub984\uc640 \uad6c\uac04 \uacbd\uacc4\ub97c \uad50\uc0ac\uac00 \ub4e3\uace0 \ud655\uc778\ud574\uc57c \ud569\ub2c8\ub2e4. \uc2b9\uc778 \uc804 \ud6c4\ubcf4\ub294 \uc77c\ubc18 \ud559\uc2b5 \uc7ac\uc0dd\uc744 \ubcf4\ub958\ud569\ub2c8\ub2e4. \uae30\uc874 \ud569\uc13126\uac1c\ub294 \uc0ac\uc6a9 \uc81c\uc678 \ucc98\ub9ac\ud588\uc73c\uba70 \uc0ac\uc6a9\uc790\uaed8\uc11c \uc774\uc804 \ud569\uc131 \uc74c\uc131\uc744 \uc88b\ub2e4\uace0 \ud558\uc2e0 \ub9d0\uc500\uc744 \uc2e4\uc81c \uc0ac\ub78c \ub179\uc74c\uc758 \uc2b9\uc778\uc73c\ub85c \uae30\ub85d\ud558\uc9c0 \uc54a\uc558\uc2b5\ub2c8\ub2e4.</p><p><a href="./hangul-audio-review.html?scope=week">\uc2e4\uc81c \uc0ac\ub78c \ub179\uc74c \uac80\uc218\ud45c \u2192</a></p><p>\uc804\uccb4 \uae00\uc790\ud310\u00b7\uc785\ubb38 \uc790\ub8cc\uc5d0 \ud655\ubcf4\ud55c \uc0ac\ub78c \ub179\uc74c \ud6c4\ubcf4 {human}\uac1c. \uc77c\ubc18 \ud559\uc2b5 \uc7ac\uc0dd {len(entries) - held}\uac1c / \ubcf4\ub958 {held}\uac1c. \uc804\uccb4 \uc74c\uc6d0 \ud655\ubcf4\ub098 \ubc1c\uc74c \uac80\uc218\uac00 \uc644\ub8cc\ub41c \uc0c1\ud0dc\ub294 \uc544\ub2d9\ub2c8\ub2e4.</p><h3>\ub179\uc74c\uc774 \ud544\uc694\ud55c \uae30\ubcf8 \uc74c\uc808 12\uac1c</h3><p class="notranslate" translate="no">\uace0 \u00b7 \ub178 \u00b7 \ub204 \u00b7 \ub3c4 \u00b7 \ub77c \u00b7 \ub9c8 \u00b7 \ubc14 \u00b7 \uc790 \u00b7 \uce74 \u00b7 \ud0c0 \u00b7 \ud30c \u00b7 \ud558</p><p><a href="./HUMAN-RECORDING-SCRIPT.txt">\ub179\uc74c \ub300\ubcf8</a></p></section><section class="panel"><h2>\ucd9c\ucc98\uc640 \ubcc0\uacbd \ub0b4\uc5ed</h2><p>Wikimedia Commons\uc758 \uac1c\ubcc4 \ud30c\uc77c \uc870\uac74\uc744 \ub530\ub985\ub2c8\ub2e4. MP3 \ubcc0\ud658\u00b7\uc74c\ub7c9 \uc870\uc808\u00b7\uad6c\uac04 \ubd84\ub9ac \ub0b4\uc5ed\uacfc \ud0c0\uc784\uc2a4\ud0ec\ud504\ub294 \uba85\uc138\uc5d0 \uae30\ub85d\ud588\uc2b5\ub2c8\ub2e4. CC BY-SA \ubcc0\ud658 \uc74c\uc6d0\uc740 \uac01 \uc6d0\ubcf8\uc5d0 \ud45c\uc2dc\ub41c \ub3d9\uc77c \uc870\uac74\uc73c\ub85c \uc81c\uacf5\ud558\uace0 CC0 \uc790\ub8cc\ub294 \uc6d0\ubcf8 \uc870\uac74\uc744 \uc720\uc9c0\ud569\ub2c8\ub2e4.</p><p><a href="./hangul-audio-manifest.json">\uac1c\ubcc4 \ud30c\uc77c\u00b7\ucd9c\ucc98\u00b7\ubcc0\uacbd \ub0b4\uc5ed</a> \u00b7 <a href="./hangul-audio-human-only.json">\uc0ac\ub78c \ub179\uc74c \uc804\ud658 \uc0c1\ud0dc</a></p></section><div class="board-scroll"><table class="table"><thead><tr><th>\uae00\uc790</th><th>\uc885\ub958\u00b7\uc0c1\ud0dc</th><th>\ub179\uc74c\uc790</th><th>\ucd9c\ucc98</th><th>\uc774\uc6a9 \uc870\uac74</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div></main><footer class="wrap footer">\ud55c\uae00\uc27d\uc9c0 \u00b7 2026-10-26 \u00b7 \uc2e4\uc81c \uc0ac\ub78c \ub179\uc74c, \ubc1c\uc74c \uccad\ucde8 \uc2b9\uc778 \uc804</footer></body></html>'''

(root / 'hangul-audio-credits.html').write_text(page, encoding='utf-8')
