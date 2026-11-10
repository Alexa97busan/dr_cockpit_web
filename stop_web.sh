#!/bin/bash
# DR-WEB 종료: API(8765)와 웹(3000) 서버를 모두 끈다. 더블클릭용 stop_web.command 에서도 호출한다.
PORTS="8765,3000"

pids() { lsof -ti:"$PORTS" 2>/dev/null; }

if [ -z "$(pids)" ]; then
  echo "실행 중인 DR-WEB 서버가 없습니다."
  exit 0
fi

echo "서버 종료 중..."
pids | xargs kill 2>/dev/null
sleep 2

if [ -n "$(pids)" ]; then
  echo "남은 프로세스를 강제 종료합니다."
  pids | xargs kill -9 2>/dev/null
  sleep 1
fi

if [ -n "$(pids)" ]; then
  echo "종료 실패: 아직 포트를 쓰는 프로세스가 있습니다."
  lsof -nP -iTCP:"$PORTS" -sTCP:LISTEN
  exit 1
fi
echo "DR-WEB 서버를 모두 종료했습니다."
