# PigeonBrief — 프로젝트 구축 기록

개인 뉴스 수집·요약·표시 시스템. 매일 자동으로 RSS와 Google News에서 관심 주제별 뉴스를 수집하고, Claude AI가 한국어로 요약해 정적 웹사이트에 게시한다.

---

## 아키텍처 개요

```
launchd (매일 1회)
  └─ scripts/run_pipeline.sh
       └─ pipeline.py
            ├─ git pull (최신 설정 반영)
            ├─ collectors/rss.py      ← RSS 피드 수집
            ├─ collectors/keyword.py  ← Google News 키워드 수집
            ├─ processor/dedup.py     ← URL/제목 중복 제거 (SQLite)
            ├─ processor/claude.py    ← Claude AI 필터링 + 한국어 요약
            └─ generator/build_site.py → website/data/articles.json
                                              └─ git push → Vercel 자동 배포
```

브라우저에서 섹션/RSS/키워드 설정 → GitHub API로 `config/sections.json` 직접 저장 → 다음 파이프라인 실행 시 `git pull`로 반영.

---

## 디렉터리 구조

```
news-intelligence/
├── pipeline.py                  # 메인 실행 스크립트
├── config/
│   ├── settings.yaml            # 파이프라인 설정 (API키 경로, dedup DB 경로 등)
│   └── sections.json            # 섹션 정의 (브라우저에서 편집 가능)
├── collectors/
│   ├── rss.py                   # RSS 피드 수집
│   └── keyword.py               # Google News 키워드 수집 (gnews 라이브러리)
├── processor/
│   ├── dedup.py                 # SQLite 기반 URL 히스토리 중복 제거
│   └── claude.py                # Claude API 필터링 + 한국어 요약
├── generator/
│   └── build_site.py            # articles.json 생성 (7일 누적 방식)
├── scripts/
│   └── run_pipeline.sh          # launchd에서 호출하는 래퍼 스크립트
├── data/
│   └── history.db               # SQLite: 수집 이력 (중복 제거용)
└── website/                     # Vercel 배포 대상
    ├── index.html
    ├── data/
    │   ├── articles.json        # 파이프라인이 생성하는 뉴스 데이터
    │   └── site_config.json     # 브라우저 설정 UI 인증 정보
    └── assets/
        ├── app.js               # 메인 프론트엔드 로직
        ├── settings.js          # 설정 패널 UI
        └── style.css            # 스타일
```

---

## 핵심 설정 파일

### `config/settings.yaml`

```yaml
anthropic:
  api_key_file: ~/.anthropic_key   # Claude API 키 파일 경로
  model: claude-haiku-4-5-20251001 # 요약에 사용할 모델

dedup:
  url_history_db: data/history.db
  title_similarity_threshold: 0.85

site:
  max_age_days: 7                  # 기사 보존 기간 (일)

git:
  auto_push: true
```

### `config/sections.json`

```json
{
  "sections": [
    {
      "id": "agentic-ai",
      "name": "Agentic AI",
      "description": "AI 에이전트·LLM 관련 뉴스",
      "enabled": true,
      "channel2_rss": {
        "sources": [
          { "name": "TechCrunch AI", "url": "https://techcrunch.com/feed/" }
        ]
      },
      "channel3_keywords": {
        "max_age_hours": 24,
        "queries": [
          "AI agent OR agentic AI",
          "LLM reasoning NOT hype"
        ]
      }
    }
  ]
}
```

- `channel2_rss.sources`: RSS 피드 목록 (name + url)
- `channel3_keywords.queries`: Google News 검색 쿼리 (AND/OR/NOT 지원)
- `enabled: false`이면 파이프라인에서 건너뜀

### `website/data/site_config.json`

```json
{
  "password_hash": "c03084ab61b5c78401b61cf53278714b0b29e69bcec1b36e9c22afbddcbd5269",
  "github_repo": "jtkimpr/news-intelligence",
  "github_branch": "main",
  "config_path": "config/sections.json"
}
```

- `password_hash`: SHA-256 해시 (기본 비밀번호: `news2024`)
- 브라우저 설정 UI 로그인 시 검증
- GitHub PAT는 세션 중 메모리에만 저장 (로컬스토리지 미사용)

---

## 파이프라인 상세

### 1단계: 수집

**RSS (`collectors/rss.py`)**
- 각 섹션의 `channel2_rss.sources`를 feedparser로 파싱
- `published_parsed` → `published_at` (UTC ISO)

**키워드 (`collectors/keyword.py`)**
- gnews 라이브러리로 Google News 검색
- `max_age_hours` 기준 최근 기사만 수집

### 2단계: 중복 제거 (`processor/dedup.py`)

1. `history.db`에 기 수집된 URL 제거
2. 동일 URL 중복 제거
3. 제목 유사도(difflib) 기반 중복 제거 (`threshold: 0.85`)

