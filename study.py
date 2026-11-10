#!/usr/bin/env python3
"""자동차정비산업기사 필기 주관식 학습 도구. db_study/(필기 PDF)만 근거로 쓴다.
- 입력이 질문이면 주관식 답안 형식으로 답하고 원리와 암기 팁을 붙인다.
- /문제 [과목] : 교사용 해설 조각에서 주관식 문제를 낸다.
- 문제가 나온 뒤 답을 입력하면 채점하고, 왜 그 답이 되는지와 암기 팁을 준다.
- /힌트 : 정답을 말하지 않고 힌트만 준다. /정답 : 정답을 보여준다. /끝 : 종료."""
import json
import os
import random
import re

import ask as ask_mod  # LLM 호출(llm_chat)과 임베딩 모델을 질문기와 같이 쓴다
ask_mod.ENGINE_MODE[0] = "local"  # 클라우드(Claude API) 호출을 막는다
from langchain_community.vectorstores import FAISS
from rich.console import Console
from rich.markdown import Markdown
from rich.text import Text

BASE = os.path.dirname(os.path.abspath(__file__))
DB_STUDY = os.path.join(BASE, "db_study")
NUM_CTX = 4096
MAX_CHARS = 2000
LIST_PAGE = 10  # /목록 한 쪽에 보여 줄 문항 수
KINDS = ("교사용", "학생용")  # 교사용 = 답지(열람), 학생용 = 풀이(채점)

db = FAISS.load_local(DB_STUDY, ask_mod.embeddings, allow_dangerous_deserialization=True)
console = Console()
POOL = [d for d in db.docstore._dict.values() if d.metadata.get("role") == "정답·해설"]
with open(os.path.join(DB_STUDY, "qbank.json"), encoding="utf-8") as f:  # study_build.py 가 만든 문제 은행
    QBANK = json.load(f)

SYSTEM_QA = (
    "당신은 자동차정비산업기사 필기 주관식 시험을 가르치는 교사입니다. "
    "[자료]에 있는 내용만 근거로 한국어로 답하세요. 아래 형식을 지키세요.\n"
    "## 핵심 답안\n시험 답안처럼 한두 문장으로 쓴다.\n"
    "## 원리\n왜 그렇게 되는지 3~5문장으로 설명한다.\n"
    "## 암기 팁\n두문자, 연상, 숫자 묶음 중 하나로 짧게 쓴다.\n"
    "## 근거\n[파일명 p.쪽] 형식으로 적는다.\n"
    "자료에 없으면 '필기 자료에서 확인되지 않습니다'라고 쓰세요."
)
SYSTEM_MAKE = (
    "당신은 자동차정비산업기사 주관식 출제자입니다. [자료]에 있는 내용만 근거로 "
    "주관식 문제 1개와 모범답안을 만드세요. 출력 형식은 정확히 다음과 같이 하세요.\n"
    "문제: (한 문장 질문)\n모범답안: (시험 답안처럼 짧게)"
)
SYSTEM_HINT = (
    "당신은 주관식 문제의 힌트를 주는 교사입니다. [자료]와 [문제]를 보고 "
    "정답 문장을 직접 말하지 마세요. 핵심 용어의 글자 수, 첫 글자, 관련 부품이나 원리의 방향을 "
    "힌트 2개로만 짧게 주세요."
)
SYSTEM_GRADE = (
    "당신은 자동차정비산업기사 주관식 채점자입니다. [자료]의 모범답안을 기준으로 수험생 답을 채점하세요. "
    "자료에 없는 수치는 쓰지 말고, 자료에 없으면 '자료로 확인되지 않음'이라고 쓰세요. "
    "아래 형식을 지키세요.\n"
    "## 판정\n정답 / 부분 정답 / 오답 중 하나\n"
    "## 채점 근거\n맞은 내용과 빠진 내용을 2문장 안에 쓴다.\n"
    "## 모범 답안\n시험 답안처럼 짧게 쓴다.\n"
    "## 원리\n왜 이 답이 되는지 3~5문장으로 설명한다.\n"
    "## 암기 팁\n두문자, 연상, 숫자 묶음 중 하나로 짧게 쓴다."
)


def context_of(docs):
    parts = []
    for d in docs:
        m = d.metadata
        parts.append(f"[{m.get('source')} p.{m.get('page')} / {m.get('subject')} / {m.get('role')}]\n"
                     f"{d.page_content[:MAX_CHARS]}")
    return "\n\n".join(parts)


def call(system, user):
    return ask_mod.llm_chat(system, user, NUM_CTX)


