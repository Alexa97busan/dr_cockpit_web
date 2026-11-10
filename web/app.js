// 정비산업기사 주관식 프론트 (스와이프 카드 뼈대). 데이터·채점·검색은 모두 study_api 를 통해서만 받는다.
const API = "http://127.0.0.1:8765";
const $ = (id) => document.getElementById(id);
const DRAG_OK = 90; // 이 거리 이상 밀면 동작이 확정된다
const VERDICT = {
  correct: ["정답", "text-emerald-600"],
  partial: ["부분 정답", "text-amber-600"],
  wrong: ["오답", "text-rose-600"],
  unknown: ["판정 불명", "text-neutral-500"],
};

let list = [];
let allList = [];   // 전체 문항 (객관식 모드에서는 list 가 이 중 객관식 가능한 것만 된다)
let qMode = localStorage.getItem("qMode") === "mc" ? "mc" : "sub";
let idx = 0;
let cur = null;
let answering = false;
let dragging = false;
let startX = 0;
let dx = 0;

const isTeacher = () => cur && cur.kind === "교사용";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function api(path, body) {
  const opt = body
    ? { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) }
    : {};
  let r;
  try {
    r = await fetch(API + path, opt);
  } catch {
    throw new Error("API 서버에 연결하지 못했습니다. study_api 서버가 켜져 있는지 확인하세요.");
  }
  if (!r.ok) {
    const j = await r.json().catch(() => ({}));
    throw new Error(typeof j.detail === "string" ? j.detail : `요청 실패 (${r.status})`);
  }
  return r.json();
}

function setStatus(msg) {
  $("status").textContent = msg || "";
}

function run(fn) {
  return Promise.resolve().then(fn).catch((e) => setStatus(e.message));
}

// ---- 데이터 ----
async function loadSubjects() {
  const subs = await api("/api/subjects");
  $("subject").add(new Option("전체", ""));
  subs.forEach((s) => $("subject").add(new Option(`${s.subject} (${s.count})`, s.subject)));
}

async function loadList() {
  reviewOn = false;
  fullList = null;
  const s = $("subject").value;
  allList = await api(`/api/questions${s ? `?subject=${encodeURIComponent(s)}` : ""}`);
  list = qMode === "mc" ? allList.filter((x) => x.mc) : allList;
  idx = 0;
  if (!list.length) {
    cur = null;
    $("question").textContent = "문항이 없습니다.";
    return;
  }
  await show();
}

async function show() {
  resetView();
  renderCur(await getQ(list[idx].n));
  prefetchAround();
  updateNext();
  renderPile();
}

// 과목 → 3D 해설 다이어그램 단원 카드 id (web/diagrams/diagrams_3d.html)
const DIAG_UNIT = {
  "가솔린 전자제어장치정비": "unit05_gasoline",
  "디젤전자제어장치정비": "unit04_crdi",
  "유압식전자제어 현가장치정비": "unit01_suspension",
  "유압식전자제어 조향장치정비": "unit02_steering",
  "전자제어공압식 제동장치정비": "unit03_brakes",
  "냉난방장치정비": "unit06_hvac",
  "네트워크통신장치정비": "unit07_can",
  "자동변속기정비": "unit08_transmission",
  "배출가스장치정비": "unit09_emissions",
};
function paintDiagLink(subject) {
  const a = $("diagLink");
  if (!a) return;
  const unit = DIAG_UNIT[subject];
  a.href = `diagrams/diagrams_3d.html${unit ? `#${unit}` : ""}`;
}

function renderCur(data) {
  cur = data;
  $("set").textContent = `${cur.subject} ${cur.set}`;
  paintDiagLink(cur.subject);
  $("pos").textContent = `${idx + 1} / ${list.length}`;
  paintEdges();
  $("question").textContent = cur.question;
  $("answerOpen").textContent = isTeacher() ? "정답 보기" : "정답 보기";
  paintChoices(cur);
  showFigures([...(cur.pages || []), ...(cur.figures || [])], cur.blur || {});
  updateRing();
}

// 원형 표시: 전체 중 몇 번째인지, 남은 문항 수
// 로딩바: 전체 중 몇 번째인지, 남은 문항 수
function updateRing() {
  const total = list.length;
  const pos = Math.min(idx + 1, total);
  $("progNum").textContent = `${pos} / ${total}`;
  $("progSub").textContent = `남은 ${Math.max(total - pos, 0)}`;
  $("progFill").style.width = `${total ? (pos / total) * 100 : 0}%`;
}
function setRingHint(t) {
  if (t) $("progSub").textContent = t;
  else updateRing();
}

// ---- 로딩바: 마우스를 피해 돌아다닌다 (웹챗 사이트의 마우스 피하기 로직 참고) ----
// 세계(중력)를 고른다. 지구·달은 바닥을 걷고 뛰고, 우주는 중력 없이 떠다닌다.
// 1 쉬움 ~ 5 어려움. 난이도는 EVADE_LV 숫자만 바꾸면 된다.
const EVADE_LV = 3;
const EVADE = {
  1: { dodge: 0.5, pad: 0.6, want: 0.35 },
  2: { dodge: 0.75, pad: 0.8, want: 0.5 },
  3: { dodge: 0.92, pad: 1, want: 0.7 },
  4: { dodge: 0.97, pad: 1.2, want: 0.85 },
  5: { dodge: 1, pad: 1.4, want: 1 },
};
const evade = EVADE[EVADE_LV];
const WORLDS = {
  earth: { g: 2400, jump: 820, floor: true },  // 지구: 중력 강함, 살짝 뜀
  moon: { g: 520, jump: 640, floor: true },    // 달: 중력 약함, 높이 뜀
  space: { g: 0, jump: 0, floor: false },      // 우주: 중력 없음, 떠다님
};
const FLOOR_H = 28; // 화면 아래 바닥 띠 높이
let world = "earth";
try { const v = localStorage.getItem("world"); if (WORLDS[v]) world = v; } catch (e) {}

const clamp = (v, a, b) => Math.min(Math.max(v, a), b);
const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;

// mode: wander(배회) · flee(도망) · lazy(귀찮아서 가만히) · rest(기운 충전)
const R = {
  world, x: 0, y: 0, vx: 0, vy: 0, tx: 0, ty: 0, w: 1.5, z: 1, cap: 600, onFloor: false,
  px: -1e4, py: -1e4, pvx: 0, pvy: 0, pt: 0,   // 마우스 위치와 속도
  mode: "wander", think: 0, reflexAt: 0, nextAt: 0, lazyUntil: 0,
  energy: 1, last: 0,                           // 기운: 도망치면 줄고 쉬면 찬다
};
// 로딩바 정지/재생: 누르면 캐릭터 움직임만 멈춘다. 상태는 localStorage "loaderPaused"에 남긴다.
const LOADER_KEY = "loaderPaused";
let LOADER_PAUSED = false;
try { LOADER_PAUSED = localStorage.getItem(LOADER_KEY) === "1"; } catch (e) {}
let loopOn = false;
function startLoop() {
  if (loopOn) return;
  loopOn = true;
  R.last = 0;
  requestAnimationFrame(frame);
}
function paintLoaderPause() {
  const b = document.getElementById("loaderPause");
  if (!b) return;
  b.textContent = LOADER_PAUSED ? "▶" : "⏸";
  b.setAttribute("aria-pressed", String(LOADER_PAUSED));
  b.setAttribute("aria-label", LOADER_PAUSED ? "캐릭터 재생" : "캐릭터 일시정지");
}
function setLoaderPaused(on) {
  LOADER_PAUSED = on;
  try { localStorage.setItem(LOADER_KEY, on ? "1" : "0"); } catch (e) {}
  paintLoaderPause();
  if (!on && !reduceMotion) {
    R.nextAt = performance.now() + 400;
    startLoop();
  }
}
const lpBtn = document.getElementById("loaderPause");
if (lpBtn) lpBtn.addEventListener("click", () => setLoaderPaused(!LOADER_PAUSED));

const barEl = () => $("progress");
const bw = () => barEl().offsetWidth;
const bh = () => barEl().offsetHeight;
const inGround = () => WORLDS[R.world].floor;
const groundY = () => Math.max(0, innerHeight - FLOOR_H - bh());
const mx = () => Math.max(0, innerWidth - bw() - 8);
const my = () => Math.max(0, innerHeight - bh() - 8);
const spring = (w, z) => { R.w = w; R.z = z; R.cap = 260 + 110 * w; };
const spend = (c) => { R.energy = Math.max(0, R.energy - c); };
const distToMouse = () => Math.hypot(R.x + bw() / 2 - R.px, R.y + bh() / 2 - R.py);
const arrived = () => (inGround()
  ? Math.abs(R.x - R.tx) < 4 && Math.abs(R.vx) < 6 && R.onFloor
  : Math.hypot(R.x - R.tx, R.y - R.ty) < 4 && Math.hypot(R.vx, R.vy) < 6);

