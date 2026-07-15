# CLAUDE.md — News 프로젝트 작업 규칙

> 이 파일은 Claude가 News 레포에서 작업할 때 가장 먼저 읽는 **유일한** 상시 문서다.
> 나머지 docs/는 필요할 때만 선택적으로 읽는다. (→ [`DEV_GUIDELINES.md`](./DEV_GUIDELINES.md))

## 도메인

조선소 작업 정의를 이해하는 LLM 어시스턴트가 외부 기술 동향을 우리 작업에 어떻게 적용할지 번역해주는 시스템. 3대 축:

1. **수집·enrich** (`scraping/`) — 네이버 / 구글 RSS / AI Times / 오토메이션월드, 본문 fetch + LLM 키워드·요약.
2. **로드맵·매칭** (`roadmap/`, `store/`) — 조선소 작업 정의 엑셀 → Parquet, 룰 기반 뉴스↔작업 매칭, 자동화 기회 매트릭스.
3. **SOLA LLM** (`sola/`, `persona/`) — 요약·제안서·채팅·부서 인사이트·매트릭스 코멘트, 페르소나 자동 주입.

UI는 **React SPA**(`web/`, Vite+TS+Router+Query), 백엔드는 **FastAPI**(`api/`). 과거 Streamlit(`app.py`·`ui/`)은 **은퇴**(2026-06 제거)했다.

## 절대 규칙 (반드시 지킬 것)

1. **토큰 절약**: 수정 대상 파일만 읽어라. UI 작업에 `sola/` 전체를 읽지 마라. (`DEV_GUIDELINES.md` §1)
2. **계층 분리**: 프런트(`web/`)는 `api/` 계약만 소비(`web/src/api/client.ts`). 도메인 로직은 백엔드(`store/`·`sola/`·`roadmap/`·`scraping/`)에 두고 라우터(`api/routers/*`)는 위임만.
3. **API 타입 드리프트 가드**: `api/` 스키마를 바꾸면 `python scripts/gen_openapi.py && cd web && npm run gen:types` 로 `web/src/api/schema.ts` 재생성. OpenAPI 스냅샷 테스트가 검증.
4. **HTTP 단일 진입점**: `scraping.http.build_session()` 외의 `requests.get/Session()` 금지.
5. **XSS 방어**: React는 기본 escape. `dangerouslySetInnerHTML` 사용 금지(불가피하면 sanitize). 백엔드에서 외부 문자열을 HTML로 합성하지 마라.
6. **세션/인증 seam**: `api/deps.py`(`current_identity`·`Identity`)는 X-User-Id **경량 식별 — 인증 아님**(신뢰 프록시 주입 전제, I-17) = SSO/토큰 Phase 2 교체점. 식별·감사 5필드는 `store/_audit.py`.
7. **main 직push 금지**: 모든 변경은 작업 브랜치 → PR → 머지.
8. **작업 완료 보고 의무 (패치노트 형식)**: 모든 개발 지시가 끝나면 사용자에게 아래를 **반드시** 한 메시지로 정리한다 (생략 금지, 단순 정보 질문 응답은 제외).
   1. **무엇을 어떻게 수정했는지 — 패치노트처럼 항목별로 명확히 쭉 나열**. 각 항목은 `무엇을(파일·함수·기능) → 어떻게 바꿨고 왜(동작·효과)` 가 한눈에 보이게 쓴다. 기호·약어만 뭉쳐 나열하지 말고, 읽어서 이해되는 문장으로.
   2. **어떻게 조치됐는지** — 테스트 결과(N/N passed), 금지 패턴 검사, 커밋·푸시·PR 번호/링크/상태, CI 상태(queued/in_progress/success/failure), 충돌 시 해소 방법.
   3. **다음 단계 — 내용까지 설명**. 후속 작업 1~3건을 제목만 던지지 말고, "무엇을 왜 하는지 · 어디 파일을 건드리는지" 를 한두 줄로 풀어 사용자가 이해하고 바로 지시할 수 있게.

   형식 예시:

   ```
   ✅ <제목> — PR #N (Draft/Ready/Merged) · CI <상태>

   ■ 무엇을 어떻게 수정했나 (패치노트)
   - <파일/모듈>: <무엇을 어떻게 바꿨는지> → <효과/이유>
   - …

   ■ 조치: pytest N/N · 금지패턴 0 · push <성공/실패> · CI <상태>

   ■ 다음 단계
   1. <작업명> — <무엇을 왜, 어디를 건드리는지 1~2줄>
   ```

