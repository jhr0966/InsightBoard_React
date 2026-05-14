# ARCHITECTURE — 제조기술 로드맵 인사이트보드

> 모듈 경계와 데이터 플로우. 새 기능 추가 전 이 문서로 "어디에 들어갈 코드인가" 확정.

## 5단계 파이프라인

```
1. 데이터 입력              2. 저장·정제              3. AI 분석(SOLA)
┌────────────────┐        ┌────────────────┐        ┌────────────────┐
│ scraping/naver │  ───►  │ store/news_db  │  ───►  │ store/match    │ (M1: 룰)
│  + extract     │        │ roadmap/ingest │        │ sola/* (M2)    │
│ roadmap/ingest │        │ roadmap/query  │        │                │
└────────────────┘        └────────────────┘        └────────────────┘
                                                            │
                                  ┌────────────────┐        ▼
                                  │   ui tabs      │  ◄─── 4. 서비스 UI
                                  │ ingest/roadmap │
                                  │ news/sola/board│
                                  └────────────────┘
                                          │
                                          ▼
                                    5. 산출물 (M3)
```

`app.py`는 평탄 Streamlit 진입점, 위→아래 5탭 라디오 디스패치.

## 디렉토리 레이아웃

```
News_TEST/
├── app.py                   # 평탄 진입점
├── config.py                # .env 로드, 경로, LLM 라우팅
├── scraping/                # HTTP 수집 (단일 진입점 http.build_session)
│   ├── http.py              # ── _build_session, default_headers
│   ├── extract.py           # 날짜/키워드/셀렉터 공용
│   ├── naver.py             # 네이버 뉴스 검색
│   ├── google.py            # 구글 뉴스 RSS 검색
│   ├── tech_sites.py        # AI Times, 오토메이션월드 도메인 사이트
│   └── enrich.py            # 본문 fetch + LLM 키워드/요약 (캐시)
├── roadmap/                 # 조선소 엑셀 → 정규화 → Parquet
│   ├── schema.py            # 한국어 헤더 ↔ snake_case
│   ├── ingest.py            # 업로드/검증/저장
│   └── query.py             # by_dept, by_lv, filter_hierarchy
├── store/                   # 저장소·매칭·집계·캐시·북마크
│   ├── paths.py             # 일자별 디렉토리
│   ├── news_db.py           # 뉴스 Parquet load/save
│   ├── match.py             # 룰 기반 뉴스↔작업 매칭
│   ├── trends.py            # by_date / by_source / top_keywords
│   ├── cache.py             # 파일 기반 LLM 응답 캐시
│   ├── chat_log.py          # 채팅 히스토리 JSONL
│   └── bookmarks.py         # 북마크 JSONL (opportunity/proposal/news/task)
├── persona/                 # 사용자 부서·직무·관심사 (M4-β)
│   ├── schema.py            # Persona dataclass
│   ├── store.py             # data/persona/profile.json JSON 영구화
│   └── context.py           # LLM 시스템 프롬프트용 컨텍스트 블록
├── sola/                    # LLM 분석 엔진 (OpenAI 호환)
│   ├── client.py            # ── chat(messages, ...) 단일 호출 진입점
│   ├── prompts.py           # 시스템 프롬프트 (요약/제안/채팅/인사이트/매트릭스)
│   ├── summarize.py         # 뉴스 요약
│   ├── propose.py           # 자동화 과제 제안서 생성 (persona 주입)
│   ├── chat_ctx.py          # 채팅용 컨텍스트(뉴스+로드맵) 조립
│   ├── insight.py           # 부서별 한 문단 인사이트 (캐시)
│   └── opportunity.py       # 부서×공정 자동화 기회 매트릭스 + LLM 코멘트
├── ui/                      # Streamlit — 5개 업무 메뉴
│   ├── sidebar.py           # 페르소나 설정 + 업무 흐름 네비 + LLM 상태
│   ├── styles.py            # CSS 주입
│   ├── task_tree.py         # 부서→Lv1→Lv2→Lv3 드릴다운 위젯
│   ├── home_tab.py          # 📊 오늘의 보드 (페르소나 기반 오늘 인사이트)
│   ├── ingest_tab.py        # 🧱 데이터 관리: 수집·Enrich
│   ├── roadmap_tab.py       # 🧱 데이터 관리: 로드맵 업로드
│   ├── board_tab.py         # 🔎 인사이트 분석
│   ├── sola_tab.py          # 🤖 SOLA 작업실: 요약·제안서·채팅
│   ├── news_tab.py          # 📦 산출물 보관함: 뉴스 콘텐츠
│   └── bookmarks_tab.py     # 📦 산출물 보관함: 북마크
├── assets/styles.css
├── data/  (.gitignore)
│   ├── news/YYYY-MM-DD/*.parquet
│   ├── roadmap/roadmap_*.parquet
│   └── sola/
└── tests/
```

