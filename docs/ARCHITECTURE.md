# ARCHITECTURE — 제조기술 로드맵 인사이트보드 (v2)

> 모듈 경계와 데이터 플로우. 새 기능 추가 전 이 문서로 "어디에 들어갈 코드인가" 확정.
> v2 셸 (5영역 디스패치 · SQLite task_defs · 글로벌 SOLA 채팅 패널) 기준.

---

## 한눈에

```
사용자
  │
  ▼
┌─────────────────────────────────────────────────────────┐
│  app.py (평탄 디스패처)                                 │
│   sidebar.render() → area 슬러그 → if/elif 5분기        │
│   chat_panel.consume_send_if_any() (어느 area든 송신)   │
└─────────────────────────────────────────────────────────┘
  │
  ├── ui/app_shell  (topbar · 좌측 nav · 우측 SOLA 패널 · ⌘K 팔레트)
  ├── ui/sidebar    (페르소나 카드 · 5-nav · LLM 상태)
  ├── ui/chat_panel (본문 끝 글로벌 채팅 expander · area_key 별 영구화)
  │
  └── area 5종 (v2 화면, 각 render() + chat_context_block() 한 쌍)
        ├── 📊 board_v2          → KPI · 기회 · 트렌드 · 매트릭스 · 탑스토리
        ├── 🧱 data_management_v2 → 뉴스 수집 · 라이브러리 · 작업 정의 CRUD
        ├── 🔎 insights_v2        → 트렌드 · 매칭 · 자동화 기회
        ├── 🤖 sola_workshop_v2   → 풀스크린 LLM 채팅 (자체 채팅, 패널 미렌더)
        └── 📦 archive_v2         → 북마크 · 채택 의사결정
```

`app.py` 는 위→아래 스크립트. area 분기 + chat 송신 핸들러 + 페르소나 온보딩 모달만 담는다. 마크업/state 로직은 모두 `ui/*_v2.py` 내부.

---

## 5영역 디스패치 (`app.py`)

| Area 슬러그 | 모듈 | `render()` | `chat_context_block()` |
|---|---|---|---|
| `📊 오늘의 보드` | `ui/board_v2.py` | ✔ | ✔ |
| `🧱 데이터 관리` | `ui/data_management_v2.py` | ✔ | ✔ |
| `🔎 인사이트 분석` | `ui/insights_v2.py` | ✔ | ✔ |
| `🤖 SOLA 작업실` | `ui/sola_workshop_v2.py` | ✔ | (자체 풀스크린, 글로벌 패널 미렌더) |
| `📦 산출물 보관함` | `ui/archive_v2.py` | ✔ | ✔ |
| (모달) 프로필 설정 | `ui/persona_page.py` | ✔ | ✔ |

- **area 선택**: `?app_area=<quoted>` 쿼리 파라미터 → `sidebar.render()` 가 읽고 `session_state["app_area"]` 에 저장 후 반환.
- **chat_context_block(persona)**: 현재 화면이 보여주는 데이터를 채팅 LLM 컨텍스트로 직렬화. `chat_panel.consume_send_if_any` 가 `session_state["_chat_context_for_sola"]` 를 함께 전송.
- **SOLA 작업실**: 풀스크린 채팅. 본문 끝 글로벌 채팅 패널 (`chat_panel.render`) 은 호출하지 않는다 (중복 방지).
- **인계 URL**: `?app_area=...&from=<kind>&dept=...` 으로 보드/인사이트 카드 → SOLA 작업실 prefill. 단일 진입점 `board_v2._sola_handoff_href` / `archive_v2._edit_handoff_href` (→ INVARIANTS I-16).

---

## 디렉토리 레이아웃

