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
page = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>발음 음원 출처·준비 상태 | 한글쉽지</title><link rel="stylesheet" href="./hangul-foundations.css?v=20261026-foundations"></head><body><header><div class="wrap"><a class="brand" href="./hangul-basics.html">← 전체 글자판</a><a href="./hangul-week.html">7일 과정</a></div></header><main class="wrap"><div class="intro"><h1>발음 음원 출처·준비 상태</h1><p>파일 확보와 실제 발음 청취 승인은 별도 단계입니다. 합성 음성을 실제 사람의 녹음으로 표시하지 않습니다.</p></div><section class="panel"><h2>1번 · 7일 과정 음성 후보 확보</h2><p>누락됐던 52개 후보 파일을 준비했습니다. 추가한 파일은 사람 녹음 26개, 합성 음성 26개입니다. 기존 11개와 합쳐 7일 과정의 고유 재생 대상 63개에 대응하는 파일이 있습니다.</p><p class="note">새 후보 52개는 2번 청취 검수 전까지 일반 학습 화면에서 재생하지 않습니다. 자음 이름·짧은 음절의 실제 소리, 분리한 모음의 경계, 합성 음성의 발음과 잘림을 확인해야 합니다. 파일 수가 갖춰졌다고 정확성을 인증하지 않습니다.</p><p><a href="./hangul-audio-review.html?scope=week">7일 과정의 음원 63개를 검수표에서 듣기 →</a></p><p>전체 음성 파일 {len(entries)}개: 사람 녹음 {human}개 / 합성 음성 {synthetic}개. 일반 학습 화면 재생 {len(entries)-held}개 / 보류 {held}개. 전체 글자판의 녹음이 완비된 상태는 아닙니다.</p></section><section class="panel"><h2>출처와 변경 내역</h2><p>사람 녹음은 Wikimedia Commons의 개별 파일 조건을 따릅니다. MP3 변환·음량 조절·일부 구간 분리 내역과 타임스탬프는 아래 명세에 기록했습니다. CC BY-SA 변환 음원은 각 원본에 표시된 동일 조건으로 제공하고, CC0 자료는 원본 조건을 유지합니다.</p><p>합성 음성은 Supertonic 3의 제공 음색 F1로 한국어 문장을 생성한 후 연습할 말을 분리한 후보입니다. 일부는 같은 말을 두 번 반복합니다. 실제 사람을 복제한 사용자 음색을 사용하지 않았습니다. 모델 제공자는 생성 출력물에 권리를 주장하지 않는다고 규정하지만, 이용자는 모델 라이선스의 사용 제한을 준수해야 합니다. 출력 파일 자체가 CC0 또는 CC BY-SA라는 뜻은 아닙니다.</p><p><a href="./assets/hangul-audio/licenses/Supertonic3-OpenRAIL-M.txt">생성 모델 OpenRAIL-M 조건 전문</a> · <a href="./hangul-audio-manifest.json">개별 파일·해시·출처·변경 내역</a> · <a href="./hangul-week-audio-step1.json">1번 파일 확보 결과</a></p></section><div class="board-scroll"><table class="table"><thead><tr><th>글자</th><th>종류·상태</th><th>녹음자·생성 도구</th><th>출처</th><th>이용 조건</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div><section class="panel"><h2>2번에서 확인할 것</h2><p>기역·니은 같은 자음 이름과 가·나 같은 음절을 구분해 듣고, 첫소리·끝소리·잡음·불필요한 모음·구간 분리 오류를 확인합니다. 특히 합성 음성과 분리한 모음은 실제 한국어 교사의 검수가 필요합니다. 기기별 TTS는 검증된 공통 음원으로 자동 대체하지 않습니다.</p></section></main><footer class="wrap footer">한글쉽지 · 2026-10-26 · 파일 준비와 청취 승인을 구분합니다.</footer></body></html>'''
(root / 'hangul-audio-credits.html').write_text(page)
