# SESSIONS — 작업 세션 로그

> **최신 세션이 상단.** 다음 세션은 상단 1개만 읽고 복원한다.
> 완료된 세션은 "✅ merged"로 닫는다.

---

## 2026-05-12 · M1 인사이트보드 시스템 처음부터 재구성

**브랜치:** `claude/plan-insight-board-system-5MfMe`
**카테고리:** `feat`
**상태:** in-progress (M1 PR 대상)

**기획 결정 (사용자 확정):**
- 첨부3(조선소 작업 정의) 엑셀 풍부한 계층을 모두 보존하도록 **스키마 확장**.
- SOLA: 사내 OpenAI 호환 API + 임시 무료 **Groq**, 기존 코드는 폐기하고 처음부터 재구성.
- 진행 순서: **M1(스키마·집계) → M2(SOLA) → M3(LLM UI)** 단계적.

**M1에서 한 일:**
1. 레거시 모듈 9종 + 종속 테스트 5종 + `components/` 삭제.
2. 새 패키지 레이아웃: `scraping/ roadmap/ store/ sola/ ui/`.
3. `config.py` — `.env` 기반 LLM 라우팅 (Groq / 사내 / Ollama), 데이터 경로 상수.
4. `roadmap/schema.py` — 첨부3 한국어 헤더 ↔ snake_case 매핑(`team/dept/lv1/lv2/lv3/task/sub_task/task_def/sws_no/sws_name`).
5. `roadmap/ingest.py` + `query.py` — 엑셀 → 검증 → Parquet, 부서/Lv별 집계, 계층 필터.
6. `scraping/http.py` — HTTP 단일 진입점(`build_session`, 재시도 어댑터).
7. `scraping/naver.py` — 네이버 뉴스 검색만 슬림하게 재구현.
8. `store/news_db.py` — 일자별 Parquet 저장/조회, `store/match.py` — 룰 기반 뉴스↔작업 매칭.
9. `ui/*` 5탭 — `ingest`/`roadmap`/`news`/`sola(M2 placeholder)`/`board`, pending flag 패턴 준수.
10. `app.py` 평탄 진입점 — 사이드바 5단계 라디오 디스패치.
11. 테스트 12개 통과: ingest 라운드트립, HTTP 어댑터, 매칭 스코어링, 저장소 입출력.
12. `docs/ARCHITECTURE.md` 전면 갱신, `CHANGELOG.md` [Unreleased] 추가.

**다음 세션 TODO (M2):**
- `sola/client.py` — OpenAI SDK 래퍼, `LLM_BACKEND` 스위치.
- `sola/summarize.py` — 일자별 뉴스 요약 (캐시 + 프롬프트 분리).
- `sola/match.py` — 룰 후보 → LLM 정제, `store.match.score_matches` 대체.
- `ui/sola_tab.py` — Q&A 채팅 / 자동화 과제 추출 UI.

**블로커:** 없음.

---

## 2026-04-30 · 앱 엔트리 정리 1차 (중복 의존성 제거)

**브랜치:** `work`
**카테고리:** `refactor`
**상태:** in-progress

**한 일:**
1. `app.py` 상단 import에서 중복 선언된 `insights`, `cardnews`, `LocalNewsRepository`를 제거해 엔트리 스크립트 가독성을 개선.
2. 코드 동작을 바꾸지 않는 안전한 범위의 리팩토링으로 정리.
3. `CHANGELOG.md` Unreleased에 변경 이력 추가.
4. `app.py`의 인라인 CSS를 제거하고 `assets/styles.css`를 읽어 주입하는 `_inject_global_styles()`로 이관.
5. `🏠 워크스페이스` 모드를 추가하고 수집/제안 KPI 요약 홈 화면을 `workspace_ui.py` + `workspace_overview.py`로 분리 구현.
6. `🧪 데이터 품질` 모드(`data_quality.py`)를 추가해 누락 필드/출처 분포를 즉시 확인할 수 있는 운영 점검 화면을 구현.
7. 조선소 업로드 전에도 흐름을 검증할 수 있도록 `create_fake_shipyard_tasks()`와 UI 생성 버튼을 추가해 팀/공정/작업 페이크 데이터를 parquet로 저장하도록 확장.
8. 자동화 과제 제안 화면에 팀/공정 필터(`proposal_filters.py`)를 추가해 타깃 작업군 중심으로 제안 생성이 가능하도록 개선.
9. 카드뉴스 화면에 PNG 단건 생성/다운로드 및 덱 ZIP 생성/다운로드를 추가하고 `tests/test_cardnews.py`로 기본 렌더 동작을 검증.

**다음 세션 TODO:**
- 렌더/스토리지/도메인 이벤트 핸들러를 기능별로 helper 함수 분리
- 미사용 컴포넌트 파일 참조 여부 검증 후 제거

**블로커:** 없음.

---

## 2026-04-28 · Phase 1 Step 4 (제안서 아티팩트 저장/다운로드)

**브랜치:** `work`
**카테고리:** `feat`
**상태:** in-progress

