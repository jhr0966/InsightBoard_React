# InsightBoard 개발 지침

> CLAUDE.md의 규칙을 정리한 개발자용 요약 문서.
> 스택: **React SPA(`web/`) + FastAPI(`api/`)** + 도메인 백엔드(`scraping`·`roadmap`·`store`·`sola`·`persona`).
> 3대 축: **수집·enrich · 로드맵·매칭 · SOLA LLM**

## 1. 토큰 절약 규칙 (최우선)

1. **코드 파일은 수정 대상만 읽는다.** "전체 파악"을 위해 모든 파일을 읽지 마라.
2. **docs/는 라우팅 표에 해당하는 문서만 1개 읽는다.** 2개 이상 동시에 읽지 마라.
3. **SESSIONS.md는 상단 1개 세션만.** 전체를 읽지 마라.
4. **단순 수정은 해당 파일만 읽고 바로 수정.** 관련 없는 파일 탐색 금지.
5. **읽기 전에 자문**: "이 파일을 안 읽으면 작업이 불가능한가?" — 아니면 읽지 마라.

## 2. 파일별 역할 및 읽는 시점

| 파일/패키지 | 역할 | 언제 읽나 |
|---|---|---|
| `api/` | FastAPI 백엔드 — React 가 소비하는 HTTP 계약(`routers/*` 위임) | API 엔드포인트·스키마 작업 시 |
| `web/` | React SPA(pages·components·charts·styles·타입드 client) | 화면/UI 작업 시 (해당 페이지·컴포넌트만) |
| `scraping/` | 네이버·구글RSS·AI Times·오토메이션월드 + HTTP 단일 진입점 + 본문 enrich | 크롤링·파서·셀렉터·enrich 작업 시 |
| `roadmap/` | 작업 정의 엑셀 → snake_case 정규화 → Parquet + SQLite | 로드맵 스키마/적재/쿼리 작업 시 |
| `store/` | 뉴스 Parquet · 매칭 · 트렌드 · 캐시 · 채팅·북마크 영구화 · 식별/감사 | 데이터 저장·조회·집계 작업 시 |
| `sola/` | LLM 호출 · 프롬프트 · 요약·제안서·인사이트·자동화 기회 (provider 추상화) | LLM 호출·프롬프트·결과 포맷 작업 시 |
| `persona/` | 사용자 부서·직무·관심 공정 (JSON 영구화) | 페르소나 컨텍스트 주입 작업 시 |
| `config.py` | `.env` 로딩 · LLM 백엔드 라우팅 · 데이터 경로 상수 | 환경/백엔드/경로 작업 시 |
| `docs/ARCHITECTURE.md` | 모듈 경계·데이터 플로우 | 아키텍처 이해 필요 시에만 |
| `docs/INVARIANTS.md` | 백엔드/계층 불변식 | 계약·식별필드·seam 작업 시에만 |
| `docs/DEPLOY.md` | Vercel(프런트)+Render(백엔드) 배포 | 배포 작업 시에만 |
| `docs/SESSIONS.md` | 세션 로그 | 이전 세션 복원 시 (상단 1개만) |
| `CHANGELOG.md` | 릴리스 이력 | 릴리스/버전 작업 시에만 |

## 3. 라우팅 표

> **단일 소스는 `CLAUDE.md` 의 "읽기 라우팅" 표다.** 화면 작업은 보통 **React 페이지 + 대응 API 라우터** 두 곳을 함께 본다.
> 여기엔 자주 쓰는 것만 발췌:

