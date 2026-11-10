"""문제 그림 쪽(figure_pages)의 원본 PDF 쪽을 PNG 로 렌더링한다.

결과: web/pages/pg_<원본쪽>.png  와  db_study/page_images.json  {uid: ["pages/pg_....png"]}
- qbank.json 을 바꾸지 않으므로 문제 은행을 다시 만들어도 이 파일은 그대로 남는다.
- 다시 실행하면 모든 쪽을 새로 그린다.
"""
import json
import os
import re
import sys
import unicodedata

import pymupdf as fitz

HERE = os.path.dirname(os.path.abspath(__file__))
QBANK = os.path.join(HERE, "db_study", "qbank.json")
OUT_JSON = os.path.join(HERE, "db_study", "page_images.json")
OUT_BLUR = os.path.join(HERE, "db_study", "page_blur.json")  # uid -> {쪽 이미지: [[x0,y0,x1,y1] 0~1 비율]} 정답 글자 위치
OUT_DIR = os.path.join(HERE, "web", "pages")
DOCS = os.path.join(HERE, "docs")
ZOOM = 1.6


def find_pdfs():
    found = {}
    for root, _, files in os.walk(DOCS):
        for f in files:
            if f.lower().endswith(".pdf"):
                found.setdefault(unicodedata.normalize("NFC", f), os.path.join(root, f))
    return found


def page_name(src, p):
    return "pg_" + re.sub(r"[^0-9A-Za-z]", "", os.path.basename(src))[:40] + f"_{p}.png"


def answer_spots(src, pages, answer):
    """정답 글자가 쪽에 나오는 자리를 찾는다. 너무 짧은 정답(3자 이하)은 다른 글자와 겹쳐 가리지 않는다."""
    out = {}
    if len(answer) < 4:
        return out
    doc = fitz.open(src)
    for p in pages:
        if not (1 <= p <= len(doc)):
            continue
        pg = doc[p - 1]
        rects = pg.search_for(answer)
        if not rects:
            continue
        W, H, pad = pg.rect.width, pg.rect.height, 3
        out["pages/" + page_name(src, p)] = [
            [round(max(0, (r.x0 - pad) / W), 4), round(max(0, (r.y0 - pad) / H), 4),
             round(min(1, (r.x1 + pad) / W), 4), round(min(1, (r.y1 + pad) / H), 4)] for r in rects]
    doc.close()
    return out


def main():
    with open(QBANK, encoding="utf-8") as f:
        qbank = json.load(f)
    pdfs = find_pdfs()
    os.makedirs(OUT_DIR, exist_ok=True)
    mapping, rendered, missing, blur = {}, {}, [], {}
    for x in qbank:
        pages = x.get("figure_pages") or []
        if not pages:
            continue
        src = pdfs.get(unicodedata.normalize("NFC", x.get("source", "")))
        if not src:
            missing.append(x.get("source"))
            continue
        out_list = []
        for p in pages:
            key = (src, p)
            if key not in rendered:
                doc = fitz.open(src)
                if not (1 <= p <= len(doc)):
                    doc.close()
                    continue
                name = "pg_" + re.sub(r"[^0-9A-Za-z]", "", os.path.basename(src))[:40] + f"_{p}.png"
                pix = doc[p - 1].get_pixmap(matrix=fitz.Matrix(ZOOM, ZOOM), alpha=False)
                pix.save(os.path.join(OUT_DIR, name))
                doc.close()
                rendered[key] = "pages/" + name
            out_list.append(rendered[key])
        if out_list:
            mapping[str(x["uid"])] = out_list
            spots = answer_spots(src, pages, (x.get("answer") or "").strip())
            if spots:
                blur[str(x["uid"])] = spots
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=1)
    with open(OUT_BLUR, "w", encoding="utf-8") as f:
        json.dump(blur, f, ensure_ascii=False, indent=1)
    print(f"정답 가림 문항 {len(blur)}개")
    print(f"문항 {len(mapping)}개, 쪽 이미지 {len(rendered)}장")
    if missing:
        print("PDF 를 못 찾은 원본:", sorted(set(missing)))


if __name__ == "__main__":
    sys.exit(main())
