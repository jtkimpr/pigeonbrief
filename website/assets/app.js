let allData = null;
let activeSection = 'today';
const articlesById = {};

// ─── localStorage 키 ──────────────────────────────────────────────────────────
const LS_LIKED      = 'ni_liked';
const LS_DELETED    = 'ni_deleted';
const LS_READ_LATER = 'ni_read_later';

function getLiked()     { return JSON.parse(localStorage.getItem(LS_LIKED)      || '{}'); }
function getDeleted()   { return JSON.parse(localStorage.getItem(LS_DELETED)    || '[]'); }
function getReadLater() { return JSON.parse(localStorage.getItem(LS_READ_LATER) || '{}'); }

// ─── 데이터 로드 ──────────────────────────────────────────────────────────────

async function loadData() {
  const res = await fetch('data/articles.json?_=' + Date.now());
  allData = await res.json();
  (allData.sections || []).forEach(sec =>
    (sec.articles || []).forEach(a => { articlesById[a.id] = a; })
  );
  buildNav();
  render();
  if (allData.generated_at) {
    const d = new Date(allData.generated_at);
    document.getElementById('generated-at').textContent =
      `${d.getFullYear()}.${String(d.getMonth()+1).padStart(2,'0')}.${String(d.getDate()).padStart(2,'0')} 업데이트`;
  }
}

// ─── 네비게이션 빌드 ──────────────────────────────────────────────────────────

let dragSrcIdx  = null;
let isDragging  = false;

function buildNav() {
  const nav = document.getElementById('section-tabs');
  nav.innerHTML = '';

  // 고정 탭: All / Today / Read Later
  [
    { id: 'all',        label: 'All' },
    { id: 'today',      label: 'Today' },
    { id: 'read-later', label: 'Read Later' },
  ].forEach(({ id, label }) => {
    const btn = document.createElement('button');
    btn.className = 'tab tab-fixed' + (activeSection === id ? ' active' : '');
    btn.dataset.section = id;
    btn.textContent = label;
    nav.appendChild(btn);
  });

  // 구분선
  const sep = document.createElement('span');
  sep.className = 'tab-sep';
  nav.appendChild(sep);

  // 주제별 섹션 탭 (draggable)
  (allData.sections || []).forEach((sec, i) => {
    const btn = document.createElement('button');
    btn.className = 'tab tab-section' + (activeSection === sec.id ? ' active' : '');
    btn.dataset.section = sec.id;
    btn.draggable = true;
    btn.textContent = sec.name;

    btn.addEventListener('dragstart', e => {
      isDragging = true;
      dragSrcIdx = i;
      btn.classList.add('dragging');
      e.dataTransfer.effectAllowed = 'move';
    });

    btn.addEventListener('dragover', e => {
      e.preventDefault();
      btn.classList.add('drag-over');
    });

    btn.addEventListener('dragleave', () => btn.classList.remove('drag-over'));

    btn.addEventListener('drop', e => {
      e.preventDefault();
      btn.classList.remove('drag-over');
      if (dragSrcIdx === null || dragSrcIdx === i) return;

      const sections = allData.sections;
      const [moved] = sections.splice(dragSrcIdx, 1);
      sections.splice(i, 0, moved);
      buildNav();
      render();

      const newIds = allData.sections.map(s => s.id);
      if (window.saveSectionOrder) window.saveSectionOrder(newIds);
    });

    btn.addEventListener('dragend', () => {
      isDragging = false;
      dragSrcIdx = null;
      nav.querySelectorAll('.tab-section').forEach(t =>
        t.classList.remove('dragging', 'drag-over')
      );
    });

    nav.appendChild(btn);
  });

  // "+" 새 섹션 버튼
  const addBtn = document.createElement('button');
  addBtn.className = 'tab tab-add';
  addBtn.title = '새 섹션 추가';
  addBtn.textContent = '+';
  nav.appendChild(addBtn);

  // 탭 전환 (이벤트 위임)
  nav.addEventListener('click', e => {
    if (isDragging) return;
    const tab = e.target.closest('.tab');
    if (!tab) return;

    if (tab.classList.contains('tab-add')) {
      if (window.openSettings) window.openSettings('__new__');
      return;
    }

    const sid = tab.dataset.section;
    if (!sid) return;
    nav.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    activeSection = sid;
    render();
  });
}

// ─── 현재 섹션 설정 열기 (헤더 ⚙️ 버튼용) ────────────────────────────────────

window.openSettingsForCurrent = function() {
  if (window.openSettings) window.openSettings(activeSection);
};

// ─── 렌더링 ───────────────────────────────────────────────────────────────────