```
News_TEST/
├── app.py                       # 평탄 디스패처 (≤120줄)
├── config.py                    # .env / st.secrets / LLM 라우팅 / 데이터 경로
│
├── scraping/                    # 외부 HTTP 수집 — 단일 진입점 http.build_session()
│   ├── http.py                  # _build_session · UA 로테이션 · 재시도
│   ├── extract.py               # 본문/날짜/키워드 공용 파서
│   ├── naver.py                 # 네이버 뉴스 검색
│   ├── google.py                # 구글 뉴스 RSS
│   ├── rss.py                   # 일반 RSS 피드
│   ├── tech_sites.py            # AI Times · 오토메이션월드 도메인 추출
│   ├── enrich.py                # 본문 fetch + LLM 키워드/요약 (캐시)
│   └── run_daily.py             # 일일 배치 진입점 (cron)
│
├── roadmap/                     # 조선소 작업 정의 엑셀 → 정규화 → 저장
│   ├── schema.py                # 한국어 헤더 ↔ snake_case
│   ├── ingest.py                # 업로드/검증/저장 (Parquet + SQLite UPSERT)
│   ├── query.py                 # load_latest()/by_dept()/by_lv() — SQLite 우선, Parquet fallback
│   ├── sqlite_sync.py           # Parquet → SQLite 마이그/동기
│   ├── task_def_form.py         # 작업 정의 CRUD UI 헬퍼
│   └── task_def_json.py         # task_def 직렬화/import-export
│
├── store/                       # 저장소·매칭·집계·캐시·북마크
│   ├── paths.py                 # 일자별 디렉토리, latest_parquet
│   ├── news_db.py               # 뉴스 Parquet load/upsert (일자별)
│   ├── task_defs_db.py          # SQLite: task_defs + task_def_history
│   ├── match.py                 # 룰 기반 뉴스↔작업 매칭 (score_matches)
│   ├── trends.py                # by_date / by_source / top_keywords
│   ├── cache.py                 # 파일 기반 LLM 응답 캐시
│   ├── chat_log.py              # 채팅 히스토리 JSONL (chat_key 별 파일)
│   ├── bookmarks.py             # 북마크 JSONL (opp/proposal/news/task + status)
│   ├── sola_threads.py          # SOLA thread 메타 JSON
│   └── sources.py               # 뉴스 출처 on/off · 커스텀 RSS
│
├── persona/                     # 사용자 부서·직무·관심 공정
│   ├── schema.py                # Persona dataclass
│   ├── store.py                 # data/persona/profile.json 영구화
│   └── context.py               # LLM 시스템 프롬프트용 컨텍스트
│
├── sola/                        # LLM 호출·프롬프트·산출 포맷
│   ├── client.py                # chat(messages, ...) — OpenAI SDK 단일 호출
│   ├── prompts.py               # 시스템 프롬프트 상수
│   ├── opportunity.py           # 부서×공정 자동화 기회 매트릭스
│   ├── board_brief.py           # 오늘의 보드 SOLA 브리핑
│   ├── trend_brief.py           # 트렌드 한 문단 브리핑
│   ├── side_context.py          # 사이드 패널 컨텍스트 블록 빌드
│   ├── preview.py               # LLM 미설정 시 입력 프리뷰
│   ├── refine.py                # 사용자 입력 정제
│   ├── thread_title.py          # SOLA thread 자동 제목
│   ├── propose.py               # ⚠ 데드 (production import 0, 테스트만)
│   ├── summarize.py             # ⚠ 데드
│   ├── insight.py               # ⚠ 데드
│   └── chat_ctx.py              # ⚠ 데드
│
├── ui/                          # Streamlit v2 셸 + 5영역
│   ├── app_shell.py             # render_topbar / render_app_side / render_app_sola
│   │                            # consume_panel_toggle · render_command_palette
│   ├── sidebar.py               # 좌측 nav (페르소나 + 5-area) — area 슬러그 반환
│   ├── chat_panel.py            # 본문 끝 글로벌 채팅 expander · consume_send_if_any
│   ├── styles.py                # CSS 토큰 · shell · streamlit override 주입
│   ├── components.py            # HTML 컴포넌트 빌더 (metric/status/action)
│   ├── onboarding.py            # 페르소나 4단계 마법사
│   ├── persona_page.py          # 페르소나 편집 폼 (모달)
│   ├── archive_v2.py            # 📦 산출물 보관함
│   ├── board_v2.py              # 📊 오늘의 보드
│   ├── data_management_v2.py    # 🧱 데이터 관리
│   ├── insights_v2.py           # 🔎 인사이트 분석
│   ├── sola_workshop_v2.py      # 🤖 SOLA 작업실
│   ├── task_def_manage.py       # 데이터 관리 안의 작업 정의 탭
│   ├── data_health.py           # 데이터 준비도 대시보드 (테스트 의존)
│   ├── layout.py                # ⚠ 데드 (main_and_chat 정의되어 있으나 production 호출 0)
│   └── task_tree.py             # ⚠ 데드 (production 호출 0)
│
├── assets/styles.css
├── data/  (.gitignore)
│   ├── news/YYYY-MM-DD/*.parquet
│   ├── roadmap/roadmap_*.parquet · task_defs.sqlite3
│   ├── persona/profile.json
│   ├── sola/chat/{chat_key}.jsonl · threads.json
│   └── bookmarks.jsonl
└── tests/                       # 654 tests, pytest -q
```

---

## 데이터 플로우

```
1) 수집
   사용자(데이터관리·수집 탭)        cron (scripts/daily_scrape.py)
        │                              │
        ▼                              ▼
   scraping/{naver,google,rss,         scraping/run_daily.py
   tech_sites} ─→ scraping/extract
        │
        ▼
   scraping/enrich (옵션, LLM 키워드/요약)
        │
        ▼
   store/news_db.upsert (data/news/YYYY-MM-DD/*.parquet)

2) 로드맵
   엑셀 업로드 (데이터관리·작업정의 탭)
        │
        ▼
   roadmap/ingest ──→ Parquet (data/roadmap/*.parquet)
                  └─→ store/task_defs_db UPSERT (SQLite)
        │
        ▼
   roadmap/query.load_latest  ── SQLite 비어있지 않으면 그 결과
                                 비어있으면 Parquet fallback

3) 매칭·기회
   roadmap.query.load_latest + store.news_db.load_today
        │
        ▼
   store/match.score_matches  (news_cols = title·summary·keywords 기본)
        │
        ▼
   sola/opportunity (LLM 코멘트 보강) → 보드 ④ · 인사이트 매트릭스

4) UI
   각 area.render() ─ chat_context_block(persona) ─→ session_state["_chat_context_for_sola"]
                                                  ─→ chat_panel.consume_send_if_any
                                                  ─→ sola.client.chat → chat_log.save_history
```

