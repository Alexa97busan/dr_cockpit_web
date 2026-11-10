#!/usr/bin/env python3
"""study.py 의 문제 은행·힌트·채점·외부 참고를 HTTP API로 노출한다. 프론트(웹/PWA)는 이 API만 부른다.
실행: venv/bin/uvicorn study_api:app --host 127.0.0.1 --port 8765
채점 입력에는 외부 참고가 들어가지 않는다 (study.py 와 같은 원칙)."""
import json
import os
import random
import re

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import ask as ask_mod
import mc_distract
import study

# study 모듈과 같이 로컬 엔진으로 고정한다. 클라우드 채점 경로는 제거되었다.
ask_mod.ENGINE_MODE[0] = "local"

app = FastAPI(title="정비산업기사 주관식 학습 API")
# 브라우저 프론트만 허용. 기본은 로컬 개발 주소, 다른 주소는 DR_STUDY_ORIGINS(쉼표 구분)로 추가한다.
ORIGINS = os.environ.get("DR_STUDY_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173").split(",")
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in ORIGINS if o.strip()],
                   allow_methods=["GET", "POST"], allow_headers=["*"])

# 오답노트 복습 모드(/api/review/*). 카드는 오답노트/*.md 에서 읽는다.
from review_api import router as review_router  # noqa: E402
app.include_router(review_router)

VERDICT_KEYS = (("부분", "partial"), ("오답", "wrong"), ("정답", "correct"))


class AnswerIn(BaseModel):
    n: int
    answer: str = Field(..., max_length=2000)  # 주관식 답안 길이 상한(과도한 입력을 LLM에 넘기지 않음)


class NoIn(BaseModel):
    n: int


class ChoiceIn(BaseModel):
    n: int
    pick: int


def _item(n):
    if not 1 <= n <= len(study.QBANK):
        raise HTTPException(404, f"1~{len(study.QBANK)} 사이 번호를 입력하세요.")
    return study.QBANK[n - 1]


# ---- 객관식: 짧은 정답이 있는 문항만 보기로 만든다. 오답 보기는 같은 과목의 다른 문항 정답에서 뽑는다 ----
_MC_POOL = None


def _mc_ok(x):
    if x.get("figures"):  # 그림 조각이 있는 문항은 주관식으로만 출제한다 (원본 쪽 이미지 figure_pages 는 기준이 아님)
        return False
    a = (x.get("answer") or "").strip()
    return 2 <= len(a) <= 24


def _pool():
    global _MC_POOL
    if _MC_POOL is None:
        pool = {}
        for x in study.QBANK:
            if _mc_ok(x):
                a = x["answer"].strip()
                lst = pool.setdefault(x["subject"], [])
                if a not in lst:
                    lst.append(a)
        _MC_POOL = pool
    return _MC_POOL


def _choices(n, x):
    """보기 4개와 정답 위치. 같은 문항은 항상 같은 보기 순서가 나오도록 번호로 시드를 고정한다."""
    correct = x["answer"].strip()
    pool = _pool()
    uid = x.get("uid") or n
    rng = random.Random(f"mc-{uid}")  # 문제 은행을 다시 만들어도 같은 문항의 보기 순서가 유지되도록 uid 로 시드
    opts = [correct] + mc_distract.pick(uid, correct, x["subject"], pool, rng)  # 오답: AI 생성·반대 개념·유사 답 순 (mc_distract.py)
    rng.shuffle(opts)
    return opts, opts.index(correct)


_PAGE_IMGS = None


def _page_imgs(uid):
    """문항의 원본 PDF 쪽 이미지 목록 (build_page_images.py 가 만든 db_study/page_images.json)."""
    global _PAGE_IMGS
    if _PAGE_IMGS is None:
        try:
            base = os.path.dirname(os.path.abspath(__file__))
            with open(os.path.join(base, "db_study", "page_images.json"), encoding="utf-8") as f:
                _PAGE_IMGS = json.load(f)
        except (OSError, ValueError):
            _PAGE_IMGS = {}
    return _PAGE_IMGS.get(str(uid), [])


