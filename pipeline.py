"""
PigeonBrief 파이프라인 메인 스크립트
launchd → scripts/run_pipeline.sh → 이 파일 실행

단계:
1. 설정 로드
2. 3채널 수집 (채널2 RSS + 채널3 키워드)
3. 중복 제거
4. Claude 필터링 + 한국어 요약
5. 사이트 JSON 생성
6. git push → Vercel 자동 배포
"""
import os
import sys
import yaml
import subprocess
from datetime import datetime, timezone

# 프로젝트 루트 기준으로 경로 설정
ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

from collectors import rss, keyword
from processor import dedup, claude
from generator import build_site


def load_configs():
    with open('config/settings.yaml') as f:
        settings = yaml.safe_load(f)

    import json
    with open('config/sections.json', encoding='utf-8') as f:
        sections_data = json.load(f)

    section_configs = {}
    for s in sections_data.get('sections', []):
        if s.get('enabled', True):
            section_configs[s['id']] = s

    return settings, section_configs


def collect_all(section_configs, settings):
    all_articles = []
    for sid, section in section_configs.items():
        print(f"\n[수집] {section['name']}")
        articles = []
        articles += rss.collect(section, settings)
        articles += keyword.collect(section, settings)
        print(f"  소계: {len(articles)}개")
        all_articles.extend(articles)
    return all_articles


def git_push(date_str: str, auto_push: bool) -> bool:
    if not auto_push:
        print("\n[git] auto_push=false, 건너뜀")
        return True
    try:
        subprocess.run(['git', 'add', 'website/data/articles.json'], check=True)
        result = subprocess.run(
            ['git', 'status', '--porcelain', 'website/data/articles.json'],
            capture_output=True, text=True
        )
        if not result.stdout.strip():
            print("\n[git] 변경사항 없음, push 건너뜀")
            return True
        subprocess.run(
            ['git', 'commit', '-m', f'daily update: {date_str}'],
            check=True
        )
        subprocess.run(['git', 'push'], check=True)
        print(f"\n[git] push 완료 → Vercel 배포 시작")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n[warn] git push 실패: {e}")
        return False


def notify_mac(title: str, message: str):
    """Mac 알림 (launchd 실행 시 실패/완료 알림)"""
    try:
        subprocess.run([
            'osascript', '-e',
            f'display notification "{message}" with title "{title}"'
        ], check=True, capture_output=True)
    except Exception:
        pass


def git_pull() -> bool:
    """실행 전 최신 설정(config/sections.json) 반영을 위해 git pull"""
    try:
        result = subprocess.run(
            ['git', 'pull', '--ff-only'],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            print(f"[git] pull 완료: {result.stdout.strip() or 'Already up to date.'}")
        else:
            print(f"[warn] git pull 실패 (계속 진행): {result.stderr.strip()}")
        return True
    except Exception as e:
        print(f"[warn] git pull 오류 (계속 진행): {e}")
        return False


def main():
    start_time = datetime.now(timezone.utc)
    date_str = start_time.strftime('%Y-%m-%d')
    print(f"{'='*50}")
    print(f"PigeonBrief 파이프라인 시작: {date_str}")
    print(f"{'='*50}")

    try:
        # 0. git pull (최신 설정 반영)
        git_pull()

        # 1. 설정 로드
        settings, section_configs = load_configs()
        auto_push = settings.get('git', {}).get('auto_push', True)
        db_path = settings.get('dedup', {}).get('url_history_db', 'data/history.db')
        max_age_days = settings.get('site', {}).get('max_age_days', 7)

        # 2. 수집
        print(f"\n{'─'*40}")
        print("1단계: 수집")
        all_articles = collect_all(section_configs, settings)
        print(f"\n수집 합계: {len(all_articles)}개")

        # 3. 중복 제거
        print(f"\n{'─'*40}")
        print("2단계: 중복 제거")
        deduped, stats = dedup.run(all_articles, db_path=db_path)
        print(f"  수집: {stats['total_collected']}  "
              f"history제거: -{stats['removed_history']}  "
              f"URL중복: -{stats['removed_url_dup']}  "
              f"제목유사: -{stats['removed_title_dup']}  "
              f"→ {stats['remaining']}개")

        if not deduped:
            print("\n처리할 새 기사 없음. 종료.")
            notify_mac("PigeonBrief", f"{date_str} - 새 기사 없음")
            return

        # 4. Claude 처리
        print(f"\n{'─'*40}")
        print("3단계: Claude 필터링 + 한국어 요약")
        processed = claude.run(deduped, settings, section_configs)
        print(f"\nClaude 처리 완료: {len(processed)}개")

        if not processed:
            print("관련 기사 없음. 종료.")
            notify_mac("PigeonBrief", f"{date_str} - 관련 기사 없음")
            return

        # 5. 사이트 JSON 생성
        print(f"\n{'─'*40}")
        print("4단계: 사이트 JSON 생성")
        data = build_site.build(processed, section_configs, max_age_days=max_age_days)
        total = data['total_articles']
        for s in data['sections']:
            print(f"  {s['name']:20}: {len(s['articles'])}개")
        print(f"  총 {total}개 → website/data/articles.json")

        # history.db 기록 (사이트 생성 성공 후)
        dedup.mark_as_seen(deduped, db_path=db_path)

        # 6. git push
        print(f"\n{'─'*40}")
        print("5단계: git push")
        git_push(date_str, auto_push)

        elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
        print(f"\n{'='*50}")
        print(f"완료: {total}개 기사, {elapsed:.0f}초 소요")
        notify_mac("PigeonBrief", f"{date_str} 업데이트 완료 ({total}개)")

    except Exception as e:
        import traceback
        print(f"\n[오류] {e}")
        traceback.print_exc()
        notify_mac("PigeonBrief 오류", str(e)[:80])
        sys.exit(1)


if __name__ == '__main__':
    main()
