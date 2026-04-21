"""
Phase 0 — AI 키워드 제안 프롬프트 단독 검증 스크립트

목적: docs/ai_keyword_design.md의 프롬프트 A, B를 10개 테스트 주제에 대해 실행하고
결과를 JSON으로 저장. 수동 평가 후 프롬프트 튜닝에 사용.

실행:
    cd /Users/jtmini/claude_github/pigeonbrief
    python scripts/test_ai_keyword.py

결과:
    data/test_results/<YYYY-MM-DD-HHMM>/<주제번호>.json
    data/test_results/<YYYY-MM-DD-HHMM>/summary.md
"""
import json
import re
import socket
import sys
import time
from datetime import datetime
from pathlib import Path

import feedparser
from openai import OpenAI

socket.setdefaulttimeout(10)

# ----------------------------------------------------------------------------
# 설정
# ----------------------------------------------------------------------------

OLLAMA_BASE_URL = "http://localhost:11434/v1"
MODEL = "qwen2.5:14b"

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_ROOT = REPO_ROOT / "data" / "test_results"

# ----------------------------------------------------------------------------
# 테스트 주제 10개 (docs/ai_keyword_design.md 9.1 참조)
# ----------------------------------------------------------------------------

TEST_TOPICS = [
    {
        "id": 1,
        "category": "헬스케어 IT / 비즈니스 모델",
        "topic": (
            "나는 유비케어라는 한국 EMR 회사의 대표다. 우리 제품을 클라우드/AI 기반 차세대 EMR로 "
            "업그레이드 중이며, 향후 미국 EPIC처럼 의사 대상 서비스 사업자로부터 연동수수료, 제약사로부터 "
            "마케팅 수수료를 받는 모델로 진화하려 한다. 미국에서 의사를 상대로 IT 서비스를 제공하는 "
            "사업자들(EPIC 등)이 어떤 사업을 하는지, AI를 어떻게 활용하는지에 대한 뉴스를 보고 싶다."
        ),
    },
    {
        "id": 2,
        "category": "엔터프라이즈 AI 활용 사례",
        "topic": (
            "기업들이 AI 또는 AI Agent를 활용해 임직원 업무를 고도화하고 생산성을 개선하며 "
            "새로운 사업기회를 포착한 사례를 보고 싶다."
        ),
    },
    {
        "id": 3,
        "category": "Legal Tech",
        "topic": "생성형 AI가 법률 산업에 미치는 영향",
    },
    {
        "id": 4,
        "category": "지정학 + 산업",
        "topic": "반도체 산업의 지정학적 이슈 (미중 갈등, 수출 규제)",
    },
    {
        "id": 5,
        "category": "바이오 / 한국",
        "topic": "한국 바이오 신약 임상 결과 및 FDA 승인 동향",
    },
    {
        "id": 6,
        "category": "빅테크 / 재무",
        "topic": "글로벌 빅테크 기업의 분기 실적과 AI 투자 전략",
    },
    {
        "id": 7,
        "category": "우주 산업",
        "topic": "우주 발사체 산업 — SpaceX 외 신생 기업 동향",
    },
    {
        "id": 8,
        "category": "한국 / 거시 정책",
        "topic": "한국 부동산 정책 및 금리가 시장에 미치는 영향",
    },
    {
        "id": 9,
        "category": "신기술",
        "topic": "양자컴퓨팅의 상용화 진전과 응용 분야",
    },
    {
        "id": 10,
        "category": "벤처 / 투자",
        "topic": "스타트업 시드 투자 트렌드 (특히 AI 분야)",
    },
    {
        "id": 11,
        "category": "개인 자산배분 / 시장 동향",
        "topic": (
            "나는 금융자산을 원화현금, 달러현금, KOSPI200 ETF, KOSDAQ150 ETF, NASDAQ100 ETF, "
            "SCHD, 미국 장기채 ETF에 장기 투자하면서 주기적으로 비중을 조절한다. 장기적 관점에서 "
            "한국·미국 주식시장과 채권시장 동향, 그리고 비중 조절의 필요성에 대한 인사이트를 얻을 수 있는 "
            "뉴스를 받고 싶다."
        ),
    },
]

