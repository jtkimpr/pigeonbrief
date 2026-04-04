"""
공통 유틸리티: URL 정규화, RSS 파싱, 기사 dict 생성
채널 1·2·3 수집기가 공유
"""
import hashlib
import html
import re
import requests
import feedparser
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse, urlencode, parse_qs, urlunparse

TRACKING_PARAMS = {
    'utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term',
    'utm_id', 'ref', 'source', 'fbclid', 'gclid', '_ga', 'mc_cid', 'mc_eid',
}


def normalize_url(url: str) -> str:
    """트래킹 파라미터 제거 후 정규화된 URL 반환"""
    try:
        parsed = urlparse(url.strip())
        params = parse_qs(parsed.query, keep_blank_values=True)
        clean = {k: v for k, v in params.items() if k.lower() not in TRACKING_PARAMS}
        return urlunparse(parsed._replace(query=urlencode(clean, doseq=True), fragment=''))
    except Exception:
        return url


def url_hash(url: str) -> str:
    """정규화된 URL의 SHA-256 해시 앞 12자리"""
    return hashlib.sha256(normalize_url(url).encode()).hexdigest()[:12]


def strip_html(text: str) -> str:
    """HTML 태그 제거 후 공백 정리"""
    if not text:
        return ''
    text = html.unescape(text)
    text = re.sub(r'<[^>]+>', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def fetch_feed(url: str, timeout: int = 15) -> feedparser.FeedParserDict:
    """requests로 fetch 후 feedparser로 파싱 (타임아웃 보장)"""
    try:
        resp = requests.get(
            url, timeout=timeout,
            headers={'User-Agent': 'news-intelligence/1.0'}
        )
        resp.raise_for_status()
        return feedparser.parse(resp.content)
    except Exception as e:
        print(f"  [warn] fetch 실패: {url[:80]} — {e}")
        return feedparser.FeedParserDict(entries=[])


def parse_entries(
    feed: feedparser.FeedParserDict,
    source_name: str,
    section_id: str,
    channel: int,
    max_age_hours: int,
) -> list:
    """
    feedparser 결과 → 표준 article dict 리스트
    max_age_hours 이내 기사만 포함
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    now_iso = datetime.now(timezone.utc).isoformat()
    articles = []

    for entry in feed.get('entries', []):
        url = entry.get('link', '').strip()
        title = entry.get('title', '').strip()
        if not url or not title:
            continue

        # 발행일 파싱
        published = None
        for field in ('published_parsed', 'updated_parsed'):
            t = getattr(entry, field, None)
            if t:
                try:
                    published = datetime(*t[:6], tzinfo=timezone.utc)
                    break
                except Exception:
                    pass

        # max_age_hours 필터 (날짜 정보가 있을 때만 적용)
        if published and published < cutoff:
            continue

        # 본문 추출
        content = ''
        if getattr(entry, 'content', None):
            content = entry.content[0].get('value', '')
        elif getattr(entry, 'summary', None):
            content = entry.summary
        content = strip_html(content)

        articles.append({
            'id': url_hash(url),
            'section': section_id,
            'channel': channel,
            'source_name': source_name,
            'title': title,
            'url': url,
            'published_at': published.isoformat() if published else '',
            'collected_at': now_iso,
            'raw_content': content,
            'summary_ko': '',
            'relevance_score': 0.0,
            'included': False,
        })

    return articles