## 모듈 계약

### scraping
- `scraping.http.build_session()` — 외부 HTTP의 **단일 진입점**. 다른 모듈은 `requests` 직접 import 금지.
- `scraping.naver.search(keyword, max_results) -> list[dict]` — HTML 스크래핑.
- `scraping.google.search(keyword, max_results) -> list[dict]` — RSS 기반.
- article dict: `title, press, date, published_at, link, summary, keywords, source, query`.
- `source` 값: `naver` | `google` (탭에서 둘 다 또는 개별 선택).

### roadmap
- `roadmap.schema.COLUMN_MAP` — 첨부3 한국어 헤더 → snake_case.
- 정규화 컬럼: `team, dept, lv1, lv2, lv3, task, sub_task, task_def, sws_no, sws_name`.
- 필수: `team, dept, lv1, lv2, lv3, task`.
- `roadmap.ingest.ingest_excel(fileobj, sheet_name) -> IngestResult` — 검증·Parquet 저장.
- `roadmap.query.load_latest() / by_dept() / by_lv() / filter_hierarchy()`.

### store
- `store.news_db.save_articles(articles, source) -> Path | None` — 오늘자 디렉토리에 저장.
- `store.news_db.load_latest(source) / load_all_today() -> DataFrame`.
- `store.match.score_matches(news_df, roadmap_df, top_k) -> DataFrame`
  - 컬럼: `dept, lv1, lv2, lv3, task, sub_task, news_title, link, score`.

### sola (M2 — 구현)
- `sola.client.chat(messages, *, model, temperature, max_tokens) -> str` — OpenAI SDK 단일 호출 진입점.
- `sola.client.is_configured() -> bool` — 환경변수 점검 (UI 상태 표시용).
- `sola.summarize.summarize_news(df) -> str` — 마크다운 요약.
- `sola.propose.propose_for_task(task: dict, news_df) -> str` — 마크다운 자동화 제안서.
- `sola.chat_ctx.build_context_block(news_df, roadmap_df) -> str` — 채팅 시스템 프롬프트에 붙일 컨텍스트.
- LLM 호출 실패는 `LLMNotConfigured` 또는 일반 Exception 으로 그대로 전파, UI 에서 사용자 메시지로 변환.

### ui
- 모든 탭은 `render()` 단일 진입점.
- pending flag 패턴만: `if st.button(): st.session_state["_do_X"] = True` → 본문에서 `pop` → `st.rerun()`.
- `on_click=` 금지. CLAUDE.md §3.

## 세션 상태 prefix

| prefix | 도메인 |
|---|---|
| `ins_*` | 뉴스 수집 (검색어, 소스, 결과 상태) |
| `rm_*` | 로드맵 업로드 (업로드 파일, 상태) |
| `board_*` | 인사이트보드 필터 |
| `sola_*` | LLM 요약/제안서/채팅 결과 + 채팅 히스토리 |
| `prop_*` | 제안서 생성 화면 입력값 |
| `_do_*`, `_pending_*` | pending flag, 다음 run 본문에서 1회 처리 |

## 환경변수 (`.env`)

- `LLM_BACKEND=groq|internal|ollama` (기본 groq)
- `LLM_API_KEY` — 백엔드별 키
- `LLM_BASE_URL` — 사내 API 사용 시 명시
- `LLM_MODEL` — 명시 안 하면 백엔드별 기본값

## 배포

Streamlit Cloud가 `main` 트래킹. 작업 브랜치 → PR → 머지 → 즉시 배포.
