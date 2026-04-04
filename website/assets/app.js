const CHANNEL_LABELS = { 1: '채널1·Feedly', 2: '채널2·RSS', 3: '채널3·키워드' };

let allData = null;
let activeSection = 'all';

async function loadData() {
  const res = await fetch('data/articles.json');
  allData = await res.json();
  buildTabs();
  render();
  if (allData.generated_at) {
    const d = new Date(allData.generated_at);
    document.getElementById('generated-at').textContent =
      `${d.getFullYear()}.${String(d.getMonth()+1).padStart(2,'0')}.${String(d.getDate()).padStart(2,'0')} 업데이트`;
  }
}

function buildTabs() {
  const nav = document.getElementById('section-tabs');
  nav.innerHTML = '<button class="tab active" data-section="all">전체</button>';
  (allData.sections || []).forEach(sec => {
    const btn = document.createElement('button');
    btn.className = 'tab';
    btn.dataset.section = sec.id;
    btn.textContent = sec.name;
    nav.appendChild(btn);
  });
  nav.addEventListener('click', e => {
    if (!e.target.classList.contains('tab')) return;
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    e.target.classList.add('active');
    activeSection = e.target.dataset.section;
    render();
  });
}

function timeAgo(dateStr) {
  if (!dateStr) return '';
  const diff = (Date.now() - new Date(dateStr)) / 1000;
  if (diff < 3600) return `${Math.floor(diff/60)}분 전`;
  if (diff < 86400) return `${Math.floor(diff/3600)}시간 전`;
  return `${Math.floor(diff/86400)}일 전`;
}

function makeCard(article) {
  return `
    <div class="card">
      <div class="card-meta">
        <span class="channel-badge">${CHANNEL_LABELS[article.channel] || ''}</span>
        <span>${timeAgo(article.published_at)}</span>
      </div>
      <div class="card-title">${article.title}</div>
      <div class="card-summary">${article.summary_ko || ''}</div>
      <div class="card-footer">
        <span class="card-source">${article.source_name}</span>
        <a class="card-link" href="${article.url}" target="_blank" rel="noopener">원문 보기 →</a>
      </div>
    </div>`;
}

function render() {
  const grid = document.getElementById('card-grid');
  const sections = allData.sections || [];

  if (activeSection === 'all') {
    if (sections.length === 0) {
      grid.innerHTML = '<div class="empty-state">아직 수집된 기사가 없습니다.</div>';
      return;
    }
    grid.innerHTML = sections.map(sec => `
      <div class="section-header">${sec.name}</div>
      ${(sec.articles || []).map(makeCard).join('')}
    `).join('');
  } else {
    const sec = sections.find(s => s.id === activeSection);
    const articles = sec ? (sec.articles || []) : [];
    grid.innerHTML = articles.length
      ? articles.map(makeCard).join('')
      : '<div class="empty-state">아직 수집된 기사가 없습니다.</div>';
  }
}

loadData();
