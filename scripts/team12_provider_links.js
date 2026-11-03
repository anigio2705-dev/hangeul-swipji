/* Preserve the selected provider role across the free-learning → existing studio navigation. */
(() => {
  'use strict';
  document.querySelectorAll('a[data-team12-provider]').forEach(link => {
    link.addEventListener('click', () => {
      const role = link.dataset.team12Provider;
      if (role !== 'partner' && role !== 'teacher') return;
      try { sessionStorage.setItem('hs-team12-provider-intent', role); } catch (_) {}
    });
  });
})();
