/* Team12 additive learner handoff; no booking or payment side effects. */
(() => {
  'use strict';
  const root = document.querySelector('[data-team12-handoff]');
  if (!root) return;
  const target = document.createElement('section');
  target.setAttribute('aria-label', '무료 학습 다음 단계');
  const heading = document.createElement('h3');
  heading.textContent = '무료 학습 다음 단계';
  const description = document.createElement('p');
  description.textContent = '무료 학습을 마친 뒤 회화 파트너 또는 전문 강사를 선택할 수 있습니다. 실제 예약은 승인된 제공자 검색 화면에서 진행합니다.';
  target.append(heading, description);
  for (const [role, label] of [['partner','회화 파트너 찾기'],['teacher','전문 강사 찾기']]) {
    const link = document.createElement('a');
    link.href = '#teaching-platform';
    link.textContent = label;
    link.dataset.providerRole = role;
    link.addEventListener('click', () => {
      try { sessionStorage.setItem('hs-team12-provider-intent', role); } catch (_) {}
    });
    target.append(link, document.createTextNode('　'));
  }
  root.append(target);
})();
