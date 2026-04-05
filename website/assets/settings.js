/**
 * settings.js — 섹션별 RSS/키워드 관리 UI
 * openSettings(sectionId) — 특정 섹션 설정 / '__new__' — 새 섹션 추가
 * All·Today·Read Later에서 열면 → 섹션 목록 표시
 */

let siteConfig   = null;
let sectionsData = null;
let currentSha   = null;

// ─── 진입점 ──────────────────────────────────────────────────────────────────

window.openSettings = async function(sectionId) {
  const panel = document.getElementById('settings-panel');
  panel.style.display = 'flex';

  if (!siteConfig) {
    try {
      const res = await fetch('data/site_config.json?_=' + Date.now());
      siteConfig = await res.json();
      window.siteConfig = siteConfig;
    } catch (e) {
      showBody(`<div class="settings-error">site_config.json 로드 실패: ${e.message}</div>`);
      return;
    }
  }

  if (!isAuthenticated()) {
    showAuthScreen(sectionId);
    return;
  }

  await routeToSection(sectionId);
};

function closeSettings() {
  document.getElementById('settings-panel').style.display = 'none';
}

function showBody(html) {
  document.getElementById('settings-body').innerHTML = html;
}

// ─── 인증 ─────────────────────────────────────────────────────────────────────

function isAuthenticated() {
  return sessionStorage.getItem('settings_auth') === 'ok';
}

function showAuthScreen(pendingId) {
  const id = pendingId || '';
  showBody(`
    <div class="settings-auth">
      <div class="settings-auth-icon">🔐</div>
      <h2>설정 접근</h2>
      <p>비밀번호를 입력하세요</p>
      <input type="password" id="auth-pw" placeholder="비밀번호"
        onkeydown="if(event.key==='Enter') submitAuth('${id}')" autofocus />
      <button class="btn-primary" onclick="submitAuth('${id}')">확인</button>
      <div id="auth-error" class="settings-error" style="display:none"></div>
    </div>
  `);
  setTimeout(() => document.getElementById('auth-pw')?.focus(), 80);
}

async function submitAuth(pendingId) {
  const input = document.getElementById('auth-pw').value;
  const hash  = await sha256(input);
  if (hash === siteConfig.password_hash) {
    sessionStorage.setItem('settings_auth', 'ok');
    await routeToSection(pendingId || null);
  } else {
    const err = document.getElementById('auth-error');
    err.textContent = '비밀번호가 틀렸습니다.';
    err.style.display = 'block';
  }
}

async function sha256(str) {
  const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(str));
  return Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2,'0')).join('');
}

// ─── GitHub PAT ───────────────────────────────────────────────────────────────

function getStoredPat() { return localStorage.getItem('github_pat') || ''; }
function savePat(pat)   { pat ? localStorage.setItem('github_pat', pat) : localStorage.removeItem('github_pat'); }

// ─── 라우팅 ───────────────────────────────────────────────────────────────────

const FIXED_SECTIONS = ['all', 'today', 'read-later', ''];

async function routeToSection(sectionId) {
  showBody('<div class="settings-loading">설정 불러오는 중...</div>');

  if (!getStoredPat()) {
    showPatScreen(sectionId, '');
    return;
  }

  try {
    if (!sectionsData) await loadSectionsFromGitHub();
  } catch (e) {
    showPatScreen(sectionId, e.message);
    return;
  }

  if (sectionId === '__new__') {
    renderNewSectionEditor();
  } else if (!sectionId || FIXED_SECTIONS.includes(sectionId)) {
    renderSectionList();
  } else {
    const idx = sectionsData.sections.findIndex(s => s.id === sectionId);
    idx === -1 ? renderSectionList() : renderSectionEditor(idx);
  }
}

async function loadSectionsFromGitHub() {
  const pat = getStoredPat();
  if (!pat) throw new Error('GitHub PAT가 없습니다.');

  const { github_repo, github_branch, config_path } = siteConfig;
  const url = `https://api.github.com/repos/${github_repo}/contents/${config_path}?ref=${github_branch}`;

  const res = await fetch(url, {
    headers: { 'Authorization': `Bearer ${pat}`, 'Accept': 'application/vnd.github+json' }
  });

  if (res.status === 401 || res.status === 403)
    throw new Error('GitHub PAT 권한 오류 (repo 읽기/쓰기 필요)');
  if (!res.ok) throw new Error(`GitHub API 오류: ${res.status}`);

  const data = await res.json();
  currentSha   = data.sha;
  sectionsData = JSON.parse(atob(data.content.replace(/\n/g, '')));
}