_PAGE_BLUR = None


def _page_blur(uid):
    """정답 글자가 쪽 이미지에서 차지하는 자리 {쪽 이미지: [[x0,y0,x1,y1] 비율]} (build_page_images.py 가 만든 db_study/page_blur.json)."""
    global _PAGE_BLUR
    if _PAGE_BLUR is None:
        try:
            base = os.path.dirname(os.path.abspath(__file__))
            with open(os.path.join(base, "db_study", "page_blur.json"), encoding="utf-8") as f:
                _PAGE_BLUR = json.load(f)
        except (OSError, ValueError):
            _PAGE_BLUR = {}
    return _PAGE_BLUR.get(str(uid), {})


def _public(n, x):
    """목록·문항 공통 필드. 학생용 문항은 정답·풀이를 여기서 빼고, 교사용만 답을 함께 준다."""
    out = {"n": n, "uid": x.get("uid"), "subject": x["subject"], "set": x["set"], "kind": x["kind"],
           "question": x["question"], "figures": x.get("figures", []),
           "pages": _page_imgs(x.get("uid")), "blur": _page_blur(x.get("uid"))}
    if x["kind"] == "교사용":
        verdict = (x.get("answer_check") or {}).get("verdict")
        if x["answer"]:
            out["answer"] = x["answer"]
        elif verdict == "일치" and x.get("answer_draft"):  # 원본 정답이 없지만 교차검증이 AI 초안과 일치 판정한 문항
            out["answer"] = x["answer_draft"]
            out["answer_note"] = "원본 자료에 정답이 없어 AI 초안을 교차검증해 일치로 판정된 답입니다. 원본 확인을 권장합니다."
        else:
            out["answer"] = "원본 자료에 정답이 없는 문항입니다."
            out["answer_note"] = "정답 미확인(검증 근거 부족)"
        if not x["answer"] and x.get("answer_fix"):  # 원본에 정답이 없을 때만 교차검증 교정답을 준다 (AI 초안은 내보내지 않는다)
            out["answer_fix"] = x["answer_fix"]
    if _mc_ok(x):
        out["choices"] = _choices(n, x)[0]  # 보기 글만 준다. 정답 위치는 채점 전까지 주지 않는다
    return out


def parse_grade(text):
    """채점 응답을 판정과 섹션 목록으로 나눈다. 판정은 정답/부분/오답 중 하나의 키로 바꾼다."""
    secs, cur = {"": []}, ""
    for line in text.splitlines():
        m = re.match(r"^#+\s*(.+?)\s*$", line)
        if m:
            cur = m.group(1)
            secs.setdefault(cur, [])
        else:
            secs[cur].append(line)
    # 판정은 첫 줄의 앞부분으로만 본다. 본문 전체에서 찾으면 템플릿 문구("정답 / 부분 정답 / 오답")를 베낀 응답이 부분정답으로 잘못 판정된다.
    verdict_lines = [l.strip() for l in secs.pop("판정", []) if l.strip()]
    head = verdict_lines[0] if verdict_lines else ""
    # '/'가 든 줄은 템플릿 문구("정답 / 부분 정답 / 오답 중 하나")를 베낀 것이므로 판정으로 보지 않는다
    verdict = next((key for word, key in VERDICT_KEYS if head.startswith(word)), "unknown")
    if "/" in head:
        verdict = "unknown"
    sections = [{"title": t, "body": "\n".join(b).strip()} for t, b in secs.items() if "\n".join(b).strip()]
    return {"verdict": verdict, "sections": sections}


@app.get("/api/health")
def health():
    return {"ok": True, "count": len(study.QBANK)}


