# ARCHITECTURE — 제조기술 로드맵 인사이트보드

> 모듈 경계와 데이터 플로우. 새 기능 추가 전 이 문서로 "어디에 들어갈 코드인가" 확정.
> 스택: **React SPA(`web/`) + FastAPI(`api/`) + 도메인 백엔드(`scraping`·`roadmap`·`store`·`sola`·`persona`)**.
> (과거 Streamlit 셸 `app.py`·`ui/` 는 2026-06 은퇴.)

---

## 한눈에

```
브라우저 (React SPA, web/)
  │  타입드 fetch + SSE  (web/src/api/client.ts)
  ▼
FastAPI (api/)
  ├─ api/main.py        앱·CORS·/api/health
  ├─ api/deps.py        current_identity / Identity (no-op 인증 = Phase 2 교체점)
  ├─ api/schemas.py     Pydantic 모델 (+ 식별·감사 필드)
  └─ api/routers/*      얇은 위임 — 도메인 로직은 아래 백엔드에
        │
        ▼
도메인 백엔드 (라우터가 호출)
  ├─ scraping/   외부 HTTP 수집·enrich (단일 진입점 http.build_session)
  ├─ roadmap/    작업 정의 엑셀 → 정규화 → Parquet + SQLite
  ├─ store/      저장소·매칭·집계·캐시·북마크·스레드
  ├─ sola/       LLM 호출·프롬프트·산출 포맷 (provider 추상화)
  └─ persona/    사용자 부서·직무·관심 공정
```

- **계층 분리(절대 규칙)**: 프런트(`web/`)는 `api/` 계약만 소비한다. 도메인 로직은 백엔드에 두고 `api/routers/*` 는 위임만 한다.
- **타입 드리프트 가드**: `api/` 스키마를 바꾸면 `python scripts/gen_openapi.py && cd web && npm run gen:types` 로 `web/src/api/schema.ts` 재생성. OpenAPI 스냅샷 테스트가 검증.

---

## 화면 ↔ 라우터 매핑

| 화면 (React 페이지) | 주요 API 라우터 |
|---|---|
| `web/src/pages/Board.tsx` — 📊 오늘의 보드 | `board.py` · `trends.py` |
| `web/src/pages/Insights.tsx` — 🔎 인사이트 분석 | `insights.py` · `trends.py` · `opportunities.py` |
| `web/src/pages/Proposals.tsx` — 🤖 자동화 제안 + 보관함 | `proposals.py` · `bookmarks.py` |
| `web/src/pages/Collect.tsx` — 🗞 뉴스 수집 | `news.py` · `collect.py` · `sources.py` |
| `web/src/pages/TaskDefs.tsx` — 📋 작업 정의 | `taskdefs.py`(+ `roadmap.ingest`) |
| `web/src/pages/Persona.tsx` · `components/Onboarding.tsx` | `persona.py` · `prefs.py` |
| 앱 셸 `components/{Layout,Sidebar,Topbar,AssistantDrawer}.tsx` | `assistant.py`(SSE 챗+context) · `threads.py` |

- **앱 셸**: 좌 nav(`Sidebar`) · topbar(`Topbar`) · 우 SOLA 드로어(`AssistantDrawer`). 반응형(태블릿 드로어 오버레이 · 모바일 사이드바 오프캔버스)은 `web/src/styles/app.css` media query.
- **화면 인계**: 보드/인사이트/매트릭스 카드 → `?from=&dept=&lv3=` 쿼리로 SOLA 드로어 자동 검토(prefill). `Layout` 이 `?from=` 감지 시 드로어 자동 오픈.
- **SSE**: 어시스턴트 챗(`/api/assistant/chat`)·수집 진행(`/api/collect/stream`) 은 `data: {json}\n\n` 프레임 스트리밍. 프런트는 `fetch` + `res.body.getReader()` 파싱.

---

## 디렉토리 레이아웃

