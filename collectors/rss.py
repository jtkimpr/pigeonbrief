"""
채널 2: 직접 RSS 수집
섹션 설정의 channel2_rss.sources 목록에서 RSS 수집
"""
from collectors.utils import fetch_feed, parse_entries


def collect(section_config: dict, settings: dict) -> list:
    """
    채널 2 수집 메인 함수
    Returns: article dict 리스트
    """
    ch2 = section_config.get('channel2_rss', {})
    sources = ch2.get('sources', [])
    max_age = settings.get('pipeline', {}).get('max_age_hours', 24)
    section_id = section_config['id']

    print(f"  [채널2] 소스 {len(sources)}개")

    articles = []
    for source in sources:
        name = source.get('name', '')
        url = source.get('url', '').strip()
        if not url:
            continue
        print(f"  [채널2] 수집 중: {name}")
        feed = fetch_feed(url)
        items = parse_entries(feed, name, section_id, 2, max_age)
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
    for a in results[:3]:
        print(f"  [{a['source_name']}] {a['title'][:60]}")
