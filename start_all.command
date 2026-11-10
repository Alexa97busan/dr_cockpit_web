#!/bin/bash
# DR 허브 실행기: 문제풀이 API(8765), 문제풀이 화면(3000)을 띄우고 허브 페이지를 연다.
# 이미 떠 있는 서버는 다시 띄우지 않는다. 파이썬 환경(venv)이 없거나 깨졌으면 자동으로 다시 만든다(처음에 몇 분 걸릴 수 있음).
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
BASE="$(cd "$(dirname "$0")" && pwd)"
LOG="$HOME/Library/Logs/DR-WEB"
mkdir -p "$LOG"
STARTLOG="$LOG/start.log"
listening() { lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1; }
log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$STARTLOG"; }
alert() { osascript -e "display dialog \"$1\" with title \"DR-HUB\" buttons {\"확인\"} default button \"확인\"" >/dev/null 2>&1; }
wait_port() {  # $1=포트 $2=초
  for _ in $(seq 1 $(( $2 * 5 ))); do
    listening "$1" && return 0
    sleep 0.2
  done
  return 1
}

PY_PKGS="fastapi uvicorn pydantic pypdf rich langchain-community langchain-huggingface faiss-cpu sentence-transformers ollama numpy"

# 쓸 수 있는 파이썬(3.10 이상) 찾기
find_python() {
  for c in /opt/homebrew/bin/python3 /usr/local/bin/python3 /Library/Frameworks/Python.framework/Versions/*/bin/python3 /usr/bin/python3 python3; do
    command -v "$c" >/dev/null 2>&1 || [ -x "$c" ] || continue
    if "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' 2>/dev/null; then
      command -v "$c" 2>/dev/null || echo "$c"; return 0
    fi
  done
  return 1
}

venv_ok() { [ -x "$BASE/venv/bin/python" ] && "$BASE/venv/bin/python" -c 'import fastapi, uvicorn' >/dev/null 2>&1; }

log "---- start_all 시작 (BASE=$BASE)"

# Ollama(로컬 LLM)는 문제풀이 사이트가 쓰지 않으므로 띄우지 않는다. 질문기 로컬 모드가 필요하면 따로 실행한다.

if ! listening 3000; then
  ( cd "$BASE/web" && nohup perl -MPOSIX -e 'POSIX::setsid(); exec { $ARGV[0] } @ARGV' python3 -m http.server 3000 --bind 127.0.0.1 >> "$LOG/web.log" 2>&1 & )
  log "문제풀이 화면(3000) 실행 요청"
else
  log "문제풀이 화면(3000) 이미 실행 중"
fi

if ! venv_ok; then
  log "venv 가 없거나 깨짐 → 다시 만듭니다"
  alert "파이썬 환경을 처음 준비합니다. 인터넷 연결이 필요하고 몇 분 걸릴 수 있습니다. 완료되면 허브가 열립니다."
  PY="$(find_python)"
  if [ -z "$PY" ]; then
    log "3.10 이상 파이썬을 찾지 못했습니다"
    alert "Python 3.10 이상을 찾지 못했습니다. python.org 에서 Python을 설치한 뒤 다시 실행해 주세요."
    exit 1
  fi
  log "사용할 파이썬: $PY"
  [ -e "$BASE/venv" ] && mv "$BASE/venv" "$BASE/venv.broken.$(date +%Y%m%d%H%M%S)"
  "$PY" -m venv "$BASE/venv" >> "$LOG/setup.log" 2>&1
  "$BASE/venv/bin/python" -m pip install --upgrade pip >> "$LOG/setup.log" 2>&1
  "$BASE/venv/bin/python" -m pip install $PY_PKGS >> "$LOG/setup.log" 2>&1
  if ! venv_ok; then
    log "패키지 설치 실패 (자세한 내용: $LOG/setup.log)"
    alert "파이썬 패키지 설치에 실패했습니다. 기록: $LOG/setup.log"
    exit 1
  fi
  log "파이썬 환경 준비 완료"
fi

if ! listening 8765; then
  ( cd "$BASE" && HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 nohup perl -MPOSIX -e 'POSIX::setsid(); exec { $ARGV[0] } @ARGV' "$BASE/venv/bin/python" -m uvicorn study_api:app \
      --host 127.0.0.1 --port 8765 >> "$LOG/api.log" 2>&1 & )
  log "API(8765) 실행 요청"
else
  log "API(8765) 이미 실행 중"
fi

FAIL=""
wait_port 3000 10 || FAIL="$FAIL 문제풀이 화면(3000)"
wait_port 8765 90 || FAIL="$FAIL 문제풀이 API(8765)"

if [ -n "$FAIL" ]; then
  log "실행 실패:$FAIL"
  alert "다음 서버가 켜지지 않았습니다:$FAIL  기록: $STARTLOG (API: $LOG/api.log)"
  exit 1
fi

log "모든 서버 실행 확인, 허브를 엽니다"
open "http://127.0.0.1:3000/hub.html"
