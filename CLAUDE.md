# DR-COCKPIT 프로젝트 안내

맥북 에어(8GB)에서 돌아가는 자동차 정비 학습 도구입니다. (OBD-II 진단 화면은 제거되어 `archive_diagnostic/`에 보관)
- `ask.py` / `ask_ui.py`: 정비 질문기. 교재·SM7 매뉴얼 PDF를 검색(FAISS)하고 답변(로컬 Ollama 또는 Anthropic API).
- `build_db.py`: docs/의 PDF로 DB(db_faiss/) 생성. `auto_build.sh`가 launchd로 주기 실행.
- `run_cockpit.sh [ask]`: 실행 진입점. 가상환경은 `venv/`.

### 문제풀이 웹앱 (정비산업기사 기출)
- `study_api.py` (FastAPI, 127.0.0.1:8765, CORS localhost:3000): 문제 조회·힌트(정적)·객관식 선택. 주관식 채점(`/api/grade`)은 중계 경로 제거로 항상 503. 외부 참고 검색(Brave·위키백과)과 `/외부` 명령도 제거됨(`/api/refs/{n}`은 error와 빈 목록). 로컬 LLM 기능(암기팁/메모)은 제거됨.
  - `/api/questions`, `/api/questions/{n}`, `/api/context/{n}`, `/api/refs/{n}`, `/api/hint`, `/api/choice`, `/api/grade`, `/api/reveal`
  - 채점 경로(`/api/grade`)는 제거되어 항상 503 `채점 불가`. 채점 응답 파싱(`study.py`의 `parse_grade`·`show_grade`)은 남아 있다. 판정은 `## 판정` 섹션의 **첫 줄 앞부분**이 `정답`/`부분`/`오답`으로 시작할 때만 인정, 그 외는 `unknown`. 첫 줄에 `/`가 있으면(템플릿 문구 에코) 역시 `unknown`. CLI(`study.py show_grade`)도 같은 규칙.
  - `/api/context/{n}`: 지문·보기·`kind`는 항상 주고, 정답·풀이는 `교사용`만 준다(학생용은 채점 전 비공개, `_public`과 같은 규칙).
- `review_api.py` (`/api/review`, study_api가 router 마운트): 오답노트 복습 모드.
  - `오답노트/*.md`를 카드로 파싱. `(1)` 복사본은 건너뛴다. 모범답안이 보기에 없는 노트는 경고를 찍고 건너뛴다(전체 목록은 유지).
  - 풀이 기록: `db_study/review_state.json`. 연속 `MASTER_STREAK`(=2)회 정답이면 숙달.
  - 엔드포인트: `/cards`, `/next?mode=all|wrong`, `/answer`, `/stats`.
- `web/`: 정적 프런트(`index.html`, `review.html`, `hub.html`, `app.js`). `run_web.sh`가 uvicorn(8765)과 `http.server 3000`을 띄우고 index.html을 연다.

## 실행
- 질문기: `bash run_cockpit.sh ask`
- 문제풀이 웹: `bash run_web.sh`

## 설정
- 로컬 모델: `DR_LOCAL_MODEL` (기본 qwen2.5:3b). 7b는 맥에서 멈춤·발열이 심해 기본에서 뺐다. 공부사이트(`study_api.py`)는 환경변수와 무관하게 3b로 고정한다.
- 임베딩 모델: `DR_EMBED_MODEL` (바꾸면 build_db.py로 DB를 다시 만들어야 함)
- 클라우드: 키는 환경변수 `ANTHROPIC_API_KEY`에서만 읽음(키체인 조회·Lumia 중계 제거). 주소는 `DR_CLOUD_BASE_URL` (기본 https://api.anthropic.com)
- 웹채팅(8767) 연계는 제거됨. `web/hub.html`·`problem_diagrams/hub.html`·`web/app.js`·`web/index.html`에서 해당 링크·버튼을 뺐다. `start_all.command`·`stop_all.command`에서 8767(웹채팅) 실행·종료를 뺐다. 웹채팅은 `~/claude-work/webchat`의 `웹채팅.command`로 따로 켠다. `~/dr_cockpit`은 아직 8767을 띄우므로 따로 정리해야 한다.
- 답변 엔진 모드: 자동 / 클라우드만 / 로컬만 / 둘 다 (질문기에서 Ctrl+G)

## 작업 규칙
- 수정 전 `파일명.vN.bak`로 백업을 남긴다.
- 수정 후 `python3 -m pyflakes <파일>`과 문법 검사를 먼저 한다.
- API 키 값은 코드, 로그, 채팅 어디에도 출력하거나 기록하지 않는다. 존재 여부만 확인한다.
- `~/.zshrc`, `~/.config/lumia/key`, `claude`·`claude-gg`·`claude-gg-yolo` 설정은 건드리지 않는다.
- 요청 범위 밖의 리팩터링이나 스타일 정리는 하지 않는다.
- 실제 기기 동작(키체인, Ollama, Terminal, tmux)은 실행해서 확인하고, 결과를 보고한다.
- 문제풀이 웹 파일을 고칠 때도 `파일명.vN.bak` 백업 → `venv/bin/python -m pyflakes study_api.py review_api.py` 순서를 지킨다.
- 채점 프롬프트(`study.py`의 `SYSTEM_GRADE`)는 사용자 승인 없이 바꾸지 않는다. 판정 파싱 쪽을 먼저 고친다.
