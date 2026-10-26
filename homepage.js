/* The homepage routes to existing services; it never duplicates course data. */
(() => {
  'use strict';
  const entries = [
    ['한글 자음 모음 발음 가나다 입문 Hangul alphabet pronunciation', '한글 기초 · 자음과 모음', 'hangul-basics.html'],
    ['한국어 교육 학습 수업 기초 초급 중급 고급 Korean lessons learn course', '한국어 학습관 · 350개 단원', 'learn.html'],
    ['읽기 리딩 독해 이야기 reading books stories', '읽기 · 15레벨 600개 학습 항목', 'reading.html'],
    ['한국인 화상 채팅 회화 대화 speaking video chat partner', '한국인과 화상대화 · 시험 운영', 'speaking-platform.html'],
    ['가격 요금 이용 안내 speaking plans price', '화상대화 이용·가격 안내', 'live.html'],
    ['한국 일상 생활 daily life', '한국 일상', 'daily.html'],
    ['학생 이야기 students stories', '학생 이야기', 'students.html'],
    ['드라마 한국 방송 drama watch television TV', 'K-드라마', 'drama.html'],
    ['케이팝 음악 K-POP kpop music', 'K-POP', 'kpop.html'],
    ['문화 음식 여행 한국 culture food travel', '한국 문화', 'culture.html'],
    ['크리에이터 마켓 판매 상품 market creator shop', '크리에이터 마켓 · 소개용 시제품', 'market.html'],
    ['진단 평가 시험 테스트 레벨 placement test level', '무료 레벨 진단', 'placement.html'],
    ['진도 기록 학습 progress dashboard', '나의 학습 기록', 'dashboard.html'],
    ['언어 번역 language translation', '언어 지원 안내', 'global-language.html'],
    ['체험 대화 experience', '한국어 체험', 'experience.html'],
    ['안내 가이드 처음 guide help', '서비스·학습 안내', 'guide.html']
  ];
  const panel = document.getElementById('search-results');
  document.getElementById('search').addEventListener('submit', event => {
    event.preventDefault();
    const query = document.getElementById('query').value.trim().toLocaleLowerCase();
    const results = entries.filter(item => !query || query.split(/\s+/).every(word => (item[0] + ' ' + item[1]).toLocaleLowerCase().includes(word)));
    const list = document.getElementById('search-list');
    list.replaceChildren();
    for (const [, title, path] of results) {
      const li = document.createElement('li');
      const link = document.createElement('a');
      link.textContent = title;
      link.href = './' + path;
      li.append(link);
      list.append(li);
    }
    document.getElementById('search-status').textContent = results.length ? results.length + '개의 관련 페이지' : '검색 결과가 없습니다. 한국어, 읽기, 발음, 드라마 등의 단어로 검색해 보세요.';
    panel.hidden = false;
    panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
  document.getElementById('close-search').addEventListener('click', () => {
    panel.hidden = true;
    document.getElementById('query').focus();
  });
  document.querySelectorAll('[data-video]').forEach(host => {
    host.querySelector('button').addEventListener('click', () => {
      const iframe = document.createElement('iframe');
      iframe.src = 'https://www.youtube-nocookie.com/embed/' + host.dataset.video + '?autoplay=1&rel=0';
      iframe.title = host.dataset.video === 'hvVlyZ5GiE8' ? 'Arirang TV · 공식 실시간 방송' : 'RealLife English · 공식 채널 영상';
      iframe.allow = 'accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture; web-share';
      iframe.allowFullscreen = true;
      iframe.referrerPolicy = 'strict-origin-when-cross-origin';
      host.replaceChildren(iframe);
    }, { once: true });
  });
})();