# ----------------------------------------------------------------------------
# 프롬프트 (docs/ai_keyword_design.md 4절 참조 — 변경 시 양쪽 모두 업데이트)
# ----------------------------------------------------------------------------

PROMPT_VERSION = "v2"

PROMPT_A_SYSTEM = """당신은 뉴스 검색 전문가입니다. 사용자가 자연어로 설명한 관심 주제를 받아서 그 의도를 명확히 파악하고, 필요 시 1회만 되묻습니다.

## 작업
1. 사용자의 진짜 의도를 한 문장으로 재정리한다 (사용자 입력 언어와 동일 언어).
2. 되묻기가 필요한지 판단한다.

## 되묻기 판단 기준 (중요)
다음 중 하나에 해당하면 needs_clarification=true:
- 주제 안에 뚜렷이 구분되는 관점이 2개 이상 가능 (예: "AI" → 기술/규제/투자/사례 등)
- 주제가 한국/글로벌, 산업/일반 등 범위가 모호
- 시간 관점(최신 동향 vs 장기 분석)이 모호

다음에 해당하면 needs_clarification=false:
- 사용자가 이미 충분히 구체적으로 설명함 (예: 회사명, 시장, 관점 명시)
- 사용자가 긴 설명으로 맥락을 이미 제공함

## 출력 JSON (다른 텍스트 금지)
{
  "interpreted_intent": "한 문장 (사용자 언어로)",
  "needs_clarification": true | false,
  "clarification_question": "1개 질문 또는 빈 문자열",
  "clarification_options": ["선택지1", "선택지2", "선택지3", "모두 포함"]
}

needs_clarification=false면 question="", options=[].

## 예시

입력: "AI"
출력: {"interpreted_intent":"AI 관련 뉴스에 관심이 있다","needs_clarification":true,"clarification_question":"AI의 어떤 측면에 가장 관심이 있으세요?","clarification_options":["빅테크 기업의 AI 제품/전략","AI 규제 및 정책","AI 스타트업/투자 동향","기업의 AI 도입 사례","모두 포함"]}

입력: "나는 유비케어 EMR 회사 대표인데 미국 EPIC 같은 의사 대상 IT 사업자들의 AI 활용 사례 뉴스가 필요해"
출력: {"interpreted_intent":"미국에서 의사 대상 IT 서비스를 제공하는 EPIC 등 사업자들의 AI 활용 사례와 사업 동향","needs_clarification":false,"clarification_question":"","clarification_options":[]}
"""

