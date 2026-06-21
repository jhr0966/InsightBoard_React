# InsightBoard

조선소 작업 정의를 이해하는 LLM 어시스턴트가 외부 기술 동향을 우리 작업에 어떻게 적용할지 번역해주는 시스템. **React(`web/`) SPA + FastAPI(`api/`) 백엔드.** 3대 축:

1. **🔍 수집·enrich** (`scraping/`) — 네이버 / 구글 RSS / AI Times / 오토메이션월드, 본문 fetch + LLM 키워드·요약.
2. **🗂 로드맵·매칭** (`roadmap/`, `store/`) — 조선소 작업 정의 엑셀 → Parquet, 룰 기반 뉴스↔작업 매칭, 자동화 기회 매트릭스.
3. **🤖 SOLA LLM** (`sola/`, `persona/`) — 요약·제안서·채팅·부서 인사이트, 페르소나 자동 주입.

UI 는 업무 흐름형 메뉴(`오늘의 보드 · 인사이트 분석 · 자동화 제안 · 뉴스 수집 · 작업 정의`)로, React 페이지(`web/src/pages/*`) + 공통 셸(`web/src/components/{Layout,Sidebar,Topbar,AssistantDrawer}.tsx`) + SVG 차트(`web/src/components/charts/*`)로 구성. 프런트는 타입드 클라이언트(`web/src/api/client.ts`)로 `api/routers/*` 계약만 소비한다. 화면 간 인계는 `?from=&dept=&lv3=` 쿼리로 SOLA 드로어 자동 검토. 디자인 토큰·테마는 `web/src/styles/*`.

> ⓘ 과거 Streamlit 앱(`app.py`·`ui/`)은 React 전환 완료 후 **2026-06 은퇴**(제거).

## 🚀 빠른 시작 (Groq 무료 API)

LLM 백엔드 기본값은 [Groq](https://groq.com/) (무료 티어, `llama-3.3-70b-versatile`)이라 키 1개만 있으면 즉시 사용 가능.

```bash
# 1) 의존성 설치
pip install -r requirements.txt

# 2) Groq API 키 발급 후 .env 작성
#    https://console.groq.com/keys → "Create API Key" → 복사
cp .env.example .env
# .env 파일을 열어 LLM_API_KEY=gsk_xxxxx... 한 줄만 채우면 OK

# 3) 백엔드 + 프런트 실행 (터미널 2개)
uvicorn api.main:app --reload          # http://127.0.0.1:8000
cd web && npm install && npm run dev   # http://127.0.0.1:5173 (vite proxy → 8000)
```

사이드바 하단의 LLM 상태가 🟢로 바뀌면 키가 정상 인식된 것. 🟠면 `.env`의 `LLM_API_KEY`를 다시 확인.
다른 백엔드(사내 OpenAI 호환 / 로컬 Ollama) 로 전환하려면 `.env.example`의 `LLM_BACKEND` / `LLM_BASE_URL` / `LLM_MODEL` 주석 참고.

## ☁️ 배포 (프런트 Vercel + 백엔드 Render)

상세 절차는 [`docs/DEPLOY.md`](./docs/DEPLOY.md). 요약:

- **백엔드(Render)**: `render.yaml` 블루프린트(Docker) → env(`LLM_BACKEND`·`LLM_API_KEY`·`LLM_MODEL`·`INSIGHTBOARD_CORS_ORIGINS`=Vercel 도메인·`INSIGHTBOARD_DATA_ROOT`). 무료 플랜은 디스크 없음(ephemeral).
- **프런트(Vercel)**: Root=`web`, build-time `VITE_API_BASE`=백엔드 URL.
- 검증: `<backend>/api/health` → `{"status":"ok"}` → 프런트에서 `/api/*` 200.

`.env`/키는 **절대 커밋 금지**. 노출 시 Groq Console 에서 키 Delete 후 재발급.

## 실행 (요약)

```bash
pip install -r requirements.txt
cp .env.example .env                   # LLM_API_KEY=... 채우기
uvicorn api.main:app --reload          # 백엔드
cd web && npm install && npm run dev   # 프런트
```

- Python ≥ 3.10, Node ≥ 18
- LLM 미설정 상태에서도 수집·로드맵·매트릭스는 정상 동작하며, LLM 결과만 graceful degrade.

## 빠른 개발 환경 세팅

```bash
./scripts/dev_setup.sh                 # venv + pip install
source .venv/bin/activate
```

- API 스키마 변경 시: `python scripts/gen_openapi.py && cd web && npm run gen:types`

## 개발 문서

| 문서 | 언제 읽나 |
|---|---|
| [`CLAUDE.md`](./CLAUDE.md) | 작업 시작 전 **항상** (단일 참조점) |
| [`DEV_GUIDELINES.md`](./DEV_GUIDELINES.md) | 라우팅 표 · 검증 명령 |
| [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) | 모듈 계약 · article 스키마 |
| [`docs/INVARIANTS.md`](./docs/INVARIANTS.md) | state/위젯 불변식 |
| [`docs/WORKFLOW.md`](./docs/WORKFLOW.md) | 브랜치 → 커밋 → 머지 루프 |
| [`docs/SESSIONS.md`](./docs/SESSIONS.md) | 이전 세션 복원 (상단 1개만) |
| [`CHANGELOG.md`](./CHANGELOG.md) | 릴리스 이력 |
| [`docs/VIBE_CODING_BLUEPRINT.md`](./docs/VIBE_CODING_BLUEPRINT.md) | 제품/아키텍처/개발전략 청사진 |
| [`docs/UX_REDESIGN_PLAN.md`](./docs/UX_REDESIGN_PLAN.md) | 인사이트보드 UI/UX 전면 개편 계획 |
| [`docs/DEVELOPMENT_PHASES.md`](./docs/DEVELOPMENT_PHASES.md) | Streamlit + Local First 단계별 실행 계획 |

## 배포

Vercel(프런트)·Render(백엔드)가 `main` 을 트래킹 — **`main` 머지 = 자동 배포**.
작업은 반드시 브랜치에서:

```bash
git checkout -b <category>-<slug>    # fix|feat|refactor|style|docs|chore
```

## 커밋 전 검증

```bash
# 스테이지된 .py 만 compile (CI 가 모든 .py 를 자동 검사)
python -m py_compile $(git diff --name-only --cached | grep '\.py$')

# requests 직접 호출 금지 (scraping/http.py 의 build_session 만 예외)
grep -rnE 'requests\.(get|post|Session)\(' \
     api/ sola/ store/ roadmap/ persona/ scraping/ \
     | grep -v 'scraping/http\.py:'                                # 0

pytest -q                                                          # 백엔드
cd web && npm run build                                            # 프런트(타입체크+빌드)
```

> `.github/workflows/ci.yml` 이 PR 마다 동일 검증을 자동 실행합니다.

## 테스트

```bash
pytest -q
```

`tests/` 아래 백엔드 단위 테스트 **462건**이 LLM 호출·HTTP·디스크 IO 를 모킹해 빠르게 돕니다(Streamlit 은퇴로 UI 테스트는 제거). 프런트는 `cd web && npm run build` 로 타입체크.