function showPatScreen(pendingId, errorMsg) {
  const id = pendingId || '';
  showBody(`
    <div class="settings-auth">
      <div class="settings-auth-icon">🔑</div>
      <h2>GitHub Personal Access Token</h2>
      <p>설정을 저장하려면 GitHub PAT가 필요합니다.<br>
        <small>repo 권한의 Classic PAT 또는 Fine-grained PAT</small></p>
      <input type="password" id="pat-input" placeholder="ghp_..."
        value="${getStoredPat()}"
        onkeydown="if(event.key==='Enter') submitPat('${id}')" autofocus />
      <button class="btn-primary" onclick="submitPat('${id}')">연결</button>
      ${errorMsg ? `<div class="settings-error">${errorMsg}</div>` : ''}
    </div>
  `);
  setTimeout(() => document.getElementById('pat-input')?.focus(), 80);
}

async function submitPat(pendingId) {
  const pat = document.getElementById('pat-input').value.trim();
  if (!pat) return;
  savePat(pat);
  sectionsData = null;  // 재로드
  await routeToSection(pendingId);
}

// ─── 섹션 목록 (고정 탭에서 ⚙️ 클릭 시) ────────────────────────────────────

function renderSectionList() {
  const sections = sectionsData?.sections || [];
  const listHtml = sections.map((sec, i) => `
    <div class="section-list-item">
      <span class="section-list-name" onclick="renderSectionEditor(${i})">${escHtml(sec.name)}</span>
      <div style="display:flex;gap:8px;align-items:center">
        <button class="btn-icon section-list-arrow" onclick="renderSectionEditor(${i})" title="편집">→</button>
        <button class="btn-icon btn-danger-text" onclick="confirmRemoveSection(${i})" title="삭제">🗑</button>
      </div>
    </div>
  `).join('');

  showBody(`
    <div class="settings-toolbar">
      <span style="flex:1; font-size:13px; color:#888">편집할 섹션을 선택하세요</span>
      <button class="btn-small btn-secondary" onclick="showPatScreen(null,'')">PAT 변경</button>
      <button class="btn-small btn-secondary"
        onclick="sessionStorage.removeItem('settings_auth'); closeSettings()">로그아웃</button>
    </div>
    <div class="section-list">${listHtml || '<div class="empty-hint">등록된 섹션이 없습니다.</div>'}</div>
    <button class="btn-add-section" onclick="renderNewSectionEditor()">+ 새 섹션 추가</button>
  `);
}

// ─── 섹션 에디터 ──────────────────────────────────────────────────────────────

function renderSectionEditor(idx, isNew = false) {
  const sec = sectionsData?.sections[idx];
  if (!sec) { renderSectionList(); return; }

  const rssHtml = buildRssHtml(idx, sec);
  const kwHtml  = buildKwHtml(idx, sec);

  const toolbar = isNew ? '' : `
    <div class="settings-toolbar">
      <button class="btn-small btn-secondary" onclick="renderSectionList()">← 목록</button>
      <span style="flex:1"></span>
      <label class="toggle-label">
        <input type="checkbox" ${sec.enabled !== false ? 'checked' : ''}
          onchange="updateSectionEnabled(${idx},this.checked)" /> 활성
      </label>
    </div>`;

  const footer = isNew
    ? `<div class="settings-footer">
        <div id="save-status"></div>
        <button class="btn-primary btn-save" onclick="saveToGitHub()">저장</button>
       </div>`
    : `<div class="settings-footer">
        <button class="btn-small btn-secondary btn-danger-text"
          onclick="confirmRemoveSection(${idx})">섹션 삭제</button>
        <div id="save-status"></div>
        <button class="btn-primary btn-save" onclick="saveToGitHub()">저장</button>
       </div>`;

  showBody(`
    ${toolbar}

    <div class="editor-field">
      <label class="editor-label">섹션 이름</label>
      <input type="text" class="editor-input" value="${escHtml(sec.name)}"
        oninput="updateSectionName(${idx},this.value)" />
    </div>
    <div class="editor-field">
      <label class="editor-label">설명</label>
      <input type="text" class="editor-input" value="${escHtml(sec.description||'')}"
        placeholder="선택 사항" oninput="updateSectionDesc(${idx},this.value)" />
    </div>

    <div class="section-block">
      <div class="section-block-title">
        채널2 RSS 소스
        <button class="btn-small btn-secondary" onclick="addRss(${idx})">+ 추가</button>
      </div>
      <div id="rss-list-${idx}">${rssHtml}</div>
    </div>

    <div class="section-block">
      <div class="section-block-title">
        채널3 키워드
        <span class="kw-hint">AND·OR·NOT 구문 사용 가능</span>
        <button class="btn-small btn-secondary" onclick="addKeyword(${idx})">+ 추가</button>
      </div>
      <div id="kw-list-${idx}">${kwHtml}</div>
    </div>

    ${footer}
  `);
}

