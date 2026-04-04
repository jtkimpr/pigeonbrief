# news-intelligence

3개 채널에서 수집한 콘텐츠를 Claude API로 필터링·요약해, 주제별 카드뉴스 스타일 웹사이트로 매일 자동 발행하는 개인 뉴스 인텔리전스 시스템.

## 섹션

| 섹션 | 설명 |
|------|------|
| Agentic AI | 기업용 AI 에이전트 트렌드·도입 사례 |
| EPIC AI | Epic Systems AI 전략 벤치마크, 국내외 의료 IT |
| Financial Macro | S&P500·Nasdaq·미국 장기채 관련 매크로 동향 |

## 수집 채널

- **채널 1**: Feedly OPML 기반 RSS (폴더별 섹션 매핑)
- **채널 2**: 직접 RSS 수집 (Feedly 미등록 소스 보완)
- **채널 3**: Google News RSS 키워드 검색 (AND/OR/NOT 쿼리)

## 실행 환경

- Mac Mini M4 (launchd 새벽 자동 실행)
- Python 3.13+
- Claude API

## 구조

```
collectors/   채널별 수집기
processor/    중복 제거 + Claude 필터링·요약
generator/    정적 사이트 생성
website/      Vercel 배포 대상
config/       섹션 설정 파일 (YAML)
scripts/      파이프라인 실행 스크립트
```

## 설정

```bash
cp .env.example .env
# .env에 ANTHROPIC_API_KEY 입력
pip install -r requirements.txt
```
