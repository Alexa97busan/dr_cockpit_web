#!/bin/bash
# DR 허브 실행기: 서버 없이 허브 페이지(web/hub.html)만 연다. 문항 데이터는 web/data/study-data.js 에 들어 있다.
BASE="$(cd "$(dirname "$0")" && pwd)"
open "$BASE/web/hub.html"
