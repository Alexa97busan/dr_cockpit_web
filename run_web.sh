#!/bin/bash
# 웹 앱 실행기: API(8765)와 웹(3000)을 백그라운드로 띄우고 브라우저를 연다. 이미 떠 있으면 다시 띄우지 않는다.
BASE="$(cd "$(dirname "$0")" && pwd)"
LOG="$HOME/Library/Logs/DR-WEB"
mkdir -p "$LOG"

listening() { lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1; }

if ! listening 8765; then
  # 모델은 이미 캐시에 있으므로 인터넷 확인을 건너뛰어 시작을 빠르게 한다.
  cd "$BASE" && HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 nohup "$BASE/venv/bin/uvicorn" study_api:app --host 127.0.0.1 --port 8765 \
    >> "$LOG/api.log" 2>&1 &
fi
if ! listening 3000; then
  cd "$BASE/web" && nohup python3 -m http.server 3000 --bind 127.0.0.1 \
    >> "$LOG/web.log" 2>&1 &
fi

# 웹 서버만 뜨면 바로 브라우저를 연다. API 준비는 화면(app.js)이 기다리며 처리한다.
for _ in $(seq 1 50); do
  listening 3000 && break
  sleep 0.1
done
open "http://127.0.0.1:3000/index.html"
