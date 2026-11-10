#!/bin/bash
# 더블클릭용: DR-WEB 서버를 끈다.
bash "$(cd -P "$(dirname "$0")" && pwd)/stop_web.sh"
echo ""
read -n 1 -s -r -p "아무 키나 누르면 창이 닫힙니다."
