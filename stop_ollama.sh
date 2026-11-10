#!/bin/bash
# Ollama 종료: 메모리에 올라간 모델을 내리고 ollama serve(11434)를 끈다. 더블클릭용 stop_ollama.command 에서도 호출한다.
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"

pids() { lsof -nP -ti tcp:11434 -sTCP:LISTEN 2>/dev/null | sort -u; }

if [ -z "$(pids)" ]; then
  echo "실행 중인 Ollama가 없습니다."
  exit 0
fi

# 1) 올라가 있는 모델을 먼저 내린다 (메모리 해제)
if command -v ollama >/dev/null 2>&1; then
  ollama ps 2>/dev/null | awk 'NR>1 && $1!="" {print $1}' | while read -r m; do
    echo "모델 내리는 중: $m"
    ollama stop "$m" 2>/dev/null
  done
fi

# 2) 서버 프로세스 종료
echo "Ollama 서버 종료 중..."
pids | xargs kill 2>/dev/null
sleep 2
if [ -n "$(pids)" ]; then
  echo "남은 프로세스를 강제 종료합니다."
  pids | xargs kill -9 2>/dev/null
  sleep 1
fi

if [ -n "$(pids)" ]; then
  echo "종료 실패: 아직 11434 포트를 쓰는 프로세스가 있습니다."
  exit 1
fi
echo "Ollama를 종료했습니다."