**한 일:**
1. `proposal_engine.py`에 `proposals_to_markdown`, `save_proposals_artifacts` 추가.
2. `app.py` 제안 화면에서 생성 결과를 세션에 보관하고 JSON/Markdown 다운로드 제공.
3. 생성 결과를 `data/artifacts/proposals/YYYY-MM-DD/`에 JSON/MD로 저장하고 경로 표시.
4. `tests/test_proposal_engine.py`에 아티팩트 저장/마크다운 렌더 검증 추가.

**다음 세션 TODO:**
- 추천 점수에 작업 난이도/효과 가중치 추가
- 제안서 템플릿(경영진 요약/현장 실행안) 2종으로 분리
- 카드뉴스 화면과 제안 화면 데이터 연동

**블로커:** 없음.

---

## 2026-04-28 · Phase 1 Step 3 (작업-뉴스 매칭 제안 화면)

**브랜치:** `work`
**카테고리:** `feat`
**상태:** in-progress

**한 일:**
1. `proposal_engine.py` 추가 — 작업-뉴스 토큰 중첩 기반 스코어링/추천(`suggest_for_tasks`) 구현.
2. `shipyard_store.py`에 최신 작업 Parquet 로더(`load_latest_shipyard_tasks`) 추가.
3. `app.py`에 신규 모드 `🤝 자동화 과제 제안` 추가(요약표 + 작업별 추천 상세).
4. `tests/test_proposal_engine.py` 추가 및 `tests/test_app_pages_smoke.py` 신규 메뉴 옵션 반영.
5. `README.md`, `CHANGELOG.md` 업데이트.

**다음 세션 TODO:**
- 제안 결과를 파일(JSON/MD)로 저장하는 export 기능 추가
- 추천 스코어에 비용/난이도/효과 가중치 반영
- 카드뉴스와 제안서 연결(선택 기사로 카드 자동 생성)

**블로커:** 없음.

---

## 2026-04-28 · Phase 1 Step 2 (조선소 작업 데이터 업로드 파이프라인)

**브랜치:** `work`
**카테고리:** `feat`
**상태:** in-progress

**한 일:**
1. `shipyard_store.py` 추가 — Excel 업로드 raw 저장, 필수 컬럼 검증, Parquet 저장 파이프라인 구현.
2. `app.py`에 신규 모드 `🏭 조선소 작업 데이터` 추가 및 업로드 UI/검증 결과 표시 연결.
3. `tests/test_shipyard_store.py` 추가 — 성공/필수 컬럼 누락 케이스 검증.
4. `tests/test_app_pages_smoke.py`에 신규 메뉴 옵션 검증 추가.
5. 엑셀 엔진 미설치(openpyxl) 환경에서도 사용자 안내 에러를 반환하도록 처리.

**다음 세션 TODO:**
- 업로드된 조선소 데이터 미리보기/필터링 UI 추가
- 뉴스-작업 매칭 스코어링 함수(룰 기반) 1차 구현
- 제안서 생성 템플릿과 근거 링크 연결

**블로커:** 없음.

---

## 2026-04-28 · Phase 1 착수 (Local First 저장소 시작)

**브랜치:** `work`
**카테고리:** `feat`
**상태:** in-progress

**한 일:**
1. `local_store.py` 추가 — 뉴스 수집 결과를 `jsonl + parquet`로 저장하는 로컬 저장소 유틸 구현.
2. `app.py` 시작 시 `naver`/`tech` 최신 로컬 배치를 자동 로드하도록 연결.
3. `app.py`에서 뉴스 수집 성공 시 자동 로컬 저장 + 저장 경로 캡션 노출.
4. `CHANGELOG.md` 업데이트.
5. `NewsRepository`/`LocalNewsRepository` 추상화 도입으로 저장소 스위치 준비.
6. `tests/test_local_store.py` 추가로 Local 저장/복구 동작 검증.

**다음 세션 TODO:**
- Shipyard Excel 업로드/검증/Parquet 저장 파이프라인 1차 구현
- `data/` 경로/스키마 검증 테스트 추가

**블로커:** 없음.

---

## 2026-04-27 · 페이지 테스트 가능 상태로 개선 (스모크 테스트 추가)

**브랜치:** `work`
**카테고리:** `test` + `docs`
**상태:** in-progress

**한 일:**
1. `tests/test_app_pages_smoke.py` 추가 — Streamlit 4개 모드 기본 렌더링 스모크 테스트 구현.
2. `Makefile`에 `test` 타깃 추가 (`pytest -q tests/test_app_pages_smoke.py`).
3. `requirements.txt`에 `pytest` 추가.
4. `README.md`에 테스트 실행 방법 추가.
5. `CHANGELOG.md` 업데이트.

**다음 세션 TODO:**
- 네트워크 의존 구간(mock) 분리해 더 안정적인 단위테스트 추가
- 카드뉴스 렌더 결과 스냅샷 테스트 도입

**블로커:** 없음.

---

## 2026-04-27 · Foundation 리팩토링 (published_at 정규화)

**브랜치:** `work`
**카테고리:** `refactor`
**상태:** in-progress

