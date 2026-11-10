#!/usr/bin/env python3
"""정비 매뉴얼 PDF를 읽어 로컬 FAISS 벡터 DB(db_faiss/)를 만드는 1회용 스크립트."""
import os
from pypdf import PdfReader
from docx import Document as DocxFile
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

BASE = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.join(BASE, "docs")
DB = os.path.join(BASE, "db_faiss")

docs = []   # PDF: 쪽 단위
texts = []  # md/docx: 파일 단위 전체 텍스트 (조각 번호를 page로 씀)
for root, _, files in os.walk(DOCS):
    for name in files:
        path = os.path.join(root, name)
        if name.lower().endswith(".pdf"):
            reader = PdfReader(path)
            total, got = len(reader.pages), 0
            for i, page in enumerate(reader.pages):
                text = (page.extract_text() or "").strip()
                if text:
                    got += 1
                    docs.append(Document(page_content=text, metadata={"source": name, "page": i + 1}))
            status = "OK" if got else "글자 없음(OCR 필요)"
            print(f"  - {name}: {got}/{total}쪽 읽음 [{status}]")
        elif name.lower().endswith(".md"):
            with open(path, encoding="utf-8") as f:
                texts.append((name, f.read()))
            print(f"  - {name}: md 읽음")
        elif name.lower().endswith(".docx"):
            d = DocxFile(path)
            parts = [p.text for p in d.paragraphs]
            for table in d.tables:
                for row in table.rows:
                    parts.append(" | ".join(c.text for c in row.cells))
            texts.append((name, "\n".join(parts)))
            print(f"  - {name}: docx 읽음")

print(f"텍스트가 추출된 페이지: {len(docs)}개, md/docx 파일: {len(texts)}개")
if not docs and not texts:
    raise SystemExit("추출된 텍스트가 없습니다. 스캔 PDF인지 확인하세요.")

splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
chunks = splitter.split_documents(docs)
for name, text in texts:
    parts = [p for p in splitter.split_text(text) if p.strip()]
    chunks += [Document(page_content=p, metadata={"source": name, "page": i + 1}) for i, p in enumerate(parts)]
print(f"청크: {len(chunks)}개")

EMBED_MODEL = os.environ.get("DR_EMBED_MODEL", "jhgan/ko-sroberta-multitask")
embeddings = HuggingFaceEmbeddings(model_name=EMBED_MODEL)
db = FAISS.from_documents(chunks, embeddings)
db.save_local(DB)
print("완료:", DB)