PROMPT_B_SYSTEM = """당신은 뉴스 검색 전문가입니다. 확정된 관심 주제를 받아서, 사용자가 즉시 뉴스 검색에 사용할 수 있는 **검색 키워드 세트**를 만듭니다.

## 핵심 원칙 (반드시 준수)
1. **표면 단어 반복 금지**: 사용자 주제의 단어를 그대로 키워드로 베끼지 마세요. 예: 주제가 "AI 활용 사례"여도 "AI", "활용 사례"는 검색용으로 무가치함. 대신 "Copilot enterprise rollout", "AI agent deployment case" 같은 **검색에 실제로 통하는 표현**으로 풀어쓰세요.
2. **검색에 통하는 표현 사용**: 실제 뉴스 헤드라인에 자주 등장하는 용어를 선택. 너무 학술적이거나 너무 일반적이면 안 됨.
3. **고유명사 우선**: related_entities에는 일반명사 절대 금지. 회사명, 제품명, 인물명, 기관명, 기술명만 허용.

## 출력 JSON (다른 텍스트 금지)
{
  "core_keywords": ["핵심 키워드 3~5개 — 검색에 즉시 통하는 구체적 용어"],
  "related_entities": ["고유명사만 3~5개 — 회사/제품/인물/기관"],
  "related_concepts": ["관련 개념 3~5개 — 검색용으로 활용 가능한 용어"],
  "exclude_keywords": ["노이즈 방지 키워드 최소 2개"],
  "recommended_query": "Google News/Naver에서 작동하는 검색 쿼리 (AND/OR/NOT)",
  "recommended_rss": [
    {"name": "소스명", "url": "https://...", "reason": "한 줄 이유"}
  ]
}

## 세부 규칙

**core_keywords**
- 주제 단어 그대로 베끼기 금지
- 헤드라인에 등장할 만한 구체적 표현
- 영어 주제: 영어 위주 + 한국어 1~2개 병기 / 한국어 주제: 한국어 위주 + 영어 1~2개 병기

**related_entities (가장 중요)**
- ✅ OK: "Epic Systems", "TSMC", "Federal Reserve", "Sam Altman", "Salesforce Einstein"
- ❌ 금지: "한국은행", "주택 보유자", "ETF 투자", "한국 증권시장" 같은 일반명사/추상명사
- 모르면 빈 배열 []이 낫다. 추측 금지.

**exclude_keywords**
- 최소 2개 이상 제시
- 해당 주제 검색 시 흔히 나오는 노이즈를 식별 (예: 자산배분 주제 → "코인", "단타", "급등주")

**recommended_query**
- 정확한 따옴표/괄호 구문
- 예: `("legal AI" OR "Harvey AI") AND ("law firm" OR "litigation") NOT ("immigration")`

**recommended_rss (가장 위험한 영역)**
- ⚠️ RSS URL은 환각이 매우 흔함. 100% 확신하는 것만.
- 한국 매체 RSS 경로는 자주 변경되므로 특히 위험. 확신 없으면 한국 매체는 제외.
- 본인이 직접 본 적 없는 URL은 절대 만들지 말 것. 빈 배열 []이 가짜 URL보다 100배 낫다.
- 안전한 영문 메이저 매체(TechCrunch, Reuters, Bloomberg, The Verge 등)는 OK.
- 의심스러우면 그냥 빼라.

## 예시 (좋은 출력)

입력: "생성형 AI가 법률 산업에 미치는 영향"
출력:
{
  "core_keywords": ["generative AI legal", "Harvey AI", "legal tech adoption", "AI law firm", "리걸테크"],
  "related_entities": ["Harvey AI", "Casetext", "Thomson Reuters", "LexisNexis", "Allen & Overy"],
  "related_concepts": ["contract review automation", "e-discovery", "legal research AI", "AI ethics in law", "billable hour disruption"],
  "exclude_keywords": ["immigration law", "crypto regulation", "true crime"],
  "recommended_query": "(\\"generative AI\\" OR \\"legal AI\\" OR \\"Harvey AI\\") AND (\\"law firm\\" OR \\"litigation\\" OR \\"legal tech\\") NOT (\\"immigration\\" OR \\"crypto\\")",
  "recommended_rss": [
    {"name": "TechCrunch", "url": "https://techcrunch.com/feed/", "reason": "리걸테크 스타트업 보도 활발"}
  ]
}
"""


# ----------------------------------------------------------------------------
# 핵심 함수
# ----------------------------------------------------------------------------

def call_llm(client: OpenAI, system: str, user: str) -> tuple[dict | None, str, float]:
    """LLM 호출. (parsed_json, raw_text, elapsed_seconds) 반환. 파싱 실패 시 parsed_json=None."""
    start = time.time()
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
        temperature=0.3,
    )
    elapsed = time.time() - start
    raw = response.choices[0].message.content or ""
    parsed = _safe_parse_json(raw)
    return parsed, raw, elapsed


def _safe_parse_json(text: str) -> dict | None:
    text = re.sub(r"```(?:json)?\s*", "", text).strip("` \n")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                return None
        return None