@app.get("/api/subjects")
def subjects():
    """과목별 문항 수. 과목 화면의 목차를 만들 때 쓴다."""
    counts = {}
    for x in study.QBANK:
        counts[x["subject"]] = counts.get(x["subject"], 0) + 1
    return [{"subject": s, "count": c} for s, c in counts.items()]


@app.get("/api/questions")
def questions(subject: str | None = None, kind: str | None = None):
    """문항 목록(문제 본문 제외). kind 는 교사용/학생용, subject 는 과목 이름 일부."""
    out = []
    for i, x in enumerate(study.QBANK, start=1):
        if subject and subject not in x["subject"]:
            continue
        if kind and x["kind"] != kind:
            continue
        out.append({"n": i, "uid": x.get("uid"), "subject": x["subject"], "set": x["set"], "kind": x["kind"],
                    "no": x.get("no"), "mc": _mc_ok(x), "q": " ".join((x.get("question") or "").split())[:70]})
    return out


@app.get("/api/questions/{n}")
def question(n: int):
    return _public(n, _item(n))


@app.get("/api/context/{n}")
def context(n: int):
    """웹채팅이 문제를 대화에 넣을 때 쓴다. 지문·보기는 항상 주고, 정답·풀이는 교사용 문항만 준다.
    학생용 문항의 정답·풀이는 채점 전에 내주지 않는다(_public 과 같은 규칙)."""
    x = _item(n)
    out = {"n": n, "subject": x["subject"], "set": x["set"], "no": x.get("no"), "kind": x["kind"],
           "question": x["question"]}
    if x["kind"] == "교사용":
        out["answer"] = (x.get("answer") or "").strip()
        out["solution"] = x.get("solution") or ""
    if _mc_ok(x):
        out["choices"] = _choices(n, x)[0]
    return out


@app.post("/api/hint")
def hint(body: NoIn):
    """힌트는 문항 은행의 정적 정보(단원·유형·그림 쪽)만으로 만든다. LLM을 쓰지 않으므로 정답 내용은 넣지 않는다."""
    x = _item(body.n)
    subject = x.get("subject") or "해당"
    text = f"이 문항은 「{subject}」 단원 문항입니다. 문제의 자료(그림·표)와 묻는 값·단위를 먼저 확인하세요."
    return {"n": body.n, "hint": text, "masked": False, "kind": x["kind"]}


@app.post("/api/choice")
def choice(body: ChoiceIn):
    """객관식 채점: 고른 보기 번호(0~3)만 받아 맞고 틀림을 판정한다."""
    x = _item(body.n)
    if not _mc_ok(x):
        raise HTTPException(400, "객관식으로 풀 수 없는 문항입니다.")
    opts, ci = _choices(body.n, x)
    if not 0 <= body.pick < len(opts):
        raise HTTPException(400, "보기 번호가 잘못되었습니다.")
    verdict = "correct" if body.pick == ci else "wrong"
    return {"verdict": verdict, "correct_index": ci,
            "answer": x["answer"].strip(), "solution": x.get("solution") or ""}


@app.post("/api/grade")
def grade(body: AnswerIn):
    """채점은 클라우드 전용이었으나 중계 경로를 제거했다. 지금은 항상 503을 돌려준다."""
    _item(body.n)
    raise HTTPException(503, "채점 불가: 클라우드 채점 경로가 제거되었습니다.")


@app.post("/api/reveal")
def reveal(body: NoIn):
    """주관식 정답·풀이를 바로 보여 준다. 채점하지 않는다."""
    x = _item(body.n)
    return {"n": body.n, "answer": (x.get("answer") or "").strip() or "원본 자료에 정답이 없는 문항입니다.",
            "solution": x.get("solution") or ""}


@app.get("/api/refs/{n}")
def refs(n: int):
    """외부 참고 검색은 제거되었다. 항상 error와 빈 목록을 돌려준다."""
    _item(n)
    return {"error": "외부 참고 검색은 제거되었습니다.", "items": [], "source": None,
            "notice": "자료 밖 · 검증되지 않음."}