function renderNewSectionEditor() {
  if (!sectionsData) return;
  sectionsData.sections.push({
    id: 'section-' + Date.now(),
    name: '',
    description: '',
    enabled: true,
    channel2_rss: { sources: [] },
    channel3_keywords: { max_age_hours: 72, queries: [] }
  });
  renderSectionEditor(sectionsData.sections.length - 1, true);
}

// ─── RSS/키워드 HTML 빌더 ─────────────────────────────────────────────────────

function buildRssHtml(idx, sec) {
  const sources = sec.channel2_rss?.sources || [];
  if (!sources.length) return '<div class="empty-hint">RSS 소스 없음</div>';
  return sources.map((s, si) => `
    <div class="rss-row">
      <input class="rss-name" type="text" value="${escHtml(s.name)}" placeholder="소스 이름"
        oninput="updateRssName(${idx},${si},this.value)" />
      <input class="rss-url" type="text" value="${escHtml(s.url)}" placeholder="https://..."
        oninput="updateRssUrl(${idx},${si},this.value)" />
      <button class="btn-icon" onclick="removeRss(${idx},${si})">✕</button>
    </div>
  `).join('');
}

function buildKwHtml(idx, sec) {
  const queries = sec.channel3_keywords?.queries || [];
  if (!queries.length) return '<div class="empty-hint">키워드 없음</div>';
  return queries.map((q, qi) => `
    <div class="kw-row">
      <input class="kw-input" type="text" value="${escHtml(q)}" placeholder="검색 키워드"
        oninput="updateKeyword(${idx},${qi},this.value)" />
      <button class="btn-icon" onclick="removeKeyword(${idx},${qi})">✕</button>
    </div>
  `).join('');
}

// ─── 데이터 조작 ──────────────────────────────────────────────────────────────

function updateSectionName(idx, val)    { sectionsData.sections[idx].name = val; }
function updateSectionDesc(idx, val)    { sectionsData.sections[idx].description = val; }
function updateSectionEnabled(idx, val) { sectionsData.sections[idx].enabled = val; }

function updateRssName(si, ri, val) { sectionsData.sections[si].channel2_rss.sources[ri].name = val; }
function updateRssUrl(si, ri, val)  { sectionsData.sections[si].channel2_rss.sources[ri].url  = val; }
function updateKeyword(si, ki, val) { sectionsData.sections[si].channel3_keywords.queries[ki] = val; }

function addRss(idx) {
  const sec = sectionsData.sections[idx];
  if (!sec.channel2_rss) sec.channel2_rss = { sources: [] };
  sec.channel2_rss.sources.push({ name: '', url: '' });
  document.getElementById(`rss-list-${idx}`).innerHTML = buildRssHtml(idx, sec);
}

function removeRss(idx, ri) {
  sectionsData.sections[idx].channel2_rss.sources.splice(ri, 1);
  const sec = sectionsData.sections[idx];
  document.getElementById(`rss-list-${idx}`).innerHTML = buildRssHtml(idx, sec);
}

function addKeyword(idx) {
  const sec = sectionsData.sections[idx];
  if (!sec.channel3_keywords) sec.channel3_keywords = { max_age_hours: 72, queries: [] };
  sec.channel3_keywords.queries.push('');
  document.getElementById(`kw-list-${idx}`).innerHTML = buildKwHtml(idx, sec);
}