def validate_rss(url: str) -> tuple[bool, str]:
    """RSS URL을 feedparser로 검증. (통과여부, 사유) 반환."""
    try:
        f = feedparser.parse(url)
        n = len(f.entries)
        status = getattr(f, "status", None)
        if n > 0 and (status is None or status < 400):
            return True, f"{n} entries"
        return False, f"status={status}, entries={n}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


_PROPER_NOUN_HINTS = (
    # 일반/추상 명사 — related_entities에 들어오면 안 됨
    "시장", "산업", "투자", "기업", "회사", "사업자", "사용자", "고객", "정부",
    "관계", "동향", "전략", "정책", "기술", "혁신", "분석", "활용", "사례",
    "market", "industry", "sector", "investment", "strategy", "policy",
    "technology", "innovation", "company", "enterprise", "user",
)


def evaluate_topic(parsed_b: dict | None, rss_results: list[dict]) -> dict:
    """프롬프트 B 출력 자동 평가. 객관적 항목만."""
    if not parsed_b:
        return {"auto_score": 0, "checks": {"parse": False}}

    checks = {}
    # 1. core_keywords 개수 (3~5개)
    ck = parsed_b.get("core_keywords", []) or []
    checks["core_keywords_count_ok"] = 3 <= len(ck) <= 5

    # 2. related_entities 고유명사 검사 (휴리스틱)
    re_list = parsed_b.get("related_entities", []) or []
    impure = [e for e in re_list if any(h in str(e).lower() for h in _PROPER_NOUN_HINTS)]
    checks["entities_count_ok"] = 3 <= len(re_list) <= 5
    checks["entities_proper_noun_ok"] = len(impure) == 0
    checks["entities_impure_examples"] = impure

    # 3. exclude_keywords 최소 2개
    ek = parsed_b.get("exclude_keywords", []) or []
    checks["exclude_min_2"] = len(ek) >= 2

    # 4. recommended_query 비어있지 않음
    rq = parsed_b.get("recommended_query", "")
    checks["query_present"] = bool(rq and len(rq) > 10)

    # 5. RSS 통과율
    total_rss = len(rss_results)
    pass_rss = sum(1 for r in rss_results if r["ok"])
    checks["rss_total"] = total_rss
    checks["rss_passed"] = pass_rss
    checks["rss_pass_rate"] = round(pass_rss / total_rss, 2) if total_rss else None
    # RSS가 0개여도 환각 없으면 OK로 본다
    checks["rss_no_hallucination"] = (total_rss == 0) or (pass_rss == total_rss)

    # 종합 점수 (5점 만점) — 객관적 항목만
    score = 0
    if checks["core_keywords_count_ok"]: score += 1
    if checks["entities_count_ok"] and checks["entities_proper_noun_ok"]: score += 1
    if checks["exclude_min_2"]: score += 1
    if checks["query_present"]: score += 1
    if checks["rss_no_hallucination"]: score += 1

    return {"auto_score": score, "checks": checks}


