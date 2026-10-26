// Placement is an advisory URL value, never identity, entitlement or a certified level.
'use strict';
const entryParams = new URLSearchParams(location.search);
const entryStage = entryParams.get('stage');
const entryValidStage = /^[0-6]$/.test(entryStage || '');
if (entryValidStage) document.getElementById('placement-note').textContent = '무료 간이 진단 권장 단계: ' + ['입문','초급 1','초급 2','중급 1','중급 2','고급 1','고급 2'][Number(entryStage)] + ' · 공식 등급이 아니며 강사 검색 수준과 자동 환산하지 않습니다.';
// Only the explicitly mounted local preview links to its own studio; no arbitrary API host.
if (location.pathname === '/free/teaching-platform.html' && ['127.0.0.1','localhost'].includes(location.hostname)) {
  const link = document.getElementById('studio-link'), target = new URL('/', location.origin);
  if (entryValidStage) target.searchParams.set('stage', entryStage);
  const language = entryParams.get('lang'); if (language && /^[a-z]{2}(?:-[A-Za-z]{2})?$/.test(language)) target.searchParams.set('lang', language);
  link.href = target.href; link.hidden = false;
  document.getElementById('server-help').hidden = true;
}
