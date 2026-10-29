/* Additive UI and authenticated progress bridge; immutable lesson HTML stays byte-for-byte. */
(function (root) {
  'use strict';
  const courseKeys = Object.freeze({
    'intro.html': 'hs-intro-v1',
    'beginner1.html': 'hs-beginner1-v1',
    'beginner2.html': 'hs-beginner2-v1',
    'intermediate1.html': 'hs-intermediate1-v1',
    'intermediate2.html': 'hs-intermediate2-v1',
    'advanced1.html': 'hs-advanced1-v1',
    'advanced2.html': 'hs-advanced2-v1'
  });
  function readingLevelSwitch(doc) {
    const progress = doc.getElementById('progress');
    const side = doc.querySelector('.layout>.side');
    const library = doc.querySelector('.library .sectionhead');
    if (!progress || !side || !library || doc.getElementById('changeLevel')) return false;
    const wrap = doc.createElement('div');
    wrap.className = 'actions';
    wrap.style.margin = '0';
    const button = doc.createElement('button');
    button.type = 'button';
    button.id = 'changeLevel';
    button.className = 'btn secondary';
    button.setAttribute('aria-controls', 'levels');
    const label = () => {
      const lang = doc.getElementById('lang');
      button.textContent = lang && lang.value === 'en' ? 'Change level' : '레벨 변경';
    };
    label();
    button.addEventListener('click', () => {
      doc.body.classList.remove('reading-level-open');
      root.requestAnimationFrame(() => side.scrollIntoView({ behavior: 'auto', block: 'start' }));
    });
    const lang = doc.getElementById('lang');
    if (lang) lang.addEventListener('change', () => root.setTimeout(label, 0));
    progress.parentNode.insertBefore(wrap, progress);
    wrap.appendChild(button);
    wrap.appendChild(progress);
    return true;
  }
  function courseProgress(doc, key) {
    if (!key || !root.fetch || !root.localStorage) return false;
    const script = doc.createElement('script');
    script.src = './scripts/team12_server_progress.js';
    script.onload = () => {
      const api = root.HSTeam12ServerProgress;
      if (!api || typeof api.client !== 'function') return;
      const storage = root.localStorage;
      let last = storage.getItem(key);
      const client = api.client(root.fetch.bind(root), storage);
      api.clientInstance = client;
      function changed() {
        const next = storage.getItem(key);
        if (next !== last) {
          last = next;
          client.changed(key, next);
        }
      }
      function afterEvent() { root.setTimeout(changed, 0); }
      for (const event of ['click', 'change', 'keyup']) doc.addEventListener(event, afterEvent, true);
      doc.addEventListener('visibilitychange', () => { if (!doc.hidden) changed(); });
      root.addEventListener('pageshow', changed);
      // The original course script has already read its local state. Refresh
      // only when authenticated server data actually changes that state.
      Promise.resolve(client.pull()).then(ok => {
        const next = storage.getItem(key);
        if (ok && next !== last) {
          root.location.reload();
        } else {
          last = next;
        }
      }).catch(() => { /* Anonymous/offline lessons stay local-only. */ });
    };
    doc.head.appendChild(script);
    return true;
  }
  function boot() {
    const doc = root.document;
    if (!doc) return;
    const page = (root.location.pathname.split('/').pop() || '').toLowerCase();
    if (page === 'reading.html') readingLevelSwitch(doc);
    else if (Object.prototype.hasOwnProperty.call(courseKeys, page)) courseProgress(doc, courseKeys[page]);
  }
  if (root.document && root.document.readyState === 'loading') {
    root.document.addEventListener('DOMContentLoaded', boot, { once: true });
  } else boot();
})(typeof window === 'object' ? window : globalThis);
