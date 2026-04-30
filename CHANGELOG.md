# Changelog

모든 주요 변경은 여기에 기록한다. 포맷: [Keep a Changelog](https://keepachangelog.com/) + SemVer.
릴리스 = `main` 머지 시점.

## [Unreleased]

### Changed
- `app.py` import 구문을 정리해 중복 import(`insights`, `cardnews`, `LocalNewsRepository`)를 제거하고 엔트리 스크립트 의존성을 단순화.
- `app.py` 인라인 `<style>` 블록을 제거하고 `assets/styles.css`를 로딩하는 `_inject_global_styles()`로 이관해 UI 스타일 자산을 코드와 분리.

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