// 땅에서 뛰기: 지구·달에서만. 중력 세기에 따라 높이가 달라진다.
function hop(p) {
  if (!inGround() || !R.onFloor || Math.random() >= p) return;
  R.vy = -WORLDS[R.world].jump * (0.85 + 0.3 * R.energy);
  R.onFloor = false;
}

function wander() {
  R.tx = Math.random() * mx();
  R.ty = inGround() ? groundY() : Math.random() * my();
}

// 도망 자리: 마우스의 예측 위치(0.2초 뒤)에서 가장 먼 곳. 기운이 많으면 후보가 많아 더 좋은 곳을 고른다.
function escapeTarget() {
  const fx = R.px + R.pvx * 0.2;
  const fy = R.py + R.pvy * 0.2;
  const n = 8 + Math.round(16 * R.energy);
  let best = { x: 0, y: 0 };
  let bestS = -Infinity;
  for (let k = 0; k < n; k++) {
    const x = Math.random() * mx();
    const y = inGround() ? groundY() : Math.random() * my();
    const cx = x + bw() / 2;
    const cy = y + bh() / 2;
    const d = Math.hypot(cx - fx, cy - fy) + 0.5 * Math.hypot(cx - R.px, cy - R.py);
    const edge = Math.min(x, mx() - x, y, my() - y);
    const s = d - (edge < 24 && !inGround() ? 80 : 0); // 우주에서는 가장자리를 조금 피한다
    if (s > bestS) {
      bestS = s;
      best = { x, y };
    }
  }
  R.tx = best.x;
  R.ty = best.y;
}

function flee(quick) {
  const E = Math.max(R.energy, 0.4);
  escapeTarget();
  if (quick && R.energy > 0.4) spring(4.5 + 2.5 * E, 0.72);
  else spring(4 + 2 * R.energy, 0.72);
  hop(quick ? 0.8 : 0.4);
}

// 마우스가 가까이 왔을 때: 기운과 레벨에 따라 피할지, 귀찮아서 가만히 있을지 정한다
function startEncounter(now) {
  const want = Math.min(1, (0.2 + 0.75 * R.energy) * (evade.want / 0.7));
  if (Math.random() > want) {
    R.mode = "lazy";
    R.lazyUntil = now + 1500 + Math.random() * 2000;
    return;
  }
  R.mode = "flee";
  R.think = now + (250 + 600 * (1 - R.energy)) * (0.7 + Math.random() * 0.6); // 지치면 고민이 길다
}

function frame(now) {
  if (LOADER_PAUSED) { loopOn = false; return; } // 정지: 루프를 멈추고 위치는 그대로 둔다
  const dt = Math.min(0.033, R.last ? (now - R.last) / 1000 : 0.016);
  R.last = now;
  const c = distToMouse();

  // 충전: 쉬는 중에 가장 빠르고, 가만히 있으면 천천히 찬다
  const rate = R.mode === "rest" ? 0.16 : R.mode === "lazy" ? 0.03 : R.mode === "wander" && arrived() ? 0.05 : 0.01;
  R.energy = Math.min(1, R.energy + rate * dt);

  // 반사: 마우스가 코앞(또는 0.25초 뒤 위치)에 오면 레벨 확률로 바로 피한다
  const sp = Math.hypot(R.pvx, R.pvy);
  const pad = (70 + Math.min(140, sp * 0.15)) * evade.pad;
  const hits = (x, y, p) => x > R.x - p && x < R.x + bw() + p && y > R.y - p && y < R.y + bh() + p;
  const ppx = R.px + R.pvx * 0.25;
  const ppy = R.py + R.pvy * 0.25;
  if (now >= R.reflexAt && (hits(R.px, R.py, pad) || hits(ppx, ppy, pad)) && Math.random() < evade.dodge) {
    R.reflexAt = now + 150;
    R.mode = "flee";
    R.think = 0;
    flee(true);
    spend(0.05);
  }

  if (R.mode === "wander") {
    if (R.energy < 0.25) {
      R.mode = "rest";
      R.tx = R.x;
      R.ty = R.y;
    } else if (c < 170) {
      startEncounter(now);
    } else if (now >= R.nextAt) {
      wander();
      spring(1.5 * (0.6 + 0.4 * R.energy), 1);
      hop(0.3); // 가끔 살짝 뛰어 생기를 준다
      R.nextAt = now + 4500 + Math.random() * 3000;
    }
  } else if (R.mode === "rest") {
    R.tx = R.x;
    R.ty = R.y;
    if (R.energy >= 0.85) {
      R.mode = "wander";
      R.nextAt = now + 400;
    }
  } else if (R.mode === "lazy") {
    R.tx = R.x;
    R.ty = R.y;
    if (now >= R.lazyUntil) {
      R.mode = "wander";
      R.nextAt = now + 600;
    }
  } else if (R.mode === "flee") {
    if (R.think && c < 110) {
      R.think = 0;
      flee(false);
      spend(0.15);
    }
    if (R.think) {
      R.tx = R.x; // 멈칫: 제자리에서 고민
      R.ty = R.y;
      if (now >= R.think) {
        R.think = 0;
        flee(Math.random() < 0.45);
        spend(0.15);
      }
    } else if (arrived() && c < 140) {
      escapeTarget(); // 막다른 곳: 고민하지 말고 바로 다른 곳으로
      spring(4 + 2 * R.energy, 0.72);
    }
    if (c > 240) {
      R.mode = "wander";
      R.nextAt = now + 800;
    }
  }

  const W = WORLDS[R.world];
  if (W.floor) {
    // 지구·달: 중력으로 떨어지고, 바닥에 닿으면 멈춘다. 가로 방향만 스프링으로 걷는다.
    R.vy += W.g * dt;
    R.y += R.vy * dt;
    const F = groundY();
    if (R.y >= F) {
      R.y = F;
      R.vy = R.vy > 120 ? -R.vy * 0.2 : 0; // 세게 떨어지면 살짝 튕긴다
    }
    if (R.y < 0) { R.y = 0; R.vy = 0; }
    R.onFloor = R.y >= F - 0.5 && R.vy === 0;
    const ax = R.w * R.w * (R.tx - R.x) - 2 * R.z * R.w * R.vx;
    R.vx += ax * dt;
    const vx = Math.abs(R.vx);
    if (vx > R.cap) R.vx *= R.cap / vx;
    R.x += R.vx * dt;
  } else {
    // 우주: 중력 없이 2차원으로 떠다닌다. 목표에 가까워질수록 감쇠를 키워 미끄러지듯 멈춘다.
    const gap = Math.hypot(R.tx - R.x, R.ty - R.y);
    const near = clamp(1 - gap / 120, 0, 1);
    const z = R.z + (1 - R.z) * near * 0.85;
    const ax = R.w * R.w * (R.tx - R.x) - 2 * z * R.w * R.vx;
    const ay = R.w * R.w * (R.ty - R.y) - 2 * z * R.w * R.vy;
    R.vx += ax * dt;
    R.vy += ay * dt;
    const v = Math.hypot(R.vx, R.vy);
    if (v > R.cap) {
      R.vx *= R.cap / v;
      R.vy *= R.cap / v;
    }
    R.x += R.vx * dt;
    R.y += R.vy * dt;
    if (R.y < 0) { R.y = 0; R.vy = 0; } else if (R.y > my()) { R.y = my(); R.vy = 0; }
  }
  const X = mx();
  if (R.x < 0) { R.x = 0; R.vx = 0; } else if (R.x > X) { R.x = X; R.vx = 0; }
  barEl().style.transform = `translate3d(${R.x.toFixed(1)}px, ${R.y.toFixed(1)}px, 0)`;
  requestAnimationFrame(frame);
}

