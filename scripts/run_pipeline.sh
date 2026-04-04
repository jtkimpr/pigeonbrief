#!/bin/bash
# 전체 파이프라인 실행 스크립트
# launchd에서 이 파일을 호출
# TODO: 구현 예정 (각 모듈 구현 완료 후 연결)

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_FILE="$PROJECT_DIR/logs/$(date +%Y%m%d).log"
PYTHON=/usr/local/bin/python3.13

mkdir -p "$PROJECT_DIR/logs"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 파이프라인 시작" | tee -a "$LOG_FILE"

# 1. 수집
# 2. 중복 제거
# 3. Claude 처리
# 4. 사이트 생성
# 5. git push

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 파이프라인 완료" | tee -a "$LOG_FILE"
