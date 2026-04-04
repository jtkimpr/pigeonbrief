"""
중복 제거 3단계:
1. history.db 조회 → 이미 처리한 기사 제거
2. 현재 배치 내 URL 해시 중복 제거
3. 같은 섹션 내 제목 유사도 비교 (SequenceMatcher ≥ 0.85)
"""
import sqlite3
import difflib
import os
from datetime import datetime, timezone

DB_PATH = 'data/history.db'


def _init_db(db_path: str) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS url_history (
            url_hash  TEXT PRIMARY KEY,
            url       TEXT NOT NULL,
            title     TEXT,
            section   TEXT,
            added_at  TEXT NOT NULL
        )
    ''')
    conn.commit()
    return conn


def _filter_seen(articles: list, db_path: str) -> list:
    """history.db에 이미 있는 기사 제거"""
    if not articles:
        return []
    conn = _init_db(db_path)
    hashes = [a['id'] for a in articles]
    placeholders = ','.join('?' * len(hashes))
    seen = {row[0] for row in conn.execute(
        f'SELECT url_hash FROM url_history WHERE url_hash IN ({placeholders})',
        hashes
    )}
    conn.close()
    return [a for a in articles if a['id'] not in seen]


def _filter_duplicate_urls(articles: list) -> list:
    """현재 배치 내 URL 해시 중복 제거 (먼저 나온 것 유지)"""
    seen = set()
    result = []
    for a in articles:
        if a['id'] not in seen:
            seen.add(a['id'])
            result.append(a)
    return result


def _filter_similar_titles(articles: list, threshold: float) -> list:
    """
    같은 섹션 내 제목 유사도 중복 제거
    채널 우선순위: 낮은 번호(2 < 3) 유지
    """
    articles = sorted(articles, key=lambda a: a['channel'])
    kept = []
    for article in articles:
        is_dup = False
        title_a = article['title'].lower()
        for existing in kept:
            if existing['section'] != article['section']:
                continue
            ratio = difflib.SequenceMatcher(
                None, existing['title'].lower(), title_a
            ).quick_ratio()
            # quick_ratio는 상한값 → 실제 ratio 계산 전 빠른 필터
            if ratio >= threshold:
                ratio = difflib.SequenceMatcher(
                    None, existing['title'].lower(), title_a
                ).ratio()
                if ratio >= threshold:
                    is_dup = True
                    break
        if not is_dup:
            kept.append(article)
    return kept


def mark_as_seen(articles: list, db_path: str = DB_PATH) -> None:
    """처리 완료된 기사를 history.db에 기록"""
    if not articles:
        return
    conn = _init_db(db_path)
    now = datetime.now(timezone.utc).isoformat()
    conn.executemany(
        'INSERT OR IGNORE INTO url_history (url_hash, url, title, section, added_at) VALUES (?, ?, ?, ?, ?)',
        [(a['id'], a['url'], a['title'], a['section'], now) for a in articles]
    )
    conn.commit()
    conn.close()


def run(articles: list, db_path: str = DB_PATH, title_threshold: float = 0.85) -> tuple:
    """
    전체 중복 제거 파이프라인 실행
    Returns: (deduplicated_articles, stats_dict)
    """
    total = len(articles)

    # 1단계: 이전에 처리한 기사 제거
    articles = _filter_seen(articles, db_path)
    after_history = len(articles)

    # 2단계: 현재 배치 내 URL 중복 제거
    articles = _filter_duplicate_urls(articles)
    after_url = len(articles)

    # 3단계: 제목 유사도 중복 제거
    articles = _filter_similar_titles(articles, title_threshold)
    after_title = len(articles)

    stats = {
        'total_collected': total,
        'removed_history': total - after_history,
        'removed_url_dup': after_history - after_url,
        'removed_title_dup': after_url - after_title,
        'remaining': after_title,
    }

    return articles, stats


if __name__ == '__main__':
    import yaml, os, json
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from collectors import rss, keyword

    with open('config/settings.yaml') as f:
        settings = yaml.safe_load(f)

    # 전체 섹션 수집
    all_articles = []
    for sec_name in ['agentic-ai', 'epic-ai', 'financial-macro']:
        with open(f'config/sections/{sec_name}.yaml') as f:
            section = yaml.safe_load(f)
        all_articles += rss.collect(section, settings)
        all_articles += keyword.collect(section, settings)

    print(f'\n수집 완료: {len(all_articles)}개')

    # 중복 제거 실행
    deduped, stats = run(all_articles)

    print(f'\n[중복 제거 결과]')
    print(f'  수집 총계       : {stats["total_collected"]:3}개')
    print(f'  history 중복    : -{stats["removed_history"]:2}개')
    print(f'  URL 중복        : -{stats["removed_url_dup"]:2}개')
    print(f'  제목 유사 중복  : -{stats["removed_title_dup"]:2}개')
    print(f'  최종 처리 대상  : {stats["remaining"]:3}개')

    # 섹션별 분포
    print(f'\n[섹션별 분포]')
    from collections import Counter
    for sec, count in Counter(a['section'] for a in deduped).items():
        print(f'  {sec:20}: {count}개')

    # history.db에 기록 (실제 파이프라인에서는 Claude 처리 후 호출)
    mark_as_seen(deduped)
    print(f'\nhistory.db에 {len(deduped)}개 기록 완료')