// 마우스 속도 추적 (마우스만 대상으로 한다. 터치는 피하지 않음)
document.addEventListener("pointermove", (e) => {
  if (e.pointerType !== "mouse") return;
  const t = performance.now();
  const nx = e.clientX;
  const ny = e.clientY;
  if (R.pt) {
    const dt = Math.max(0.008, (t - R.pt) / 1000);
    R.pvx = clamp(R.pvx * 0.5 + ((nx - R.px) / dt) * 0.5, -2000, 2000);
    R.pvy = clamp(R.pvy * 0.5 + ((ny - R.py) / dt) * 0.5, -2000, 2000);
  }
  R.px = nx;
  R.py = ny;
  R.pt = t;
});
window.addEventListener("mouseout", (e) => {
  if (e.relatedTarget) return;
  R.px = -1e4; R.py = -1e4; R.pvx = 0; R.pvy = 0; R.pt = 0;
});

// 세계(배경) 바꾸기. 지구·달은 떨어져서 바닥에 선다. 우주는 떠 있던 자리에서 그대로 떠다닌다.
function setWorld(w) {
  if (!WORLDS[w]) return;
  R.world = w;
  world = w;
  try { localStorage.setItem("world", w); } catch (e) {}
  document.body.classList.remove("world-earth", "world-moon", "world-space", "dark");
  document.body.classList.add(`world-${w}`);
  document.querySelectorAll("#worldPick button").forEach((b) => b.classList.toggle("on", b.dataset.w === w));
  R.vy = 0;
  R.onFloor = false;
  R.mode = "wander";
  R.think = 0;
  R.tx = R.x;
  R.ty = R.y;
  R.nextAt = performance.now() + 600;
}

// 시작 위치: 지구·달은 바닥 가운데, 우주는 화면 가운데
function startBar() {
  setWorld(world);
  R.x = (innerWidth - bw()) / 2;
  R.y = inGround() ? groundY() : innerHeight / 2;
  R.onFloor = inGround();
  R.tx = R.x;
  R.ty = R.y;
  barEl().style.transform = `translate3d(${R.x.toFixed(1)}px, ${R.y.toFixed(1)}px, 0)`;
  paintLoaderPause();
  if (reduceMotion) return; // 움직임을 줄이기로 한 사용자는 가만히 둔다
  R.nextAt = performance.now() + 800;
  if (!LOADER_PAUSED) startLoop();
}
window.addEventListener("resize", () => {
  R.x = clamp(R.x, 0, mx());
  R.tx = clamp(R.tx, 0, mx());
  if (inGround()) { R.y = groundY(); R.ty = groundY(); }
  else { R.y = clamp(R.y, 0, my()); R.ty = clamp(R.ty, 0, my()); }
});
document.querySelectorAll("#worldPick button").forEach((b) => b.addEventListener("click", () => setWorld(b.dataset.w)));
setTimeout(startBar, 0);

// 원본 PDF에서 잘라 둔 그림. 웹 서버(3000) 기준 상대 경로로 불러온다.
// 원본 PDF 쪽·그림은 왼쪽 패널에 16:9 칸으로 보여 주고, 문제 카드는 오른쪽에 둔다
// 정답 글자 자리는 블러로 가린다. 켜고 끄는 상태는 이 브라우저에만 기억한다.
let blurOn = (() => { try { return localStorage.getItem("blurOn") !== "0"; } catch { return true; } })();
function paintBlur() {
  $("pageView").classList.toggle("unblur", !blurOn);
  $("blurToggle").textContent = blurOn ? "블러 끄기" : "블러 켜기";
}
$("blurToggle").onclick = () => {
  blurOn = !blurOn;
  try { localStorage.setItem("blurOn", blurOn ? "1" : "0"); } catch {}
  paintBlur();
};

function showFigures(list, blur = {}) {
  const box = $("figures");
  box.textContent = "";
  $("pageView").hidden = !list.length;
  $("main").classList.toggle("wide", list.length > 0);
  paintBlur();
  for (const src of list) {
    const frame = document.createElement("div");
    frame.className = "page-frame";
    const img = document.createElement("img");
    img.src = src;
    img.alt = "문제 그림";
    img.loading = "lazy";
    frame.append(img);
    for (const [x0, y0, x1, y1] of blur[src] || []) {
      const spot = document.createElement("div");
      spot.className = "ans-blur";
      spot.style.left = `${x0 * 100}%`;
      spot.style.top = `${y0 * 100}%`;
      spot.style.width = `${(x1 - x0) * 100}%`;
      spot.style.height = `${(y1 - y0) * 100}%`;
      frame.append(spot);
    }
    box.append(frame);
  }
}

// ---- 화면 상태 ----
function resetView(keepPos) {
  setAnswering(false);
  $("revealBox").hidden = true;
  $("answerIn").value = "";
  setStatus("");
  closeSheet();
  if (!keepPos) setCardX(0, false);
}

function setAnswering(on) {
  answering = on;
  $("answerBox").hidden = !on;
  $("answerOpen").hidden = on;
  $("hint").hidden = on;
  if (on) $("answerIn").focus();
}

function setCardX(x, animate) {
  if (animate) animateCard(x, 300, EASE_OUT);
  else paint(x);
}

// ---- 객관식 ----
function paintChoices(d) {
  const box = $("choices");
  box.textContent = "";
  const mc = qMode === "mc" && Array.isArray(d.choices);
  box.hidden = !mc;
  $("answerOpen").hidden = mc;
  if (!mc) return;
  d.choices.forEach((text, i) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "choice";
    b.textContent = `${"①②③④"[i]}  ${text}`;
    b.onclick = (e) => {
      e.currentTarget.blur();
      pickChoice(d.n, i);
    };
    box.append(b);
  });
}

async function pickChoice(n, i) {
  if (!cur || cur.n !== n) return;
  const btns = [...$("choices").children];
  if (btns.some((b) => b.disabled)) return; // 이미 고른 문제
  btns.forEach((b) => { b.disabled = true; });
  setStatus("채점 중…");
  let r;
  try {
    r = await api("/api/choice", { n, pick: i });
  } catch (e) {
    btns.forEach((b) => { b.disabled = false; });
    setStatus(e.message);
    return;
  }
  if (n !== cur.n) return;
  setStatus("");
  btns.forEach((b, k) => {
    if (k === r.correct_index) b.classList.add("right");
    else if (k === i) b.classList.add("wrong");
  });
  btns[i].classList.add("pick");
  markSolved(n, r.verdict);
  renderSheet({
    verdict: r.verdict,
    sections: r.solution ? [{ title: "해설", body: r.solution }] : [],
    answer: r.answer,
  });
  openSheet();
}

// 모드 전환: 지금 보던 문제는 유지하고 목록만 바꾼다
function setQMode(m) {
  const cn = cur ? cur.n : null;
  if (reviewOn) exitReview();
  qMode = m;
  localStorage.setItem("qMode", m);
  list = m === "mc" ? allList.filter((x) => x.mc) : allList;
  if (!list.length) {
    qMode = "sub";
    list = allList;
    setStatus("객관식으로 풀 수 있는 문제가 없습니다.");
  }
  const at = cn == null ? -1 : list.findIndex((x) => x.n === cn);
  idx = at >= 0 ? at : 0;
  paintModeBtn();
  gen++;
  pendingSteps = 0;
  stopCardAnim();
  run(showReturn);
}
function paintModeBtn() {
  $("modeBtn").textContent = qMode === "mc" ? "객관식" : "주관식";
}
$("modeBtn").onclick = (e) => {
  e.currentTarget.blur();
  setQMode(qMode === "mc" ? "sub" : "mc");
};
paintModeBtn();

// ---- 스와이프 동작 ----
// 왼쪽으로 밀기 = 패스(다음 문제), 오른쪽으로 밀기 = 정답 보기(채점 없이 답을 바로 보여 줌)
function openAnswer() {
  if (!cur || qMode === "mc") return;
  if (isTeacher()) {
    $("reveal").textContent = cur.answer;
    $("revealNote").textContent = cur.answer_note || "";
    $("revealNote").hidden = !cur.answer_note;
    $("fix").hidden = !cur.answer_fix;
    $("fixText").textContent = cur.answer_fix || "";
    $("revealBox").hidden = false;
    $("answerOpen").hidden = true;
    markSolved(cur.n, "reveal");
    return;
  }
  revealAnswer();
}

// 주관식: 답을 직접 쓰지 않고 정답·풀이를 바로 보여 준다 (채점 없음)
async function revealAnswer() {
  const n = cur.n;
  const r = await api("/api/reveal", { n });
  if (n !== cur.n) return null;
  $("reveal").textContent = r.answer;
  $("revealNote").textContent = r.solution ? `풀이: ${r.solution}` : "";
  $("revealNote").hidden = !r.solution;
  $("fix").hidden = true;
  $("revealBox").hidden = false;
  $("answerOpen").hidden = true;
  markSolved(n, "reveal");
  return r;
}

