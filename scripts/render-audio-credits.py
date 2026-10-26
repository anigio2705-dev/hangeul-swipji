"""Render attribution and the current acquisition status from the manifest."""
import html
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
manifest = json.loads((root / 'hangul-audio-manifest.json').read_text())
entries = manifest['recordings']
human = sum(a.get('kind', 'human') == 'human' for a in entries.values())
synthetic = len(entries) - human
held = sum(bool(a.get('disabled')) for a in entries.values())
esc = html.escape
rows = []
for word, a in entries.items():
    kind = '합성 음성 후보' if a.get('kind') == 'synthetic' else '사람 녹음'
    state = '검수 전 보류' if a.get('disabled') else '재생 가능 · 청취 승인 전'
    rows.append(f'<tr><td class="notranslate" translate="no">{esc(word)}</td><td>{kind}<br>{state}</td><td>{esc(a["author"])}</td><td><a href="{esc(a["sourceUrl"])}">출처</a></td><td><a href="{esc(a["licenseUrl"])}">{esc(a["license"])}</a></td></tr>')
page = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>사람 녹음 출처·검수 상태 | 한글쉽지</title><link rel="stylesheet" href="./hangul-foundations.css?v=20261026-foundations"></head><body><header><div class="wrap"><a class="brand" href="./hangul-basics.html">← 전체 글자판</a><a href="./hangul-week.html">7일 과정</a></div></header><main class="wrap"><div class="intro"><h1>실제 사람의 녹음만 사용합니다.</h1><p>합성 음성과 기기 TTS는 한글 기초 학습·검수 재생에서 제외했습니다.</p></div><section class="panel"><h2>7일 과정 사람 녹음 후보 51/63개</h2><p>기존 사람 녹음37개에 자음 이름 연속 녹음에서 분리한 후보14개를 추가했습니다. 12개 기본 음절은 실제 녹음이 필요합니다. 사람의 녹음이라는 사실과 발음·글자 대응이 맞는다는 청취 승인은 다릅니다.</p><p class="note">새 자음 이름14개는 순서로 임시 대응한 후보입니다. 실제 이름과 구간 경계를 교사가 듣고 확인해야 합니다. 승인 전 후보는 일반 학습 재생을 보류합니다. 기존 합성26개는 사용 제외 처리했으며 사용자께서 이전 합성 음성을 좋다고 하신 말씀을 실제 사람 녹음의 승인으로 기록하지 않았습니다.</p><p><a href="./hangul-audio-review.html?scope=week">실제 사람 녹음 검수표 →</a></p><p>전체 글자판·입문 자료에 확보한 사람 녹음 후보 {human}개. 일반 학습 재생 {len(entries)-held}개 / 보류 {held}개. 전체 음원 확보나 발음 검수가 완료된 상태는 아닙니다.</p><h3>녹음이 필요한 기본 음절 12개</h3><p class="notranslate" translate="no">고 · 노 · 누 · 도 · 라 · 마 · 바 · 자 · 카 · 타 · 파 · 하</p><p><a href="./HUMAN-RECORDING-SCRIPT.txt">녹음 대본</a></p></section><section class="panel"><h2>출처와 변경 내역</h2><p>Wikimedia Commons의 개별 파일 조건을 따릅니다. MP3 변환·음량 조절·구간 분리 내역과 타임스탬프는 명세에 기록했습니다. CC BY-SA 변환 음원은 각 원본에 표시된 동일 조건으로 제공하고 CC0 자료는 원본 조건을 유지합니다.</p><p><a href="./hangul-audio-manifest.json">개별 파일·출처·변경 내역</a> · <a href="./hangul-audio-human-only.json">사람 녹음 전환 상태</a></p></section><div class="board-scroll"><table class="table"><thead><tr><th>글자</th><th>종류·상태</th><th>녹음자</th><th>출처</th><th>이용 조건</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div></main><footer class="wrap footer">한글쉽지 · 2026-10-26 · 실제 사람 녹음, 발음 청취 승인 전</footer></body></html>'''

(root / 'hangul-audio-credits.html').write_text(page)