```
InsightBoard_React/
├── config.py                    # .env / (streamlit secrets fallback) / LLM 라우팅 / 데이터 경로
│
├── api/                         # FastAPI 백엔드 — React 가 소비하는 HTTP 계약
│   ├── main.py                  # 앱·CORS·/api/health
│   ├── deps.py                  # current_identity / Identity (no-op 인증)
│   ├── schemas.py               # Pydantic 모델 (식별·감사 필드)
│   └── routers/                 # taskdefs·bookmarks·news·trends·opportunities·proposals
│                                # ·collect·threads·assistant·board·persona·prefs·sources·insights·matches
│
├── web/                         # React SPA (Vite + TS + Router + Query)
│   └── src/
│       ├── api/{client,types,schema}.ts   # 타입드 fetch+SSE / schema.ts=openapi-typescript 자동생성
│       ├── pages/*.tsx                     # 화면 7종
│       ├── components/{Layout,Sidebar,Topbar,AssistantDrawer,Onboarding}.tsx
│       ├── components/ui/*                  # Card·KPIStatGrid·Chip·Tabs·Modal·Kanban·EmptyState …
│       ├── components/charts/*             # SVG: Line·Bar·Sparkline·BubbleMatrix·Heatmap
│       └── styles/{app,tokens,themes,ui}.css · screens/*.css
│
├── scraping/                    # 외부 HTTP 수집 — 단일 진입점 http.build_session()
│   ├── http.py · extract.py · naver.py · google.py · rss.py · tech_sites.py
│   ├── enrich.py                # 본문 fetch + LLM 키워드/요약 (캐시)
│   └── run_daily.py             # 일일 배치 진입점 (cron)
│
├── roadmap/                     # 작업 정의 엑셀 → 정규화 → 저장
│   ├── schema.py · ingest.py(+preview_excel) · query.py · sqlite_sync.py
│   └── task_def_form.py · task_def_json.py
│
├── store/                       # 저장소·매칭·집계·캐시·북마크
│   ├── paths.py · news_db.py · task_defs_db.py · match.py · trends.py · cache.py
│   ├── chat_log.py · bookmarks.py · sola_threads.py · sources.py · run_log.py
│   ├── _audit.py                # 식별·감사 5필드 표준 (stamp/backfill/now_iso)
│   └── repository.py            # 영구화 seam (Repository·JsonlRepository — Phase 2 교체점)
│
├── persona/                     # schema.py · store.py · context.py
│
├── sola/                        # LLM 호출·프롬프트·산출 포맷
│   ├── client.py                # facade — chat / chat_stream
│   ├── providers/*              # openai(내장·groq 호환) · anthropic  (LLM_PROVIDER 로 교체)
│   ├── prompts.py
│   ├── opportunity.py · board_brief.py · trend_brief.py
│   └── side_context.py          # orphan(보존) — 향후 AssistantDrawer 컨텍스트 일원화 연결점
│
├── scripts/                     # gen_openapi · daily_scrape · diagnose_article · refresh_articles · verify_scrape …
├── Dockerfile · render.yaml · Procfile · requirements*.txt   # 배포
├── data/  (.gitignore)          # news/*.parquet · roadmap/*.parquet · task_defs.sqlite3 · persona · sola · bookmarks
└── tests/                       # 백엔드 단위 테스트 (pytest -q, 462)
```

---

## 데이터 플로우

```
1) 수집
   React Collect (SSE /api/collect/stream)        cron (scripts/daily_scrape.py)
        │                                            │
        ▼                                            ▼
   scraping/{naver,google,rss,tech_sites} ─→ scraping/extract
        │
        ▼  scraping/enrich (옵션, LLM 키워드/요약)
        ▼
   store/news_db.upsert (data/news/YYYY-MM-DD/*.parquet) · store/run_log.record_run

2) 로드맵
   React TaskDefs 엑셀 업로드 → /api/taskdefs/upload(+/preview)
        │
        ▼  roadmap/ingest ──→ Parquet (data/roadmap/*.parquet)
        ▼                 └─→ store/task_defs_db UPSERT (SQLite)
   roadmap/query.load_latest  ── SQLite 우선, 비어있으면 Parquet fallback

3) 매칭·기회
   roadmap.query.load_latest + store.news_db.load_today
        │
        ▼  store/match.score_matches  →  sola/opportunity (LLM 코멘트)
        ▼
   /api/insights · /api/opportunities → 보드 · 인사이트 매트릭스·히트맵

4) LLM (어시스턴트·브리핑)
   React → /api/assistant/chat (SSE) · /api/board/brief · /api/proposals/*
        │
        ▼  api/routers → sola.client.chat / chat_stream → store(chat_log·sola_threads)
```

---

## 모듈 계약