// ---- 스와이프: 손가락을 따라가고, 놓을 때 속도로 넘길지 정한다 ----
// 모든 움직임은 transform만 쓰고 Web Animations API로 돌려 합성 단계(60fps)에서 처리한다.
const MOTION = matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 1;
const EASE_OUT = "cubic-bezier(.2,.8,.2,1)";
const EASE_SPRING = "cubic-bezier(.3,1.25,.5,1)"; // 살짝 넘쳤다 돌아오는 느낌
const EASE_EXIT = "cubic-bezier(.4,0,.9,.5)";      // 손을 떠나며 가속해서 빠져나간다
const EASE_ENTER = "cubic-bezier(.16,.84,.3,1)";   // 들어올 때는 부드럽게 감속해서 자리 잡는다
const card = $("card");
let lastShown = 0;   // 지금 화면에 보이는 가로 위치
let paintRaf = 0;
let pendingX = 0;
let samples = [];
let gen = 0;         // 진행 중인 넘김을 끊기 위한 세대 번호

const xform = (x) => `translate3d(${x.toFixed(1)}px,0,0)`;

function paint(x, op = 1) {
  lastShown = x;
  card.style.transform = xform(x);
  card.style.opacity = op;
}
// 손가락 이벤트는 프레임당 한 번만 그린다
function queuePaint(x) {
  pendingX = x;
  if (!paintRaf) paintRaf = requestAnimationFrame(() => { paintRaf = 0; paint(pendingX); });
}
// 진행 중인 애니메이션을 멈추고, 지금 보이는 위치에서 이어 간다 (중간에 잡아도 튀지 않는다)
function stopCardAnim() {
  const anims = card.getAnimations();
  if (!anims.length) return;
  anims.forEach((a) => { try { a.commitStyles(); } catch (e) {} a.cancel(); });
  const cs = getComputedStyle(card);
  lastShown = new DOMMatrixReadOnly(cs.transform).m41;
  card.style.transform = xform(lastShown);
  card.style.opacity = cs.opacity;
}
// opts.from: 시작 위치(없으면 지금 위치), opts.fromOp/toOp: 투명도 시작·끝
function animateCard(to, ms, ease, opts = {}) {
  const from = opts.from ?? lastShown;
  const fromOp = opts.fromOp ?? 1;
  const toOp = opts.toOp ?? 1;
  const a = card.animate(
    [
      { transform: xform(from), opacity: fromOp },
      { transform: xform(to), opacity: toOp },
    ],
    { duration: ms * MOTION, easing: ease }
  );
  return a.finished.then(() => { paint(to, toOp); a.cancel(); }).catch(() => {});
}

// 최근 100ms 동안의 손가락 속도 (px/ms)
function flickVelocity() {
  if (samples.length < 2) return 0;
  const last = samples[samples.length - 1];
  const recent = samples.filter((p) => last.t - p.t < 100);
  const a = recent[0];
  return (last.x - a.x) / Math.max(1, last.t - a.t);
}

// ---- 문제 데이터 캐시 · 미리 받기 ----
const qcache = new Map(); // 문항 번호 -> 문제 데이터
async function getQ(n) {
  if (qcache.has(n)) return qcache.get(n);
  const d = await api(`/api/questions/${n}`);
  qcache.set(n, d);
  return d;
}
// 현재 문제 앞뒤 2개씩을 미리 받아 두면, 빠르게 넘겨도 기다리지 않는다
function prefetchAround() {
  for (const k of [-2, -1, 1, 2]) {
    const j = idx + k;
    if (j >= 0 && j < list.length) getQ(list[j].n).catch(() => {});
  }
}

// ---- 넘김: 키 입력을 쌓아 두었다가, 한 번에 한 번씩 처리한다 ----
let pendingSteps = 0;   // 아직 처리하지 않은 이동 칸 수 (+는 다음, -는 이전)
let pendingKey = false; // 대기 중인 넘김이 키보드에서 왔는지 (키보드는 가로로 밀린다)
let stepping = false;   // 지금 넘김을 처리하는 중인지
let enterRunning = false;
let pressTimes = [];

// 최근 0.7초 안의 키 입력 수에 따라 애니메이션을 짧게 한다 (빨리 누를수록 짧게)
function speedFactor() {
  const now = performance.now();
  pressTimes = pressTimes.filter((t) => now - t < 700);
  pressTimes.push(now);
  const n = pressTimes.length;
  return n >= 5 ? 0.35 : n >= 3 ? 0.6 : 1;
}

async function moveBy(d, keyMode = false) {
  const my = gen;
  const W = innerWidth;
  const dir = Math.sign(d);
  const target = clamp(idx + d, 0, list.length - 1);
  if (target === idx) {
    animateCard(0, 380, EASE_SPRING);
    setStatus(dir < 0 ? "첫 문제입니다." : "마지막 문제입니다.");
    return;
  }
  const k = speedFactor();
  document.documentElement.style.setProperty("--pile-ms", `${Math.round(500 * k)}ms`);
  const fetched = getQ(list[target].n);
  fetched.catch(() => {});
  const leavingSolved = isSolved(cur.n);
  // 키보드: 다음(→)은 카드가 오른쪽으로 빠지고 새 카드가 왼쪽에서 들어온다. 이전(←)은 반대.
  // 푼 문제는 항상 자기 더미로 내려간다.
  const sideSlide = keyMode && !leavingSolved;
  const useNext = !keyMode && dir > 0 && target === idx + 1; // 스와이프 다음 문제는 뒤 층에서 바로 올라온다
  const jobs = [];
  if (useNext) jobs.push(riseNext(300 * k));
  if (sideSlide) jobs.push(animateCard(dir * W, 300 * k, EASE_EXIT, { toOp: 0.2 }));
  else jobs.push(leavingSolved ? tuckToPile(300 * k) : exitBack(300 * k));
  await Promise.all(jobs);
  let data;
  try {
    data = await fetched;
  } catch (e) {
    animateCard(0, 380, EASE_OUT);
    throw e;
  }
  if (my !== gen) return;
  idx = target;
  resetView(true);
  renderCur(data);
  prefetchAround();
  updateNext();
  renderPile();
  if (sideSlide) {
    // 새 카드는 반대쪽에서 들어온다
    paint(-dir * W, 0);
    enterRunning = true;
    animateCard(0, 520 * k, EASE_ENTER, { fromOp: 0, toOp: 1 }).then(() => { enterRunning = false; });
  } else if (useNext) {
    paint(0, 1);
  } else {
    enterRunning = true;
    enterBack(520 * k).then(() => { enterRunning = false; });
  }
}

async function runSteps() {
  if (stepping) return;
  stepping = true;
  try {
    while (pendingSteps !== 0) {
      const d = pendingSteps;
      const km = pendingKey;
      pendingSteps = 0;
      pendingKey = false;
      await moveBy(d, km);
    }
  } finally {
    stepping = false;
  }
}

function move(step, keyMode = false) {
  if (!cur) return;
  // 들어오는 중이면 바로 끊고 다음 넘김을 시작한다
  if (enterRunning) stopCardAnim();
  pendingSteps += step;
  if (keyMode) pendingKey = true;
  runSteps().catch(() => {});
}

const DRAG_START = 6; // 이 거리보다 적게 움직이면 탭으로 본다
card.addEventListener("pointerdown", (e) => {
  if (answering || e.button !== 0 || !cur) return;
  if (e.target.closest("button, textarea, input, select")) return;
  gen++;
  pendingSteps = 0;
  stopCardAnim();
  dragging = true;
  startX = e.clientX;
  dx = 0;
  samples = [{ x: e.clientX, t: e.timeStamp }];
  card.setPointerCapture(e.pointerId);
});
card.addEventListener("pointermove", (e) => {
  if (!dragging) return;
  dx = e.clientX - startX;
  samples.push({ x: e.clientX, t: e.timeStamp });
  if (samples.length > 10) samples.shift();
  const nextSide = dx > 0;
  const edge = nextSide ? idx >= list.length - 1 : idx <= 0;
  // 끝 문제에서 더 밀면 고무줄처럼 조금만 따라온다
  queuePaint(edge ? dx * 0.28 : dx);
  if (dx > DRAG_OK) setRingHint("놓으면 다음 문제");
  else if (dx < -DRAG_OK) setRingHint("놓으면 이전 문제");
  else setRingHint(null);
});
function endDrag() {
  dragging = false;
  setRingHint(null);
}
card.addEventListener("pointerup", () => {
  if (!dragging) return;
  endDrag();
  if (Math.abs(dx) < DRAG_START) {
    animateCard(0, 260, EASE_OUT);
    return;
  }
  // 손을 놓을 때의 속도를 더해서 "던지듯" 넘길지 정한다
  const projected = dx + flickVelocity() * 160;
  const dir = projected > 0 ? 1 : -1;
  const edge = dir > 0 ? idx >= list.length - 1 : idx <= 0;
  if (!edge && Math.abs(projected) > innerWidth * 0.22) run(() => move(dir));
  else animateCard(0, 380, EASE_SPRING);
});
card.addEventListener("pointercancel", () => {
  endDrag();
  animateCard(0, 380, EASE_SPRING);
});