function render() {
  const grid    = document.getElementById('card-grid');
  const deleted = new Set(getDeleted());

  if (activeSection === 'today') {
    const arts = getTodayArticles().filter(a => !deleted.has(a.id));
    grid.innerHTML = arts.length
      ? arts.map(makeCard).join('')
      : '<div class="empty-state">오늘 수집된 기사가 없습니다.</div>';

  } else if (activeSection === 'read-later') {
    const arts = getReadLaterArticles().filter(a => !deleted.has(a.id));
    grid.innerHTML = arts.length
      ? arts.map(makeCard).join('')
      : '<div class="empty-state">나중에 읽기로 저장된 기사가 없습니다.</div>';

  } else if (activeSection === 'all') {
    const sections = allData?.sections || [];
    if (!sections.length) {
      grid.innerHTML = '<div class="empty-state">아직 수집된 기사가 없습니다.</div>';
      return;
    }
    grid.innerHTML = sections.map(sec => {
      const arts = (sec.articles || []).filter(a => !deleted.has(a.id));
      if (!arts.length) return '';
      return `<div class="section-header">${sec.name}</div>` + arts.map(makeCard).join('');
    }).join('');

  } else {
    const sec  = (allData?.sections || []).find(s => s.id === activeSection);
    const arts = (sec?.articles || []).filter(a => !deleted.has(a.id));
    grid.innerHTML = arts.length
      ? arts.map(makeCard).join('')
      : '<div class="empty-state">아직 수집된 기사가 없습니다.</div>';
  }
}

// ─── 특수 섹션 데이터 ─────────────────────────────────────────────────────────

function getTodayArticles() {
  const cutoff = Date.now() - 24 * 60 * 60 * 1000;
  return (allData?.sections || [])
    .flatMap(s => s.articles || [])
    .filter(a => a.published_at && new Date(a.published_at).getTime() >= cutoff)
    .sort((a, b) => new Date(b.published_at) - new Date(a.published_at));
}

function getReadLaterArticles() {
  const saved = getReadLater();
  return Object.keys(saved).map(id => articlesById[id] || saved[id]);
}

// ─── 카드 렌더링 ──────────────────────────────────────────────────────────────

function timeAgo(dateStr) {
  if (!dateStr) return '';
  const diff = (Date.now() - new Date(dateStr)) / 1000;
  if (diff < 3600)  return `${Math.floor(diff / 60)}분 전`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}시간 전`;
  return `${Math.floor(diff / 86400)}일 전`;
}

function makeCard(article) {
  const id      = article.id;
  const isLiked = !!getLiked()[id];
  const isRL    = !!getReadLater()[id];

  return `
    <div class="card" id="card-${id}">
      <div class="card-meta">
        <span class="card-source">${article.source_name || ''}</span>
        <span class="card-time">${timeAgo(article.published_at)}</span>
      </div>
      <a class="card-title-link" href="${article.url}" target="_blank" rel="noopener">
        <div class="card-title">${article.title}</div>
      </a>
      <div class="card-summary">${article.summary_ko || ''}</div>
      <div class="card-footer">
        <div class="card-actions">
          <button class="action-btn ${isLiked ? 'active-like' : ''}"
            data-action="like" data-id="${id}"
            title="${isLiked ? '좋아요 취소' : '좋아요'}">♥</button>
          <button class="action-btn ${isRL ? 'active-rl' : ''}"
            data-action="read-later" data-id="${id}"
            title="${isRL ? 'Read Later 취소' : '나중에 읽기'}">🔖</button>
          <button class="action-btn action-delete"
            data-action="delete" data-id="${id}"
            title="삭제">✕</button>
        </div>
        <a class="card-link" href="${article.url}" target="_blank" rel="noopener">원문 보기 →</a>
      </div>
    </div>`;
}

// ─── 카드 액션 (이벤트 위임) ─────────────────────────────────────────────────

document.getElementById('card-grid').addEventListener('click', e => {
  const btn = e.target.closest('[data-action]');
  if (!btn) return;
  e.preventDefault();
  const { action, id } = btn.dataset;
  if (action === 'like')            toggleLike(id);
  else if (action === 'read-later') toggleReadLater(id);
  else if (action === 'delete')     deleteArticle(id);
});

function toggleLike(id) {
  const liked = getLiked();
  if (liked[id]) {
    delete liked[id];
  } else {
    const a = articlesById[id] || getReadLater()[id];
    if (a) liked[id] = a;
  }
  localStorage.setItem(LS_LIKED, JSON.stringify(liked));
  refreshCard(id);
}

function toggleReadLater(id) {
  const rl = getReadLater();
  if (rl[id]) {
    delete rl[id];
  } else {
    const a = articlesById[id];
    if (a) rl[id] = a;
  }
  localStorage.setItem(LS_READ_LATER, JSON.stringify(rl));
  refreshCard(id);
  if (activeSection === 'read-later') render();
}

function deleteArticle(id) {
  const deleted = getDeleted();
  if (!deleted.includes(id)) deleted.push(id);
  localStorage.setItem(LS_DELETED, JSON.stringify(deleted));

  const liked = getLiked();
  delete liked[id];
  localStorage.setItem(LS_LIKED, JSON.stringify(liked));

  const rl = getReadLater();
  delete rl[id];
  localStorage.setItem(LS_READ_LATER, JSON.stringify(rl));

  const card = document.getElementById('card-' + id);
  if (card) card.remove();
}

function refreshCard(id) {
  const article = articlesById[id] || getLiked()[id];
  if (!article) return;
  const card = document.getElementById('card-' + id);
  if (card) card.outerHTML = makeCard(article);
}

// ─── 토스트 알림 ──────────────────────────────────────────────────────────────

window.showToast = function(msg) {
  let toast = document.getElementById('ni-toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'ni-toast';
    document.body.appendChild(toast);
  }
  toast.textContent = msg;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), 3000);
};

loadData();
