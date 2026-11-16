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

  // 주관식 자가채점 (서버 없이). 정답 키를 '또는', '/', ',' 로 나눈 표현 중 하나와 같으면 정답.
  // 띄어쓰기·괄호·대소문자·하이픈은 무시한다. 키가 없는 문항은 판정하지 않는다.
  function normKey(s) {
    return String(s || "").toLowerCase().replace(/[\s()\[\]·.,'"‘’“”\-_/]/g, "");
  }
  function altsOf(answer) {
    return String(answer || "").split(/\s*(?:또는|\bor\b|\/|;|,)\s*/i).map(normKey).filter(Boolean);
  }
  function gradeSubjective(n, text) {
    const s = secret[String(n)];
    const hasKey = s && s.answer && !s.answer.startsWith("원본 자료에");
    if (!hasKey) {
      return {
        verdict: "unknown",
        sections: [{ title: "판정", body: "이 문항은 정답 키가 없어 자동 채점하지 않습니다. 해설을 보고 직접 확인하세요." }],
        answer: s ? s.answer : "",
      };
    }
    const got = normKey(text);
    const hit = got !== "" && altsOf(s.answer).includes(got);
    const sections = [{
      title: "판정",
      body: hit ? "정답 키와 일치합니다." : "정답 키와 일치하지 않습니다. 모범답안의 명칭을 그대로 확인하세요.",
    }];
    if (s.solution) sections.push({ title: "풀이", body: s.solution });
    return { verdict: hit ? "correct" : "wrong", sections, answer: s.answer };
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
        return ok(gradeSubjective(checkN(body.n), body.answer));
      }
      return fail("지원하지 않는 요청입니다.");
    } catch (e) {
      return fail(e.message);
    }
  };
})();
