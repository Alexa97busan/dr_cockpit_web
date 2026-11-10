"""객관식 AI 오답 생성기 (로컬 Ollama 만 사용, 클라우드 비용 없음).

사용:  venv/bin/python build_distractors.py [개수제한]
결과:  db_study/distractors.json  {uid: {"correct": 정답, "options": [{"text": ..., "reject": false}]}}

- 이미 생성된 uid 는 건너뛴다(중단 후 재실행하면 이어서 한다).
- 생성 결과는 mc_distract 의 같은 규칙(형식·모호성)으로 검증해서 통과한 보기만 options 에 넣는다.
- 검수: 잘못된 보기 옆의 "reject" 를 true 로 바꾸면 출제에서 빠진다.
"""
import json
import os
import re
import sys
import time

import ask as ask_mod
import mc_distract as md

HERE = os.path.dirname(os.path.abspath(__file__))
QBANK = os.path.join(HERE, "db_study", "qbank.json")
OUT = md.GEN_PATH
NUM_CTX = 4096

ask_mod.ENGINE_MODE[0] = "local"  # 클라우드 호출을 막는다

SYSTEM = (
    "너는 자동차정비산업기사 객관식 출제위원이다. 정답이 아닌 '그럴듯한 오답' 보기 3개를 만든다.\n"
    "규칙:\n"
    "1. 오답은 시험 범위 안의 실제 용어·수치여야 하고, 문제 조건에서 틀린 것이어야 한다.\n"
    "2. 정답과 같은 형식으로 쓴다 (수치면 수치+단위, 약어면 약어, 문장이면 짧은 문장).\n"
    "3. 정답의 동의어, 정답을 포함하거나 포함되는 표현은 쓰지 않는다.\n"
    "4. 세 보기는 서로 다른 개념이어야 한다.\n"
    "5. 출력은 JSON 배열 문자열 하나만: [\"보기1\", \"보기2\", \"보기3\"]"
)


def load_qbank():
    with open(QBANK, encoding="utf-8") as f:
        return json.load(f)


def load_out():
    try:
        with open(OUT, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_out(data):
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, OUT)


def parse_list(text):
    m = re.search(r"\[.*\]", text or "", re.S)
    if not m:
        return []
    try:
        arr = json.loads(m.group(0))
    except ValueError:
        return []
    return [s.strip() for s in arr if isinstance(s, str) and s.strip()]


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    qbank = load_qbank()
    # 객관식 가능 문항만 (study_api._mc_ok 와 같은 조건)
    items = [x for x in qbank if not x.get("figure_pages") and 2 <= len((x.get("answer") or "").strip()) <= 24]
    pool = {}
    for x in qbank:
        a = (x.get("answer") or "").strip()
        if 2 <= len(a) <= 24:
            lst = pool.setdefault(x["subject"], [])
            if a not in lst:
                lst.append(a)

    data = load_out()
    todo = [x for x in items if str(x["uid"]) not in data]
    done_before = len(items) - len(todo)
    if limit:
        todo = todo[:limit]
    print(f"대상 {len(items)}문항, 이미 있음 {done_before}, 이번 실행 {len(todo)}문항", flush=True)

    t0 = time.time()
    for i, x in enumerate(todo, 1):
        correct = x["answer"].strip()
        sol = (x.get("solution") or "")[:300]
        user = (f"[과목] {x['subject']}\n[문제] {x['question']}\n[정답] {correct}\n"
                f"[풀이 참고] {sol or '(없음)'}\n\n위 문제의 오답 보기 3개를 JSON 배열로만 답하라.")
        try:
            raw = ask_mod.llm_chat(SYSTEM, user, NUM_CTX)
        except Exception as e:  # 한 문항 실패가 전체를 멈추지 않게
            raw = ""
            print(f"  ! {x['uid']} 호출 실패: {type(e).__name__}", flush=True)
        cands = parse_list(raw)
        ok = []
        for c in cands:
            if c in ok or md.ambiguous(c, correct):
                continue
            if md.fmt_class(c) != md.fmt_class(correct):
                continue
            ok.append(c)
        data[str(x["uid"])] = {
            "correct": correct,
            "options": [{"text": c, "reject": False} for c in ok[:3]],
        }
        save_out(data)
        el = time.time() - t0
        print(f"[{i}/{len(todo)}] {el:5.0f}s 통과 {len(ok)}/3  {correct[:20]}", flush=True)
    print(f"끝. 누적 {len(data)}문항, 소요 {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
