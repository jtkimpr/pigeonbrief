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

### 도메인 (Cloudflare DNS + Vercel)
- 도메인: `pigeonbrief.com` (Cloudflare에서 구매)
- 프론트엔드: `pigeonbrief.com` / `www.pigeonbrief.com` → Vercel (pigeonbrief 프로젝트)
- API: `api.pigeonbrief.com` → Cloudflare Tunnel → `localhost:8000`

**Cloudflare DNS 레코드**
| Type | Name | Value | Proxy |
|------|------|-------|-------|
| A | `@` | `216.198.79.1` | DNS only |
| CNAME | `www` | `530585508f0e547f.vercel-dns-017.com` | DNS only |

> Proxy를 DNS only(회색)로 유지해야 함 — Vercel이 SSL을 직접 처리하므로 Cloudflare 프록시와 충돌

**Vercel Domains 설정**
- `pigeonbrief.com` → 307 redirect → `www.pigeonbrief.com`
- `www.pigeonbrief.com` → Production

### Clerk
- 애플리케이션명: PigeonBrief
- 프론트엔드 API: `becoming-salmon-61.clerk.accounts.dev`
- 사용자 관리: [clerk.com 대시보드](https://clerk.com) → Users 메뉴
- 가입 방식: 오픈 가입 (Allowlist 비활성화 — 누구든 가입 가능)
- 신규 사용자 DB 등록: 로그인 후 설정 페이지(`/settings.html`) 첫 방문 시 자동 등록

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
파이프라인은 **DB 기반 사용자별 수집**으로 전환 완료.

### 현재 흐름
```
DB (사용자별 sections/rss/keywords)
  → 사용자별 수집 (rss.collect + keyword.collect)
  → seen_urls 필터 (pigeonbrief.db, 사용자별)
  → 배치 중복 제거 (URL 해시 + 제목 유사도)
  → Ollama 필터링·요약
  → articles 테이블 저장
  → seen_urls 기록
  → FastAPI /api/articles → 프론트엔드
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

(현재 미해결 이슈 없음)

---

## 주요 변경 이력

### 2026-04-09

**브라우저 "Failed to fetch" 해결 — `.env` 로드 import 순서 버그**
- 증상: `pigeonbrief.com` 로그인 후 `/api/articles` 호출이 브라우저에서 CORS 오류처럼 보이며 실패. 실제로는 백엔드가 500을 반환했고, 500 응답에는 CORSMiddleware가 헤더를 붙이지 못해 브라우저에 CORS 오류로 표출됨
- 근본 원인: `backend/main.py`가 `.env`를 로드하기 **전에** `from backend.routers import ...`를 먼저 실행 → `auth.py:15`의 `CLERK_JWKS_URL = os.environ.get(...)`이 모듈 로드 시점에 빈 문자열로 고정 → JWKS 조회 단계에서 `RuntimeError` 발생
- 수정:
  - `backend/main.py`: `.env` 로드 블록을 모든 `backend.*` import 위로 이동
  - `backend/auth.py`: `CLERK_JWKS_URL`을 모듈 전역 상수가 아닌 `_get_jwks()` 호출 시점에 `os.environ.get(...)`으로 읽도록 변경 (import 순서 의존성 제거, 재발 방지)
- 검증: `launchctl kickstart -k` 후 `/health` 200, `/api/articles`(인증 없음) 500 → 401 로 정상화. 브라우저에서도 정상 동작 확인

**`.env` 로딩을 `python-dotenv`로 교체 (후속)**
- 수동 파서(직접 파일 읽어 split)를 `dotenv.load_dotenv()`로 교체
- `Path(__file__).resolve().parent.parent / ".env"` 절대경로 지정 → cwd 의존성 제거
- `requirements.txt`에 `python-dotenv>=1.0.0` 추가
- `.venv`에 설치 후 launchd 재시작, 동일하게 정상 동작 확인

### 2026-04-08 (5차)

**신규 사용자 온보딩 위저드 추가 (`website/assets/app.js`, `website/assets/style.css`)**
- 로그인 후 섹션 없는 신규 사용자에게 `settings.html` 이탈 없이 인라인 3단계 위저드 표시
- Step 1: 주제 이름/설명 입력 → FastAPI 백엔드로 섹션 생성
- Step 2: RSS 피드 / 키워드 탭 전환 UI로 소스 등록 (스킵 가능)
- Step 3: 완료 화면 + "오늘 밤 첫 브리핑 도착" 수집 예약 안내
- 단계 인디케이터(●—●—●), 태그 목록, API 오류 처리 포함
- `loadData()`에 try-catch 추가 → 오류 시 "⚠️ 다시 시도" 버튼 표시 (빈 화면 방지)

**인프라 이슈 수정**
- Cloudflare 터널 plist(`homebrew.mxcl.cloudflared.plist`) 수정:
  - `ProgramArguments`에 `tunnel run pigeonbrief` 인수 추가 (누락으로 터널 미실행 상태였음)
  - `LimitLoadToSessionType` 제거 (bootstrap 오류 원인)
  - `KeepAlive: true` 설정 (프로세스 죽으면 자동 재시작)
- uvicorn 중복 프로세스 정리: 수동 실행 프로세스가 포트 점유 → launchd 재기동 실패 반복 → 정리 후 launchd 단독 관리로 정상화
- `com.pigeonbrief.backend.plist` 연결 plist는 정상, launchd로 uvicorn 관리 중

**미커밋 코드 Git 동기화**
- `pipeline.py`, `processor/claude.py`, `backend/database.py`, `processor/dedup.py` — 이전 세션에서 구현됐으나 미커밋 상태였던 변경사항 푸시 완료

### 2026-04-08 (4차)

**비로그인 랜딩 페이지 추가 (`website/index.html`, `website/assets/style.css`, `website/assets/app.js`)**

- `index.html`: `#landing` / `#app` 두 섹션으로 분리
  - 비로그인 → 랜딩 표시, 로그인 → 앱 표시 (Clerk 로드 후 전환)
  - `<head>` 인라인 스크립트로 `pb_loggedin` localStorage 플래그 확인 → 재방문 로그인 유저는 랜딩을 렌더링 전에 CSS로 즉시 숨겨 flash 완전 제거
  - 로그아웃 시 `pb_loggedin` 플래그 삭제 → 다음 방문 시 랜딩 재표시
- `style.css`: 랜딩 전용 스타일 추가 (landing-nav, hero, features-section, how-it-works, landing-bottom-cta, 반응형)
- `app.js`: 섹션 미등록 신규 사용자에게 빈 화면 대신 온보딩 안내 표시 ("첫 섹션 추가하기 →")

**랜딩 페이지 구성**
- 네비게이션: PigeonBrief 로고 + 로그인 버튼
- 히어로: "나만의 뉴스를 자동으로" + 설명 + CTA 버튼 + 샘플 뉴스 카드 3개
- 기능 소개: 📡 원하는 소스 구독 / 🤖 AI 자동 요약 / 🗂️ 주제별 정리
- 이용 방법: 3단계 (가입 → 주제·소스 등록 → 매일 자동 브리핑)
- 하단 CTA: 다크 배경 재강조

### 2026-04-08 (3차)

**도메인 연결 완료**
- Vercel Domains에 `pigeonbrief.com`, `www.pigeonbrief.com` 추가
- Cloudflare DNS에 A 레코드(`@` → `216.198.79.1`), CNAME(`www` → `530585508f0e547f.vercel-dns-017.com`) 추가
- Proxy status DNS only 설정 (Vercel SSL과 충돌 방지)
- `pigeonbrief.com` 접속 및 로그인 정상 확인
- Clerk Allowlist 비활성화 확인 (오픈 가입)

### 2026-04-08 (2차)

**파이프라인 DB 전환 완료**
- `pipeline.py`: `config/sections.json` → SQLite DB 기반 사용자별 루프로 전면 교체
  - `get_all_users()` → 사용자 루프
  - `get_user_sections_config()` → 섹션+RSS+키워드 조회
  - `filter_seen_urls()` / `mark_urls_seen()` → seen_urls 테이블 활용
  - `save_articles_to_db()` → articles 테이블 저장
  - git push 제거 (기사는 DB→API로 서빙)
- `backend/database.py`: 파이프라인 전용 헬퍼 5개 추가
  (`get_all_users`, `get_user_sections_config`, `filter_seen_urls`, `mark_urls_seen`, `save_articles_to_db`)
- `processor/dedup.py`: `run_batch()` 추가 (seen_urls 제외, 배치 내 중복만 처리)

### 2026-04-08 (1차)

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