**한 일:**
1. `scraper.py`에 `normalize_published_at()` 추가, 네이버/포탈 수집 결과에 `published_at` 저장.
2. `insights.py` `trend_by_date()`가 `published_at` 우선 사용하도록 개선.
3. `app.py` 결과 테이블에 `발행시각(UTC)` 컬럼 표시 추가.
4. `docs/ARCHITECTURE.md` article 스키마에 `published_at` 필드 반영.
5. `CHANGELOG.md` 업데이트.

**다음 세션 TODO:**
- 수집 결과를 parquet/db로 저장하는 repository 계층 추가
- 작업 데이터(엑셀) 업로드 및 parquet 변환 파이프라인 추가
- 작업-뉴스 매칭 PoC 구현

**블로커:** 없음.

---

## 2026-04-27 · Streamlit 바이브코딩 운영 청사진/환경 셋업

**브랜치:** `work`
**카테고리:** `docs` + `chore`
**상태:** in-progress

**한 일:**
1. `.streamlit/config.toml` 생성 (테마/서버 기본값).
2. `scripts/dev_setup.sh` 생성 (venv + requirements 설치 자동화).
3. `Makefile` 생성 (`install`, `run`, `check`, `format`, `clean`).
4. `docs/VIBE_CODING_BLUEPRINT.md` 작성 (전략/아키텍처/로드맵/운영규칙).
5. `README.md`에 빠른 시작 절차 및 blueprint 링크 추가.
6. `CHANGELOG.md` [Unreleased] 업데이트.

**다음 세션 TODO:**
- DB 스키마 초안(`articles`, `tasks`, `embeddings`, `proposals`) 구체화
- 워드클라우드 + 시간대 트렌드 차트 구현
- 작업-뉴스 매칭 점수 함수 PoC 구현

**블로커:** 없음.

---

## 2026-04-23 · 바이브코딩 Readiness 개선

**브랜치:** `claude/organize-dev-guidelines-4VTac`
**카테고리:** `docs` + `feat`
**상태:** in-progress (같은 브랜치 push)

**한 일 (5건 · 1커밋):**
1. `insights.py` 시그니처를 `list[dict]` 로 변경 — `articles_to_dataframe` 한국어 컬럼 DataFrame 과 혼동 제거.
2. `docs/ARCHITECTURE.md` article 스키마 실제 키 (`link`, `img_url`) 로 정정.
3. `docs/INVARIANTS.md` **I-12 레거시 예외** 추가 — 기존 세션 키·`render_*` 2개는 별도 브랜치 이관 전까지 예외.
4. `app.py` 사이드바에 **인사이트 보드 / 카드뉴스** 모드 실제 동작 스켈레톤 추가 (스크래퍼 pool 공유).
5. `README.md` 추가 (실행·문서 라우팅·검증 명령).

**직전 검토에서 Blocker 였던 항목:** 모두 해소 ✅

**다음 세션이 할 일 (제안):**
- `refactor-session-keys`: `articles_naver/articles_tech/keyword_naver/debug_log` → `sc_*` prefix 일괄 rename.
- `feat-cardnews-migrate`: `render_cards_html`/`render_results` → `cardnews.render_html`/`render_deck` 로 이관, I-4 준수.
- `feat-cardnews-png`: `cardnews.render_png` + Streamlit `st.download_button` 으로 PNG export.
- `refactor-css-extract`: `app.py` 인라인 `<style>` → `assets/styles.css` 로 이관.

**블로커:** 없음.

---

## 2026-04-22 · 개발 가이드라인 셋업

**브랜치:** `claude/organize-dev-guidelines-4VTac`
**카테고리:** `docs`
**상태:** in-progress

**한 일:**
- `DEV_GUIDELINES.md`를 SOTONG_M 템플릿 → News 3대 도메인(스크래핑/인사이트/카드뉴스)에 맞게 재작성.
- `CLAUDE.md` 신규 작성 (상시 문서, 단일 참조점).
- `docs/ARCHITECTURE.md` — 모듈 계약·데이터 플로우·세션 키 prefix 규정.
- `docs/INVARIANTS.md` — I-1~I-11 정리 (Streamlit pending flag, HTTP 단일 진입점 등).
- `docs/WORKFLOW.md` — 브랜치→개발→커밋→머지 루프.
- `docs/SESSIONS.md` (이 파일).
- `CHANGELOG.md` [Unreleased] 초기 항목.
- 모듈 스텁: `insights.py`, `cardnews.py`.
- `assets/styles.css` 토큰 추출 skeleton.
- `components/` 디렉터리: `card/`, `filter_bar/`, `cardnews_template/`.

**다음 세션이 할 일 (제안):**
- `app.py` 세션 state 키를 `sc_*` prefix로 마이그레이션 (I-9 준수).
- `app.py`의 `render_cards_html` → `cardnews.render_html`로 이관 (I-4).
- `insights.py` 첫 실제 구현 (by_press, by_keyword, trend_by_date).
- `requirements.txt`에 `Pillow` 추가 (cardnews.render_png 구현 시).

**블로커:** 없음.

---
