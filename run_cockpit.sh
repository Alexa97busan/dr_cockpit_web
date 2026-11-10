#!/bin/bash
# 실행 공통 부분: 가상환경 활성화 → Ollama 서버 기동 → 선택한 프로그램 실행
# 사용법: run_cockpit.sh [ask|study]  (인자 없으면 메뉴에서 고른다)
cd "$(dirname "$0")" || exit 1
source venv/bin/activate

if ! curl -s http://localhost:11434 > /dev/null 2>&1; then
  ollama serve > /dev/null 2>&1 &
  sleep 3
fi

choice="$1"
if [ -z "$choice" ]; then
  clear
  echo "=============================="
  echo "  DR COCKPIT"
  echo "=============================="
  echo "  1) 자동차 질문기 (매뉴얼 RAG)"
  echo "  2) 자동차산업기사 공부 (주관식)"
  echo "  q) 종료"
  echo "------------------------------"
  read -r -p "선택: " choice
fi

clear
case "$choice" in
  1|ask)   python3 ask_ui.py ;;
  2|study) python3 study.py ;;
  *)       echo "종료합니다." ;;
esac
