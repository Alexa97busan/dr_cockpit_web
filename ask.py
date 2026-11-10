#!/usr/bin/env python3
"""정비 매뉴얼 질문기: SM7 매뉴얼에서 관련 '페이지 전체'를 찾아 로컬 Qwen으로 출처와 함께 답변한다."""
import os
# 로컬 Ollama(localhost)는 프록시를 거치지 않도록 설정 (프록시 사용 시 502 Bad Gateway 방지)
os.environ['NO_PROXY'] = 'localhost,127.0.0.1'
os.environ['no_proxy'] = 'localhost,127.0.0.1'
# 오프라인 모드: 임베딩 모델은 이미 내려받아 캐시에 있으므로 인터넷 확인을 건너뛴다 (와이파이 없이도 동작)
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'

import os
import re
import ollama
import json
import socket
import urllib.request
import urllib.error
import logging
from pypdf import PdfReader
logging.getLogger("pypdf").setLevel(logging.ERROR)  # 세로 글씨 경고 숨김
from rich.console import Console
from rich.markdown import Markdown
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

BASE = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.join(BASE, "docs")
DB = os.path.join(BASE, "db_faiss")
# ---- 모델 설정 (환경변수로 바꿀 수 있음) ----
PREFERRED_MODEL = os.environ.get("DR_LOCAL_MODEL", "qwen2.5:3b")  # 기본 3b (7b는 이 맥에서 멈춤·발열이 심해 기본에서 뺌). 7b를 쓰려면 DR_LOCAL_MODEL=qwen2.5:7b
FALLBACK_MODEL = "qwen2.5:3b"
EMBED_MODEL = os.environ.get("DR_EMBED_MODEL", "jhgan/ko-sroberta-multitask")  # 바꾸면 build_db.py로 인덱스를 다시 만들어야 함
CLOUD_MODEL = os.environ.get("DR_CLOUD_MODEL", "claude-haiku-5-5")
# 클라우드 호출 주소. 기본은 Anthropic 공식 주소. 다른 주소를 쓰려면 DR_CLOUD_BASE_URL로 바꾼다.
CLOUD_BASE_URL = os.environ.get("DR_CLOUD_BASE_URL", "https://api.anthropic.com")
FETCH_K = 80            # 넉넉히 뽑은 뒤 아래 조건으로 거른다
SOURCE_KEYWORD = "SM7"  # 파일명에 이 단어가 있는 문서만 사용
TOP_PAGES = 3           # 검색 상위 몇 개 페이지를 통째로 넘길지
MAX_CHARS = 2000        # 페이지 하나당 최대 글자 수 (8GB 메모리 고려)
BOOST = " 정기점검 및 교환주기표 교환 주기"  # 정비 매뉴얼 표 페이지를 위로 올리기 위한 검색어 보강
# 주제별 검색어 보강: 질문에 키워드가 있으면 해당 보강어를 쓴다 (그림·라벨 위주 내용을 찾기 위함)
TOPIC_BOOST = {
    "공기압": " 타이어 공기압 TIRE PRESSURE 고속 주행 kg/cm psi 차량 라벨 TPMS",
    "타이어": " 타이어 공기압 TIRE PRESSURE 고속 주행 kg/cm psi 차량 라벨 TPMS",
}

SYSTEM = (
    "당신은 자동차 정비 매뉴얼 도우미입니다. 아래 [자료]는 매뉴얼 페이지 원문입니다. "
    "표가 있으면 항목, 주행거리(km), 기간(년)을 맞춰서 읽으세요. "
    "[자료]에 있는 내용만 근거로 한국어로 답하고, 없으면 '매뉴얼에서 확인되지 않습니다'라고 답하세요. "
    "답변 끝에 근거 페이지를 [파일명 p.페이지] 형식으로 적으세요."
)

SYSTEM_GENERAL = (
    "당신은 자동차정비산업기사 시험 공부를 돕는 도우미입니다. "
    "교재에 근거 자료가 없으므로 일반적인 자동차 공학 지식으로 한국어로 간단히 답하세요. "
    "수치나 기준값은 확실한 것만 말하고, 확신이 없으면 확신이 없다고 말하세요. 페이지 번호는 적지 마세요."
)

console = Console()
embeddings = HuggingFaceEmbeddings(model_name=EMBED_MODEL)
db = FAISS.load_local(DB, embeddings, allow_dangerous_deserialization=True)

