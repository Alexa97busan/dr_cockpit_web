"""문항 고유 ID(uid). 과목·세트·번호·문제 본문으로 만들어서, 문항 번호가 바뀌어도 같은 문항이면 같은 uid가 나온다."""
import hashlib


def make_uid(x: dict) -> str:
    key = "|".join(str(x.get(k) or "") for k in ("subject", "set", "no", "question"))
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]


def add_uids(items: list) -> list:
    """모든 문항에 uid를 붙인다. 같은 uid가 둘 이상이면 오류로 멈춘다."""
    seen = {}
    for x in items:
        x["uid"] = make_uid(x)
        if x["uid"] in seen:
            raise SystemExit(f"uid 중복: {x['uid']} ({x.get('subject')} / {x.get('set')} / {x.get('no')})")
        seen[x["uid"]] = True
    return items
