#!/usr/bin/env python3
"""정비 질문기 화면 (Textual). 답변 로직은 ask.py를 그대로 쓰고, 보이는 방식만 다듬었다.
단축키: Enter 질문 · Ctrl+T 교재/매뉴얼 전환 · Ctrl+L 대화 지우기 · Ctrl+Q 종료"""
import os
import io
import time

os.environ['NO_PROXY'] = 'localhost,127.0.0.1'
os.environ['no_proxy'] = 'localhost,127.0.0.1'
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'

from rich.console import Console
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Footer, Input, Markdown, Static

import ask as ask_mod  # 검색·답변 로직 (처음 불러올 때 DB를 연다)

MODE_LABEL = {"book": "교재", "manual": "SM7 매뉴얼"}
PLACEHOLDER = {"book": "교재에 질문하기", "manual": "SM7 매뉴얼에 질문하기"}
EXAMPLES = {
    "book": ["밸브 오버랩이란 무엇이고, 왜 필요한가?",
             "점화 1차 회로와 2차 회로의 차이는?",
             "클러치 자유간극이 작을 때 증상은?",
             "옴의 법칙으로 전압 12V, 저항 4Ω의 전류는?"],
    "manual": ["SM7 냉각수 교환 주기는?",
               "타이어 공기압 기준값은?",
               "엔진오일 교환 주기는?"],
}


ENGINE_NAMES = {"auto": "자동", "cloud": "클라우드만", "local": "로컬만", "both": "둘 다"}
ENGINE_KIND_NAME = {"cloud": "Claude API", "local": "로컬 LLM", "both": "로컬 + Claude",
                    "unavailable": "클라우드 사용 불가"}


def engine_text(kind: str, name: str) -> str:
    return f"{ENGINE_KIND_NAME.get(kind, kind)} · {name}"