def _installed_models():
    try:
        listed = ollama.list()
        items = getattr(listed, "models", None) or listed.get("models", [])
        names = set()
        for m in items:
            n = getattr(m, "model", None) or (m.get("model") or m.get("name") if isinstance(m, dict) else None)
            if n:
                names.add(n)
        return names
    except Exception:
        return set()


_names = _installed_models()
MODEL = PREFERRED_MODEL if (PREFERRED_MODEL in _names or f"{PREFERRED_MODEL}:latest" in _names) else FALLBACK_MODEL


def is_online(timeout: float = 1.5) -> bool:
    """인터넷 연결 여부를 빠르게 확인한다. 연결이 없으면 바로 로컬로 답한다."""
    try:
        socket.create_connection(("1.1.1.1", 443), timeout=timeout).close()
        return True
    except OSError:
        return False


def cloud_chat(system: str, user: str) -> str:
    """온라인 모드: 질문과 발췌문만 보내고 답변을 받는다. 교재 전체는 보내지 않는다."""
    body = json.dumps({
        "model": CLOUD_MODEL,
        "max_tokens": 1024,
        "temperature": 0.1,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }).encode("utf-8")
    req = urllib.request.Request(
        CLOUD_BASE_URL.rstrip("/") + "/v1/messages", data=body, method="POST",
        headers={"content-type": "application/json",
                 "x-api-key": get_api_key(),
                 "anthropic-version": "2023-06-01"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        # 서버가 알려 준 원인(예: 키 오류, 크레딧 부족, 모델 이름 오류)을 그대로 보여 준다. 키 값은 포함되지 않는다.
        detail = ""
        try:
            err = json.loads(e.read().decode("utf-8"))
            detail = err.get("error", {}).get("message", "")
        except Exception:
            pass
        raise RuntimeError(f"HTTP {e.code} {detail}".strip()) from None
    return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")


def get_api_key() -> str:
    """ANTHROPIC_API_KEY 환경변수에서만 읽는다. 키체인 조회는 제거되었다."""
    return os.environ.get("ANTHROPIC_API_KEY", "").strip()


ENGINE_MODES = ("auto", "cloud", "local", "both")
ENGINE_MODE = ["auto"]  # auto=자동, cloud=클라우드만, local=로컬만, both=둘 다 (답을 나란히 표시)


def _local_chat(system: str, user: str, num_ctx: int) -> str:
    resp = ollama.chat(
        model=MODEL,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        options={"temperature": 0.1, "num_ctx": num_ctx},
    )
    return resp.message.content


def cloud_ready() -> bool:
    return (os.environ.get("DR_CLOUD_OFF") != "1"
            and bool(get_api_key())
            and is_online())


def llm_chat(system: str, user: str, num_ctx: int) -> str:
    """답변 생성의 한 곳. ENGINE_MODE 에 따라 클라우드, 로컬, 또는 둘 다 사용한다."""
    mode = ENGINE_MODE[0]

    if mode == "local":
        LAST_ENGINE[0] = f"local|{MODEL}"
        return _local_chat(system, user, num_ctx)

    if mode == "cloud":
        if not cloud_ready():
            raise RuntimeError("클라우드만 모드인데 API 키가 없거나 인터넷이 연결되어 있지 않습니다. "
                               "Ctrl+G로 다른 모드를 고르세요.")
        LAST_ENGINE[0] = f"cloud|{CLOUD_MODEL}"
        return cloud_chat(system, user)

    if mode == "both":
        parts = [(f"로컬 LLM · {MODEL}", _local_chat(system, user, num_ctx))]
        if cloud_ready():
            try:
                parts.append((f"Claude API · {CLOUD_MODEL}", cloud_chat(system, user)))
            except Exception as e:
                parts.append((f"Claude API · {CLOUD_MODEL}", f"호출에 실패했습니다: {e}"))
        else:
            parts.append(("Claude API", "API 키 또는 인터넷이 없어서 건너뛰었습니다."))
        LAST_ENGINE[0] = f"both|{MODEL}+{CLOUD_MODEL}"
        return "\n\n---\n\n".join(f"### {h}\n\n{t}" for h, t in parts)

    # auto: 온라인이고 키가 있으면 클라우드, 실패하거나 오프라인이면 로컬
    if cloud_ready():
        try:
            text = cloud_chat(system, user)
            if text.strip():
                console.print("  [dim]온라인 모드: 클라우드 모델로 답합니다[/dim]")
                LAST_ENGINE[0] = f"cloud|{CLOUD_MODEL}"
                return text
        except Exception as e:
            console.print(f"  [dim]클라우드 응답 실패, 로컬 모델로 답합니다 ({e})[/dim]")
    LAST_ENGINE[0] = f"local|{MODEL}"
    return _local_chat(system, user, num_ctx)


def engine_status():
    """화면 표시용: 지금 모드에서 답하게 될 엔진."""
    mode = ENGINE_MODE[0]
    if mode == "local":
        return ("local", MODEL)
    if mode == "cloud":
        return ("cloud", CLOUD_MODEL) if cloud_ready() else ("unavailable", "키 또는 인터넷 없음")
    if mode == "both":
        return ("both", f"{MODEL} + {CLOUD_MODEL}")
    return ("cloud", CLOUD_MODEL) if cloud_ready() else ("local", MODEL)


# 파일명 -> 실제 경로 (docs 하위 전체 탐색)
PDF_PATHS = {}
for root, _, files in os.walk(DOCS):
    for name in files:
        if name.lower().endswith(".pdf"):
            PDF_PATHS[name] = os.path.join(root, name)

_reader_cache = {}


CHUNK_TEXT = {}  # md·docx 조각: (파일명, 조각번호) -> 원문 (PDF가 아니어서 쪽 조회가 안 됨)


def full_text(source: str, page_no: int) -> str:
    """해당 PDF의 해당 페이지 원문 전체(레이아웃 유지). md·docx는 저장된 조각 원문."""
    if (source, page_no) in CHUNK_TEXT:
        return CHUNK_TEXT[(source, page_no)]
    if source not in _reader_cache:
        _reader_cache[source] = PdfReader(PDF_PATHS[source])
    page = _reader_cache[source].pages[page_no - 1]
    try:
        text = page.extract_text(extraction_mode="layout")
    except TypeError:
        text = page.extract_text()
    return (text or "").strip()


def page_text(source: str, page_no: int) -> str:
    """답변 모델에 넘길 페이지 원문 (글자 수 제한 적용)."""
    return full_text(source, page_no)[:MAX_CHARS]


# ---- 질문 핵심어: 핵심어(또는 동의어)가 페이지에 있어야 근거로 쓴다 ----
STOP_WORDS = {"무엇", "무엇이고", "무엇인가", "무엇인지", "왜", "필요한가", "필요", "설명", "설명해줘",
              "알려줘", "알려", "어떻게", "대해", "원인", "방법", "정리", "교재", "매뉴얼", "페이지",
              "핵심", "내용", "있나", "있는지", "차이", "차이점", "의미", "기준", "값", "이유", "그림",
              "내가", "제가", "나는", "저는", "만약", "경우", "어떤", "무슨", "이라면", "때문에"}
PARTICLES = ("이란", "란", "에서", "으로", "에게", "은", "는", "이", "가", "을", "를", "의", "에", "와", "과", "도", "로")
ENDINGS = ("한다면", "하면", "한다", "하는", "하고", "하며", "되는", "되면", "인가", "이면", "하나요",
           "입니다", "해야", "할때", "하다", "할")
# 질문 단어 → 매뉴얼에서 쓰는 말 (둘 중 하나라도 있으면 맞은 것으로 본다)
SYNONYMS = {
    "가속": ["급가속"],
    "여름": ["무더운", "더운", "고온"],
    "주행": ["운행"],
    "운행": ["주행"],
    "짧은": ["단거리"],
    "자주": ["잦은"],
    "공회전": ["공회전"],
}


def key_terms(question: str):
    """질문에서 핵심어(조사·어미를 뺀 단어)를 뽑는다. 예: '밸브 오버랩이란 무엇이고' -> ['밸브', '오버랩']"""
    terms = []
    for w in re.findall(r"[가-힣A-Za-z0-9]+", question):
        if w in STOP_WORDS:
            continue
        for p in PARTICLES:
            if w.endswith(p) and len(w) - len(p) >= 2:
                w = w[: -len(p)]
                break
        for e in ENDINGS:
            if w.endswith(e) and len(w) - len(e) >= 2:
                w = w[: -len(e)]
                break
        if len(w) >= 2 and w not in STOP_WORDS:
            terms.append(w)
    return list(dict.fromkeys(terms))


def _compact(text: str) -> str:
    """공백과 쉼표를 빼서 '엔진 오일', '5,000km' 같은 표기 차이를 없앤다."""
    return re.sub(r"[\s,]", "", text)


def _has(compact: str, term: str) -> bool:
    return term in compact or any(syn in compact for syn in SYNONYMS.get(term, []))


def specific_term(terms):
    """가장 구체적인 핵심어 (숫자가 아닌 단어 중 가장 긴 것)."""
    words = [t for t in terms if not re.search(r"\d", t)] or terms
    return max(words, key=len)


def _enough(compact: str, terms) -> bool:
    """핵심어가 충분히 들어 있는지 판단한다.
    - 핵심어 2개 이하: 구체적인 핵심어(가장 긴 단어)가 반드시 있어야 한다. (예: 밸브 오버랩)
    - 핵심어 3개 이상: 절반 이상이 있으면 된다. 시나리오형 질문은 표현이 달라서 이 기준이 맞다."""
    if not terms:
        return True
    hits = sum(_has(compact, t) for t in terms)
    if len(terms) <= 2:
        return _has(compact, specific_term(terms)) and hits >= 1
    return hits >= (len(terms) + 1) // 2


def page_matches(source: str, page_no: int, terms) -> bool:
    """구체적인 핵심어가 있고, 핵심어의 절반 이상(동의어 포함)이 있어야 근거로 인정."""
    if not terms:
        return True
    compact = _compact(full_text(source, page_no))
    return _enough(compact, terms)


def keyword_pages(terms, limit: int = 30):
    """벡터 검색과 별개로, DB에 들어 있는 페이지 중 핵심어(동의어 포함)가 실제로 나오는 페이지를 찾는다.
    구체적인 핵심어가 있어야 하고, 핵심어가 많이 들어 있을수록 앞에 둔다."""
    if not terms:
        return []
    by_page = {}
    for doc in db.docstore._dict.values():
        src, pg = doc.metadata.get("source", ""), doc.metadata.get("page")
        if pg is None or src not in PDF_PATHS or not in_mode(src):
            continue
        by_page.setdefault((src, pg), []).append(doc.page_content)
    scored = []
    for key, parts in by_page.items():
        compact = _compact("\n".join(parts))
        if _enough(compact, terms):
            scored.append((sum(_has(compact, t) for t in terms), key))
    scored.sort(key=lambda x: -x[0])
    return [key for _, key in scored[:limit]]


def line_has_term(line: str, terms) -> bool:
    compact = _compact(line)
    return not terms or any(_has(compact, t) for t in terms)


# 수치·단위가 들어 있는 줄만 원문 그대로 뽑는다 (모델 해석 없이 확인용)
UNIT_RE = re.compile(r"(kg/?cm|psi|kPa|bar|N\s?[·.]\s?m|km|℃|°C|ℓ|mm|rpm|V\b|%|개월|년)", re.IGNORECASE)


def value_lines(text: str, limit: int = 8):
    out = []
    for line in text.splitlines():
        s = " ".join(line.split())
        if len(s) < 200 and UNIT_RE.search(s) and re.search(r"\d", s):
            out.append(s)
        if len(out) >= limit:
            break
    return out


LAST_ENGINE = [""]  # 마지막 답변을 만든 엔진: "cloud|모델" 또는 "local|모델"
CURRENT_MODE = ["manual"]  # "manual" = SM7 매뉴얼, "book" = 자동차정비산업기사 교재

def in_mode(source: str) -> bool:
    is_sm7 = SOURCE_KEYWORD.lower() in source.lower()
    return is_sm7 if CURRENT_MODE[0] == "manual" else not is_sm7


def general_answer(question: str) -> str:
    """교재에 근거가 없을 때: 일반 지식으로 답하고 근거 없음을 표시한다."""
    text = llm_chat(SYSTEM_GENERAL, question, num_ctx=4096)
    return ("> **교재 근거 없음 · 일반 지식 답변**입니다. 시험 전에 교재와 대조해 확인하세요.\n\n"
            + text)


def ask(question: str) -> str:
    if CURRENT_MODE[0] == "book":
        boost = ""
    else:
        boost = next((v for k, v in TOPIC_BOOST.items() if k in question), BOOST)
    candidates = db.similarity_search(question + boost, k=FETCH_K)
    hits = [d for d in candidates if in_mode(d.metadata["source"])]
    if not hits:
        return "매뉴얼에서 확인되지 않습니다. (검색된 SM7 구절이 없습니다)"

    for d in hits:
        if d.metadata["source"] not in PDF_PATHS:
            CHUNK_TEXT[(d.metadata["source"], d.metadata["page"])] = d.page_content

    # 상위 검색 결과에서 중복 없이 페이지를 고른다
    terms = key_terms(question)
    pages, seen = [], set()
    for key in keyword_pages(terms) + [(d.metadata["source"], d.metadata["page"]) for d in hits]:
        if key in seen or (key[0] not in PDF_PATHS and key not in CHUNK_TEXT):
            continue
        seen.add(key)
        if page_matches(key[0], key[1], terms):
            pages.append(key)
        if len(pages) >= TOP_PAGES:
            break

    label = "교재" if CURRENT_MODE[0] == "book" else "매뉴얼"
    if not pages:
        if CURRENT_MODE[0] == "book":
            return general_answer(question)
        # 매뉴얼(SM7)은 차량 기준값을 다루므로 일반 지식으로 답하지 않는다
        return (f"{label}에서 확인되지 않습니다.\n\n"
                f"찾은 핵심어: {' · '.join(terms) or '없음'}\n"
                f"이 단어들이 들어 있는 페이지가 없어서 근거를 제시하지 않습니다. "
                f"매뉴얼에서 쓰는 말로 바꿔 질문해 보세요. 예: 급가속, 무더운 날씨, 운행 거리")

    blocks, excerpts, plain = [], [], []
    for source, page_no in pages:
        console.print(f"  [dim]- {source} p.{page_no}[/dim]")
        text = page_text(source, page_no)
        blocks.append(f"[{source} p.{page_no}]\n{text}")
        for line in value_lines(full_text(source, page_no)):
            if line_has_term(line, terms):
                excerpts.append(f"- {line}  _({source} p.{page_no})_")
                plain.append(f"- {line}  (p.{page_no})")
    # 질문과 관련된 원문 문장을 맨 앞에 두어 작은 모델이 핵심을 놓치지 않게 한다
    key_block = ("[질문과 관련된 원문 문장]\n" + "\n".join(plain) + "\n\n") if plain else ""
    context = key_block + "\n\n".join(blocks)

    system_prompt = SYSTEM if CURRENT_MODE[0] == "manual" else SYSTEM.replace("매뉴얼", "교재")
    answer = llm_chat(system_prompt, f"[자료]\n{context}\n\n[질문]\n{question}", num_ctx=8192)
    if "확인되지 않습니다" in answer and ENGINE_MODE[0] != "both":
        # 모델이 근거를 못 읽었더라도, 핵심어가 들어 있는 원문 문장은 그대로 보여 준다
        if excerpts:
            return ("**원문에서 찾은 문장입니다.** 요약 답변이 불확실해 원문을 그대로 보여 드립니다.\n\n"
                    + "\n".join(excerpts))
        if CURRENT_MODE[0] == "book":
            return general_answer(question)

    if excerpts:
        answer += "\n\n---\n**원문 수치 발췌 (모델 해석 없이 매뉴얼 원문에서 그대로 가져온 줄)**\n" + "\n".join(excerpts)
    return answer


if __name__ == "__main__":
    console.print("[bold]정비 매뉴얼 · 교재 질문기[/bold]  (전환: /매뉴얼 /교재  |  종료: q)")
    if console.input("모드 선택 [1] SM7 매뉴얼  [2] 교재 (Enter=1): ").strip() == "2":
        CURRENT_MODE[0] = "book"
    while True:
        label = "교재" if CURRENT_MODE[0] == "book" else "매뉴얼"
        q = console.input(f"\n[{label}] 질문> ").strip()
        if q.lower() in ("q", "quit", "exit"):
            break
        if q in ("/매뉴얼", "/manual"):
            CURRENT_MODE[0] = "manual"
            console.print("→ SM7 매뉴얼 모드")
            continue
        if q in ("/교재", "/book"):
            CURRENT_MODE[0] = "book"
            console.print("→ 교재 모드")
            continue
        if not q:
            continue
        with console.status("검색 중..."):
            answer = ask(q)
        console.print(Markdown(answer))
