# Changelog

모든 주요 변경은 여기에 기록한다. 포맷: [Keep a Changelog](https://keepachangelog.com/) + SemVer.
릴리스 = `main` 머지 시점.

## [Unreleased]

### Added (M4-α — 본문 enrich + 도메인 사이트)
- `scraping/enrich.py` — 기사 본문 fetch + LLM 키워드/요약, 본문 해시 캐시.
  - `fetch_content(url)` 단일 진입점, 다양한 본문 selector + p-fallback.
  - `enrich_one(article, with_llm)`, `enrich_articles(articles, progress_cb)` — Streamlit 진행률 콜백 호환.
  - LLM 미설정 시 본문만 채우고 graceful degrade.
- `scraping/tech_sites.py` — AI Times, 오토메이션월드 도메인 사이트.
  - `TECH_SITES` dict 로 확장 가능.
  - 휴리스틱(제목 길이 + 같은 root domain + nav blocklist) 기반 추출.
  - `search_all()` 사이트별 실패 swallow + 합본.
- `sola/prompts.py` — `SYSTEM_KEYWORD_EXTRACT`, `SYSTEM_SUMMARY_SHORT` 추가.
- `store/news_db.py` 스키마 확장 — `content`, `keywords_llm`, `summary_llm`, `enriched_at` 컬럼.
  - `_normalize_loaded()` 로 과거 Parquet 도 안전 로드.
  - `drop_duplicates(keep="last")` 로 enrich 결과가 원본을 덮어쓰도록.
- `ui/ingest_tab.py` 재작성 — 멀티 소스 선택, "본문 Enrich" 버튼, Streamlit 진행률, LLM 키워드 뱃지·LLM 요약 카드 표시.
- 테스트 10건 추가 (`test_enrich.py` 6 + `test_tech_sites.py` 4). 전체 45/45 통과.

### Added (M3 — 트렌드 + 부서별 AI 인사이트 + 채팅 영구화)
- `store/cache.py` — 파일 기반 LLM 응답 캐시 (SHA1 키, UTF-8 텍스트). 동일 입력에 LLM 재호출 방지.
- `store/trends.py` — `by_date` / `by_source` / `top_keywords` 집계.
- `store/chat_log.py` — 채팅 히스토리 JSONL 영구 저장 (`data/sola/chat_history.jsonl`). 새로고침 후에도 복원.
- `sola/insight.py` — 부서 단위 한 문단 인사이트 생성. (부서·뉴스셋·모델) 조합으로 캐시.
- `sola/prompts.SYSTEM_INSIGHT` 추가 — 1~2문장 평문 출력 가정.
- `ui/board_tab.py` 강화 — 트렌드(일자별·소스별) 차트 + 버튼 트리거 부서별 AI 인사이트 카드(2열 그리드).
- `ui/sola_tab.py` — 채팅 히스토리 자동 로드/저장, 초기화 버튼이 디스크 캐시도 함께 삭제.
- `tests/test_m3_cache_trends.py` (8건) + `tests/test_sola_insight.py` (3건) — 캐시·트렌드·채팅 영구화·인사이트 캐싱 동작 검증. 전체 35/35 통과.

### Added (M2 — 구글 뉴스 + SOLA LLM 채팅)
- `scraping/google.py` — 구글 뉴스 RSS(`news.google.com/rss/search`) 기반 검색. 표준 라이브러리 ElementTree 로 파싱(추가 의존성 없음).
- `ui/ingest_tab.py` 소스 선택 UI — 네이버 / 구글 / 둘 다.
- `sola/client.py` — OpenAI 호환 SDK 단일 호출 진입점, `LLM_BACKEND` 스위치, `LLMNotConfigured` 예외.
- `sola/prompts.py` — 시스템 프롬프트 3종 (요약/제안서/채팅).
- `sola/summarize.py` — 뉴스 DataFrame → 마크다운 요약.
- `sola/propose.py` — 작업 1건 + 매칭 뉴스로 자동화 과제 제안서 마크다운.
- `sola/chat_ctx.py` — 채팅 시 오늘 뉴스 헤드라인·로드맵 분포를 컨텍스트로 자동 첨부.
- `ui/sola_tab.py` 재작성 — 3 sub-mode (뉴스 요약 / 자동화 과제 제안서 / 채팅). 채팅은 `st.chat_message`/`st.chat_input` 사용, 히스토리는 세션에 보관, 제안서는 마크다운 다운로드 지원.
- `tests/test_google_search.py` — RSS 파싱 / 빈 키워드 / 중복 제거 / HTTP 실패 회귀 (4건).
- `tests/test_sola.py` — 요약/제안서 입력 포맷팅 + 컨텍스트 조립 (4건).
- `tests/test_sola_client.py` — 환경변수 미설정 분기 + OpenAI 호출 라우팅 (4건).

### Changed
- `config.py` — `python-dotenv` 사용해 `.env` 자동 로드 (없으면 무시).
- `requirements.txt` — `openai>=1.40`, `python-dotenv` 추가, 불필요한 `Pillow` 제거.
- `docs/ARCHITECTURE.md` — sola 모듈 계약 · 새 세션 prefix(`sola_*`, `prop_*`) 반영.

### Added (M1 — 인사이트보드 시스템 처음부터 재구성)
- `config.py` — `.env` 기반 LLM 라우팅(`LLM_BACKEND=groq|internal|ollama`) 및 데이터 경로 상수.
- `.env.example` — Groq 기본 / 사내 OpenAI 호환 API 전환용 템플릿.
- `scraping/` 패키지 — `http.build_session()` 단일 진입점, `naver.search()`, 공용 `extract.py`.
- `roadmap/` 패키지 — 첨부 엑셀(Master_Table) 한국어 헤더 → snake_case 정규화, 검증, Parquet 저장.
  - 정규화 스키마: `team/dept/lv1/lv2/lv3/task/sub_task/task_def/sws_no/sws_name`.
- `store/` 패키지 — 일자별 뉴스 Parquet, 룰 기반 뉴스↔작업 매칭(`store.match.score_matches`).
- `ui/` 패키지 — 5탭 Streamlit UI(`ingest_tab`, `roadmap_tab`, `news_tab`, `sola_tab`, `board_tab`) + `styles.py`.
- `app.py` 평탄 진입점 — 사이드바 5단계 라디오 디스패치, pending flag 패턴 준수.
- `tests/conftest.py` — `data/` 경로를 tmp_path로 격리.
- `tests/test_roadmap_ingest.py`, `tests/test_scraping_http.py`, `tests/test_news_db.py` — 12개 단위 테스트.

### Changed
- `requirements.txt` — `pyarrow`, `openpyxl` 추가 (Parquet · xlsx).
- `docs/ARCHITECTURE.md` — 5단계 파이프라인·새 디렉토리 구조로 전면 갱신.

### Removed
- `scraper.py`, `insights.py`, `cardnews.py`, `local_store.py`, `shipyard_store.py`,
  `proposal_engine.py`, `proposal_filters.py`, `workspace_overview.py`, `workspace_ui.py`,
  `data_quality.py` — 인사이트보드 시스템 재설계에 따라 폐기. 스크래핑 로직은 `scraping/`에 슬림하게 재구현.
- `components/`, 기존 `tests/test_*` 5종 — 폐기 모듈에 종속되어 함께 제거.

### Changed (이전 작업, 변경 없음)
- `app.py` import 구문을 정리해 중복 import(`insights`, `cardnews`, `LocalNewsRepository`)를 제거하고 엔트리 스크립트 의존성을 단순화.
- `app.py` 인라인 `<style>` 블록을 제거하고 `assets/styles.css`를 로딩하는 `_inject_global_styles()`로 이관해 UI 스타일 자산을 코드와 분리.
- `app.py`에 신규 진입 모드 `🏠 워크스페이스`를 추가하고, 수집/제안 현황을 요약하는 대시보드형 홈 화면을 연결.
- 워크스페이스 렌더/메트릭 계산 로직을 `workspace_ui.py`, `workspace_overview.py`로 분리해 기능별 구조화를 시작.
- `🧪 데이터 품질` 모드를 추가해 필수 필드 누락률과 상위 출처 분포를 앱 내에서 즉시 점검할 수 있도록 개선.
- `🏭 조선소 작업 데이터` 화면에서 업로드 데이터가 없을 때를 대비해 팀/공정/작업 기반의 페이크 데이터를 즉시 생성하는 기능을 추가.
- `🤝 자동화 과제 제안` 화면에 팀/공정 필터를 추가해 필요한 작업군만 추려 제안을 생성할 수 있도록 개선.
- `🎨 카드뉴스` 화면에서 선택 기사 PNG 생성/다운로드와 다중 기사 PNG 덱 ZIP 생성/다운로드를 지원하도록 확장.

### Added
- `local_store.py` 추가 — Local First Phase 1 시작을 위해 뉴스 배치를 `data/raw/news/*.jsonl` + `data/processed/news/*.parquet`로 저장/복구하는 유틸리티 제공.
- `tests/test_local_store.py` 추가 — LocalNewsRepository 저장/복구 및 빈 입력 케이스 검증.
- `shipyard_store.py` 추가 — 조선소 작업 데이터 Excel 업로드 raw 저장, 필수 컬럼 검증, Parquet 저장 파이프라인 제공.
- `tests/test_shipyard_store.py` 추가 — 조선소 업로드 성공/필수 컬럼 누락 검증.
- `proposal_engine.py` 추가 — 작업-뉴스 토큰 중첩 기반 추천 스코어링 및 작업별 추천 생성.
- `tests/test_proposal_engine.py` 추가 — 스코어링/추천 top-k 기본 동작 검증.
- `proposal_engine.py`에 제안서 Markdown 렌더(`proposals_to_markdown`) 및 아티팩트 저장(`save_proposals_artifacts`) 추가.
- `tests/test_app_pages_smoke.py` 추가 — Streamlit 4개 페이지의 기본 렌더링 스모크 테스트 자동화.
- `Makefile`에 `test` 타깃 추가 (`pytest -q tests/test_app_pages_smoke.py`).
- `requirements.txt`에 `pytest` 추가.
- `README.md`에 페이지 스모크 테스트 실행 가이드 추가.
- `.streamlit/config.toml` 추가 — Streamlit 테마/서버 실행 기본값 표준화.
- `scripts/dev_setup.sh` 추가 — 가상환경 생성·의존성 설치 원클릭 세팅 스크립트.
- `Makefile` 추가 — `install/run/check/format/clean` 개발 명령 표준화.
- `docs/VIBE_CODING_BLUEPRINT.md` 추가 — 뉴스+조선소 자동화 과제 시스템의 전략/아키텍처/로드맵 정의.

### Changed
- `app.py`가 시작 시 최근 로컬 저장본(`naver`, `tech`)을 자동 로드하도록 변경.
- `app.py`에서 뉴스 수집 성공 시 배치 결과를 자동으로 로컬 저장하고 저장 경로를 UI에 표시하도록 변경.
- `local_store.py`에 `NewsRepository` 추상 인터페이스와 `LocalNewsRepository` 구현체를 도입해 향후 DB 저장소 전환 기반을 마련.
- `app.py` 사이드바에 `🏭 조선소 작업 데이터` 모드를 추가하고 업로드 처리 흐름을 연결.
- `tests/test_app_pages_smoke.py`가 신규 모드 옵션을 검증하도록 확장.
- `shipyard_store.py`가 엑셀 엔진 미설치 시 사용자 안내 에러를 반환하도록 보완.
- `shipyard_store.py`에 최신 작업 Parquet 로더(`load_latest_shipyard_tasks`) 추가.
- `app.py`에 `🤝 자동화 과제 제안` 모드를 추가해 작업-뉴스 추천 요약/상세 확인 가능.
- `app.py` 제안 화면에서 JSON/Markdown 다운로드와 아티팩트 경로 표시를 지원하도록 확장.
- `README.md`에 Streamlit 개발환경 빠른 시작 절차와 blueprint 문서 링크를 추가.
- `scraper.py`에 `published_at`(UTC ISO8601) 정규화 로직을 추가해 상대시간(예: N분 전/시간 전/일 전)을 절대시각으로 저장하도록 개선.
- `insights.trend_by_date`가 `published_at` 우선 집계를 사용하도록 변경해 날짜 트렌드 정확도를 개선.
- `app.py` 테이블 컬럼 설정에 `발행시각(UTC)` 표시를 추가.
- `docs/ARCHITECTURE.md` article 스키마에 `published_at` 필드를 명시.

### Changed
- `insights.py` 입력을 `list[dict]` (rename 전 article) 로 변경 — `articles_to_dataframe` 의 한국어 컬럼 DataFrame 과 혼동 방지.
- `docs/ARCHITECTURE.md` article 스키마를 실제 키 (`link`, `img_url`) 로 정정.
- `app.py` 사이드바 라디오에 **📊 인사이트 보드**, **🎨 카드뉴스** 모드 추가 — 스크래퍼가 모은 기사를 공유 pool 로 집계·렌더.
- `requirements.txt`: `streamlit>=1.32`, `Pillow` 추가.

### Added
- `README.md` — 실행·문서 라우팅·검증 명령 요약.
- `docs/INVARIANTS.md` **I-12 레거시 예외** 섹션 — 기존 세션 키 (`articles_naver` 등)와 `render_*` 2개는 별도 브랜치 마이그레이션 전까지 예외.
- `CLAUDE.md` 상시 작업 규칙 문서 신규.
- `DEV_GUIDELINES.md`를 News 3대 도메인(스크래핑·인사이트·카드뉴스) 버전으로 재작성.
- `docs/ARCHITECTURE.md` — 모듈 경계·데이터 플로우·세션 키 prefix.
- `docs/INVARIANTS.md` — I-1 ~ I-11 (pending flag, HTTP 단일 진입점, XSS 방어 등).
- `docs/WORKFLOW.md` — 브랜치→개발→커밋→머지 루프.
- `docs/SESSIONS.md` — 세션 로그.
- `insights.py` 스텁 — `by_press`, `by_keyword`, `trend_by_date`, `related_articles` 시그니처 고정.
- `cardnews.py` 스텁 — `render_html`, `render_png`, `render_deck`, `available_templates`.
- `assets/styles.css` — 기존 `app.py` 인라인 스타일에서 토큰 추출 skeleton.
- `components/` 디렉터리 (`card/`, `filter_bar/`, `cardnews_template/`) placeholder.

### Changed
- 없음 (코드 동작 변경 없음, 문서·스캐폴딩만 추가).

### Deprecated
- `app.py`의 `render_cards_html` (차기 세션에서 `cardnews.render_html`로 이관 예정).

---

## 템플릿 (새 세션 복사용)

```md
## [Unreleased]

### Added
- `.streamlit/config.toml` 추가 — Streamlit 테마/서버 실행 기본값 표준화.
- `scripts/dev_setup.sh` 추가 — 가상환경 생성·의존성 설치 원클릭 세팅 스크립트.
- `Makefile` 추가 — `install/run/check/format/clean` 개발 명령 표준화.
- `docs/VIBE_CODING_BLUEPRINT.md` 추가 — 뉴스+조선소 자동화 과제 시스템의 전략/아키텍처/로드맵 정의.

### Changed
- `README.md`에 Streamlit 개발환경 빠른 시작 절차와 blueprint 문서 링크를 추가.

### Added
- ...

### Changed
- ...

### Fixed
- ...

### Removed
- ...
```
