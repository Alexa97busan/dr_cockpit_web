#!/usr/bin/env python3
"""새 문제 은행 만들기: '문제 제대로 넣기. 새롭게./교사용' PDF의 문항을 읽어 db_study/qbank.new.json 을 만든다.

- 문항 표시 '문제N]' 단위로 지문·정답·풀이를 나눈다 (study_build.py 의 규칙과 같다).
- 모든 문항은 kind='학생용' (문제풀기용). 정답·풀이는 채점용으로 저장하고, study_api 가 채점 전에는 내주지 않는다.
- 그림이 있는 쪽(페이지에 이미지가 있는 문항)은 figure_pages 에 쪽 번호를 적고, 객관식 출제에서 뺀다(주관식으로만 쓴다).
- 결과는 qbank.new.json 으로만 쓴다. 검토 후 qbank.json 으로 바꾼다.

사용: venv/bin/python build_qbank_new.py
"""
import glob
import json
import os
import re
import sys
import unicodedata

import pymupdf

from qbank_ids import add_uids

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "docs", "문제 제대로 넣기. 새롭게.", "교사용")
OUT = os.path.join(HERE, "db_study", "qbank.new.json")
PAGE_SEP = "\n\x0c\n"  # 쪽 경계 표시 (쪽 번호 계산용)

MARK_RE = re.compile(r"문제\s*(\d+)\s*\]")
BODY_END_RE = re.compile(r"정\s*답|풀이\s*[:：]|모\s*의\s*고\s*사\s*\d+\s*회|모\s*범\s*답\s*안|점수")
ANS_RE = re.compile(r"정\s*답\s*[:：]\s*([\s\S]*?)(?=모\s*의\s*고\s*사|모\s*범\s*답\s*안|\Z)")
SOL_RE = re.compile(r"풀\s*이\s*[:：]\s*([\s\S]*?)(?=정\s*답\s*[:：]|모\s*의\s*고\s*사|\Z)")
NOISE_RE = re.compile(r"점수\s*\d+\s*점|\S+ 주관식 출제 예상문제")


def subject_of(name):
    stem = os.path.splitext(name)[0]
    stem = re.sub(r"^\d+\.\s*", "", stem)
    stem = re.split(r"\s*(?:주관식|교사용|학생용|-교사용|-학생용|예상)", stem)[0]
    stem = re.sub(r"\s*\d+$", "", stem).strip(" -")
    return stem or "기타"


def set_of(name):
    m = re.search(r"예상문제\s*(\d+)", name)
    if m:
        return f"예상문제{m.group(1)}"
    stem = re.sub(r"^\d+\.\s*", "", os.path.splitext(name)[0])
    m = re.search(r"(\d+)\s*-?\s*교사용", stem)
    return f"세트 {m.group(1)}" if m else "기본"


def clean(s):
    return " ".join(NOISE_RE.sub(" ", s).split())


def parse(text, subject, source, set_name, page_of):
    """page_of(offset) -> 쪽 번호. 문항 하나를 dict 로 돌려준다."""
    items = []
    marks = list(MARK_RE.finditer(text))
    for k, m in enumerate(marks):
        end = marks[k + 1].start() if k + 1 < len(marks) else len(text)
        seg = text[m.end():end]
        cut = BODY_END_RE.search(seg)
        body = seg[:cut.start()] if cut else seg
        q = clean(body)
        am = ANS_RE.search(seg)
        a = clean(am.group(1)) if am else ""
        sm = SOL_RE.search(seg)
        sol = clean(sm.group(1)) if sm else ""
        if not q:
            continue
        items.append({
            "subject": subject, "set": set_name, "source": source, "no": int(m.group(1)),
            "question": q, "answer": a, "solution": sol, "kind": "학생용",
            "figure_pages": [], "_page": page_of(m.start()),
        })
    return items


def main():
    files = sorted(glob.glob(os.path.join(SRC, "*.pdf")))
    qbank = []
    report = []
    for path in files:
        name = unicodedata.normalize("NFC", os.path.basename(path))
        doc = pymupdf.open(path)
        pages_text, pages_img = [], []
        for pg in doc:
            pages_text.append(pg.get_text())
            pages_img.append(len(pg.get_images()) > 0)
        text = PAGE_SEP.join(pages_text)
        starts = []
        pos = 0
        for t in pages_text:
            starts.append(pos)
            pos += len(t) + len(PAGE_SEP)

        def page_of(off, starts=starts):
            n = 0
            for i, s in enumerate(starts):
                if s <= off:
                    n = i
            return n + 1

        items = parse(text, subject_of(name), name, set_of(name), page_of)
        for x in items:
            p = x.pop("_page")
            if pages_img[p - 1]:
                x["figure_pages"] = [p]
            qbank.append(x)
        markers = len(MARK_RE.findall(text))
        report.append((name, len(doc), markers, len(items)))

    add_uids(qbank)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(qbank, f, ensure_ascii=False, indent=1)

    print("PDF별 (쪽수, 문제표식, 추출 문항):")
    for name, pages, markers, n in report:
        print(f"  {n:3d} / 표식 {markers:3d} / {pages:2d}쪽  {name[:40]}")
    total = len(qbank)
    no_ans = sum(1 for x in qbank if not x["answer"])
    no_sol = sum(1 for x in qbank if not x["solution"])
    fig = sum(1 for x in qbank if x["figure_pages"])
    print(f"합계 {total}문항, 정답 없음 {no_ans}, 풀이 없음 {no_sol}, 그림 쪽 문항 {fig}")
    print("저장:", OUT)


if __name__ == "__main__":
    sys.exit(main())