## 읽기 라우팅 (작업별 최소 파일)

> UI는 React(`web/src/pages/*`, `web/src/components/*`), 백엔드는 FastAPI(`api/routers/*`).
> 화면 작업은 보통 **React 페이지 + 대응 API 라우터** 두 곳을 함께 본다.

| 작업 | 읽을 파일 |
|---|---|
| 스크래퍼 셀렉터·HTTP | `scraping/<source>.py` (+ `scraping/http.py`) |
| 본문 enrich / 키워드·요약 | `scraping/enrich.py` |
| 일일 cron 수집 · 수집 런 로그 | `scraping/run_daily.py`, `scripts/daily_scrape.py` (+ `store/run_log.py`) |
| 로드맵 엑셀 적재·스키마 | `roadmap/ingest.py`, `roadmap/schema.py` |
| 작업 정의 CRUD (SQLite) | `store/task_defs_db.py`, `roadmap/{task_def_form,task_def_json}.py` |
| 로드맵 조회 (SQLite→Parquet) | `roadmap/query.py`, `roadmap/sqlite_sync.py` |
| 기사 정체성·정렬·중복 병합 | `store/article_id.py`(URL 정규화 해시), `store/news_db.py`(`sort_at` 정렬·필드 병합 — I-14·I-15) |
| 뉴스↔작업 매칭 / 자동화 기회 | `store/match.py`(v2·이유 컴포넌트), `store/links_db.py`(영구화 — I-16), `sola/opportunity.py` |
| 기술 분류 (TECH-* ID·별칭) | `store/taxonomy.py` (+ 오버라이드 `data/taxonomy/taxonomy.json`) |
| 개인화 랭킹·피드백 이벤트 | `store/rank.py`(RANKING_VERSION·왜-관련 문장), `store/feedback.py` (+ `api/routers/feedback.py`) |
| 트렌드·캐시·북마크·채팅 영구화 | `store/{trends,cache,bookmarks,chat_log,sola_threads,sources}.py` |
| LLM 호출·프롬프트 | `sola/client.py`(facade·`chat`/`chat_stream`), `sola/providers/*`(openai 내장·`anthropic`), `sola/prompts.py`. 교체: `LLM_PROVIDER`(openai/anthropic) |
| 보드/트렌드 LLM 산출 | `sola/{board_brief,trend_brief,opportunity,side_context}.py` |
| 페르소나 | `persona/{schema,store,context}.py` |
| 🏠 오늘 (개인화 다이제스트) | `web/src/pages/Board.tsx` (5요소 홈; + `api/routers/board.py`(digest·brief)·`feedback.py`, `store/rank.py`) |
| 🗞 뉴스 탐색 | `web/src/pages/Feed.tsx` (카드/표·기사모달·검색; + `api/routers/news.py`) |
| ⚙️ 수집 관리 | `web/src/pages/Collect.tsx` (수집 SSE·출처·진단·이력; + `api/routers/collect.py`·`sources.py`) |
| 📋 작업 정의 | `web/src/pages/TaskDefs.tsx` (엑셀 업로드·diff 미리보기·풀편집폼·이력; + `api/routers/taskdefs.py`, `roadmap/ingest.py`, `store/task_defs_db.py`) |
| 🔬 분석실 | `web/src/pages/Insights.tsx` (탭: 트렌드/BubbleMatrix/Heatmap+셀매칭; + `api/routers/insights.py`·`trends.py`·`opportunities.py`) |
| 📚 적용 사례 (검토·승인) | `web/src/pages/Cases.tsx` (+ `api/routers/cases.py`, `store/cases_db.py`, `sola/case_extract.py`) |
| 🤖 자동화 과제 (생성 + 엔터티 칸반) | `web/src/pages/Proposals.tsx` (+ `api/routers/proposals.py`, `store/proposals_db.py`(상태 9종·이력), `sola/propose.py`(근거 선정)) |
| 👤 페르소나 / 온보딩 | `web/src/pages/Persona.tsx`, `web/src/components/Onboarding.tsx` (+ `api/routers/persona.py`·`prefs.py`) |
| 앱 셸 (좌 nav·topbar·우 SOLA 드로어·반응형) | `web/src/components/{Layout,Sidebar,Topbar,AssistantDrawer}.tsx`, `web/src/nav.ts` |
| SOLA 채팅(SSE)·화면별 추천질문·핸드오프 | `web/src/components/AssistantDrawer.tsx` (+ `api/routers/assistant.py`·`threads.py`) |
| CSS·스타일·테마 | `web/src/styles/{app.css,tokens.css,themes.css,ui.css,screens/*.css}` |
| 공통 컴포넌트·차트 | `web/src/components/ui/*`, `web/src/components/charts/*`(SVG: Line·Bar·Sparkline·BubbleMatrix·Heatmap) |
| 타입드 API 클라이언트 | `web/src/api/client.ts`(fetch+SSE), `web/src/api/types.ts`, `web/src/api/schema.ts`(openapi-typescript 자동생성) |
| 백엔드 HTTP API | `api/main.py`(앱·CORS·health), `api/deps.py`(X-User-Id 경량 식별 — 인증 아님·I-17·SSO 교체점), `api/schemas.py`(식별필드), `api/routers/*` — `store`/`sola` 위임 |
| 식별·감사 필드 표준 | `store/_audit.py` (`stamp`/`backfill`/`now_iso`) |
| 영구화 백엔드 seam (Phase 2 교체점) | `store/repository.py` (`Repository`·`JsonlRepository`·`get_repository`, `INSIGHTBOARD_STORAGE`). bookmarks 적용 |
| 아키텍처 파악 | `docs/ARCHITECTURE.md` |
| 2026-07 개편 현황·회고 (Step 0~13) | `docs/REDESIGN_STATUS.md` |
| 계층·계약 불변식 | `docs/INVARIANTS.md` |
| 배포(프런트 Vercel + 백엔드 Render) | `docs/DEPLOY.md` |
| 전환 현황·핸드오프 (완료) | `docs/REACT_STATUS.md` |
| 전환 계획·리팩토링·UX 등 히스토리 (완료) | `docs/archive/*` (REACT_MIGRATION_PLAN·REACT_PARITY_PLAN·REACT_PREP_INVENTORY·REFACTOR_PLAN·UX_REDESIGN_PLAN·INVARIANTS_STREAMLIT 등) |

