#!/bin/bash
# 인터넷이 연결돼 있고, docs 안의 PDF가 추가·변경·삭제됐을 때만 build_db.py를 실행한다.
BASE="$(cd "$(dirname "$0")" && pwd)"
LOG="$BASE/auto_build.log"
STAMP="$BASE/.last_build_sig"
LOCK="$BASE/.build_lock"

# 1) 인터넷 연결 확인 (없으면 조용히 종료)
if ! curl -s -I --max-time 6 https://huggingface.co > /dev/null 2>&1; then
  exit 0
fi

# 2) 이미 빌드 중이면 중복 실행하지 않음
if ! mkdir "$LOCK" 2>/dev/null; then
  exit 0
fi
trap 'rm -rf "$LOCK"' EXIT

# 3) 자료가 바뀌었는지 확인 (파일 경로 + 크기 + 수정시각)
SIG=$(find "$BASE/docs" -type f \( -name "*.pdf" -o -name "*.md" -o -name "*.docx" \) -exec stat -f "%N %z %m" {} \; 2>/dev/null | sort | shasum | cut -d' ' -f1)
OLD=$(cat "$STAMP" 2>/dev/null)
if [ "$SIG" = "$OLD" ] && [ -d "$BASE/db_faiss" ]; then
  exit 0
fi

# 4) 배터리로 동작 중이면 미룸 (충전기 연결 시 다음 주기에 실행)
if ! pmset -g batt 2>/dev/null | grep -q "AC Power"; then
  exit 0
fi

# 5) 변경이 있으면 DB 다시 만들기
echo "[$(date '+%F %T')] 자료 변경 감지 → build_db.py 실행" >> "$LOG"
cd "$BASE" || exit 1
source venv/bin/activate
if python build_db.py >> "$LOG" 2>&1; then
  echo "$SIG" > "$STAMP"
  echo "[$(date '+%F %T')] DB 갱신 완료" >> "$LOG"
else
  echo "[$(date '+%F %T')] DB 갱신 실패 (위 로그 확인)" >> "$LOG"
fi