// ---- 채점 ----
async function submit() {
  const ans = $("answerIn").value.trim();
  if (!ans) {
    setStatus("답을 먼저 적어 주세요.");
    return;
  }
  setStatus("채점 중…");
  const n = cur.n;
  const r = await api("/api/grade", { n, answer: ans });
  if (n !== cur.n) return; // 채점 도중 문제가 바뀌었으면 버린다
  setStatus("");
  renderSheet(r);
  markSolved(n, r.verdict);
  setAnswering(false); // 채점 후에는 답 칸을 닫아야 다음 문제로 넘어갈 수 있다
  openSheet();
}

function renderSheet(r) {
  const [label, cls] = VERDICT[r.verdict] || VERDICT.unknown;
  const chip = $("chip");
  chip.textContent = label;
  chip.className = `text-2xl font-bold ${cls}`;

  const box = $("sections");
  box.textContent = "";
  const blocks = [...r.sections];
  if (r.answer) blocks.push({ title: "모범답안", body: r.answer });
  for (const s of blocks) {
    const wrap = document.createElement("div");
    const h = document.createElement("h3");
    h.className = "text-xs font-semibold text-neutral-400";
    h.textContent = s.title;
    const p = document.createElement("p");
    p.className = "mt-1 whitespace-pre-wrap break-keep text-[15px] leading-relaxed";
    p.textContent = s.body.replace(/\*\*/g, "");
    wrap.append(h, p);
    box.append(wrap);
  }
}

// ---- 하단 시트 ----
// 채점 결과(해설)는 문제 카드 안, 답 바로 아래에 펼친다. 닫으면 원래 자리로 돌아간다.
const sheetHomeParent = $("sheet").parentNode;
function openSheet() {
  const sheet = $("sheet");
  card.appendChild(sheet);
  sheet.classList.add("inline", "open");
  $("scrim").classList.remove("show");
}

function closeSheet() {
  const sheet = $("sheet");
  sheet.classList.remove("open", "inline");
  if (sheet.parentNode !== sheetHomeParent) sheetHomeParent.appendChild(sheet);
  $("scrim").classList.remove("show");
}

async function advance() {
  closeSheet();
  if (idx >= list.length - 1) {
    setStatus("마지막 문제입니다.");
    return;
  }
  idx += 1;
  await show();
}

// ---- 연결 ----
$("subject").onchange = () => run(loadList);
$("submit").onclick = () => run(submit);
// Enter = 제출, Shift+Enter = 줄바꿈. 한글 조합 중 Enter는 글자를 확정하는 키이므로 제출하지 않는다.
$("answerIn").addEventListener("keydown", (e) => {
  if (e.key !== "Enter" || e.shiftKey || e.isComposing || e.keyCode === 229) return;
  e.preventDefault();
  run(submit);
});
$("close").onclick = closeSheet;
$("scrim").onclick = closeSheet;
$("next").onclick = () => run(advance);

document.addEventListener("keydown", (e) => {
  const arrow = e.key === "ArrowLeft" || e.key === "ArrowRight";
  if (e.target.matches("textarea, select, input") || (e.target.matches("button") && !arrow) || answering) {
    // 버튼·입력창에 포커스가 없을 때만 Enter 단축키가 동작한다 (답 칸이 열린 상태는 아래 입력창 처리)
    return;
  }
  // Enter: 정답을 바로 보여 준다 (주관식은 채점하지 않는다)
  if (e.key === "Enter" && !e.isComposing && cur) {
    e.preventDefault();
    openAnswer();
    return;
  }
  if (e.key === "ArrowLeft") run(() => move(-1, true));
  if (e.key === "ArrowRight") run(() => move(1, true));
  if (e.key === "Escape") closeSheet();
});

// ---- 정비소 모드 (음성) ----
// 문제는 SpeechSynthesis 로 읽고, 말은 SpeechRecognition 으로 받는다.
// 명령: 다음·이전·N번·정답 말해줘·그만. 그 밖의 말은 답으로 보고 채점해서 결과를 음성으로 알려 준다.
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
let voiceOn = false;
let rec = null;

function speak(text) {
  return new Promise((resolve) => {
    if (!("speechSynthesis" in window) || !text) return resolve();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = "ko-KR";
    u.onend = resolve;
    u.onerror = resolve;
    speechSynthesis.cancel();
    speechSynthesis.speak(u);
  });
}

function listen() {
  return new Promise((resolve, reject) => {
    rec = new SR();
    rec.lang = "ko-KR";
    rec.interimResults = false;
    rec.maxAlternatives = 1;
    let got = "";
    rec.onresult = (e) => {
      got = e.results[0][0].transcript;
    };
    rec.onerror = (e) => {
      const err = new Error(`음성 인식 오류: ${e.error}`);
      err.code = e.error;
      reject(err);
    };
    rec.onend = () => resolve(got.trim());
    rec.start();
  });
}

function updateVoiceBtn() {
  $("voice").textContent = voiceOn ? "정비소 모드 끄기" : "정비소 모드 켜 줘";
}

async function moveTo(i) {
  if (i < 0 || i >= list.length) return false;
  idx = i;
  await show();
  return true;
}