| 작업 | 읽을 파일 |
|---|---|
| 스크래퍼 셀렉터·HTTP 버그 | `scraping/<source>.py` (+ `scraping/http.py`) |
| 본문 enrich / 키워드·요약 | `scraping/enrich.py` |
| 로드맵 엑셀 스키마/적재 | `roadmap/{schema,ingest}.py` |
| 작업 정의 CRUD (SQLite) | `store/task_defs_db.py`, `roadmap/{task_def_form,task_def_json}.py` |
| 뉴스↔작업 매칭 / 자동화 기회 | `store/match.py`, `sola/opportunity.py` |
| LLM 호출·프롬프트 | `sola/client.py` + `sola/providers/*` + `sola/prompts.py` |
| 📊 오늘의 보드 | `web/src/pages/Board.tsx` (+ `api/routers/board.py`·`trends.py`) |
| 🗞 뉴스 수집 | `web/src/pages/Collect.tsx` (+ `api/routers/news.py`·`collect.py`·`sources.py`) |
| 📋 작업 정의 | `web/src/pages/TaskDefs.tsx` (+ `api/routers/taskdefs.py`, `roadmap/ingest.py`) |
| 🔎 인사이트 분석 | `web/src/pages/Insights.tsx` (+ `api/routers/insights.py`·`trends.py`·`opportunities.py`) |
| 🤖 자동화 제안 | `web/src/pages/Proposals.tsx` (+ `api/routers/proposals.py`·`bookmarks.py`) |
| 👤 페르소나 / 온보딩 | `web/src/pages/Persona.tsx`, `web/src/components/Onboarding.tsx` (+ `api/routers/persona.py`·`prefs.py`) |
| 앱 셸 · SOLA 드로어 | `web/src/components/{Layout,Sidebar,Topbar,AssistantDrawer}.tsx` (+ `api/routers/assistant.py`·`threads.py`) |
| 타입드 API 클라이언트 | `web/src/api/{client,types,schema}.ts` |
| CSS·테마 | `web/src/styles/{app,tokens,themes,ui}.css` · `screens/*.css` |
| 아키텍처 파악 | `docs/ARCHITECTURE.md` |
| 이전 세션 복원 | `docs/SESSIONS.md` (상단 1개) |
| 단순 문답 | **CLAUDE.md 만으로 충분** |

## 4. 불변 규칙 요약

자세한 내용: [`docs/INVARIANTS.md`](./docs/INVARIANTS.md)

- **계층 분리**: 프런트(`web/`)는 `api/` 계약만 소비(`web/src/api/client.ts`). 도메인 로직은 백엔드, `api/routers/*` 는 위임만.
- **API 타입 드리프트 가드**: `api/` 스키마 변경 시 `python scripts/gen_openapi.py && cd web && npm run gen:types`. OpenAPI 스냅샷 테스트가 검증.
- **HTTP 단일 진입점**: 외부 HTTP 는 항상 `scraping.http.build_session()`. 다른 곳의 `requests.get/post/Session()` 금지.
- **enrich 단일 진입점**: 본문 enrich 는 `scraping.enrich` 진입점만.
- **LLM 단일 진입점**: `sola.client.chat/chat_stream`, 프롬프트는 `sola/prompts.py` 상수. provider 는 `LLM_PROVIDER` 로 교체.
- **XSS**: React 기본 escape. `dangerouslySetInnerHTML` 금지. 백엔드에서 외부 문자열 HTML 합성 금지.
- **인증/식별 seam**: `api/deps.py`(no-op 인증=Phase 2 교체점), 식별·감사 5필드 `store/_audit.py`.

## 5. 브랜치 전략

- **`main`**: 안정 코드만. 직접 push 금지. 머지만 허용.
- **작업 브랜치**: 수정 요청마다 최신 `main`에서 별도 브랜치. 이미 PR 올린 브랜치 재사용 금지.
- **PR 올리기 전**: 가능한 환경에서 최신 `main`에 rebase/merge 로 충돌 먼저 확인.
- **고충돌 파일**: `CHANGELOG.md`, `docs/SESSIONS.md`는 `.gitattributes` `merge=union`. 머지 후 중복/순서만 리뷰.
- **네이밍**: `<카테고리>-<설명>` (슬래시 금지, 하이픈) — `fix`/`feat`/`refactor`/`style`/`docs`/`chore`.

## 6. 검증 (커밋 전 필수)

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

> `.github/workflows/ci.yml` 이 PR 마다 동일 검증을 자동 실행한다.

## 7. 변경 시 갱신

작업 브랜치의 같은 커밋에서 다음을 함께 업데이트:

1. `CHANGELOG.md` [Unreleased] 섹션에 엔트리 추가
2. `docs/SESSIONS.md` 상단에 세션 항목 추가
3. 새로운 invariant 발생 시 → `docs/INVARIANTS.md`에 추가

## 8. 스택

- **프런트**: React 18 + Vite + TypeScript + React Router + TanStack Query (`web/`). SVG 차트 직접 구현. openapi-typescript 로 타입 생성.
- **백엔드**: FastAPI + uvicorn (`api/`). Pydantic 스키마. OpenAPI 스냅샷 테스트.
- **수집**: BeautifulSoup4 + lxml (fallback `html.parser`) + curl_cffi (`scraping/`).
- **데이터**: Pandas + PyArrow (Parquet) · SQLite(task_defs) · openpyxl(엑셀).
- **LLM**: OpenAI SDK(groq 호환)·anthropic SDK. `LLM_PROVIDER`/`LLM_BACKEND` 스위치(`sola/`).
- **환경**: python-dotenv (`.env`).
- **배포**: 프런트 Vercel + 백엔드 Render (`main` 추적). → `docs/DEPLOY.md`.