`dedup.mark_as_seen()`: 사이트 JSON 생성 성공 후에만 DB에 기록 (실패 시 다음 실행에서 재처리)

### 3단계: Claude 처리 (`processor/claude.py`)

- **필터링**: 각 섹션 description 기준으로 관련 없는 기사 제거
- **요약**: 한국어 3~4문장 요약 생성
  - 입력: 본문 최대 1000자
  - 출력: 최대 350 토큰
  - 배치 처리 (API 비용 최적화)

### 4단계: 사이트 JSON 생성 (`generator/build_site.py`)

- 기존 `articles.json` 로드 → 새 기사와 병합
- `max_age_days`(기본 7일)보다 오래된 기사 자동 삭제
- 섹션별로 기사 분류 후 저장

출력 형식:
```json
{
  "generated_at": "2026-04-05T09:00:00Z",
  "total_articles": 42,
  "sections": [
    {
      "id": "agentic-ai",
      "name": "Agentic AI",
      "articles": [
        {
          "id": "sha256_prefix",
          "title": "...",
          "url": "https://...",
          "source_name": "TechCrunch",
          "published_at": "2026-04-05T07:30:00Z",
          "summary_ko": "한국어 요약..."
        }
      ]
    }
  ]
}
```

### 5단계: Git Push → Vercel 배포

```python
git add website/data/articles.json
git commit -m "daily update: 2026-04-05"
git push  # → Vercel이 자동 감지하여 배포
```

---

## 프론트엔드

### 탭 구조

```
[ Today ] [ Read Later ] | [ Agentic AI ] [ Epic AI ] [ Financial ] [ + ]
  고정 탭 (파란색)        구분선   주제별 탭 (검정, 드래그 가능)   새 섹션 추가
```

- **Today**: 최근 24시간 기사 (published_at 기준)
- **Read Later**: 사용자가 🔖로 저장한 기사
- **주제별 탭**: 드래그앤드롭으로 순서 변경 가능

### 카드 액션 (localStorage 기반)

| 버튼 | 동작 | 저장 키 |
|------|------|---------|
| ♥ 좋아요 | 토글 | `ni_liked` (object) |
| 🔖 나중에 읽기 | 토글 | `ni_read_later` (object) |
| ✕ 삭제 | 즉시 숨김 | `ni_deleted` (array) |

- 좋아요한 기사: 7일 자동삭제 시 localStorage에 전체 데이터 보존
- Read Later 탭에서 🔖 해제 시 목록에서 제거

### 설정 UI

⚙️ 버튼 → 현재 활성 탭의 섹션 설정 오픈 (Today/Read Later 탭에서는 섹션 목록)

**인증 흐름:**
1. SHA-256 비밀번호 검증 (sessionStorage로 세션 중 유지)
2. GitHub PAT 입력 (메모리에만 보관)
3. 섹션 편집 → GitHub API PUT으로 `config/sections.json` 저장

**섹션 편집:**
- 섹션명, RSS 소스(이름+URL) 추가/삭제
- 키워드 쿼리 추가/삭제 (AND/OR/NOT 사용 가능)
- 섹션 순서: 드래그앤드롭 → 자동 저장

---

## launchd 설정

`~/Library/LaunchAgents/com.pigeonbrief.pipeline.plist` 예시:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "...">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.pigeonbrief.pipeline</string>
  <key>ProgramArguments</key>
  <array>
    <string>/Users/jintaekim/news-intelligence/scripts/run_pipeline.sh</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>8</integer>
    <key>Minute</key>
    <integer>0</integer>
  </dict>
  <key>StandardOutPath</key>
  <string>/Users/jintaekim/news-intelligence/logs/pipeline.log</string>
  <key>StandardErrorPath</key>
  <string>/Users/jintaekim/news-intelligence/logs/pipeline.err</string>
</dict>
</plist>
```

---

## 비밀번호 변경 방법

```python
import hashlib
new_hash = hashlib.sha256("새비밀번호".encode()).hexdigest()
print(new_hash)
```

결과를 `website/data/site_config.json`의 `password_hash`에 저장.

---

## 주요 설계 결정

| 결정 | 이유 |
|------|------|
| 브라우저 → GitHub API 직접 저장 | 별도 백엔드 서버 불필요, Vercel 정적 호스팅 유지 |
| articles.json 7일 누적 | 하루치만 저장하면 파이프라인 실패 시 빈 화면; 누적으로 안정성 확보 |
| PAT를 세션 메모리에만 보관 | 보안 (localStorage에 토큰 저장 지양) |
| data-action 이벤트 위임 | 카드 제목에 따옴표 포함 시 onclick 인라인 JSON 파싱 오류 방지 |
| dedup mark_as_seen 지연 | 사이트 생성 실패 시 다음 실행에서 재처리 가능하게 |
| launchd (not cron) | Mac 절전 후 자동 재실행, 로그 통합 관리 |