// 말한 내용을 명령으로 처리한다. read: 다음에 문제를 다시 읽을지
async function voiceCommand(said) {
  const t = said.replace(/\s+/g, "");
  if (/^(그만|종료|끝)/.test(t)) {
    voiceOn = false;
    await speak("정비소 모드를 끕니다.");
    return { read: false };
  }
  if (/^(다음|패스|넘겨)/.test(t)) {
    if (await moveTo(idx + 1)) return { read: true };
    await speak("마지막 문제입니다.");
    return { read: false };
  }
  if (/^이전/.test(t)) {
    if (await moveTo(idx - 1)) return { read: true };
    await speak("첫 문제입니다.");
    return { read: false };
  }
  const num = t.match(/^(\d+)번?(문제)?$/);
  if (num) {
    if (await moveTo(Number(num[1]) - 1)) return { read: true };
    await speak(`1번부터 ${list.length}번까지 있습니다.`);
    return { read: false };
  }
  if (t === "정답" || /^정답(알려|말해|보여|읽어)/.test(t)) {
    if (isTeacher()) await speak(cur.answer_fix || cur.answer || "답이 없는 문항입니다.");
    else {
      const r = await revealAnswer();
      await speak(r ? `정답. ${r.answer}` : "정답을 불러오지 못했습니다.");
    }
    return { read: false };
  }

  // 주관식은 말한 내용을 채점하지 않는다
  if (qMode !== "mc") {
    await speak("주관식은 채점하지 않습니다. 정답이라고 말하면 답을 보여 드립니다.");
    return { read: false };
  }
  // 그 밖의 말은 답으로 보고 채점한다 (객관식 모드)
  setStatus("채점 중…");
  const n = cur.n;
  const r = await api("/api/grade", { n, answer: said });
  if (n !== cur.n) return { read: false };
  setStatus("다음이라고 말하면 넘어갑니다.");
  renderSheet(r);
  markSolved(n, r.verdict);
  setAnswering(false); // 채점 후에는 답 칸을 닫아야 다음 문제로 넘어갈 수 있다
  openSheet();
  const label = (VERDICT[r.verdict] || VERDICT.unknown)[0];
  const clean = (s) => s.replace(/[*#]/g, "");
  const body = clean(r.sections.map((s) => s.body).join(" "));
  await speak(`${label}. 모범답안. ${clean(r.answer)}. 해설. ${body}`.slice(0, 400));
  return { read: false };
}

async function voiceLoop() {
  let read = true;
  while (voiceOn) {
    if (!cur) {
      setStatus("문항이 없습니다.");
      break;
    }
    try {
      if (read) {
        await speak(`${idx + 1}번. ${cur.question}`);
        read = false;
      }
      if (!voiceOn) break;
      setStatus("듣는 중… 다음, 이전, 번호, 정답 말해줘, 또는 답을 말하세요");
      const said = await listen();
      if (!voiceOn) break;
      if (!said) {
        setStatus("말씀이 들리지 않았습니다.");
        continue;
      }
      setStatus(`인식: ${said}`);
      read = (await voiceCommand(said)).read;
    } catch (e) {
      if (!voiceOn) break;
      setStatus(e.message);
      if (["not-allowed", "service-not-allowed", "audio-capture", undefined].includes(e.code)) break;
      await sleep(500);
    }
  }
  voiceOn = false;
  updateVoiceBtn();
}

$("voice").onclick = () => {
  if (voiceOn) {
    voiceOn = false;
    if (rec) rec.abort();
    speechSynthesis.cancel();
    updateVoiceBtn();
    setStatus("정비소 모드를 껐습니다.");
    return;
  }
  if (!SR || !("speechSynthesis" in window)) {
    setStatus("이 브라우저는 음성 기능을 지원하지 않습니다. Chrome에서 여세요.");
    return;
  }
  voiceOn = true;
  updateVoiceBtn();
  run(voiceLoop);
};

// API가 아직 시작 중이어도 화면은 바로 뜨고, 준비되면 데이터를 채운다.
async function waitApi() {
  for (let i = 0; i < 300; i++) {
    try {
      await fetch(API + "/api/health");
      return;
    } catch {
      setStatus("서버를 시작하는 중입니다… (첫 실행은 몇 초 걸립니다)");
      await sleep(1000);
    }
  }
  throw new Error("API 서버가 응답하지 않습니다. study_api 서버가 켜져 있는지 확인하세요.");
}

// 문항 번호가 바뀌면 푼 기록의 번호도 새 번호로 옮긴다 (한 번만 실행). 삭제된 문항의 기록은 지운다.
async function migrateSolved() {
  try {
    if (localStorage.getItem("remapV") === "1") return;
    const map = await (await fetch("remap.json", { cache: "no-store" })).json();
    const moved = new Map();
    solvedList.forEach((n) => {
      const to = map[String(n)];
      if (to) moved.set(n, to);
    });
    const nextList = [];
    const nextV = {};
    solvedList.forEach((n) => {
      const to = moved.get(n);
      if (!to || nextList.includes(to)) return;
      nextList.push(to);
      if (solvedV[n]) nextV[to] = solvedV[n];
    });
    solvedList = nextList;
    solvedV = nextV;
    localStorage.setItem("solvedQ", JSON.stringify(solvedList));
    localStorage.setItem("solvedV", JSON.stringify(solvedV));
    localStorage.setItem("remapV", "1");
  } catch (e) {
    setStatus(`이전 진도 옮기기 실패(다음에 다시 시도합니다): ${e.message}`);
  }
}

// 진도는 문항 번호가 아니라 문항 uid(내용 해시)로 저장한다. 문제 은행을 다시 만들어도 같은 문제의 기록이 유지된다.
let uidOf = {};      // 번호 -> uid
let nOfUid = {};     // uid -> 번호
let uidReady = false; // 문항 목록을 받아 uid 를 알게 된 뒤에만 저장한다 (빈 값으로 덮어쓰지 않게)

function saveProgress() {
  if (!uidReady) return;
  localStorage.setItem("solvedU", JSON.stringify(solvedList.map((n) => uidOf[n]).filter(Boolean)));
  const v = {};
  solvedList.forEach((n) => { if (uidOf[n] && solvedV[n]) v[uidOf[n]] = solvedV[n]; });
  localStorage.setItem("solvedUV", JSON.stringify(v));
}

async function loadProgress() {
  const all = await api("/api/questions");
  uidOf = {};
  nOfUid = {};
  all.forEach((x) => { if (x.uid) { uidOf[x.n] = x.uid; nOfUid[x.uid] = x.n; } });
  uidReady = true;
  let lost = 0;
  if (localStorage.getItem("uidV") !== "1") {
    // 처음 한 번: 지금 메모리에 있는 번호 기준 기록(migrateSolved 로 새 번호에 맞춰진 값)을 uid 로 옮긴다
    lost = solvedList.filter((n) => !uidOf[n]).length;
    solvedList = solvedList.filter((n) => uidOf[n]);
    Object.keys(solvedV).forEach((n) => { if (!uidOf[n]) delete solvedV[n]; });
    saveProgress();
    localStorage.setItem("uidV", "1");
  } else {
    const us = JSON.parse(localStorage.getItem("solvedU") || "[]");
    const uv = JSON.parse(localStorage.getItem("solvedUV") || "{}");
    const ns = us.map((u) => nOfUid[u]).filter(Number.isInteger);
    lost = us.length - ns.length;
    solvedList = ns;
    solvedV = {};
    Object.entries(uv).forEach(([u, v]) => { if (nOfUid[u]) solvedV[nOfUid[u]] = v; });
  }
  if (lost) setStatus(`문제 은행이 바뀌어 푼 기록 ${lost}개를 옮기지 못했습니다.`);
  renderPile(null);
}

run(async () => {
  await waitApi();
  await migrateSolved();
  await loadProgress();
  setStatus("");
  await loadSubjects();
  await loadList();
});


// ---- 문제 목록: 골라서 바로 풀기 ----
// list 는 현재 과목의 문항 목록이다. 항목을 누르면 그 문제로 이동해 카드에서 바로 푼다.
// 목록은 기본으로 지금 보고 있는 단원(과목·세트)만 보여 준다. 버튼으로 전체 보기와 바꾼다.
let listUnitOnly = true;
function currentUnit() {
  const x = list[idx];
  return x ? { subject: x.subject, set: x.set } : null;
}
function renderList() {
  const body = $("listBody");
  const q = $("listSearch").value.trim();
  const unit = listUnitOnly ? currentUnit() : null;
  $("listScope").textContent = unit ? `단원: ${unit.subject} ${unit.set}` : "전체 문제";
  $("listScopeBtn").textContent = unit ? "전체 보기" : "이 단원만 보기";
  body.textContent = "";
  // 큰 분류(과목) > 작은 분류(세트) 순으로 접었다 펼친다. 검색 중에는 모두 펼친다.
  const groups = new Map();
  list.forEach((x, i) => {
    if (unit && (x.subject !== unit.subject || x.set !== unit.set)) return;
    if (q && !(x.q || "").includes(q)) return;
    if (!groups.has(x.subject)) groups.set(x.subject, new Map());
    const sets = groups.get(x.subject);
    if (!sets.has(x.set)) sets.set(x.set, []);
    sets.get(x.set).push({ x, i });
  });
  if (!groups.size) {
    const e = document.createElement("p");
    e.className = "mt-6 text-center text-sm text-neutral-500";
    e.textContent = list.length ? "검색 결과가 없습니다." : "문항이 없습니다.";
    body.append(e);
    return;
  }
  const folder = (summaryText, count, open) => {
    const d = document.createElement("details");
    d.className = "mb-2";
    d.open = open;
    const sm = document.createElement("summary");
    sm.className = "flex cursor-pointer select-none items-center justify-between rounded-2xl bg-white px-4 py-3 text-sm font-semibold shadow-sm";
    const name = document.createElement("span");
    name.textContent = summaryText;
    const cnt = document.createElement("span");
    cnt.className = "text-xs font-normal tabular-nums text-neutral-400";
    cnt.textContent = `${count}문항`;
    sm.append(name, cnt);
    d.append(sm);
    return d;
  };
  for (const [subject, sets] of groups) {
    const total = [...sets.values()].reduce((a, v) => a + v.length, 0);
    const big = folder(subject, total, !!q);
    big.classList.add("mt-4");
    const inner = document.createElement("div");
    inner.className = "mt-2 pl-2";
    for (const [setName, items] of sets) {
      const small = folder(setName, items.length, !!q);
      small.classList.add("mb-1");
      const wrap = document.createElement("div");
      wrap.className = "mt-2 pl-1";
      for (const { x, i } of items) {
        const b = document.createElement("button");
        b.className = "mb-2 flex w-full items-start gap-3 rounded-2xl bg-white px-4 py-3 text-left shadow-sm active:scale-[.99]";
        const num = document.createElement("span");
        num.className = "shrink-0 tabular-nums text-sm font-bold text-neutral-500";
        num.textContent = `${x.no ?? i + 1}번`;
        const t = document.createElement("span");
        t.className = "break-keep text-sm leading-relaxed";
        t.textContent = x.q || "(문항)";
        b.append(num, t);
        b.onclick = () => {
          idx = i;
          closeList();
          run(showReturn);
        };
        wrap.append(b);
      }
      small.append(wrap);
      inner.append(small);
    }
    big.append(inner);
    body.append(big);
  }
}

$("listScopeBtn").onclick = () => {
  listUnitOnly = !listUnitOnly;
  renderList();
};

function openList() {
  listUnitOnly = true;
  $("listSearch").value = "";
  renderList();
  $("listPanel").hidden = false;
  $("listPanel").scrollTop = 0;
}

function closeList() {
  $("listPanel").hidden = true;
}

$("listBtn").onclick = openList;
$("listClose").onclick = closeList;
$("listSearch").addEventListener("input", renderList);

$("answerOpen").onclick = () => openAnswer();

// ---- 도트 매트릭스 시계 (왼쪽 위, 카시오 점자 스타일) ----
// 5x7 점 글꼴. 1 = 켜진 점
const DOT_FONT = {
  "0": ["01110","10001","10011","10101","11001","10001","01110"],
  "1": ["00100","01100","00100","00100","00100","00100","01110"],
  "2": ["01110","10001","00001","00010","00100","01000","11111"],
  "3": ["11111","00010","00100","00010","00001","10001","01110"],
  "4": ["00010","00110","01010","10010","11111","00010","00010"],
  "5": ["11111","10000","11110","00001","00001","10001","01110"],
  "6": ["00110","01000","10000","11110","10001","10001","01110"],
  "7": ["11111","00001","00010","00100","01000","01000","01000"],
  "8": ["01110","10001","10001","01110","10001","10001","01110"],
  "9": ["01110","10001","10001","01111","00001","00010","01100"],
  ":": ["00000","00100","00100","00000","00100","00100","00000"],
};
const pad2 = (n) => String(n).padStart(2, "0");
const DOT_ON = "#1040E8";
const DOT_OFF = "#B4C4D6";
const clockCells = []; // 글자 하나당 점 35개
let clockLast = "";
function buildClock() {
  const root = $("clockDots");
  root.textContent = "";
  for (let i = 0; i < 8; i++) {
    const g = document.createElement("div");
    g.className = "grid grid-cols-5 gap-[3px]";
    const cells = [];
    for (let k = 0; k < 35; k++) {
      const d = document.createElement("span");
      d.className = "h-[4px] w-[4px] rounded-full";
      g.append(d);
      cells.push(d);
    }
    root.append(g);
    clockCells.push(cells);
  }
}
function paintClock() {
  const t = new Date();
  const str = `${pad2(t.getHours())}:${pad2(t.getMinutes())}:${pad2(t.getSeconds())}`;
  if (str === clockLast) return;
  clockLast = str;
  for (let i = 0; i < 8; i++) {
    const rows = DOT_FONT[str[i]];
    for (let r = 0; r < 7; r++) {
      for (let c = 0; c < 5; c++) {
        clockCells[i][r * 5 + c].style.background = rows[r][c] === "1" ? DOT_ON : DOT_OFF;
      }
    }
  }
  $("clockDate").textContent = `${t.getFullYear()}.${pad2(t.getMonth() + 1)}.${pad2(t.getDate())}`;
}
buildClock();
paintClock();
setInterval(paintClock, 250);

// 목록에서 문제를 골라 돌아올 때: 아래에서 천천히 올라오며 선명해진다
async function showReturn() {
  await show();
  card.animate(
    [
      { transform: BACK_T, opacity: 0 },
      { transform: "translate3d(0,0,0)", opacity: 1 },
    ],
    { duration: 480 * MOTION, easing: EASE_ENTER }
  );
}

// ---- 덱: 뒤 카드, 푼 문제 더미 ----
const cardNextEl = () => $("cardNext");
// 다음 문제를 뒤 층에 놓는다 (목록 정보만으로 미리 보여 준다)
function updateNext() {
  const el = cardNextEl();
  el.getAnimations().forEach((a) => a.cancel());
  const nx = list[idx + 1];
  if (!nx) {
    el.style.opacity = "0";
    return;
  }
  $("nextSet").textContent = `${nx.subject} ${nx.set}`;
  $("nextQ").textContent = nx.q || "";
  el.style.transform = "translate3d(0,14px,0) scale(.96)";
  el.style.opacity = ".85";
}
// 뒤 카드가 앞으로 올라오는 움직임 (교체 뒤 updateNext가 정리한다)
function riseNext(ms) {
  if (!list[idx + 1]) return Promise.resolve();
  return cardNextEl().animate(
    [
      { transform: "translate3d(0,14px,0) scale(.96)", opacity: 0.85 },
      { transform: "translate3d(0,0,0) scale(1)", opacity: 1 },
    ],
    { duration: ms * MOTION, easing: EASE_SPRING, fill: "forwards" }
  ).finished.catch(() => {});
}
// 푼 카드는 자기 더미(맞음/틀림)의 자기 종이 자리로 가라앉는다
function tuckToPile(ms) {
  const cr = card.getBoundingClientRect();
  const cx = cr.left + cr.width / 2 - lastShown;
  const cy = cr.top + cr.height / 2;
  const side = $(PILE_EL[sideOf(cur.n)]);
  const target = side.querySelector(`:scope > div[data-n="${cur.n}"]`) || side;
  const r = target.getBoundingClientRect();
  const dx = r.left + r.width / 2 - cx;
  const dy = r.top + r.height / 2 - cy;
  const a = card.animate(
    [
      { transform: xform(lastShown), opacity: 1 },
      { transform: `translate3d(${dx.toFixed(1)}px,${dy.toFixed(1)}px,0) scale(.92)`, opacity: 0.1 },
    ],
    { duration: ms * MOTION, easing: EASE_EXIT, fill: "forwards" }
  );
  return a.finished.then(() => {
    card.style.opacity = "0";
    a.cancel();
    if (target !== side) target.animate([{ scale: "1" }, { scale: "0.96", offset: 0.4 }, { scale: "1" }], { duration: 280 * MOTION, easing: EASE_OUT });
  }).catch(() => {});
}

// 푼 문제 목록. 맞은 문제는 오른쪽 더미, 나머지(틀림·부분정답·미확인)는 왼쪽 더미에 쌓는다.
// 브라우저에 저장해서 다음에 열어도 남는다.
let solvedList = [];
try {
  const v = JSON.parse(localStorage.getItem("solvedQ") || "[]");
  if (Array.isArray(v)) solvedList = v.filter(Number.isInteger);
} catch (e) {}
let solvedV = {};
try {
  const v = JSON.parse(localStorage.getItem("solvedV") || "{}");
  if (v && typeof v === "object" && !Array.isArray(v)) solvedV = v;
} catch (e) {}
const isSolved = (n) => solvedList.includes(n);
const sideOf = (n) => (solvedV[n] === "correct" ? "right" : "left");
const PILE_EL = { right: "pileRight", left: "pileWrong" };
const paperTilt = (n) => ((n * 37) % 7 - 3) * 0.5; // 종이마다 고정된 살짝 다른 기울기

function markSolved(n, verdict) {
  const first = !isSolved(n);
  if (first) {
    solvedList.push(n);
    bumpToday();
  }
  // 정답 보기(reveal)는 이미 채점된 결과를 덮어쓰지 않는다
  if (verdict || !solvedV[n]) solvedV[n] = verdict || "unknown";
  try {
    saveProgress();
  } catch (e) {
    setStatus(`진도를 저장하지 못했습니다: ${e.message}`);
  }
  renderPile(first ? n : null);
}

function pileLabel(n) {
  const li = list.find((x) => x.n === n);
  return li ? `${li.set} ${li.no ?? n}번` : `${n}번`;
}

// 새로 쌓인 종이는 방금 푼 카드 자리에서 날아와 살짝 내려앉는다
function landPaper(d) {
  const cr = card.getBoundingClientRect();
  const r = d.getBoundingClientRect();
  const dx = cr.left + cr.width / 2 - (r.left + r.width / 2);
  const dy = cr.top + cr.height / 2 - (r.top + r.height / 2);
  d.animate(
    [
      { transform: `translate3d(${dx.toFixed(1)}px,${dy.toFixed(1)}px,0) rotate(-4deg) scale(.94)`, opacity: 0.2 },
      { opacity: 1 },
    ],
    { duration: 560 * MOTION, easing: EASE_SPRING }
  );
  d.animate(
    [{ scale: "1" }, { scale: "0.97", offset: 0.5 }, { scale: "1" }],
    { duration: 300 * MOTION, delay: 500 * MOTION, easing: EASE_OUT }
  );
}

// 한 더미를 그린다. 기존 종이는 그대로 두고 자리만 옮겨서 부드럽게 이동하게 한다.
function paintPile(el, items, fresh) {
  const recent = items.slice(-3); // 오래된 것이 위, 가장 최근 것이 맨 밑 층 (나머지는 숫자로만 센다)
  const keep = new Set(recent);
  el.querySelectorAll(":scope > div").forEach((c) => {
    if (!keep.has(Number(c.dataset.n))) c.remove();
  });
  recent.forEach((n, k) => {
    let d = el.querySelector(`:scope > div[data-n="${n}"]`);
    const isNew = !d;
    if (isNew) {
      d = document.createElement("div");
      d.dataset.n = String(n);
      d.onclick = () => openSolved(n);
      el.append(d);
    }
    d.style.setProperty("--d", String(k));
    d.style.setProperty("--r", `${paperTilt(n)}deg`);
    d.style.setProperty("--j", String((n * 7) % 4));
    d.style.zIndex = String(10 - k);
    const mark = document.createElement("span");
    mark.className = "pm";
    mark.textContent = solvedV[n] === "correct" ? "✓" : "–";
    d.replaceChildren(mark, document.createTextNode(pileLabel(n)));
    if (isNew && n === fresh) landPaper(d);
  });
}

// ---- 복습 모드: 틀린 문제만 원래 순서대로 넘긴다 ----
let reviewOn = false;
let fullList = null; // 복습 중일 때 전체 문항 목록을 잠시 보관한다
function startReview() {
  const all = list;
  const wrong = new Set(solvedList.filter((n) => sideOf(n) === "left"));
  const items = all.filter((x) => wrong.has(x.n));
  if (!items.length) {
    setStatus("틀린 문제가 없습니다.");
    return;
  }
  fullList = all;
  list = items;
  idx = 0;
  reviewOn = true;
  gen++;
  pendingSteps = 0;
  stopCardAnim();
  run(showReturn);
}
function exitReview() {
  if (!reviewOn) return;
  const cn = cur ? cur.n : null;
  reviewOn = false;
  list = fullList;
  fullList = null;
  idx = Math.max(0, list.findIndex((x) => x.n === cn));
}

// 가장자리와 점 진도판: 현재 번호, 방향 버튼, 오늘 푼 수, 단원 점 진도
function paintEdges() {
  const all = fullList || list;
  const cu = cur ? all.find((x) => x.n === cur.n) : null;
  $("bigNoV").textContent = cu ? (cu.no ?? "") : "";
  $("bigNoT").textContent = cu ? `/ ${all.length}` : "";
  const dots = $("dots");
  dots.textContent = "";
  if (!cu) { dots.hidden = true; return; }
  const inUnit = all.filter((x) => x.subject === cu.subject && x.set === cu.set);
  dots.hidden = inUnit.length === 0;
  inUnit.forEach((x) => {
    const d = document.createElement("button");
    d.type = "button";
    d.className = "dot";
    if (isSolved(x.n)) d.classList.add(sideOf(x.n) === "right" ? "ok" : "ng");
    if (x.n === cu.n) d.classList.add("cur");
    d.setAttribute("aria-label", `${x.no ?? ""}번`);
    d.title = `${x.no ?? ""}번`;
    d.onclick = (e) => {
      e.currentTarget.blur();
      openSolved(x.n);
    };
    dots.append(d);
  });
  paintToday();
}
function todayKey() {
  return new Date().toLocaleDateString("sv-SE");
}
function paintToday() {
  let t = { d: "", n: 0 };
  try { t = JSON.parse(localStorage.getItem("todayCnt") || "{}") || t; } catch (e) {}
  const n = t.d === todayKey() ? t.n || 0 : 0;
  $("today").textContent = `오늘 ${n}문제`;
}
function bumpToday() {
  let t = { d: "", n: 0 };
  try { t = JSON.parse(localStorage.getItem("todayCnt") || "{}") || t; } catch (e) {}
  const n = (t.d === todayKey() ? t.n || 0 : 0) + 1;
  try { localStorage.setItem("todayCnt", JSON.stringify({ d: todayKey(), n })); } catch (e) {}
  paintToday();
}

// 세로 게이지: 왼쪽은 지금 단원의 진도, 오른쪽은 전체 정답률
function paintGauges() {
  const all = fullList || list;
  const cu = cur ? all.find((x) => x.n === cur.n) : null;
  if (cu) {
    const inUnit = all.filter((x) => x.subject === cu.subject && x.set === cu.set);
    const done = inUnit.filter((x) => isSolved(x.n)).length;
    const pct = inUnit.length ? (done / inUnit.length) * 100 : 0;
    $("gaugeLFill").style.height = `${pct}%`;
    $("gaugeLTxt").textContent = `${cu.set} ${done}/${inUnit.length}`;
  } else {
    $("gaugeLFill").style.height = "0%";
    $("gaugeLTxt").textContent = "";
  }
  const att = solvedList.length;
  const cor = solvedList.filter((n) => sideOf(n) === "right").length;
  const rp = att ? (cor / att) * 100 : 0;
  $("gaugeRFill").style.height = `${rp}%`;
  $("gaugeRTxt").textContent = att ? `정답률 ${Math.round(rp)}%` : "";
}

function renderPile(fresh = null) {
  const right = solvedList.filter((n) => sideOf(n) === "right");
  const left = solvedList.filter((n) => sideOf(n) === "left");
  // 종이 더미 그림은 그리지 않는다. 개수와 복습 버튼은 아래 글자로만 보여 준다.
  $("pileRightTag").textContent = right.length ? `맞음 ${right.length}` : "";
  $("pileWrongTag").textContent = reviewOn ? "복습 끝내기" : left.length ? `틀림 ${left.length} · 복습` : "";
  $("pile").hidden = solvedList.length === 0;
  paintGauges();
  paintEdges();
}

function openSolved(n) {
  exitReview();
  const i = list.findIndex((x) => x.n === n);
  if (i < 0) {
    setStatus("이 과목 목록에 없는 문제입니다.");
    return;
  }
  gen++;
  pendingSteps = 0;
  stopCardAnim();
  idx = i;
  run(showReturn);
}
// 복습 켜기/끄기 (틀림 표시 버튼과 패널 머리글 버튼이 같이 쓴다)
function toggleReview(e) {
  if (e) { e.stopPropagation(); e.currentTarget.blur(); }
  if (!reviewOn) return startReview();
  exitReview();
  gen++;
  pendingSteps = 0;
  stopCardAnim();
  run(showReturn);
}
$("pileWrongTag").onclick = toggleReview;
$("navPrev").onclick = (e) => { e.currentTarget.blur(); run(() => move(-1, true)); };
$("navNext").onclick = (e) => { e.currentTarget.blur(); run(() => move(1, true)); };
renderPile();

// ---- 뒤로 가기: 카드는 옆이 아니라 뒤(위쪽으로 살짝 올라가고 작아지며 흐려짐)로 물러난다 ----
const BACK_T = "translate3d(0,-22px,0) scale(.92)";
// 나갈 때: 뒤 층으로 물러나며 흐려진다
function exitBack(ms) {
  const a = card.animate(
    [
      { transform: xform(lastShown), opacity: 1 },
      { transform: BACK_T, opacity: 0.25 },
    ],
    { duration: ms * MOTION, easing: EASE_EXIT, fill: "forwards" }
  );
  return a.finished.then(() => { card.style.transform = BACK_T; card.style.opacity = "0.25"; a.cancel(); }).catch(() => {});
}
// 들어올 때: 뒤에 있던 카드가 앞으로 나온다
function enterBack(ms) {
  lastShown = 0;
  card.style.transform = BACK_T;
  card.style.opacity = "0";
  const a = card.animate(
    [
      { transform: BACK_T, opacity: 0 },
      { transform: xform(0), opacity: 1 },
    ],
    { duration: ms * MOTION, easing: EASE_ENTER }
  );
  return a.finished.then(() => paint(0, 1)).catch(() => {});
}