> ⚠ Streamlit 은퇴(2026-06): `app.py`·`ui/`·`assets/v2`·streamlit 의존 테스트·전용 스크립트 삭제, `requirements.txt` 에서 streamlit 제거. `config.py` 의 streamlit secrets fallback 만 try/except 로 보존(백엔드는 streamlit 없이 동작). `sola/side_context.py` 는 orphan·보존(향후 AssistantDrawer 컨텍스트 연결점).

전체 라우팅 표는 [`DEV_GUIDELINES.md §3`](./DEV_GUIDELINES.md#3-라우팅-표).

## 커밋 전 체크리스트

```bash
# 스테이지된 .py 만 compile (CI 가 모든 .py 를 자동 검사)
python -m py_compile $(git diff --name-only --cached | grep '\.py$')

# requests 직접 호출 금지(scraping/http.py 의 build_session 만 예외)
grep -rnE 'requests\.(get|post|Session)\(' \
     api/ sola/ store/ roadmap/ persona/ scraping/ \
     | grep -v 'scraping/http\.py:'                                # 0

pytest -q                                                          # 백엔드
cd web && npm run build                                            # 프런트(타입체크+빌드)
```

> GitHub Actions(`.github/workflows/ci.yml`)이 동일 검증을 PR 마다 자동 실행한다.

커밋에는 다음이 함께 포함되어야 한다:
- `CHANGELOG.md` [Unreleased] 항목 추가
- `docs/SESSIONS.md` 상단 세션 기록
- 새 invariant 발생 시 `docs/INVARIANTS.md` 갱신

## 브랜치 네이밍

`<카테고리>-<설명>` — 슬래시 금지, 하이픈 구분.
카테고리: `fix`, `feat`, `refactor`, `style`, `docs`, `chore`.

예: `feat-insight-trend`, `fix-scraper-selector`, `style-cardnews-typography`.

## PR 충돌 방지

- 작업마다 최신 `main`에서 새 브랜치를 만들고, 이미 PR을 올린 브랜치를 다음 작업에 재사용하지 않는다.
- PR 생성 전 가능한 경우 최신 `main`으로 rebase/merge해서 충돌을 로컬에서 먼저 확인한다.
- `CHANGELOG.md`와 `docs/SESSIONS.md`는 모든 PR이 상단을 수정하는 고충돌 파일이므로 `.gitattributes`의 `merge=union` 설정으로 자동 병합한다. 병합 후 중복/순서만 리뷰한다.
