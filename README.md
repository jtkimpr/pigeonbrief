# PigeonBrief

RSS·Google News에서 주제별 뉴스를 수집해 로컬 LLM으로 필터링·요약, 회원제 웹사이트로 자동 발행하는 개인 뉴스 인텔리전스 시스템.

## 아키텍처

```
[사용자 브라우저]
  ↕ Clerk 인증 / 기사·설정 API 호출
[Vercel — 프론트엔드]
  ↕
[Cloudflare Tunnel — api.pigeonbrief.com]
  ↕
[Mac Mini M4]
  ├── FastAPI 백엔드 (port 8000)
  ├── SQLite DB (data/pigeonbrief.db)
  └── 파이프라인 (launchd 자동 실행)
        ├── collectors/   RSS + Google News 수집
        ├── processor/    중복 제거 + Ollama 필터링·요약
        └── generator/    사이트 데이터 생성
```

## 실행 환경

- Mac Mini M4 / Python 3.13 / `.venv`
- Ollama + qwen2.5:14b (로컬 LLM)
- Cloudflare Tunnel (`api.pigeonbrief.com`)
- Clerk (인증)
- Vercel (프론트엔드 배포)

## 구조

```
backend/      FastAPI 백엔드 (API 서버)
collectors/   채널별 수집기
processor/    중복 제거 + LLM 필터링·요약
generator/    사이트 데이터 생성
website/      Vercel 배포 대상
config/       파이프라인 설정 파일 (YAML)
scripts/      실행 스크립트
data/         SQLite DB 저장 위치
```

## 초기 설정

```bash
/opt/homebrew/bin/python3.13 -m venv .venv
.venv/bin/pip install -r requirements.txt

cp .env.example .env
# .env에 Clerk 키 입력 (CLERK_JWKS_URL 등)
```

## 백엔드 실행

```bash
.venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000
# launchd 자동 실행: com.pigeonbrief.backend.plist
```

## 파이프라인 실행

```bash
.venv/bin/python3.13 pipeline.py
# launchd 자동 실행: com.pigeonbrief.pipeline.plist
```

상세 내용은 `PIGEONBRIEF.md` 참조.
