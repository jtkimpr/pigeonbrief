/**
 * /api/config — GitHub config/sections.json 읽기/쓰기 프록시
 *
 * GITHUB_PAT 환경변수만 Vercel에 설정하면 됩니다.
 * password_hash, github_repo 등은 site_config.json에서 읽습니다.
 *
 * GET  /api/config → sections.json 내용 반환
 * PUT  /api/config → sections.json 업데이트
 *
 * 모든 요청에 x-password-hash 헤더 필요 (서버에서 인증 검증)
 */

const fs   = require('fs');
const path = require('path');

let _cfg = null;

function getSiteConfig() {
  if (!_cfg) {
    const p = path.join(process.cwd(), 'website', 'data', 'site_config.json');
    _cfg = JSON.parse(fs.readFileSync(p, 'utf8'));
  }
  return _cfg;
}

module.exports = async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Methods', 'GET, PUT, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, x-password-hash');
  if (req.method === 'OPTIONS') return res.status(200).end();

  // ── 인증: 클라이언트가 보낸 해시를 서버에서 재검증 ──────────────────────
  const cfg        = getSiteConfig();
  const clientHash = req.headers['x-password-hash'];
  if (!clientHash || clientHash !== cfg.password_hash) {
    return res.status(401).json({ error: '인증 실패' });
  }

  // ── GitHub API 설정 ──────────────────────────────────────────────────────
  const pat = process.env.GITHUB_PAT;
  if (!pat) {
    return res.status(500).json({ error: 'GITHUB_PAT 환경변수가 설정되지 않았습니다.' });
  }

  const { github_repo, github_branch, config_path } = cfg;
  const apiUrl = `https://api.github.com/repos/${github_repo}/contents/${config_path}`;
  const ghHeaders = {
    'Authorization':        `Bearer ${pat}`,
    'Accept':               'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28',
  };

  try {
    // ── GET: sections.json 읽기 ─────────────────────────────────────────────
    if (req.method === 'GET') {
      const r = await fetch(`${apiUrl}?ref=${github_branch}`, { headers: ghHeaders });
      const d = await r.json();
      if (!r.ok) return res.status(r.status).json({ error: d.message });
      return res.status(200).json(d);
    }

    // ── PUT: sections.json 쓰기 ─────────────────────────────────────────────
    if (req.method === 'PUT') {
      const { message, content, sha } = req.body;
      const r = await fetch(apiUrl, {
        method:  'PUT',
        headers: { ...ghHeaders, 'Content-Type': 'application/json' },
        body:    JSON.stringify({ message, content, sha, branch: github_branch }),
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