---

## 모듈 계약

### scraping
- `scraping.http.build_session()` — 외부 HTTP **단일 진입점**. 다른 모듈은 `requests` 직접 import 금지 (I-6).
- 아티클 dict: `title, press, date, published_at, link, summary, keywords, source, query`.
- enrich: `scraping.enrich.enrich_articles_parallel` 단일 진입점 (I-7).

### roadmap
- `roadmap.schema.COLUMN_MAP` — 한국어 헤더 → snake_case.
- 필수 컬럼: `team, dept, lv1, lv2, lv3, task`.
- `roadmap.ingest.ingest_excel(fileobj, sheet_name) -> IngestResult` — 검증·Parquet·SQLite 동시 저장.
- `roadmap.query.load_latest(prefer="sqlite")` — DataFrame 반환. **SQLite 우선, Parquet fallback** (스키마는 동일).

### store
- `store.news_db.save_articles(articles, source) -> Path` — 일자 디렉토리 Parquet.
- `store.task_defs_db` — SQLite. 테이블 `task_defs` (PK: process_id), `task_def_history`. 함수: `upsert · list_all · search · history`.
- `store.match.score_matches(news_df, tasks_df, top_k, news_cols=("title","summary","keywords")) -> DataFrame` — 룰 기반 점수.
- `store.bookmarks` — JSONL. 키: `bm_id, kind(opp|proposal|news|task), title, content, status(draft|adopted|rejected), created_at`.
- `store.chat_log.{save_history,load_history,reset}` — `chat_key` 별 `data/sola/chat/{key}.jsonl` (I-15).

### sola
- `sola.client.chat(messages, *, model, temperature, max_tokens) -> str` — OpenAI SDK 단일 호출.
- `sola.client.is_configured() -> bool` — LLM 상태 표시.
- `sola.prompts` — 시스템 프롬프트 상수. 직접 문자열 prompt 금지 (I-10 정신).
- `sola.opportunity` · `sola.board_brief` · `sola.trend_brief` — 화면별 LLM 산출 헬퍼.

### ui
- 모든 v2 화면: `render()` + `chat_context_block(persona)` 한 쌍.
- pending flag 패턴만 (I-1·I-2·I-3): `if st.button(): st.session_state["_do_X"] = ... ; st.rerun()`.
- `on_click=` 금지.
- HTML 출력 전 `html.escape()` (I-8).
- 인계 URL은 `_sola_handoff_href` / `_edit_handoff_href` 단일 진입점 (I-16).

---

## 세션 상태 prefix

| prefix | 도메인 |
|---|---|
| `sc_*` | 수집 (검색어·결과·debug) |
| `rm_*` | 로드맵 업로드 |
| `ins_*` | 인사이트 분석 화면 필터 |
| `sola_*` | SOLA 작업실 (thread·composer·결과) |
| `bm_*` | 북마크/보관함 |
| `_do_*`, `_*_pending` | pending flag, 다음 run 본문에서 1회 처리 |
| `_chat_context_for_sola` | area → chat 컨텍스트 임시 핸드오프 |
| `_board_brief_items` | 보드 ② brief 인계용 뉴스 리스트 (I-16) |
| `app_area`, `show_persona_editor` | 라우팅 상태 |

---

## 환경변수 (`.env` / `st.secrets`)

| 키 | 기본값 | 의미 |
|---|---|---|
| `LLM_BACKEND` | `groq` | `groq` / `internal` / `ollama` |
| `LLM_API_KEY` | — | 백엔드별 키 |
| `LLM_BASE_URL` | 백엔드 디폴트 | 사내 API 사용 시 명시 |
| `LLM_MODEL` | 백엔드 디폴트 | 모델 ID 오버라이드 |

모두 `config._env_or_secret(name, default)` 경유 (I-14). `os.getenv` 직접 호출 금지.

---

## 배포

Streamlit Cloud 가 `main` 트래킹. 작업 브랜치 → PR → 머지 → 즉시 배포.

---

## 알려진 데드 코드 (정리 예정 — `docs/REFACTOR_PLAN.md` Phase 4)

- `ui/layout.py` (218줄) — `main_and_chat` 컨텍스트매니저 정의되어 있으나 production 호출 0.
- `ui/task_tree.py` (74줄) — 드릴다운 위젯, production 호출 0.
- `sola/propose.py` · `sola/summarize.py` · `sola/insight.py` · `sola/chat_ctx.py` — 모두 production import 0 (테스트만). 결정-1·결정-3 후 부활 또는 삭제.
- `store/task_defs_db.upsert_many` — 호출처 0, docstring 의 "rollback" 주장과 실제 행별 commit 불일치.

전수 점검 결과·결정 사항·단계적 PR 계획: [`docs/REFACTOR_PLAN.md`](./REFACTOR_PLAN.md).
