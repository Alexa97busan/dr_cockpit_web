"""오답노트 복습 모드. 오답노트/*.md 를 문제 카드로 읽고, 풀이 기록은 db_study/review_state.json 에 남긴다.

엔드포인트 (study_api.py 가 router 를 붙인다):
  GET  /api/review/cards            카드 목록(정답·해설 제외) + 각 카드의 풀이 상태
  GET  /api/review/next?mode=all|wrong   다음 문제 한 장 (wrong: 틀린 뒤 아직 못 맞힌 것만)
  POST /api/review/answer           {id, choice} 채점. 정답·해설을 이때만 내준다
  GET  /api/review/stats            전체/틀린/숙달 개수
"""
import json
import random
import re
import threading
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

BASE = Path(__file__).resolve().parent
NOTE_DIR = BASE / "오답노트"
STATE_PATH = BASE / "db_study" / "review_state.json"
MASTER_STREAK = 2  # 틀린 뒤 이만큼 연속으로 맞히면 숙달로 본다
CIRCLED = "①②③④"
SUBJECT = "유압식전자제어 조향장치정비 예상문제1"

_lock = threading.Lock()
router = APIRouter(prefix="/api/review")


def _norm(s):
    return re.sub(r"[\s·\.\(\)]", "", s).lower()


def parse_note(path):
    """노트 한 개를 카드 dict 로 바꾼다. 형식이 맞지 않으면 None."""
    txt = path.read_text(encoding="utf-8")
    head = re.search(r"예상문제1 (\d+)번\]", txt)
    if not head or "## AI" not in txt:
        return None
    no = int(head.group(1))
    first = txt.split("## AI", 1)[0]  # 첫 번째 질문 블록만 쓴다 (일부 노트는 같은 블록이 뒤에 또 붙어 있음)
    lines = first.splitlines()
    # 본문 머리말 줄("[자동차정비산업기사 ... N번]")부터 본다. 제목 줄("# [...]")은 '#'으로 시작하므로 제외된다.
    start = next(i for i, l in enumerate(lines) if l.strip().startswith("[자동차") and "번]" in l)
    question_lines, options, answer = [], [], None
    for l in lines[start + 1:]:
        s = l.strip()
        if s.startswith("[모범답안]"):
            answer = s[len("[모범답안]"):].strip()
            break
        if s[:1] in CIRCLED and s:
            options.append(s[1:].strip())
        elif s and not options:
            question_lines.append(s)
    if not options or not answer:
        return None
    ans_idx = next((i for i, o in enumerate(options) if _norm(o) == _norm(answer)), None)
    if ans_idx is None:
        raise ValueError(f"{path.name}: 모범답안 '{answer}' 이 보기에 없습니다")

    tail = txt.split("## AI", 1)[1]
    expl = re.split(r"\n## (?:나|출처)\b", tail, maxsplit=1)[0].strip()
    src = ""
    if "## 출처" in txt:
        src = txt.split("## 출처", 1)[1].strip()[:600]
    return {
        "id": f"jonghap-{no}",
        "no": no,
        "subject": SUBJECT,
        "question": " ".join(question_lines),
        "options": options,
        "answer_index": ans_idx,
        "explanation": expl,
        "source": src,
        "file": path.name,
    }


def load_cards():
    """오답노트 폴더의 카드들. 같은 번호가 여러 파일이면 '(1)' 복사본은 건너뛴다.
    한 파일이 깨져도(보기와 모범답안 불일치 등) 나머지 카드는 계속 보여준다."""
    cards, seen = [], set()
    for p in sorted(NOTE_DIR.glob("*.md")):
        if " (1)" in p.name:
            continue
        try:
            c = parse_note(p)
        except ValueError as e:
            print(f"[review] 건너뜀: {e}", flush=True)
            continue
        if c and c["id"] not in seen:
            seen.add(c["id"])
            cards.append(c)
    return sorted(cards, key=lambda c: c["no"])


def _load_state():
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_state(state):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(STATE_PATH)


def _st(state, cid):
    s = state.get(cid, {})
    wrong, streak = s.get("wrong", 0), s.get("streak", 0)
    return {"attempts": s.get("attempts", 0), "wrong": wrong, "streak": streak,
            "mastered": streak >= MASTER_STREAK, "needs_review": wrong > 0 and streak < MASTER_STREAK}


def _public(c, state):
    return {"id": c["id"], "no": c["no"], "subject": c["subject"], "question": c["question"],
            "options": c["options"], "state": _st(state, c["id"])}


class AnswerIn(BaseModel):
    id: str
    choice: int


@router.get("/cards")
def review_cards():
    state = _load_state()
    return [_public(c, state) for c in load_cards()]


@router.get("/next")
def review_next(mode: str = "all", exclude: str | None = None):
    state = _load_state()
    pool = [c for c in load_cards() if not (mode == "wrong" and not _st(state, c["id"])["needs_review"])]
    if exclude:
        pool = [c for c in pool if c["id"] != exclude] or pool
    if not pool:
        return {"done": True, "card": None}
    return {"done": False, "card": _public(random.choice(pool), state)}


@router.post("/answer")
def review_answer(body: AnswerIn):
    cards = {c["id"]: c for c in load_cards()}
    c = cards.get(body.id)
    if c is None:
        raise HTTPException(404, "문항을 찾을 수 없습니다")
    if not (0 <= body.choice < len(c["options"])):
        raise HTTPException(400, "보기 번호가 범위를 벗어났습니다")
    with _lock:
        state = _load_state()
        s = state.setdefault(body.id, {"attempts": 0, "wrong": 0, "streak": 0})
        right = body.choice == c["answer_index"]
        s["attempts"] += 1
        if right:
            s["streak"] += 1
        else:
            s["wrong"] += 1
            s["streak"] = 0
        s["last"] = time.strftime("%Y-%m-%d %H:%M:%S")
        _save_state(state)
    return {"correct": right, "correct_index": c["answer_index"],
            "correct_text": c["options"][c["answer_index"]], "explanation": c["explanation"],
            "source": c["source"], "state": _st(state, body.id)}


@router.get("/stats")
def review_stats():
    state = _load_state()
    cards = load_cards()
    st = [_st(state, c["id"]) for c in cards]
    return {"total": len(cards),
            "wrong_ever": sum(1 for s in st if s["wrong"] > 0),
            "needs_review": sum(1 for s in st if s["needs_review"]),
            "mastered": sum(1 for s in st if s["mastered"])}
