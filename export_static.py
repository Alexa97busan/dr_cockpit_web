#!/usr/bin/env python3
"""문제풀이 웹을 서버 없이 쓰도록 문항 데이터를 web/data/study-data.js 로 내보낸다.
실행: venv/bin/python export_static.py   (문항 은행(db_study/qbank.json)이나 보기 규칙이 바뀌면 다시 실행)

study_api 의 문항 가공 함수(_public, _choices, _mc_ok)를 그대로 써서, API 가 주던 값과 같은 값을 만든다.
study·ask 모듈은 임베딩 모델과 FAISS 를 올리므로 문항 은행만 읽는 가짜 모듈로 대신한다."""
import json
import os
import sys
import types

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

with open(os.path.join(BASE, "db_study", "qbank.json"), encoding="utf-8") as f:
    qbank = json.load(f)

fake_study = types.ModuleType("study")
fake_study.QBANK = qbank
fake_ask = types.ModuleType("ask")
fake_ask.ENGINE_MODE = ["local"]
sys.modules["study"] = fake_study
sys.modules["ask"] = fake_ask

import study_api  # noqa: E402

items, secret = [], {}
for n, x in enumerate(qbank, start=1):
    items.append(study_api._public(n, x))  # 학생용은 정답·풀이가 빠진 문항 (화면에 바로 쓰는 값)
    ans = (x.get("answer") or "").strip()
    ci = study_api._choices(n, x)[1] if study_api._mc_ok(x) else None
    # 객관식 채점·정답 보기에 쓰는 값. 서버 API 와 같은 규칙으로 만든다.
    secret[str(n)] = {
        "answer": ans or "원본 자료에 정답이 없는 문항입니다.",
        "solution": x.get("solution") or "",
        "ci": ci,
    }

out_dir = os.path.join(BASE, "web", "data")
os.makedirs(out_dir, exist_ok=True)
out = os.path.join(out_dir, "study-data.js")
payload = json.dumps({"items": items, "secret": secret}, ensure_ascii=False, separators=(",", ":"))
with open(out, "w", encoding="utf-8") as f:
    f.write("// 자동 생성: export_static.py. 직접 고치지 말고 스크립트를 다시 실행한다.\n")
    f.write("window.STUDY_DATA = " + payload + ";\n")

print(f"문항 {len(items)}개 -> {os.path.relpath(out, BASE)} ({os.path.getsize(out) // 1024} KB)")
