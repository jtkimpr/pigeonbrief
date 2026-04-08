# PigeonBrief — 프로젝트 상세 문서

RSS·Google News에서 주제별 뉴스를 수집해 로컬 LLM으로 필터링·요약, 회원제 웹사이트로 자동 발행하는 개인 뉴스 인텔리전스 시스템.

---

## 아키텍처 개요

```
[사용자 브라우저]
  ↕ Clerk 인증
  ↕ 기사·설정 API 호출
[Vercel — 프론트엔드 (pigeonbrief.vercel.app)]
  ↕
[Cloudflare Tunnel — api.pigeonbrief.com]
  ↕
[Mac Mini M4 — localhost:8000]
  ├── FastAPI 백엔드
  │     ├── GET  /api/articles        사용자별 기사 목록
  │     ├── GET  /api/settings        내 섹션/RSS/키워드 조회
  │     ├── POST /api/settings/sections   섹션 추가
  │     ├── PUT  /api/settings/sections/{id}
  │     ├── DELETE /api/settings/sections/{id}
  │     ├── POST /api/settings/rss    RSS 소스 추가
  │     ├── DELETE /api/settings/rss/{id}
  │     ├── POST /api/settings/keywords
  │     └── DELETE /api/settings/keywords/{id}
  ├── SQLite DB (data/pigeonbrief.db)
  │     ├── users
  │     ├── sections     (사용자별)
  │     ├── rss_sources  (섹션별)
  │     ├── keywords     (섹션별)
  │     ├── articles     (사용자별)
  │     └── seen_urls    (중복 방지, 사용자별)
  └── 파이프라인 (launchd 매일 자동 실행)
        ├── git pull
        ├── collectors/rss.py       RSS 수집
        ├── collectors/keyword.py   Google News 수집
        ├── processor/dedup.py      중복 제거
        ├── processor/claude.py     Ollama 필터링 + 한국어 요약
        └── generator/build_site.py → DB 저장 + git push → Vercel 배포
```

---

## 디렉터리 구조

```
pigeonbrief/
├── pipeline.py                  # 메인 파이프라인 실행 스크립트
├── backend/                     # FastAPI 백엔드
│   ├── main.py                  # 앱 진입점, CORS 설정
│   ├── database.py              # SQLite 초기화 및 연결
│   ├── auth.py                  # Clerk JWT 검증
│   └── routers/
│       ├── settings.py          # 섹션/RSS/키워드 CRUD API
│       └── articles.py          # 기사 조회 API
├── collectors/
│   ├── rss.py                   # RSS 피드 수집 (feedparser)
│   └── keyword.py               # Google News 키워드 수집
├── processor/
│   ├── dedup.py                 # SQLite 기반 URL·제목 중복 제거
│   └── claude.py                # Ollama(qwen2.5:14b) 필터링 + 한국어 요약
├── generator/
│   └── build_site.py            # 기사 데이터 생성 및 저장
├── config/
│   ├── settings.yaml            # 파이프라인 전역 설정
│   └── sections.json            # 기본 섹션 정의 (파이프라인용 fallback)
├── scripts/
│   ├── run_pipeline.sh          # launchd 파이프라인 실행 스크립트
│   └── run_backend.sh           # 백엔드 수동 실행 스크립트
├── website/                     # Vercel 배포 대상
│   ├── index.html               # 메인 화면 (Clerk 인증 체크 포함)
│   ├── sign-in.html             # 로그인 페이지 (Clerk UI)
│   ├── settings.html            # 사용자 설정 페이지 (섹션/RSS/키워드)
│   └── assets/
│       ├── app.js               # 메인 프론트엔드 로직 (API 호출 방식)
│       ├── settings.js          # 설정 패널 UI
│       └── style.css            # 스타일
├── data/
│   └── pigeonbrief.db           # SQLite DB (사용자·기사·설정 통합)
├── .env                         # 환경변수 (gitignore됨)
└── requirements.txt             # Python 의존성
```

