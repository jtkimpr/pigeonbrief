"""
Claude API 처리: 2단계
1단계: 섹션별 관련성 필터링 (제목+소스만 입력, 배치)
2단계: 한국어 요약 생성 (통과한 기사만, 본문 1000자 truncate)

비용 최적화:
- 필터링은 Haiku (간단한 분류 작업)
- 요약은 설정 모델 (기본 Haiku, 품질 원하면 Sonnet으로 변경)
- 시스템 프롬프트 캐싱 적용 (반복 호출 비용 절감)
"""
import os
import json
import re
from anthropic import Anthropic


def _get_client() -> Anthropic:
    key = os.environ.get('ANTHROPIC_API_KEY', '')
    if not key and os.path.exists('.env'):
        with open('.env') as f:
            for line in f:
                if line.startswith('ANTHROPIC_API_KEY='):
                    key = line.strip().split('=', 1)[1].strip().strip('"\'')
    if not key:
        raise ValueError(".env 파일에 ANTHROPIC_API_KEY를 설정하세요")
    return Anthropic(api_key=key)


def _parse_json(text: str) -> list:
    """Claude 응답에서 JSON 배열 추출 (마크다운 코드블록 포함 대응)"""
    text = re.sub(r'```(?:json)?\s*', '', text).strip('` \n')
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r'\[.*?\]', text, re.DOTALL)
        return json.loads(m.group()) if m else []


def filter_section(
    articles: list,
    section_config: dict,
    client: Anthropic,
    min_score: float = 0.6,
) -> list:
    """
    1단계: 관련성 필터링
    제목 + 소스만 입력 → 관련 기사만 반환
    필터링은 haiku 고정 (저비용 분류 작업)
    """
    if not articles:
        return []

    numbered = {i + 1: a for i, a in enumerate(articles)}
    article_list = '\n'.join(
        f"{i}. [{a['source_name']}] {a['title']}"
        for i, a in numbered.items()
    )

    try:
        response = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=512,
            system=[{
                "type": "text",
                "text": (
                    "You are a news relevance filter. "
                    "Given a list of articles, return ONLY a JSON array of relevant ones with scores. "
                    "Format: [{\"num\": 1, \"score\": 0.9}, ...] "
                    "Score 0.0–1.0. No explanation. JSON only."
                ),
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": (
                f"Topic: {section_config['name']}\n"
                f"Purpose: {section_config.get('description', '')}\n\n"
                f"Articles:\n{article_list}\n\n"
                f"Return JSON array with score >= {min_score}."
            )}],
        )
        results = _parse_json(response.content[0].text)
        relevant_nums = {r['num'] for r in results if isinstance(r, dict) and r.get('score', 0) >= min_score}
        return [numbered[n] for n in sorted(relevant_nums) if n in numbered]
    except Exception as e:
        print(f"  [warn] 필터링 실패 ({section_config['name']}): {e}")
        return articles  # 실패 시 전체 통과


def summarize_article(
    article: dict,
    client: Anthropic,
    model: str,
    max_chars: int = 1000,
) -> str:
    """
    2단계: 한국어 요약 생성
    영문 기사도 한국어로 요약
    시스템 프롬프트 캐싱으로 반복 비용 절감
    """
    content = article.get('raw_content', '').strip()
    if len(content) > max_chars:
        content = content[:max_chars] + '...'

    body = f"제목: {article['title']}\n\n본문:\n{content}" if content else f"제목: {article['title']}"

    try:
        response = client.messages.create(
            model=model,
            max_tokens=350,
            system=[{
                "type": "text",
                "text": (
                    "당신은 뉴스 요약 전문가입니다.\n"
                    "주어진 기사를 한국어로 3~4문장으로 요약하세요.\n"
                    "요약에는 반드시 다음을 포함하세요:\n"
                    "1) 무슨 일이 있었는지\n"
                    "2) 왜 중요한지\n"
                    "3) 독자(기업 CEO, 투자자, 의료 IT 전문가)에게 주는 시사점\n"
                    "영문 기사도 반드시 한국어로 요약하세요.\n"
                    "요약문만 출력하고 다른 설명은 하지 마세요."
                ),
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": body}],
        )
        return response.content[0].text.strip()
    except Exception as e:
        print(f"  [warn] 요약 실패: {article['title'][:40]} — {e}")
        return ''


def run(articles: list, settings: dict, section_configs: dict) -> list:
    """
    전체 Claude 처리 파이프라인
    section_configs: {section_id: section_config_dict}
    Returns: 필터링 통과 + 한국어 요약 완료된 article 리스트
    """
    model = settings.get('claude', {}).get('model', 'claude-haiku-4-5-20251001')
    max_chars = settings.get('claude', {}).get('max_input_tokens', 1000)
    min_score = settings.get('claude', {}).get('min_relevance_score', 0.6)

    client = _get_client()

    # 섹션별 그룹화
    by_section: dict = {}
    for a in articles:
        by_section.setdefault(a['section'], []).append(a)

    results = []
    for section_id, section_articles in by_section.items():
        section_cfg = section_configs.get(section_id, {'name': section_id})
        name = section_cfg.get('name', section_id)
        print(f"\n  [{name}] {len(section_articles)}개 → 필터링 중...")

        # 1단계: 관련성 필터링
        filtered = filter_section(section_articles, section_cfg, client, min_score)
        print(f"  [{name}] {len(filtered)}개 통과 → 한국어 요약 중...")

        # 2단계: 한국어 요약
        for i, article in enumerate(filtered, 1):
            summary = summarize_article(article, client, model, max_chars)
            article['summary_ko'] = summary
            article['included'] = True
            results.append(article)
            print(f"    ({i}/{len(filtered)}) {article['title'][:55]}")

    return results


if __name__ == '__main__':
    import yaml, os
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from collectors import rss, keyword
    from processor import dedup

    with open('config/settings.yaml') as f:
        settings = yaml.safe_load(f)

    section_configs = {}
    all_articles = []
    for sec_name in ['agentic-ai', 'epic-ai', 'financial-macro']:
        with open(f'config/sections/{sec_name}.yaml') as f:
            section = yaml.safe_load(f)
        section_configs[section['id']] = section
        all_articles += rss.collect(section, settings)
        all_articles += keyword.collect(section, settings)

    print(f'\n수집: {len(all_articles)}개')
    deduped, stats = dedup.run(all_articles)
    print(f'중복 제거 후: {stats["remaining"]}개\n')

    results = run(deduped, settings, section_configs)

    print(f'\n=== 최종 결과: {len(results)}개 ===')
    for a in results[:5]:
        print(f'\n[{a["section"]}] {a["title"]}')
        print(f'요약: {a["summary_ko"][:120]}...')

    dedup.mark_as_seen(deduped)