### api
- `api/routers/*` 는 **얇게** — 검증·직렬화만 하고 도메인 로직은 `store`/`sola`/`roadmap`/`scraping` 에 위임.
- 모든 라우터는 `api/deps.current_identity`(no-op 인증=Phase 2 교체점)·식별/감사 필드(`store/_audit.py`) 적용.
- 스키마 변경 → OpenAPI 재생성(위 "타입 드리프트 가드"). 스냅샷 테스트(`tests/test_openapi_snapshot.py`)가 드리프트 차단.

### web
- `web/src/api/client.ts` 가 **유일한** HTTP 진입점(fetch+SSE). 페이지/컴포넌트는 이 클라이언트만 호출.
- `schema.ts` 는 자동생성(수정 금지). `types.ts` 는 dict 반환 엔드포인트의 손수 유지 타입.
- XSS: React 기본 escape. `dangerouslySetInnerHTML` 금지.

### scraping
- `scraping.http.build_session()` — 외부 HTTP **단일 진입점**. 다른 모듈의 `requests` 직접 호출 금지.
- 아티클 dict: `title, press, date, published_at, link, summary, keywords, source, query`.
- enrich: `scraping.enrich.enrich_articles_parallel` 단일 진입점.

### roadmap
- `roadmap.schema.COLUMN_MAP` — 한국어 헤더 → snake_case. 필수: `team, dept, lv1, lv2, lv3, task`.
- `roadmap.ingest.ingest_excel(...)` — 검증·Parquet·SQLite 동시 저장. `preview_excel(...)` — 저장 없이 diff 미리보기.
- `roadmap.query.load_latest(prefer="sqlite")` — SQLite 우선, Parquet fallback.

### store
- `store.news_db.save_articles(articles, source) -> Path`.
- `store.task_defs_db` — SQLite `task_defs`(PK process_id) + `task_def_history`. `upsert · list_all · search · history`.
- `store.match.score_matches(news_df, tasks_df, top_k, news_cols=(...)) -> DataFrame`.
- `store.bookmarks` — JSONL: `bm_id, kind(opp|proposal|news|task), title, content, status(draft|adopted|rejected), …`.
- `store.repository` — 영구화 seam(Phase 2 교체점, `INSIGHTBOARD_STORAGE`).

### sola
- `sola.client.chat(messages, …) -> str` · `chat_stream(...)` — provider facade.
- `sola.providers.*` — `openai`(groq 호환 base_url)·`anthropic`. `LLM_PROVIDER` 로 교체.
- `sola.prompts` — 시스템 프롬프트 상수. `sola.opportunity`·`board_brief`·`trend_brief` — 화면별 LLM 산출.

---

## 환경변수 (`.env` / 호스팅 env)

| 키 | 기본값 | 의미 |
|---|---|---|
| `LLM_PROVIDER` | `openai` | `openai` / `anthropic` |
| `LLM_BACKEND` | `groq` | `groq` / `internal` / `ollama` (base_url 라우팅) |
| `LLM_API_KEY` | — | 백엔드별 키 |
| `LLM_BASE_URL` / `LLM_MODEL` | 백엔드 디폴트 | 오버라이드 |
| `INSIGHTBOARD_DATA_ROOT` | `data/` | 데이터 루트(호스팅 디스크) |
| `INSIGHTBOARD_CORS_ORIGINS` | — | 프런트 도메인(정확 일치) |

모두 `config.*` 헬퍼 경유. `config.py` 는 `.env`(`os.getenv`) 우선, 과거 streamlit `st.secrets` fallback 만 try/except 로 보존(streamlit 미설치 시 빈 값).

---

## 배포

- **백엔드(Render)**: `render.yaml` 블루프린트(Docker, `uvicorn api.main:app`). env + `INSIGHTBOARD_CORS_ORIGINS`. 무료 플랜은 디스크 없음(ephemeral).
- **프런트(Vercel)**: Root=`web`, build-time `VITE_API_BASE`=백엔드 URL.
- 상세: [`docs/DEPLOY.md`](./DEPLOY.md).

---

## 알려진 orphan (보존)

- `sola/side_context.py` — 과거 Streamlit 사이드 채팅이 호출하던 컨텍스트 빌더. 현재 production 호출 0이나, React `AssistantDrawer` 컨텍스트 일원화 시 연결 대상으로 보존(`tests/test_side_context.py` 가 시그니처 검증).