def make_question(subject_key):
    pool = [d for d in POOL if not subject_key or subject_key in d.metadata.get("subject", "")]
    if not pool:
        return None
    doc = random.choice(pool)
    raw = call(SYSTEM_MAKE, f"[자료]\n{context_of([doc])}")
    q = re.search(r"문제[:：]\s*(.+)", raw)
    a = re.search(r"모범답안[:：]\s*([\s\S]+)", raw)
    if not q or not a:
        return None
    question = re.sub(r"^\(.*?\)\s*", "", q.group(1).strip())  # 모델이 붙인 '(한 문장 질문)' 같은 표시 제거
    return {"question": question, "answer": a.group(1).strip(),
            "context": context_of([doc]), "subject": doc.metadata.get("subject")}


def show_list(key):
    """/목록 : 과목 → 세트 목차. /목록 과목명 : 그 과목을 세트별로 문항 번호와 함께 보여준다."""
    if not key:
        lines = []
        for s in dict.fromkeys(x["subject"] for x in QBANK):
            sets = [x["set"] for x in QBANK if x["subject"] == s]
            names = ", ".join(dict.fromkeys(sets))
            lines.append(f"- **{s}** · {len(sets)}문항 (세트: {names})")
        console.print(Markdown("**목차 (과목 → 세트)**\n\n" + "\n".join(lines) +
                               "\n\n`/목록 교사용` 은 답지, `/목록 학생용` 은 풀이용 문항입니다. `/목록 과목명` 으로 세트별 문항을 보고, `/문제 번호` 로 고르세요."))
        return
    page = 1
    head, _, tail = key.rpartition(" ")
    if head and tail.isdigit():  # "/목록 디젤 2" 처럼 끝에 쪽 번호를 주면 그 쪽을 본다
        key, page = head.strip(), int(tail)
    if key in KINDS:
        items = [(i, x) for i, x in enumerate(QBANK, 1) if x["kind"] == key]
        title = key
    else:
        items = [(i, x) for i, x in enumerate(QBANK, 1) if key in x["subject"]]
        title = items[0][1]["subject"] if items else key
    if not items:
        console.print("해당 과목이나 종류가 없습니다. /목록 으로 확인하세요.")
        return
    pages = (len(items) + LIST_PAGE - 1) // LIST_PAGE
    if not 1 <= page <= pages:
        console.print(f"쪽 번호는 1~{pages} 사이입니다.")
        return
    chunk = items[(page - 1) * LIST_PAGE: page * LIST_PAGE]
    out = [f"**[{title}] 문항 목록 ({page}/{pages}쪽)**"]
    cur = None
    for i, x in chunk:
        if x["set"] != cur:
            cur = x["set"]
            out.append(f"\n### {cur}")
        out.append(f"- `#{i}` 문제{x['no']} {'✓' if x['answer'] else '·'} {x['question']}")
    nav = []
    if page > 1:
        nav.append(f"이전: `/목록 {key} {page - 1}`")
    if page < pages:
        nav.append(f"다음: `/목록 {key} {page + 1}`")
    out.append("\n" + " · ".join(nav) if nav else "")
    out.append("\n`/문제 번호` 로 고르세요. (✓ 정답 있음, · 정답 없음)")
    console.print(Markdown("\n".join(out)))


def pick(n):
    x = QBANK[n - 1]
    if x["answer"]:
        context = f"[{x['source']} / {x['subject']} / 정답·해설]\n문제: {x['question']}\n정답: {x['answer']}"
    else:  # 학생용 모의고사처럼 정답이 없는 문항은 교사용 해설 조각을 검색해 근거로 쓴다
        hits = db.similarity_search(x["question"], k=4)
        context = context_of(hits)
    return {"question": x["question"], "answer": x["answer"], "context": context, "subject": x["subject"],
            "kind": x["kind"], "solution": x.get("solution", "")}


VERDICTS = (("부분", "[bold yellow]△ 부분[/bold yellow]"), ("오답", "[bold red]✕ 오답[/bold red]"),
            ("정답", "[bold green]○ 정답[/bold green]"))


