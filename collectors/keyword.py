"""
채널 3: Google News RSS 키워드 검색 수집
섹션 설정의 channel3_keywords.queries를 AND/OR/NOT 쿼리로 검색
한글 포함 쿼리 → 한국어 Google News, 영문 쿼리 → 영문 Google News
"""
import urllib.parse
from collectors.utils import fetch_feed, parse_entries


def build_gnews_url(query: str) -> str:
    """
    Google News RSS 검색 URL 생성
    한글 포함 여부로 언어/지역 자동 감지
    """
    has_korean = any('\uAC00' <= c <= '\uD7A3' for c in query)
    encoded = urllib.parse.quote(query)

    if has_korean:
        return (
            f"https://news.google.com/rss/search"
            f"?q={encoded}&hl=ko&gl=KR&ceid=KR:ko"
        )
    else:
        return (
            f"https://news.google.com/rss/search"
            f"?q={encoded}&hl=en-US&gl=US&ceid=US:en"
        )


def collect(section_config: dict, settings: dict) -> list:
    """
    채널 3 수집 메인 함수
    Returns: article dict 리스트
    """
    ch3 = section_config.get('channel3_keywords', {})
    queries = ch3.get('queries', [])
    # 채널 3은 Google News 검색 특성상 결과가 오래된 경우 많음 → 섹션 설정에서 override 가능
    default_max_age = settings.get('pipeline', {}).get('max_age_hours', 24)
    max_age = ch3.get('max_age_hours', default_max_age * 3)  # 기본값: 전역 설정의 3배
    section_id = section_config['id']

    print(f"  [채널3] 쿼리 {len(queries)}개")

    articles = []
    for query in queries:
        url = build_gnews_url(query)
        source_name = f"Google News: {query[:40]}"
        print(f"  [채널3] 검색: {query[:50]}")
        feed = fetch_feed(url)
        items = parse_entries(feed, source_name, section_id, 3, max_age)
        print(f"          → {len(items)}개")
        articles.extend(items)

    return articles


if __name__ == '__main__':
    import yaml, os
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    with open('config/settings.yaml') as f:
        settings = yaml.safe_load(f)
    with open('config/sections/epic-ai.yaml') as f:
        section = yaml.safe_load(f)

    results = collect(section, settings)
    print(f"\n총 {len(results)}개 수집")
    for a in results[:5]:
        print(f"  [{a['source_name'][:30]}] {a['title'][:60]}")
