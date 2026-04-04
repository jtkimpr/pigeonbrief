"""
채널 1: Feedly OPML 기반 RSS 수집
OPML 파일에서 폴더명 매칭 → 피드 URL 추출 → RSS 수집
"""
import xml.etree.ElementTree as ET
from collectors.utils import fetch_feed, parse_entries


def parse_opml(opml_file: str, folder_name: str) -> list:
    """
    OPML 파일에서 folder_name과 일치하는 폴더의 피드 목록 반환
    Returns: [(feed_url, source_name), ...]
    """
    try:
        tree = ET.parse(opml_file)
    except FileNotFoundError:
        print(f"  [warn] OPML 파일 없음: {opml_file}")
        print("  → Feedly에서 OPML 내보내기 후 config/feedly.opml에 저장하세요")
        return []
    except ET.ParseError as e:
        print(f"  [warn] OPML 파싱 실패: {e}")
        return []

    root = tree.getroot()
    feeds = []

    for outline in root.iter('outline'):
        # 폴더 outline: xmlUrl 없고 text/title이 folder_name과 일치
        if outline.get('xmlUrl'):
            continue
        name = outline.get('text') or outline.get('title', '')
        if name.strip() == folder_name.strip():
            for feed in outline:
                xml_url = feed.get('xmlUrl', '').strip()
                feed_name = feed.get('text') or feed.get('title', xml_url)
                if xml_url:
                    feeds.append((xml_url, feed_name))

    if not feeds:
        print(f"  [warn] OPML에서 폴더 '{folder_name}' 를 찾지 못했습니다")

    return feeds


def collect(section_config: dict, settings: dict) -> list:
    """
    채널 1 수집 메인 함수
    section_config: YAML에서 로드한 섹션 설정
    settings: settings.yaml 전역 설정
    Returns: article dict 리스트
    """
    ch1 = section_config.get('channel1_feedly_opml')
    if not ch1:
        return []

    folder_name = ch1.get('folder', '')
    opml_file = ch1.get('opml_file', 'config/feedly.opml')
    max_age = settings.get('pipeline', {}).get('max_age_hours', 24)
    section_id = section_config['id']

    print(f"  [채널1] OPML 폴더: {folder_name}")
    feeds = parse_opml(opml_file, folder_name)
    print(f"  [채널1] 피드 {len(feeds)}개 발견")

    articles = []
    for feed_url, source_name in feeds:
        print(f"  [채널1] 수집 중: {source_name}")
        feed = fetch_feed(feed_url)
        items = parse_entries(feed, source_name, section_id, 1, max_age)
        print(f"          → {len(items)}개")
        articles.extend(items)

    return articles


if __name__ == '__main__':
    import yaml, os
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    with open('config/settings.yaml') as f:
        settings = yaml.safe_load(f)
    with open('config/sections/agentic-ai.yaml') as f:
        section = yaml.safe_load(f)

    results = collect(section, settings)
    print(f"\n총 {len(results)}개 수집")
    for a in results[:3]:
        print(f"  [{a['source_name']}] {a['title'][:60]}")
