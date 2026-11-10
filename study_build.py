#!/usr/bin/env python3
"""필기 공부용 PDF(docs/필기공부용 자동차정비산업기사 PDF/)만 읽어 db_study/ 벡터 DB를 만든다.
각 조각에 과목(subject)과 역할(role: 정답·해설 / 문제 / 모의고사 / 기타)을 메타데이터로 붙인다."""
import json
import os
import unicodedata
import re
from pypdf import PdfReader
import logging
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from qbank_ids import add_uids

logging.getLogger("pypdf").setLevel(logging.ERROR)
BASE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(BASE, "docs", "필기공부용 자동차정비산업기사 PDF")
OUT = os.path.join(BASE, "db_study")
EMBED_MODEL = os.environ.get("DR_EMBED_MODEL", "jhgan/ko-sroberta-multitask")


def subject_of(name: str) -> str:
    """'2.디젤전자제어장치정비1 교사용.pdf' -> '디젤전자제어장치정비'. 모의고사·안별 문제는 '종합'."""
    if "모의고사" in name or "복원문제" in name or "안별" in name:
        return "종합"
    stem = os.path.splitext(name)[0]
    stem = re.sub(r"^\d+\.\s*", "", stem)
    stem = re.split(r"\s*(?:주관식|교사용|학생용|-교사용|-학생용|예상)", stem)[0]
    stem = re.sub(r"\s*\d+$", "", stem).strip(" -")
    return stem or "기타"


def role_of(name: str) -> str:
    if "교사용" in name or "예상답안" in name:
        return "정답·해설"
    if "학생용" in name or "예상문제" in name:
        return "문제"
    if "모의고사" in name or "복원문제" in name or "안별" in name:
        return "모의고사"
    return "기타"


def set_of(name: str) -> str:
    """세트 이름: '1. 가솔린 ... 1-교사용' -> '1', '... 예상문제2-교사용' -> '예상문제2', 모의고사 -> '모의고사 N회'."""
    if "모의고사" in name:
        m = re.search(r"(\d+)\s*회차", name)
        return f"모의고사 {m.group(1)}회" if m else "모의고사"
    m = re.search(r"예상문제\s*(\d+)", name)
    if m:
        return f"예상문제{m.group(1)}"
    if "예상답안" in name:
        return "예상답안"
    stem = re.sub(r"^\d+\.\s*", "", os.path.splitext(name)[0])
    m = re.search(r"(\d+)\s*-?\s*교사용", stem)
    return f"세트 {m.group(1)}" if m else "기본"


MARK_RE = re.compile(r"문제\s*(\d+)\s*\]")  # 문항 시작 표시
# 지문이 끝나는 곳: 정답 표시, 풀이, 모의고사 답안지 머리글, 배점
BODY_END_RE = re.compile(r"정\s*답|풀이\s*[:：]|모\s*의\s*고\s*사\s*\d+\s*회|모\s*범\s*답\s*안|점수")
ANS_RE = re.compile(r"정\s*답\s*[:：]\s*([\s\S]*?)(?=모\s*의\s*고\s*사|모\s*범\s*답\s*안|\Z)")
SOL_RE = re.compile(r"풀\s*이\s*[:：]\s*([\s\S]*?)(?=정\s*답\s*[:：]|모\s*의\s*고\s*사|\Z)")  # 원본 풀이(채점 근거)


NOISE_RE = re.compile(r"점수\s*\d+\s*점|\S+ 주관식 출제 예상문제")  # 배점 표시·단원 머리글은 지문이 아니므로 제거


def parse_qa(text: str, subject: str, source: str, set_name: str) -> list:
    """'문제N] ... 정답: ...' 블록을 문제 은행 항목으로 바꾼다. 정답이 비어 있으면 answer는 ''(모의고사 학생용)."""
    items = []
    marks = list(MARK_RE.finditer(text))
    for k, m in enumerate(marks):  # 문항마다 다음 문항 표시 전까지만 본다
        end = marks[k + 1].start() if k + 1 < len(marks) else len(text)
        seg = text[m.end():end]
        cut = BODY_END_RE.search(seg)
        body = seg[:cut.start()] if cut else seg
        q = " ".join(NOISE_RE.sub(" ", body).split())
        am = ANS_RE.search(seg)
        a = " ".join(NOISE_RE.sub(" ", am.group(1)).split()) if am else ""
        sm = SOL_RE.search(seg)
        sol = " ".join(NOISE_RE.sub(" ", sm.group(1)).split()) if sm else ""
        if q:
            items.append({"subject": subject, "set": set_name, "source": source, "no": int(m.group(1)),
                          "question": q, "answer": a, "solution": sol,
                          "kind": "학생용" if "모의고사" in source else "교사용"})
    return items


docs = []
qbank = []
for name in sorted(os.listdir(SRC)):
    name = unicodedata.normalize("NFC", name)  # macOS 파일명은 자모 분해(NFD)라서 한글 비교 전에 정규화
    if not name.lower().endswith(".pdf"):
        continue
    reader = PdfReader(os.path.join(SRC, unicodedata.normalize("NFD", name)))
    subject, role = subject_of(name), role_of(name)
    got = 0
    full = []
    for i, page in enumerate(reader.pages):
        text = (page.extract_text() or "").strip()
        full.append(text)
        if text:
            got += 1
            docs.append(Document(page_content=text,
                                 metadata={"source": name, "page": i + 1,
                                           "subject": subject, "role": role}))
    if role == "정답·해설" or (role == "모의고사" and "모의고사" in name):  # 복원문제·안별 자료는 형식이 달라 제외
        before = len(qbank)
        qbank += parse_qa("\n".join(full), subject, name, set_of(name))
        print(f"    문제 은행 +{len(qbank) - before}문항 (세트 {set_of(name)})")
    print(f"  - [{role}] {subject} ← {name}: {got}/{len(reader.pages)}쪽")

print(f"문제 은행: {len(qbank)}문항")

splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
chunks = splitter.split_documents(docs)
print(f"쪽 {len(docs)}개 → 조각 {len(chunks)}개")
if not chunks:
    raise SystemExit("추출된 텍스트가 없습니다.")

embeddings = HuggingFaceEmbeddings(model_name=EMBED_MODEL)
db = FAISS.from_documents(chunks, embeddings)
db.save_local(OUT)
add_uids(qbank)  # 재생성해도 문제 내용이 같으면 uid가 같아서 푼 기록이 유지된다
with open(os.path.join(OUT, "qbank.json"), "w", encoding="utf-8") as f:
    json.dump(qbank, f, ensure_ascii=False, indent=1)
print("완료:", OUT)
