#!/bin/bash
# 문제풀이 웹 실행기: 서버 없이 web/index.html 을 바로 연다. 문항 데이터는 web/data/study-data.js 에 들어 있다.
# 문항 은행이 바뀌었으면 먼저 venv/bin/python export_static.py 를 실행한다.
BASE="$(cd "$(dirname "$0")" && pwd)"
open "$BASE/web/index.html"