def show_grade(text):
    """채점 결과: 판정은 기호 한 줄, 나머지는 소제목만 옅게 두고 본문은 평문으로 찍는다."""
    secs, cur = {"": []}, ""
    for line in text.splitlines():
        m = re.match(r"^#+\s*(.+?)\s*$", line)
        if m:
            cur = m.group(1)
            secs.setdefault(cur, [])
        else:
            secs[cur].append(line)
    # API(study_api.parse_grade)와 같은 규칙: 판정 섹션 첫 줄이 정답/부분/오답으로 시작할 때만 인정
    verdict_lines = [l.strip() for l in secs.get("판정", []) if l.strip()]
    head = verdict_lines[0] if verdict_lines else ""
    mark = None if "/" in head else next((m for key, m in VERDICTS if head.startswith(key)), None)  # '/'는 템플릿 문구 → 판정 불명
    console.print(mark or "[dim]판정 불명[/dim]")
    for title, body in secs.items():
        content = "\n".join(body).strip()
        if not content or title == "판정":
            continue
        console.print()
        if title:
            console.print(Text(title, style="dim"))
        console.print(Text(content))


def main():
    pending = None
    console.print("[bold]정비산업기사 주관식[/bold]")
    console.print("[dim]/목록  /문제  /힌트  /정답  /모드  /끝[/dim]")
    while True:
        line = console.input("\n[bold cyan]>[/bold cyan] ").strip()
        if not line:
            continue
        if line == "/끝":
            break
        if line.startswith("/모드"):  # 클라우드 비활성: 엔진은 로컬로 고정
            console.print(Text("엔진은 로컬 고정입니다.", style="dim"))
            continue
        if line.startswith("/답지"):  # 번호의 문항을 문제와 정답으로 바로 보여 준다 (채점 없음)
            key = line[3:].strip()
            if not key.isdigit() or not 1 <= int(key) <= len(QBANK):
                console.print(f"/답지 번호 로 입력하세요. (1~{len(QBANK)})")
                continue
            x = QBANK[int(key) - 1]
            console.print(Text(x["question"], style="bold"))
            console.print()
            console.print(Text(x["answer"] or "원본 자료에 정답이 없는 문항입니다."))
            continue
        if line.startswith("/목록"):
            show_list(line[3:].strip())
            continue
        if line.startswith("/문제"):
            key = line[3:].strip()
            if key.isdigit():  # 목록의 번호로 고른 문항
                n = int(key)
                if not 1 <= n <= len(QBANK):
                    console.print(f"1~{len(QBANK)} 사이 번호를 입력하세요.")
                    continue
                pending = pick(n)
            else:  # 과목 이름이면 그 과목에서 무작위로
                pending = make_question(key)
            if pending is None:
                console.print("해당 과목의 문제를 만들지 못했습니다. 과목명을 바꿔 보세요.")
                continue
            if pending.get("kind") == "교사용":  # 교사용 문항은 답지라서 풀지 않고 정답을 바로 보여 준다
                console.print(Text(pending["question"], style="bold"))
                console.print()
                console.print(Text(pending["answer"] or "원본 자료에 정답이 없는 문항입니다."))
                pending = None
                continue
            console.print(Text(pending["question"], style="bold"))
            continue
        if line == "/힌트":
            if not pending:
                console.print("먼저 /문제 로 문제를 받으세요.")
                continue
            hint = call(SYSTEM_HINT, f"[자료]\n{pending['context']}\n\n[문제]\n{pending['question']}")
            # 힌트에 정답 핵심어가 그대로 나오면 가린다 (작은 모델이 정답을 말해 버리는 경우 방지)
            words = [w for w in re.split(r"[\s,.·()]+", pending["answer"]) if len(w) >= 2][:3]
            if any(w in hint for w in words):
                hint = "힌트가 정답을 포함해서 가렸습니다. /힌트 를 다시 입력해 보세요."
            console.print(Text(hint))
            continue
        if line == "/정답":
            if not pending:
                console.print("진행 중인 문제가 없습니다.")
                continue
            console.print(Text("모범 답안", style="dim"))
            console.print(Text(pending["answer"] or "원본 자료에 정답이 없는 문항입니다."))
            pending = None
            continue
        if pending:
            user = (f"[자료]\n{pending['context']}\n\n[문제]\n{pending['question']}\n\n"
                    f"[모범답안]\n{pending['answer'] or '(원본에 정답 없음: [자료]를 근거로 판단하고, 근거가 부족하면 그렇다고 쓰세요)'}\n\n"
                    f"[원본 풀이]\n{pending.get('solution') or '(원본 풀이 없음)'}\n\n[수험생 답]\n{line}")
            console.print()
            show_grade(call(SYSTEM_GRADE, user))
            pending = None
            continue
        hits = db.similarity_search(line, k=4)
        console.print(Markdown(call(SYSTEM_QA, f"[자료]\n{context_of(hits)}\n\n[질문]\n{line}")))


if __name__ == "__main__":
    main()
