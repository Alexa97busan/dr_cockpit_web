"""객관식 오답 보기 고르기.

오답 후보는 우선순위대로 모은다.
1. AI 생성 오답 (db_study/distractors.json, build_distractors.py 가 만들고 규칙 검증을 통과한 것만, reject=true 는 제외)
2. 반대 개념 쌍 (db_study/contrast_groups.json, 같은 묶음의 다른 답)
3. 정답과 글자 유사도가 높은 같은 과목 답 상위권
4. 나머지 같은 과목 답 → 부족하면 다른 과목 답

모든 후보는 (a) 정답과 형식이 같은지(숫자·약어·문장), (b) 정답과 모호하지 않은지(포함관계·동의어·유사도 과다 제외)를 본다.
형식이 맞는 후보가 모자라면 형식 조건만 푼다.
"""
import json
import os
import re
from functools import lru_cache

HERE = os.path.dirname(os.path.abspath(__file__))
DB_STUDY = os.path.join(HERE, "db_study")
GROUPS_PATH = os.path.join(DB_STUDY, "contrast_groups.json")
GEN_PATH = os.path.join(DB_STUDY, "distractors.json")

_UNIT_WORDS = {"이하", "이상", "이내", "초과", "미만"}
_SIM_LIMIT = 0.7  # 정답과 이 값 이상으로 닮은 보기는 모호하므로 제외


def _norm(s):
    return re.sub(r"[\s()\[\]·,.\-]", "", s or "").lower()


def fmt_class(s):
    """숫자형(수치+단위), 약어형(영문·숫자 조합), 문장형."""
    s = (s or "").strip()
    words = re.findall(r"[가-힣]+", s)
    if re.search(r"\d", s) and len(s) <= 16 and "또는" not in s and all(w in _UNIT_WORDS for w in words):
        return "num"
    if re.fullmatch(r"[A-Za-z0-9/ .\-]+", s):
        return "abbr"
    return "text"


@lru_cache(maxsize=None)
def _bigrams(s):
    t = re.sub(r"\s", "", s or "")
    return frozenset(t[i:i + 2] for i in range(len(t) - 1)) or frozenset([t])


def _sim(a, b):
    A, B = _bigrams(a), _bigrams(b)
    return len(A & B) / max(1, len(A | B))


def ambiguous(cand, correct):
    """정답과 헷갈려 둘 다 맞는 답이 될 수 있는 보기인가."""
    nc, nr = _norm(cand), _norm(correct)
    if len(nc) < 2 or nc == nr:
        return True
    if nc in nr or nr in nc:  # 'AFS' 와 'AFS 또는 공기유량센서' 같은 포함 관계
        return True
    if _sim(cand, correct) >= _SIM_LIMIT:
        return True
    return False


def len_ok(cand, correct):
    """보기 길이를 정답과 비슷하게 맞춘다. 정답만 길거나 짧은 것을 찍는 힌트를 줄이기 위함."""
    nc, nr = len(_norm(cand)), len(_norm(correct))
    return abs(nc - nr) <= max(3, 0.35 * nr)


def same_or(cand, correct):
    """'A 또는 B' 형식은 정답에만 있으면 힌트가 되므로 양쪽이 같을 때만 쓴다."""
    return ("또는" in cand) == ("또는" in correct)


def _load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


_CACHE = {}


def _cached(path, loader):
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        mtime = None
    hit = _CACHE.get(path)
    if hit and hit[0] == mtime:
        return hit[1]
    val = loader(path)
    _CACHE[path] = (mtime, val)
    return val


def _groups():
    return _cached(GROUPS_PATH, lambda p: _load_json(p, []))


def _generated():
    """uid -> 검증된 AI 오답 목록. reject=true 로 표시된 보기는 뺀다."""
    def build(p):
        raw = _load_json(p, {})
        out = {}
        for uid, entry in raw.items():
            opts = [o["text"] for o in entry.get("options", []) if isinstance(o, dict) and not o.get("reject")]
            out[uid] = (entry.get("correct", ""), opts)
        return out
    return _cached(GEN_PATH, build)


def _contrast(correct):
    nr = _norm(correct)
    found = []
    for g in _groups():
        if any(_norm(m) == nr for m in g):
            found += [m for m in g if _norm(m) != nr]
    return list(dict.fromkeys(found))


def pick(uid, correct, subject, pool, rng):
    """보기 오답 3개를 고른다. rng 는 호출한 쪽이 uid 로 시드를 고정한 Random 이어야 한다."""
    want = 3
    cfmt = fmt_class(correct)
    same = [a for a in pool.get(subject, []) if a != correct]
    everything = [a for lst in pool.values() for a in lst if a != correct]

    gen = [t for t in _generated().get(str(uid), ("", []))[1]]
    contrast = _contrast(correct)
    # 글자 유사도 상위 20개에서 무작위로 고른다. 상위 10개를 고정하면 같은 오답이 여러 문항에 반복된다.
    similar = sorted(same, key=lambda a: -_sim(a, correct))[:20]

    tiers = []
    # 난이도: AI 오답 → 글자 유사도 상위권(무작위) → 반대 개념 → 나머지
    for tier in (gen, similar, contrast):
        t = list(dict.fromkeys(tier))
        rng.shuffle(t)
        tiers.append(t)
    rest = list(dict.fromkeys(same + everything))
    rng.shuffle(rest)
    tiers.append(rest)

    chosen = []

    def take(cands, need_fmt, need_len):
        for c in cands:
            if len(chosen) >= want:
                return
            if c in chosen or ambiguous(c, correct):
                continue
            if not same_or(c, correct):
                continue
            if need_fmt and fmt_class(c) != cfmt:
                continue
            if need_len and not len_ok(c, correct):
                continue
            chosen.append(c)

    # 1차: 형식·길이가 맞는 후보. 2차: 길이 조건을 풀고 형식만 맞춘다. 3차: 형식도 푼다(후보가 모자랄 때만).
    for need_fmt, need_len in ((True, True), (True, False), (False, False)):
        for tier in tiers:
            take(tier, need_fmt, need_len)
    return chosen[:want]
