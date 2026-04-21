"""
Phase 0 추가 검증 — 짧은 입력에 대한 프롬프트 A 되묻기 발생률 측정.

배경: v2 11개 주제 테스트에서 needs_clarification이 한 번도 true로 나오지 않음.
짧고 모호한 입력에서도 되묻지 않으면 사용자 경험이 떨어지므로 별도 검증.

실행:
    cd /Users/jtmini/claude_github/pigeonbrief
    python scripts/test_short_inputs.py
"""
import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from openai import OpenAI

from test_ai_keyword import (
    PROMPT_A_SYSTEM,
    MODEL,
    OLLAMA_BASE_URL,
    RESULTS_ROOT,
    call_llm,
)

# 짧고 모호한 입력 — 모두 needs_clarification=true가 나와야 이상적
SHORT_INPUTS = [
    "AI",
    "반도체",
    "투자",
    "암호화폐",
    "헬스케어",
    "스타트업",
    "기후변화",
    "주식",
    "바이오",
    "정치",
]


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M")
    out_dir = RESULTS_ROOT / f"{timestamp}-short-inputs"
    out_dir.mkdir(parents=True, exist_ok=True)

    client = OpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama")
    try:
        client.models.list()
    except Exception as e:
        print(f"❌ Ollama 연결 실패: {e}", file=sys.stderr)
        return 1

    results = []
    clarif_count = 0
    print(f"짧은 입력 {len(SHORT_INPUTS)}개에 대해 프롬프트 A 실행\n")

    for inp in SHORT_INPUTS:
        parsed, raw, elapsed = call_llm(client, PROMPT_A_SYSTEM, inp)
        needs = bool(parsed and parsed.get("needs_clarification"))
        if needs:
            clarif_count += 1
        intent = parsed.get("interpreted_intent", "-") if parsed else "(파싱 실패)"
        question = parsed.get("clarification_question", "") if parsed else ""
        options = parsed.get("clarification_options", []) if parsed else []
        mark = "🔁" if needs else "➡️ "
        print(f"  {mark} '{inp}' ({elapsed:.1f}s)")
        print(f"      intent: {intent}")
        if needs:
            print(f"      Q: {question}")
            for o in options:
                print(f"        - {o}")
        print()
        results.append({
            "input": inp,
            "elapsed_sec": round(elapsed, 2),
            "needs_clarification": needs,
            "interpreted_intent": intent,
            "clarification_question": question,
            "clarification_options": options,
            "raw": raw,
        })

    rate = clarif_count / len(SHORT_INPUTS)
    print(f"\n되묻기 발생률: {clarif_count}/{len(SHORT_INPUTS)} ({rate*100:.0f}%)")
    print(f"목표: ≥80% (8/10 이상)\n")

    summary = {
        "model": MODEL,
        "timestamp": timestamp,
        "total": len(SHORT_INPUTS),
        "clarification_count": clarif_count,
        "clarification_rate": rate,
        "target_rate": 0.8,
        "passed": rate >= 0.8,
        "results": results,
    }
    (out_dir / "result.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"저장: {out_dir / 'result.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