class AskUI(App):
    TITLE = "정비 질문"
    CSS = """
    Screen { background: #101214; color: #e6e8eb; }

    #top { height: 3; padding: 1 2 0 2; }
    #title { width: 1fr; text-style: bold; color: #e6e8eb; }
    Button.seg {
        background: transparent; border: none; min-width: 10; height: 1;
        color: #6b727c; margin-left: 2; padding: 0;
        transition: color 220ms in_out_cubic;
    }
    Button.seg:hover { color: #aab1ba; }
    Button.seg.-active { color: #7fb3ff; text-style: bold; }
    #engine-dot { width: auto; margin-left: 3; color: #8fd19e;
                  transition: color 320ms in_out_cubic; }
    #engine-dot.-cloud { color: #7fb3ff; }
    #engine-dot.-off { color: #6b727c; }
    #engine-label { width: auto; margin-left: 1; color: #6b727c; }

    #log { height: 1fr; padding: 0 2; }
    .turn { width: 100%; }
    .question { margin-top: 2; color: #7fb3ff; text-style: bold; }
    .answer { margin-top: 1; padding: 0 0 0 2; border-left: solid #262b31;
              transition: opacity 260ms in_out_cubic; }
    .answer.-enter { opacity: 0; }
    .answer.-general { border-left: solid #d6a86a; }
    .meta { color: #6b727c; height: 1; }
    .md { background: transparent; padding: 0; margin: 0; }
    .notice { color: #6b727c; margin-top: 1; }

    .chips { height: auto; padding: 0 2; margin-top: 1; }
    .chips.-hidden { display: none; }
    Button.chip {
        background: #1a1d21; color: #aab1ba; border: none; height: 1;
        min-width: 4; margin: 0 1 0 0; padding: 0 1;
        transition: background 180ms in_out_cubic, color 180ms in_out_cubic;
    }
    Button.chip:hover { background: #262b31; color: #e6e8eb; }
    Button.chip:focus { text-style: bold; }

    #status { height: 1; padding: 0 2; color: #6b727c; }
    #q {
        margin: 0 2 1 2; background: #15181b; border: round #262b31; color: #e6e8eb;
        transition: border 200ms in_out_cubic;
    }
    #q:focus { border: round #7fb3ff; }
    """
    BINDINGS = [
        ("ctrl+t", "toggle_mode", "교재/매뉴얼"),
        ("ctrl+g", "cycle_engine", "엔진"),
        ("ctrl+l", "clear", "지우기"),
        ("ctrl+q", "quit", "종료"),
    ]

    def __init__(self):
        super().__init__()
        self.mode = "book"
        self.busy = False
        self._turn_start = 0.0
        self._dots = 0

    def compose(self) -> ComposeResult:
        with Horizontal(id="top"):
            yield Static("정비 질문", id="title")
            yield Button("교재", id="mode-book", classes="seg")
            yield Button("SM7 매뉴얼", id="mode-manual", classes="seg")
            yield Static("●", id="engine-dot")
            yield Static("확인 중", id="engine-label")
        with VerticalScroll(id="log"):
            yield Static("교재나 SM7 매뉴얼에 질문하세요. 답변에는 근거 페이지가 붙습니다.", classes="notice")
        with Horizontal(id="chips-book", classes="chips"):
            for i, q in enumerate(EXAMPLES["book"]):
                yield Button(q, id=f"chip-book-{i}", classes="chip")
        with Horizontal(id="chips-manual", classes="chips -hidden"):
            for i, q in enumerate(EXAMPLES["manual"]):
                yield Button(q, id=f"chip-manual-{i}", classes="chip")
        yield Static("", id="status")
        yield Input(placeholder=PLACEHOLDER["book"], id="q")
        yield Footer()

    def on_mount(self) -> None:
        self.set_mode("book", notice=False)
        self.set_interval(0.4, self._tick)
        self.set_interval(15, self._check_engine)
        self._check_engine()
        self.query_one("#q", Input).focus()

    # ---------- 모드 ----------
    def set_mode(self, mode: str, notice: bool = True) -> None:
        self.mode = mode
        for m in ("book", "manual"):
            self.query_one(f"#mode-{m}", Button).set_class(m == mode, "-active")
            self.query_one(f"#chips-{m}").set_class(m != mode, "-hidden")
        self.query_one("#q", Input).placeholder = PLACEHOLDER[mode]
        if notice:
            self.add_notice(f"{MODE_LABEL[mode]} 모드로 바꿨습니다.")

    def action_toggle_mode(self) -> None:
        self.set_mode("manual" if self.mode == "book" else "book")

    # ---------- 질문·답변 ----------
    def add_notice(self, text: str) -> None:
        log = self.query_one("#log", VerticalScroll)
        log.mount(Static(text, classes="notice turn"))
        log.scroll_end(animate=False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "mode-book":
            self.set_mode("book")
        elif bid == "mode-manual":
            self.set_mode("manual")
        elif "chip" in event.button.classes:
            self.ask(str(event.button.label))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        q = event.value.strip()
        if q:
            event.input.value = ""
            self.ask(q)

    def ask(self, question: str) -> None:
        if self.busy:
            self.query_one("#status", Static).update("답변을 기다리는 중입니다.")
            return
        self.busy = True
        self._turn_start = time.time()
        log = self.query_one("#log", VerticalScroll)
        log.mount(Static(question, classes="question turn"))
        log.scroll_end(animate=False)
        self.run_worker(lambda: self._work(question, self.mode), thread=True, exclusive=False)

    def _work(self, question: str, mode: str) -> None:
        ask_mod.CURRENT_MODE[0] = mode
        ask_mod.LAST_ENGINE[0] = ""
        ask_mod.console = Console(file=io.StringIO(), width=100)  # 검색 중 출력이 화면을 깨지 않게 숨김
        try:
            answer = ask_mod.ask(question)
        except Exception as e:
            answer = f"**오류**: {e}"
        engine = ask_mod.LAST_ENGINE[0]
        self.call_from_thread(self._answer, answer, mode, time.time() - self._turn_start, engine)

    def _answer(self, answer: str, mode: str, secs: float, engine: str = "") -> None:
        self.busy = False
        general = "근거 없음" in answer
        log = self.query_one("#log", VerticalScroll)
        label = "일반 지식 답변" if general else f"{MODE_LABEL[mode]} 답변"
        meta = f"{label} · {secs:.1f}초"
        if engine:
            kind, name = engine.split("|", 1)
            color = "#7fb3ff" if kind in ("cloud", "both") else "#8fd19e"
            meta += f"  [{color}]●[/] {engine_text(kind, name)}"
        card = Vertical(
            Static(meta, classes="meta"),
            Markdown(answer, classes="md"),
            classes="answer turn -enter" + (" -general" if general else ""),
        )
        log.mount(card)
        log.scroll_end(animate=False)
        self.set_timer(0.05, lambda: card.remove_class("-enter"))  # 살짝 페이드 인

    def _tick(self) -> None:
        status = self.query_one("#status", Static)
        if self.busy:
            self._dots = (self._dots + 1) % 4
            status.update(f"검색 중 · {MODE_LABEL[self.mode]}" + "·" * self._dots)
        else:
            status.update("Enter 질문   ·   Ctrl+T 교재/매뉴얼   ·   Ctrl+G 엔진   ·   Ctrl+L 지우기")

    # ---------- 엔진 표시 ----------
    def _check_engine(self) -> None:
        self.run_worker(self._probe_engine, thread=True, exclusive=True, group="engine")

    def _probe_engine(self) -> None:
        kind, name = ask_mod.engine_status()
        self.call_from_thread(self._show_engine, kind, name)

    def _show_engine(self, kind: str, name: str) -> None:
        dot = self.query_one("#engine-dot", Static)
        dot.set_class(kind in ("cloud", "both"), "-cloud")
        dot.set_class(kind == "unavailable", "-off")
        mode = ENGINE_NAMES[ask_mod.ENGINE_MODE[0]]
        self.query_one("#engine-label", Static).update(f"{mode} · {engine_text(kind, name)}")

    def action_cycle_engine(self) -> None:
        modes = list(ask_mod.ENGINE_MODES)
        nxt = modes[(modes.index(ask_mod.ENGINE_MODE[0]) + 1) % len(modes)]
        ask_mod.ENGINE_MODE[0] = nxt
        self.add_notice(f"답변 엔진: {ENGINE_NAMES[nxt]}")
        self._check_engine()

    # ---------- 기타 ----------
    def action_clear(self) -> None:
        log = self.query_one("#log", VerticalScroll)
        for w in list(log.query(".turn")):
            w.remove()

    def action_quit(self) -> None:
        self.exit()


if __name__ == "__main__":
    print("정비 질문기를 준비하는 중입니다 (처음에는 잠시 걸립니다)...")
    AskUI().run()
