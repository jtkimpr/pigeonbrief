/**
 * /api/config — GitHub config/sections.json 읽기/쓰기 프록시
 *
 * Vercel 환경변수 필요:
 *   GITHUB_PAT      — GitHub Personal Access Token (필수)
 *   PASSWORD_HASH   — site_config.json의 password_hash 값 (필수)
 *   GITHUB_REPO     — 기본값: jtkimpr/news-intelligence
 *   GITHUB_BRANCH   — 기본값: main
 *   CONFIG_PATH     — 기본값: config/sections.json
 */

module.exports = async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Methods', 'GET, PUT, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, x-password-hash');
  if (req.method === 'OPTIONS') return res.status(200).end();

  // ── 인증 ─────────────────────────────────────────────────────────────────
  const clientHash   = req.headers['x-password-hash'];
  const passwordHash = process.env.PASSWORD_HASH;

  if (!passwordHash) {
    return res.status(500).json({ error: 'PASSWORD_HASH 환경변수가 설정되지 않았습니다.' });
  }
  if (!clientHash || clientHash !== passwordHash) {
    return res.status(401).json({ error: '인증 실패' });
  }

  // ── GitHub 설정 ──────────────────────────────────────────────────────────
  const pat        = process.env.GITHUB_PAT;
  const repo       = process.env.GITHUB_REPO   || 'jtkimpr/news-intelligence';
  const branch     = process.env.GITHUB_BRANCH || 'main';
  const configPath = process.env.CONFIG_PATH   || 'config/sections.json';

  if (!pat) {
    return res.status(500).json({ error: 'GITHUB_PAT 환경변수가 설정되지 않았습니다.' });
  }

  const apiUrl    = `https://api.github.com/repos/${repo}/contents/${configPath}`;
  const ghHeaders = {
    'Authorization':        `Bearer ${pat}`,
    'Accept':               'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28',
  };

  try {
    // ── GET ───────────────────────────────────────────────────────────────
    if (req.method === 'GET') {
      const r = await fetch(`${apiUrl}?ref=${branch}`, { headers: ghHeaders });
      const d = await r.json();
      if (!r.ok) return res.status(r.status).json({ error: d.message });
      return res.status(200).json(d);
    }

    // ── PUT ───────────────────────────────────────────────────────────────
    if (req.method === 'PUT') {
      const { message, content, sha } = req.body;
      const r = await fetch(apiUrl, {
        method:  'PUT',
        headers: { ...ghHeaders, 'Content-Type': 'application/json' },
        body:    JSON.stringify({ message, content, sha, branch }),
      });
      const d = await r.json();
      if (!r.ok) return res.status(r.status).json({ error: d.message });
      return res.status(200).json(d);
    }

    return res.status(405).json({ error: 'Method not allowed' });
  } catch (e) {
    return res.status(500).json({ error: e.message });
  }
};