---

## 환경변수 (.env)

```env
# Clerk 인증
CLERK_PUBLISHABLE_KEY=pk_test_...
CLERK_SECRET_KEY=sk_test_...
CLERK_JWKS_URL=https://becoming-salmon-61.clerk.accounts.dev/.well-known/jwks.json
```

---

## 인프라 설정

### Cloudflare Tunnel
- 터널명: `pigeonbrief`
- 터널 ID: `a35624e3-6d74-40ae-b253-ff5f09acb696`
- 설정 파일: `~/.cloudflared/config.yml`
- 연결: `api.pigeonbrief.com` → `localhost:8000`
- 자동 실행: `brew services start cloudflared`

### launchd 서비스
| 서비스 | plist 파일 | 역할 |
|--------|-----------|------|
| 파이프라인 | `com.pigeonbrief.pipeline.plist` | 매일 자동 수집·요약 |
| 백엔드 | `com.pigeonbrief.backend.plist` | FastAPI 서버 상시 실행 |
| Cloudflare | `homebrew.mxcl.cloudflared` | 터널 상시 유지 |

### Clerk
- 애플리케이션명: PigeonBrief
- 프론트엔드 API: `becoming-salmon-61.clerk.accounts.dev`
- 사용자 관리: [clerk.com 대시보드](https://clerk.com) → Users 메뉴
- 신규 사용자 초대: Configure → Restrictions → Allowlist에 이메일 추가

---

## LLM 설정 (processor/claude.py)

Claude API 대신 로컬 Ollama + qwen2.5:14b 사용.

```yaml
# config/settings.yaml
llm:
  model: qwen2.5:14b
  base_url: http://localhost:11434/v1
  max_input_tokens: 1000
  min_relevance_score: 0.6
```

- 1단계: 관련성 필터링 (JSON 배열 반환, `response_format: json_object`)
- 2단계: 한국어 3~4문장 요약
- API 비용 없음, 속도: 기사당 약 20~30초

---

## 파이프라인 상세

### 현재 상태 (2026-04-08 기준)
파이프라인은 아직 **YAML 파일 기반**으로 동작. DB 기반 사용자별 수집으로의 전환이 남은 작업.

### 현재 흐름
```
config/sections.json (YAML) → 수집 → Ollama 필터링·요약 → articles.json → git push → Vercel
```

### 목표 흐름 (미완성 — 남은 작업 1)
```
DB (사용자별 sections/rss/keywords) → 사용자별 수집 → Ollama 필터링·요약 → DB 저장 → git push
```

---

## 프론트엔드

### 인증 흐름
1. `index.html` 접속 → Clerk SDK 로드
2. 로그인 안 된 경우 → `sign-in.html`로 자동 이동
3. 로그인 완료 → `initApp()` 호출 → 백엔드 API에서 기사 로드
4. 헤더 로그아웃 버튼(→ 아이콘) → `Clerk.signOut()` → `sign-in.html`

### 설정 흐름 (settings.html)
- 헤더 ⚙️ 버튼 클릭 → `settings.html` 이동
- 섹션 추가/삭제, RSS 소스 추가/삭제, 키워드 추가/삭제
- 변경사항 즉시 API 호출로 DB 저장

### 기사 로드
- `app.js`의 `loadData()`: `GET https://api.pigeonbrief.com/api/articles` (Bearer 토큰)
- 기존 `articles.json` 파일 방식 → API 방식으로 전환 완료

---

## 남은 작업

### 1. 파이프라인 DB 전환 (미완료)

**목표**: `config/sections.json` (YAML) 대신 SQLite DB의 사용자별 설정을 읽어 수집

**변경 필요 파일:**
- `pipeline.py` — 사용자 루프 추가 (DB에서 전체 사용자 목록 조회 → 사용자별 실행)
- `collectors/rss.py` — `section` 파라미터를 DB rows 형태로 수신하도록 수정
- `collectors/keyword.py` — 동일
- `processor/dedup.py` — `seen_urls` 테이블을 사용자별로 분리
- `generator/build_site.py` — `articles.json` 생성 대신 DB에 저장

**구현 방향:**
```python
# pipeline.py 변경 흐름
users = db.get_all_users()
for user in users:
    sections = db.get_sections(user.id)
    for section in sections:
        articles = collect(section.rss_sources, section.keywords)
        deduped = dedup(articles, user.id)
        filtered = llm_filter(deduped, section)
        db.save_articles(filtered, user.id, section.id)
```

### 2. Clerk Allowlist 설정 (미완료)

신규 사용자가 가입하려면 Clerk 대시보드에서 이메일을 허용 목록에 추가해야 함.

**방법:**
1. [clerk.com](https://clerk.com) 로그인
2. PigeonBrief 프로젝트 선택
3. Configure → Restrictions → Allowlist
4. 초대할 사람의 이메일 추가

---

## 주요 변경 이력

### 2026-04-08

**LLM 교체: Claude API → Ollama 로컬 LLM**
- `processor/claude.py`: `anthropic` → `openai` (Ollama OpenAI 호환 API)
- 모델: `qwen2.5:14b` (맥미니 로컬 설치)
- `requirements.txt`: `anthropic` → `openai>=1.0.0`
- `config/settings.yaml`: `claude:` → `llm:` 섹션으로 변경
- Python 3.13 설치 (Homebrew), `.venv` 생성

**멀티유저 인증 및 개인화 시스템 추가**
- Cloudflare Tunnel 설치·설정 (`api.pigeonbrief.com`)
- `pigeonbrief.com` 도메인 Cloudflare에서 구매
- FastAPI 백엔드 신규 개발 (`backend/`)
  - SQLite DB 설계 (users, sections, rss_sources, keywords, articles, seen_urls)
  - Clerk JWT 검증 (`auth.py`)
  - 설정 CRUD API (`routers/settings.py`)
  - 기사 조회 API (`routers/articles.py`)
- Clerk 인증 연동
  - `website/sign-in.html` 신규 생성
  - `website/index.html` Clerk 인증 체크 + 로그아웃 버튼 추가
  - `website/settings.html` 신규 생성 (섹션/RSS/키워드 관리 UI)
  - `website/assets/app.js` API 호출 방식으로 전환
- launchd 서비스 등록 (`com.pigeonbrief.backend.plist`)

### 2026-04-06

**채널3 키워드 UI 개선 (`settings.js`, `style.css`)**
- 시각적 태그 빌더로 교체 (AND/OR/NOT 그룹)
- 쿼리 미리보기 실시간 확인

**헤더 디자인 개선 (`index.html`, `style.css`)**
- 비둘기 SVG 로고 추가
- 폰트: Libre Baskerville (Google Fonts)

---

## 주요 설계 결정

| 결정 | 이유 |
|------|------|
| Ollama 로컬 LLM | Claude API 비용 절감, 맥미니 상시 가동 활용 |
| FastAPI + SQLite | 경량, Python 기반(기존 코드와 통일), 외부 DB 불필요 |
| Cloudflare Tunnel | 공유기 포트포워딩 불필요, IP 노출 없음, 무료 |
| Clerk 인증 | 완성된 로그인 UI 제공, 10,000 MAU 무료 |
| 로그인 장벽 방식 | articles.json URL 보안보다 실용성 우선 (지인 대상 소규모 운영) |
| 파이프라인 per-user | 사용자별 독립적 설정, 소규모에서 단순함 우선 |
| dedup mark_as_seen 지연 | 사이트 생성 실패 시 다음 실행에서 재처리 가능하게 |
| launchd (not cron) | Mac 절전 후 자동 재실행, 로그 통합 관리 |
