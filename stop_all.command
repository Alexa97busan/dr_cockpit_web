#!/bin/bash
# DR 전체 종료: 문제풀이 API(8765), 문제풀이 화면(3000)을 끈다.
# 서버가 열어 둔 포트(LISTEN)만 끄므로 브라우저 같은 다른 프로그램은 건드리지 않는다.
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
PORTS="8765 3000"
LOG="$HOME/Library/Logs/DR-WEB"
mkdir -p "$LOG"

pids() {
  for p in $PORTS; do
    lsof -nP -ti tcp:"$p" -sTCP:LISTEN 2>/dev/null
  done | sort -u
}

if [ -z "$(pids)" ]; then
  MSG="실행 중인 DR 서버가 없습니다."
else
  pids | xargs kill 2>/dev/null
  sleep 2
  if [ -n "$(pids)" ]; then
    pids | xargs kill -9 2>/dev/null
    sleep 1
  fi
  if [ -n "$(pids)" ]; then
    MSG="일부 서버를 끄지 못했습니다. 아직 떠 있는 포트: $(for p in $PORTS; do lsof -nP -iTCP:$p -sTCP:LISTEN >/dev/null 2>&1 && printf '%s ' $p; done)"
  else
    MSG="DR 서버 2개(문제풀이 API, 문제풀이 화면)를 모두 껐습니다."
  fi
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') $MSG" >> "$LOG/start.log"
osascript -e "display dialog \"$MSG\" with title \"DR-STOP\" buttons {\"확인\"} default button \"확인\"" >/dev/null 2>&1
