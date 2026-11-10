// 서버 없이 쓰는 문항 API. study_api 의 응답과 같은 모양을 window.STUDY_DATA(data/study-data.js)에서 만든다.
// 데이터는 export_static.py 가 만든다. 문항 은행이 바뀌면 그 스크립트를 다시 실행한다.
(function () {
  const D = window.STUDY_DATA;
  if (!D) {
    window.api = async function () {
      throw new Error("문항 데이터(web/data/study-data.js)가 없습니다. export_static.py 를 먼저 실행하세요.");
    };
    return;
  }
  const items = D.items;
  const secret = D.secret;

  function ok(j) { return Promise.resolve(j); }
  function fail(msg) { return Promise.reject(new Error(msg)); }

  function checkN(n) {
    if (!Number.isInteger(n) || n < 1 || n > items.length) {
      throw new Error(`1~${items.length} 사이 번호를 입력하세요.`);
    }
    return n;
  }

  function query(path) {
    const q = {};
    const i = path.indexOf("?");
    if (i >= 0) {
      new URLSearchParams(path.slice(i + 1)).forEach((v, k) => { q[k] = v; });
    }
    return q;
  }

  window.api = async function api(path, body) {
    const p = path.split("?")[0];
    try {
      if (p === "/api/health") {
        return ok({ ok: true, count: items.length });
      }
      if (p === "/api/subjects") {
        const counts = {};
        items.forEach((x) => { counts[x.subject] = (counts[x.subject] || 0) + 1; });
        return ok(Object.entries(counts).map(([subject, count]) => ({ subject, count })));
      }
      if (p === "/api/questions") {
        const { subject, kind } = query(path);
        const out = [];
        items.forEach((x) => {
          if (subject && !x.subject.includes(subject)) return;
          if (kind && x.kind !== kind) return;
          const n = x.n;
          out.push({
            n, uid: x.uid, subject: x.subject, set: x.set, kind: x.kind, no: x.no,
            mc: secret[String(n)].ci !== null,
            q: (x.question || "").split(/\s+/).filter(Boolean).join(" ").slice(0, 70),
          });
        });
        return ok(out);
      }
      if (p.startsWith("/api/questions/")) {
        const n = checkN(Number(p.slice("/api/questions/".length)));
        return ok(items[n - 1]);
      }
      if (p === "/api/choice") {
        const n = checkN(body.n);
        const s = secret[String(n)];
        if (s.ci === null) throw new Error("객관식으로 풀 수 없는 문항입니다.");
        const opts = items[n - 1].choices || [];
        if (!Number.isInteger(body.pick) || body.pick < 0 || body.pick >= opts.length) {
          throw new Error("보기 번호가 잘못되었습니다.");
        }
        return ok({
          verdict: body.pick === s.ci ? "correct" : "wrong",
          correct_index: s.ci,
          answer: s.answer,
          solution: s.solution,
        });
      }
      if (p === "/api/reveal") {
        const n = checkN(body.n);
        const s = secret[String(n)];
        return ok({ n, answer: s.answer, solution: s.solution });
      }
      if (p === "/api/grade") {
        return fail("주관식 채점은 서버가 필요해 이 버전에서는 쓸 수 없습니다. 정답 보기를 이용하세요.");
      }
      return fail("지원하지 않는 요청입니다.");
    } catch (e) {
      return fail(e.message);
    }
  };
})();