def run_topic(client: OpenAI, topic: dict, out_dir: Path) -> dict:
    """단일 주제에 대해 프롬프트 A → B 실행. 결과 dict 반환."""
    print(f"\n[{topic['id']}] {topic['category']}")
    print(f"    주제: {topic['topic'][:80]}...")

    # 프롬프트 A
    print("    → 프롬프트 A (해석 + 되묻기) 실행 중...")
    a_parsed, a_raw, a_time = call_llm(client, PROMPT_A_SYSTEM, topic["topic"])
    print(f"      완료 ({a_time:.1f}s, JSON 파싱: {'OK' if a_parsed else 'FAIL'})")

    # 프롬프트 B 입력 구성: 원 주제 + (있으면) 해석된 의도
    if a_parsed and a_parsed.get("interpreted_intent"):
        b_input = (
            f"원 주제: {topic['topic']}\n\n"
            f"해석된 의도: {a_parsed['interpreted_intent']}"
        )
    else:
        b_input = topic["topic"]

    # 프롬프트 B
    print("    → 프롬프트 B (키워드 + RSS 추천) 실행 중...")
    b_parsed, b_raw, b_time = call_llm(client, PROMPT_B_SYSTEM, b_input)
    print(f"      완료 ({b_time:.1f}s, JSON 파싱: {'OK' if b_parsed else 'FAIL'})")

    # RSS 검증
    rss_results = []
    if b_parsed:
        for rss in b_parsed.get("recommended_rss", []) or []:
            url = rss.get("url", "")
            ok, reason = validate_rss(url)
            rss_results.append({"name": rss.get("name", ""), "url": url, "ok": ok, "reason": reason})
            print(f"      RSS {'✅' if ok else '❌'} {rss.get('name','')}: {reason}")

    # 자동 평가
    evaluation = evaluate_topic(b_parsed, rss_results)
    print(f"      자동 점수: {evaluation['auto_score']}/5")

    result = {
        "id": topic["id"],
        "category": topic["category"],
        "topic": topic["topic"],
        "prompt_version": PROMPT_VERSION,
        "prompt_a": {
            "elapsed_sec": round(a_time, 2),
            "parse_ok": a_parsed is not None,
            "parsed": a_parsed,
            "raw": a_raw,
        },
        "prompt_b": {
            "elapsed_sec": round(b_time, 2),
            "parse_ok": b_parsed is not None,
            "parsed": b_parsed,
            "raw": b_raw,
        },
        "rss_validation": rss_results,
        "evaluation": evaluation,
    }

    out_path = out_dir / f"{topic['id']:02d}.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def write_summary(results: list[dict], out_dir: Path) -> None:
    """수동 평가용 마크다운 요약."""
    lines = ["# AI 키워드 제안 프롬프트 검증 결과", ""]
    lines.append(f"실행 시각: {out_dir.name}")
    lines.append(f"모델: {MODEL}")
    lines.append(f"테스트 주제 수: {len(results)}")
    lines.append("")

    lines.append(f"프롬프트 버전: {PROMPT_VERSION}")
    lines.append("")

    # 요약 표
    lines.append("## 요약 표")
    lines.append("")
    lines.append("| # | 카테고리 | A | B | A초 | B초 | RSS pass | 자동점수 |")
    lines.append("|---|----------|---|---|-----|-----|----------|----------|")
    total_score = 0
    for r in results:
        ev = r.get("evaluation", {})
        ck = ev.get("checks", {})
        rss_str = f"{ck.get('rss_passed','-')}/{ck.get('rss_total','-')}"
        score = ev.get("auto_score", 0)
        total_score += score
        lines.append(
            f"| {r['id']} | {r['category']} | "
            f"{'✅' if r['prompt_a']['parse_ok'] else '❌'} | "
            f"{'✅' if r['prompt_b']['parse_ok'] else '❌'} | "
            f"{r['prompt_a']['elapsed_sec']}s | "
            f"{r['prompt_b']['elapsed_sec']}s | "
            f"{rss_str} | "
            f"{score}/5 |"
        )
    lines.append("")
    lines.append(f"**전체 평균 자동 점수: {total_score / len(results):.2f}/5** ({total_score}/{len(results)*5})")
    lines.append("")

    # 각 주제 상세
    lines.append("## 상세 결과")
    lines.append("")
    for r in results:
        lines.append(f"### [{r['id']}] {r['category']}")
        lines.append("")
        lines.append(f"**주제**: {r['topic']}")
        lines.append("")

        lines.append("**프롬프트 A (해석 + 되묻기)**")
        if r["prompt_a"]["parsed"]:
            p = r["prompt_a"]["parsed"]
            lines.append(f"- 해석: {p.get('interpreted_intent', '-')}")
            lines.append(f"- 되묻기 필요: {p.get('needs_clarification', '-')}")
            if p.get("clarification_question"):
                lines.append(f"- 질문: {p['clarification_question']}")
                for opt in p.get("clarification_options", []):
                    lines.append(f"  - {opt}")
        else:
            lines.append("- ❌ JSON 파싱 실패")
            lines.append(f"  ```\n  {r['prompt_a']['raw'][:500]}\n  ```")
        lines.append("")

        lines.append("**프롬프트 B (키워드 + RSS)**")
        if r["prompt_b"]["parsed"]:
            p = r["prompt_b"]["parsed"]
            lines.append(f"- 핵심 키워드: {', '.join(p.get('core_keywords', []))}")
            lines.append(f"- 관련 기업/인물: {', '.join(p.get('related_entities', []))}")
            lines.append(f"- 관련 개념: {', '.join(p.get('related_concepts', []))}")
            lines.append(f"- 제외 키워드: {', '.join(p.get('exclude_keywords', []))}")
            lines.append(f"- 검색 쿼리: `{p.get('recommended_query', '-')}`")
            rss = p.get("recommended_rss", [])
            if rss:
                lines.append("- 추천 RSS:")
                for s in rss:
                    lines.append(f"  - **{s.get('name', '?')}**: {s.get('url', '?')} — {s.get('reason', '')}")
            else:
                lines.append("- 추천 RSS: (없음)")
        else:
            lines.append("- ❌ JSON 파싱 실패")
            lines.append(f"  ```\n  {r['prompt_b']['raw'][:500]}\n  ```")
        lines.append("")
        # 자동 평가 결과
        ev = r.get("evaluation", {})
        ck = ev.get("checks", {})
        lines.append(f"**자동 평가 (점수 {ev.get('auto_score','-')}/5)**")
        lines.append(f"- core_keywords 개수 (3~5): {'✅' if ck.get('core_keywords_count_ok') else '❌'}")
        lines.append(f"- related_entities 개수 (3~5): {'✅' if ck.get('entities_count_ok') else '❌'}")
        lines.append(f"- related_entities 고유명사: {'✅' if ck.get('entities_proper_noun_ok') else '❌ '+str(ck.get('entities_impure_examples',[]))}")
        lines.append(f"- exclude_keywords ≥2: {'✅' if ck.get('exclude_min_2') else '❌'}")
        lines.append(f"- recommended_query 존재: {'✅' if ck.get('query_present') else '❌'}")
        lines.append(f"- RSS 환각 없음: {'✅' if ck.get('rss_no_hallucination') else '❌'} ({ck.get('rss_passed','-')}/{ck.get('rss_total','-')} pass)")
        if r.get("rss_validation"):
            for rv in r["rss_validation"]:
                mark = "✅" if rv["ok"] else "❌"
                lines.append(f"  - {mark} {rv['name']}: {rv['reason']}")
        lines.append("")
        lines.append("---")
        lines.append("")

    (out_dir / "summary.md").write_text("\n".join(lines))


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M")
    out_dir = RESULTS_ROOT / f"{timestamp}-{PROMPT_VERSION}"
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"결과 저장 경로: {out_dir}")

    client = OpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama")

    # Ollama 헬스체크
    try:
        client.models.list()
    except Exception as e:
        print(f"❌ Ollama 연결 실패: {e}", file=sys.stderr)
        print(f"   {OLLAMA_BASE_URL}에서 Ollama가 실행 중이고 {MODEL} 모델이 설치되어 있는지 확인하세요.")
        return 1

    results = []
    total_start = time.time()
    for topic in TEST_TOPICS:
        try:
            results.append(run_topic(client, topic, out_dir))
        except Exception as e:
            print(f"    ❌ 주제 {topic['id']} 실행 실패: {e}", file=sys.stderr)
            results.append({
                "id": topic["id"],
                "category": topic["category"],
                "topic": topic["topic"],
                "error": str(e),
                "prompt_a": {"parse_ok": False, "elapsed_sec": 0, "parsed": None, "raw": ""},
                "prompt_b": {"parse_ok": False, "elapsed_sec": 0, "parsed": None, "raw": ""},
            })

    total_elapsed = time.time() - total_start
    print(f"\n총 소요 시간: {total_elapsed/60:.1f}분")

    write_summary(results, out_dir)
    print(f"요약 파일: {out_dir / 'summary.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