function removeKeyword(idx, ki) {
  sectionsData.sections[idx].channel3_keywords.queries.splice(ki, 1);
  const sec = sectionsData.sections[idx];
  document.getElementById(`kw-list-${idx}`).innerHTML = buildKwHtml(idx, sec);
}

function confirmRemoveSection(idx) {
  const name = sectionsData.sections[idx]?.name || '이 섹션';
  if (!confirm(`"${name}" 섹션을 삭제하시겠습니까?`)) return;
  sectionsData.sections.splice(idx, 1);
  renderSectionList();
  saveToGitHub();
}

// ─── GitHub 저장 ──────────────────────────────────────────────────────────────

async function saveToGitHub() {
  const statusEl = document.getElementById('save-status');
  const btn      = document.querySelector('.btn-save');
  if (btn) { btn.disabled = true; btn.textContent = '저장 중...'; }
  if (statusEl) { statusEl.textContent = ''; statusEl.className = ''; }

  try {
    const pat = getStoredPat();
    if (!pat) throw new Error('GitHub PAT 없음');

    const { github_repo, github_branch, config_path } = siteConfig;
    const content    = JSON.stringify(sectionsData, null, 2);
    const contentB64 = btoa(unescape(encodeURIComponent(content)));

    const res = await fetch(
      `https://api.github.com/repos/${github_repo}/contents/${config_path}`,
      {
        method: 'PUT',
        headers: {
          'Authorization':  `Bearer ${pat}`,
          'Accept':         'application/vnd.github+json',
          'Content-Type':   'application/json',
        },
        body: JSON.stringify({
          message: `settings update: ${new Date().toISOString().slice(0,10)}`,
          content: contentB64,
          branch:  github_branch,
          sha:     currentSha,
        }),
      }
    );

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.message || `HTTP ${res.status}`);
    }

    const result = await res.json();
    currentSha   = result.content.sha;

    if (statusEl) { statusEl.textContent = '저장 완료!'; statusEl.className = 'save-ok'; }
    if (window.showToast) window.showToast('저장됐습니다.');
  } catch (e) {
    if (statusEl) { statusEl.textContent = '실패: ' + e.message; statusEl.className = 'save-error'; }
    if (window.showToast) window.showToast('저장 실패: ' + e.message);
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = '저장'; }
  }
}

// ─── 섹션 순서 저장 (app.js drag-drop 후 호출) ───────────────────────────────

window.saveSectionOrder = async function(newSectionIds) {
  const pat = getStoredPat();
  if (!pat) {
    if (window.showToast) window.showToast('순서 저장: 설정에서 PAT를 먼저 입력하세요.');
    return;
  }

  if (!siteConfig) {
    try {
      const res = await fetch('data/site_config.json?_=' + Date.now());
      siteConfig = await res.json();
    } catch(e) { return; }
  }

  try {
    if (!sectionsData) await loadSectionsFromGitHub();
    const byId = {};
    sectionsData.sections.forEach(s => { byId[s.id] = s; });
    sectionsData.sections = newSectionIds.map(id => byId[id]).filter(Boolean);
    // 혹시 누락된 섹션 보전
    Object.values(byId).forEach(s => {
      if (!sectionsData.sections.find(x => x.id === s.id)) sectionsData.sections.push(s);
    });
    await saveToGitHub();
    if (window.showToast) window.showToast('섹션 순서가 저장됐습니다.');
  } catch(e) {
    if (window.showToast) window.showToast('순서 저장 실패: ' + e.message);
  }
};

// ─── 유틸 ─────────────────────────────────────────────────────────────────────

function escHtml(str) {
  return String(str || '')
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

document.addEventListener('DOMContentLoaded', async () => {
  // siteConfig 미리 로드 (drag-drop 순서 저장에서 필요)
  try {
    const res = await fetch('data/site_config.json?_=' + Date.now());
    siteConfig = await res.json();
    window.siteConfig = siteConfig;
  } catch(e) {}

  document.getElementById('settings-panel')?.addEventListener('click', e => {
    if (e.target.id === 'settings-panel') closeSettings();
  });
});
