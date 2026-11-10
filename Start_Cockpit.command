#!/bin/bash
# 더블클릭용: 실행 메뉴(질문기 / 공부)는 run_cockpit.sh 가 보여준다.
cd "$(dirname "$0")" || exit
exec bash run_cockpit.sh
