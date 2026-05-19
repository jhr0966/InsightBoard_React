# Changelog

모든 주요 변경은 여기에 기록한다. 포맷: [Keep a Changelog](https://keepachangelog.com/) + SemVer.
릴리스 = `main` 머지 시점.

## [Unreleased]

### Fixed (scraping — `&nbsp;` 잔재 / "No Image" 다발 회귀)
- `scraping/enrich.py::_clean_article_text` 가 `html.unescape()` 를 두 번 호출해 RSS description 처럼 escape 된 HTML(예: `&amp;nbsp;`, `&lt;br&gt;`) 이 본문에 그대로 남던 회귀 해결.
- `_extract_image_url` selector 강화 — `og:image:secure_url`, `twitter:image:src`, `link[rel=image_src]`, `meta[itemprop=image]` 추가. `picture > source[srcset]` 와 `srcset` / `data-lazy-src` / `data-thumb` 등 lazy-loading 속성도 우선 탐색하도록 `_img_src_from_attrs` 도입. 광고/스페이서 필터 키워드(`1x1`, `transparent`) 보강.

### Changed (ingest — 수집 시 본문·이미지 자동 fetch)
- `ui/ingest_tab.py::_run_collect` 가 수집 직후 `_hydrate_articles()` 로 `enrich_articles(with_llm=False)` 를 호출해 본문·대표 이미지를 함께 저장. 진행 바는 소스별 갱신, 결과 메시지에 본문 확보 건수 노출. LLM 키워드/요약은 기존 "Enrich" 버튼에 그대로 분리.
- 회귀 가드: `tests/test_enrich.py` 에 `_clean_article_text` 의 entity decode + picture/srcset + lazy data-src 케이스 3건 추가.

### Changed (components — 빌더 출력 정리, markdown code-block 회귀 방어)
- `ui/components.py` 의 `metric_card`, `status_card`, `action_card`, `step_item` 가 4-space 들여쓰기로 시작하는 multi-line f-string을 반환해 실수로 `st.markdown` 경로로 보내면 code block으로 해석되던 회귀 원인을 제거. 각 빌더가 컬럼 0부터 시작하는 single-line concatenated f-string을 반환하도록 정리. `metric_grid` / `action_grid` / `step_guide` 시그니처와 출력 클래스/속성은 그대로.

### Fixed (home — 자동화 기회 Top 5 raw HTML 노출)
- `ui/home_tab.py` 538줄 뒤에 같은 "자동화 기회 Top 5" 섹션이 `st.markdown(..., unsafe_allow_html=True)` 로 중복 렌더되던 코드 제거. `metric_card` / `_top_opportunities_html` 의 출력은 4-space 들여쓰기로 시작해 markdown이 code block으로 처리해 화면에 `<div class="metric-card …">` 텍스트가 그대로 노출되던 회귀 해결. `tests/test_html_rendering.py` PASS.

### Changed (refactor — 인사이트보드 평탄화 / 재계산 제거)
- `ui/board_tab.py` 리팩토링: `_TrendsPayload` dataclass 도입, 카드 HTML 헬퍼 (`_dept_insight_card_html`, `_opportunity_card_html`, `_match_card_html`) 분리, 페르소나 강조 (`_persona_emphasis`) 와 부서 정렬 (`_ordered_depts`) 통합.
- 트렌드 섹션을 `_render_trend_brief` / `_render_trend_charts` / `_render_emergence` 로 분리, 오포튜니티 카드 그리드는 `_render_opportunity_cards`, 보드 진입부는 `_render_overview` 로 분리.
- `render()` 에서 `payload` / `cells` 를 한 번만 계산해 `_build_page_context` 에 전달 — 채팅 토글 시 동일 데이터 재계산 제거.
- 시그니처 보존 (테스트로 잠긴 `_insight_flow_html`, `_opportunity_to_sola_state`, `_opportunity_flow_context`), 동작 등가성 유지.

### Changed (UX — 사이드바 프로필 개선)
- `ui/sidebar.py` 의 페르소나 입력 폼을 사이드바에서 제거하고, 최상단 사용자 프로필 카드(큰 상반신 아바타 + 설정 정보 요약)로 교체.
- `ui/persona_page.py` 추가 — 아바타 프로필 카드 클릭 시 메인 영역에서 페르소나 편집 페이지를 열어 사이드바가 길어지지 않도록 개선.
- `assets/styles.css` 에 큰 프로필 아바타/상반신 카드 스타일 추가.
- `tests/test_sidebar_profile.py` 추가 — 프로필 카드 escape, 미설정 기본값, 페르소나 편집 옵션 헬퍼 회귀 테스트.

### Fixed (PR merge conflict 방지)
- `.gitattributes` 추가 — `CHANGELOG.md`, `docs/SESSIONS.md` 에 Git built-in `merge=union` 을 적용해 여러 PR이 같은 상단 로그를 수정할 때 발생하는 반복 merge conflict를 완화.
- `CLAUDE.md`, `DEV_GUIDELINES.md` 에 PR 충돌 방지 규칙 추가 — 최신 main 기반 새 브랜치 사용, PR 전 rebase/merge 확인, 고충돌 문서의 union merge 정책 명시.

### Added (UX 마무리 QA)
- `docs/UX_QA_CHECKLIST.md` 추가 — Phase 0~6 완료 상태, 자동화 테스트 결과, 메뉴별 수동 QA 시나리오, 남은 운영 검수 리스크 정리.
- `docs/UX_REDESIGN_PLAN.md` 에 2026-05-18 기준 Phase 0~6 구현 완료 상태와 대표 파일, 최종 QA 상태를 추가.

### Added (UX Phase 6 후속 — 제안서 작업장/보관함 연결)
- `ui/bookmarks_tab.py` 제안서 카드에 `작업장` CTA 를 추가해 보관된 제안서를 바로 SOLA 제안서 작업장 수정 모드로 열 수 있게 개선.
- `ui/proposal_workbench.py` 에 원본 북마크 업데이트, 상태/결정 메모 명시 저장, 다운로드 동선을 정리해 수정 결과가 보관함 기록으로 이어지도록 개선.
- `store.bookmarks.update_content` 추가 — 작업장에서 수정한 제안서 본문/태그/제목을 기존 북마크에 in-place 반영.
- `tests/test_bookmarks.py`, `tests/test_sola_workspace.py` 에 작업장 라우팅과 북마크 업데이트 회귀 테스트 추가.

### Added (UX Phase 6 — SOLA 작업실/산출물 보관함 정리)
- `ui/sola_tab.py` 에 작업 유형 카드와 SOLA 준비 상태 카드를 추가해 요약·제안서·채팅·보관함 흐름을 작업 단위로 안내.
- SOLA 뉴스 요약 결과를 다운로드하거나 산출물 보관함에 저장할 수 있는 동선을 추가.
- `store.bookmarks.summary_counts` 와 보관함 KPI 를 추가해 전체 산출물, 제안서, 채택 과제, 검토 중 상태를 한눈에 표시.
- `tests/test_sola_workspace.py` 와 `tests/test_bookmarks.py` 회귀 테스트를 추가해 작업 카드/준비 상태/보관함 집계를 검증.

### Added (UX Phase 5 — 인사이트 분석 실행 흐름)
- `ui/board_tab.py` 에 `트렌드 확인 → 로드맵 연결 → 기회 선별 → SOLA 제안` 단계 가이드를 추가해 분석 화면의 실행 흐름을 명확히 표시.
- 자동화 기회 카드에 `SOLA 제안` CTA 를 추가해 선택한 부서×공정 기회를 SOLA 제안서 생성 필터로 바로 전달.
- 인사이트 분석 사이드 컨텍스트에 실행 전환 대상 자동화 기회 Top 후보를 포함하도록 개선.
- `tests/test_board_flow.py` 추가 — 분석 흐름 StepGuide, SOLA 라우팅 상태, 기회 후보 context 회귀 테스트.

### Added (UX Phase 4 — 데이터 관리 준비 상태 대시보드)
- `ui/data_health.py` 추가 — 뉴스 DB, 본문 Enrich, 로드맵 DB, LLM 설정 상태를 한눈에 보는 데이터 준비 상태 대시보드.
- `app.py` 의 `데이터 관리` 메뉴 상단에 준비 상태 KPI와 품질 점검 카드를 표시해 상세 탭 진입 전 필요한 조치를 안내.
- `assets/styles.css` 에 데이터 품질 카드 그리드 스타일 추가.
- `tests/test_data_health.py` 추가 — 준비 상태 판정, Enrich 비율, HTML escape, context 요약 회귀 테스트.

### Added (UX Phase 3 — 오늘의 보드 추천 행동)
- `ui/home_tab.py` 에 데이터 준비 상태·페르소나·자동화 기회 점수를 기반으로 우선순위를 정하는 `추천 다음 행동` 카드 섹션을 추가.
- 오늘의 보드에 `자동화 기회 Top 5` 펄스 카드를 추가해 첫 화면에서 부서×공정 기준 실행 후보를 바로 확인하도록 개선.
- `assets/styles.css` 에 추천 행동 카드와 자동화 기회 펄스 카드 스타일을 추가하고, 홈 컨텍스트에 추천 행동/Top 기회를 포함해 사이드 SOLA 대화 품질을 개선.
- `tests/test_home_trend_widget.py` 에 추천 행동 우선순위, HTML escape, 내 부서 하이라이트, page context 회귀 테스트 추가.

### Added (UX Phase 2 후속 — 로드맵 업로드 단계 안내)
- `ui/roadmap_tab.py` 에 `엑셀 선택 → 시트 확인 → 검증·저장 → 매칭 준비` StepGuide 를 추가하고, 로드맵 작업/부서 수/Lv3 공정 현황을 공통 `metric_card` 로 표시.

### Added (UX Phase 2 후속 — 데이터 관리 단계 안내)
- `ui.components.step_item` / `step_guide` 추가 — 데이터 준비처럼 순서가 중요한 화면에 쓰는 단계 안내 컴포넌트.
- `ui/ingest_tab.py` 상단에 `키워드·소스 선택 → 수집·저장 → 본문 Enrich → 분석으로 이동` 4단계 가이드를 추가하고, 수집 현황을 공통 `metric_card`/`status_card` 로 정리.
- `tests/test_ui_components.py` 에 StepGuide escape/active 상태 회귀 테스트 추가.

### Changed (UX Phase 2 후속 — 빈 상태 통일)
- `roadmap_tab`, `board_tab`, `news_tab`, `bookmarks_tab`, `task_tree` 의 주요 빈 상태/준비 필요 안내를 공통 `status_card` 로 교체해 데이터 준비·분석·보관함 화면의 안내 문법 통일.
- `board_tab` 상단 KPI 를 공통 `metric_card` 기반으로 교체해 오늘의 보드와 인사이트 분석의 핵심 지표 카드 스타일 정렬.

### Added (UX Phase 2 — 공통 UI 컴포넌트)
- `ui/components.py` 추가 — `MetricCard`, `StatusCard`, `ActionCard` 계열 HTML 빌더를 공통화하고 모든 문자열을 escape 처리.
- `assets/styles.css` 에 Navy/Teal 제품 토큰과 metric/status/action 공통 카드 스타일 추가.
- `ui/home_tab.py` 의 오늘의 보드 KPI, 데이터 준비 안내, 빠른 행동 카드를 공통 컴포넌트로 교체.
- `tests/test_ui_components.py` 추가 — HTML escape, tone class allowlist, grid wrapper 회귀 테스트.

### Changed (UX Phase 1 — 앱 쉘)
- `app.py` 와 `ui/sidebar.py` 를 UX 개편 계획의 5개 업무 메뉴(`오늘의 보드`, `데이터 관리`, `인사이트 분석`, `SOLA 작업실`, `산출물 보관함`)로 1차 재구성. 기존 `탐색`/`작업실` 하위 탭에 섞여 있던 기능을 업무 목적별 메뉴로 분리.
- 홈 화면 문구와 빠른 행동 카드를 새 메뉴명에 맞게 갱신하고, 사이드바에 `데이터 준비 → 인사이트 분석 → SOLA 산출물 생성` 흐름 힌트 추가.
- `README.md` 와 `docs/ARCHITECTURE.md` 의 UI 구조 설명을 5개 업무 메뉴 기준으로 갱신.

### Added (UX 개편 계획)
- `docs/UX_REDESIGN_PLAN.md` 추가 — 첨부 구조도의 5단계 흐름(데이터 입력 → 저장·정제 → SOLA 분석 → 서비스 UI → 최종 산출물)을 기준으로 새 IA, 화면별 재배치, 디자인 방향, 사용자 시나리오, 단계별 구현 로드맵 정리.
- `README.md` 개발 문서 표에 UX 개편 계획 문서 링크 추가.

### Fixed (검증/보안 정리)
- `.env.example` 에 커밋되어 있던 실제 Groq API 키 형태의 값을 placeholder 로 교체하고, 실제 키는 gitignore 된 `.env` 에만 입력하도록 주석 추가.
- `Makefile` 의 오래된 파일명(`scraper.py`, `insights.py`, `cardnews.py`, `tests/test_app_pages_smoke.py`) 참조를 제거하고, 현재 CI/README 기준과 같은 전체 Python compile, 금지 패턴 검사, 전체 pytest 실행으로 정렬.
- `make check` 에 `.env.example` 내 API 키 패턴 검사를 추가해 예시 파일에 실제 키가 재유입되는 것을 방지.

### Fixed (Phase 6-A 후속 — roadmap 의존성 제거)
- `ui/home_tab.render` 의 트렌드 위젯이 `if roadmap.empty or news.empty` 분기 안에 갇혀 있어 로드맵 미업로드 onboarding 상태(뉴스만 수집된 상태)에서 위젯이 보이지 않던 버그 수정 (Codex review #21). 트렌드 위젯은 roadmap 의존성이 없으므로 `news` 만 있어도 렌더되도록 분기 분리. 부서 매칭 카드/안내는 기존대로 roadmap+news 모두 필요.

### Added (Phase 6-A — 홈 트렌드 위젯)
- `ui/home_tab._compute_home_trend_payload(news_today, *, days=7, now=None)` — 홈용 (`period_df`, `vol_df`, `emergence`) 일괄 계산. `now` 주입으로 테스트 결정성 확보.
- `ui/home_tab._chip_row(label, df, color)` — emergence 키워드 칩 행 HTML 생성. delta 컬럼 있으면 `+N`, 아니면 count. `<script>` 자동 escape.
- `ui/home_tab._trend_widget_html(brief_text, emergence)` — 🧠 SOLA 한 줄 + 🆕 새 / 📈 상승 / 📉 사라진 키워드 칩 3행 카드.
- `ui/home_tab._build_trend_context(brief_text, payload)` — 일자별 카운트 + 새/상승 키워드 + brief 를 사이드 채팅 컨텍스트 라인으로 직렬화.
- `ui/home_tab.render` — 메인 영역(부서 뉴스 위)에 위젯 + `[🔄 갱신]` 버튼 (pending flag → `st.rerun` 패턴) 삽입. brief 는 `_home_brief_text` 세션 키로 보관, page_context 에 자동 합류.
- `_build_page_context(..., trend_ctx="")` 시그니처 확장 — 홈 트렌드 컨텍스트가 부서 뉴스/인사이트와 동등하게 사이드 채팅에 전달.
- `tests/test_home_trend_widget.py` 14건 신설 — payload(days=1/7/empty/published_at fallback) + 칩 HTML(count/delta/empty/XSS escape) + 위젯 HTML(brief 표시/placeholder) + trend_context 합산 + page_context 통합. 전체 **134/134** 통과.
- 회귀 수정 (Codex review #20): `_compute_home_trend_payload` 의 today/base 분류가 raw `date` 컬럼 대신 `store.trends._date_col` 패턴(`published_at` 우선) 사용. 스크래퍼별로 `date` 가 표시 텍스트("1시간 전", RFC pubDate, "최근 동향")인 실데이터에서도 emergence 칩이 빈 결과로 떨어지지 않음.

### Added (Phase 6-B — cron 일일 자동 수집)
- `config.DEFAULT_DAILY_KEYWORDS` 추가 — 조선소 도메인 8개 기본 키워드(`조선소 자동화`, `용접 로봇`, `디지털 트윈`, `스마트팩토리`, `산업용 로봇`, `협동 로봇`, `제조 AI`, `선박 건조`). cron/CLI 기본값.
- `scraping/run_daily.py` 신설 — UI 와 분리된 배치 진입점.
  - `collect_batch(keywords, *, sources, max_results, on_step)` — 키워드×소스 매트릭스 수집. 키워드 기반 소스(`naver`/`google`)는 키워드별 결과를 메모리에 누적 후 **소스당 1번만** `save_articles` 호출(stamp 충돌 회피). `tech` 는 키워드 무관 1회. 키워드/소스 단위 실패는 격리.
  - `CollectionReport` dataclass — saved(소스당 1 entry: source/keywords/count/path) + errors(키워드 단위 실패). `summary_lines()` 가 CLI 로그용 사람 친화 텍스트 생성.
- `scripts/daily_scrape.py` 신설 — `python -m scripts.daily_scrape` CLI.
  - 인자: `--keywords`(미지정 시 DEFAULT_DAILY_KEYWORDS) / `--sources naver google tech` / `--max-results N`. 항상 exit 0 (cron 안정성).
- `.github/workflows/scrape-daily.yml` 신설 — 매일 KST 09:00 (UTC 00:00) cron + `workflow_dispatch` 수동 트리거.
  - 실행 흐름: checkout → pip install → `python -m scripts.daily_scrape` → `data/news/` 변경 감지 → `peter-evans/create-pull-request@v6` 로 **Draft PR 자동 생성** (브랜치 `scrape/daily-YYYY-MM-DD`, 라벨 `automated,scrape`). `LLM_*` secrets 노출(선택 — enrich 미사용 시 비워도 동작).
- `tests/test_run_daily.py` 7건 — 매트릭스 디스패치/저장 / 키워드 단위 실패 격리 / 부분 키워드 실패 시 나머지 보존 / 빈 키워드 스킵 / 소스 필터 / `CollectionReport.summary_lines` 사람 친화 출력 / CLI 가 DEFAULT_DAILY_KEYWORDS 기본 사용. 전체 120/120 통과.

### Added (M5-β — 트렌드 LLM 한 줄 해석 카드)
- `sola/prompts.SYSTEM_TREND_BRIEF` 추가 — "1~2문장 평문, 굵은 키워드 1~3개, 입력에 없는 사실 금지" 가정.
- `sola/trend_brief.py` 신설 — `brief(period_label, vol_df, emergence, force=False)` 함수.
  - 입력: `daily_volume` + `keyword_emergence` 결과 + 사용자에게 노출되는 기간 라벨.
  - 파일 캐시(`store.cache`) 적용 — 동일 (period · top 키워드 셋 · 모델) 입력은 LLM 재호출 없이 즉시 반환.
  - `LLMNotConfigured` 또는 호출 실패 시 룰 기반 fallback 문장(총 기사 수 + 새/상승 키워드) 생성 → graceful degrade.
- `ui/board_tab` 트렌드 섹션 상단에 **🧠 SOLA 한 줄 카드** + [갱신] 버튼 추가. 갱신 결과는 `_brief_text_<period>` 세션에 보관, 페이지 컨텍스트에도 자동 포함 → 사이드 채팅 LLM 이 해석을 인지.
- 내부 리팩터: `_compute_trends_payload(news_today)` 헬퍼로 (period, days, period_df, vol_df, emergence) 일괄 계산 → `_render_trends` 와 `_build_page_context` 가 동일 로직 재사용 (DRY).
- `tests/test_trend_brief.py` 8건 — 시스템·user 프롬프트 포맷 / 캐시 히트 / `force` 우회 / `LLMNotConfigured` fallback / 일반 예외 fallback / "변화 없음" 분기 / period 다른 캐시 키 / 키워드 다른 캐시 키. 전체 113/113 통과.

### Added (M5-α — 다중 일자 트렌드, Phase 5)
- `store/news_db.load_news_for_days(days=7, now=None)` — 오늘 포함 최근 N일 일자 디렉토리(`data/news/YYYY-MM-DD/*.parquet`)를 합쳐 반환. 누락 일자 스킵, `link` 기준 중복 제거.
- `store/trends.daily_volume(df, days=7, now=None)` — 최근 N일 일자별 기사 수, **데이터 없는 일자는 0 으로 채움** (라인 차트 끊김 방지).
- `store/trends.keyword_emergence(today_df, base_df, top_n=10, min_count=1)` — 오늘 vs 기준 기간 키워드 차이. `new`(오늘만 등장), `gone`(기준에만 등장), `rising`(둘 다 있지만 today 가 더 많음) 3개 DataFrame 반환. `keywords_llm` 우선, fallback `keywords`.
- `store/trends.compare_distribution(today_df, base_df, key="press", top_n=10)` — 분포 비교 (delta 내림차순).
- `ui/board_tab` 트렌드 섹션 — **기간 라디오** (오늘 / 최근 7일 / 최근 30일) 추가. 라인 차트(days>1) / 바 차트(days=1) 자동 전환. days>1 일 때 🆕 새 키워드 / 📈 상승 키워드 / 📉 사라진 키워드 3열 카드.
- `ui/board_tab._build_page_context` — 선택된 기간 + 일자별 카운트 + emergence 가 사이드 채팅 컨텍스트에 자동 포함.
- `tests/test_trends_multi_day.py` 11건 — `load_news_for_days`(다일 합본·누락 스킵·중복 dedupe·zero 거부) + `daily_volume`(zero-fill·empty·zero 거부) + `keyword_emergence`(new/gone/rising 분리·empty·top_n) + `compare_distribution`(delta 정렬). 전체 105/105 통과.
- `tests/conftest.py` — `store.news_db.NEWS_DIR` from-import 바인딩도 동기 패치.

### Changed (UI-4 — 사이드바 컴팩트 개편, Phase 4)
- `ui/sidebar.py` 리팩터 — 페르소나가 설정된 상태에서는 큰 폼이 아닌 **컴팩트 카드** 노출.
  - `.persona-card` — 아바타(이름/부서 첫글자, 파랑 그라데이션) + 이름 + 부서·직무·팀 meta. ellipsis 처리.
  - `.persona-cta` — 미설정 상태일 때 dashed border 파란 CTA 카드 + 폼 즉시 열림.
  - **편집 토글** — 카드 아래 `✏️ 편집` 버튼으로 폼 expander 열고 닫기. 저장 시 자동 닫힘.
  - 내부 헬퍼 분리: `_avatar_text` / `_persona_card_html` / `_persona_form_body` / `_handle_persona_pending` / `_render_persona_block`.
- 시스템 상태 → **사이드바 푸터** 로 이동 (`.sidebar-footer`). 작은 점선 인디케이터 (`.sidebar-dot.ok/warn`) + backend/model 2줄.
- 영역 네비 라디오 — 큰 네비 버튼 스타일 (전폭, padding `9px 13px`, 좌측 정렬). 사이드바 안의 라디오만 세로 컬럼 배치.
- 결과: 페르소나 설정 후 사이드바가 한눈에 짧아져 영역 네비·시스템 정보 가독성 ↑. on_click 0건 (편집 토글은 pending flag 패턴 유지).

### Added (UI-3 — 사이드 채팅 컨텍스트 강화, Phase 3)
- `sola/side_context.py` 신설 — `build_side_system(base_system, persona, page_context, session_proposal, adopted_proposals, max_chars)` 순수 함수.
  - 배치: base 시스템 → 페르소나 → 현재 화면 → 직전 작성 제안서 → 이전 사이클 채택 제안서.
  - 채택 제안서는 (제목 + 결정일 + 메모)만 노출 → 토큰 부담 최소.
  - 직전 제안서는 `PROPOSAL_HEAD_CHARS=3000` 까지 앞부분만.
  - 전체 `max_chars=8000` 초과 시 뒷부분 절단.
  - 반환값 `(sys_msg, labels)` — 라벨은 패널 UI 에 첨부 칩으로 노출.
- `ui/layout.render_chat_panel` 강화 — 시그니처에 `include_adopted` / `include_session_proposal` / `adopted_limit` 추가.
  - 패널 헤더 아래 `📎 페르소나 · 현재 화면 · 직전 제안서 · 채택 제안서 N건` 첨부 칩 자동 노출.
  - 모든 탭(home/board/ingest/news/bookmarks/roadmap)의 사이드 채팅이 자동으로 채택 제안서 5건 + 직전 제안서를 인지.
- `tests/test_side_context.py` 10건 — 빈 입력 / 페이지 컨텍스트 마커 / 페르소나 설정·미설정 라벨 / 직전 제안서 절단 / 채택 제안서 필드·라벨 / 빈 adopted / max_chars 절단 / 배치 순서 / base 시스템 위치. 전체 94/94 통과.

### Changed (UI-2 — 사이드 채팅 + 새 디자인 전체 탭 적용, Phase 2)
- `ui/board_tab` 인사이트보드 — `main_and_chat("board")` + page_context: 트렌드(일자/소스), 자동화 기회 매트릭스 상위 8셀. `section_label` 로 4개 섹션 정리.
- `ui/ingest_tab` 뉴스 수집 — `main_and_chat("ingest")` + page_context: 오늘 통계 + 소스 분포 + 최근 10건 헤드라인.
- `ui/news_tab` 뉴스 콘텐츠 — `main_and_chat("news")` + page_context: 언론사 분포 + 키워드 빈도. `section_label` 정리.
- `ui/bookmarks_tab` 북마크 — `main_and_chat("bookmarks")` + page_context: 현재 필터링된 북마크 목록(타입별 그룹 + 상태). 상태 배지를 인라인 style → `.status-badge.*` 클래스로 통일. 내부 렌더 `_render_items()` 분리.
- `ui/roadmap_tab` 로드맵 — `main_and_chat("roadmap")` + page_context: 부서별/Lv3별 작업 수 상위.
- `ui/sola_tab` SOLA — 상단 상태 패널을 `.card-flat` 으로 통일, 모드 라디오 label_visibility 정리. (자체 채팅이 본체라 사이드 채팅 토글 제외)
- `ui/proposal_workbench` 제안서 작업장 — `st.subheader` → `page_header` 로 통일. (자체 채팅 본체)
- 모든 탭의 페이지 컨텍스트는 lazy (`page_context_fn`), 토글 ON 일 때만 평가 → 닫혀 있으면 추가 비용 0.
- 전체 84/84 통과, on_click·외부 requests 0건.

### Changed (UI-1 — 디자인 시스템 v2 + 사이드 채팅 인프라)
- `assets/styles.css` 전면 리뉴얼 — Pretendard 단일 폰트, 흰색 베이스 + 파란 포인트(`#2563EB`).
  - 라운드 스케일(8/12/16/20px), shadow 스케일, neutral gray 시스템, 일관된 위젯(버튼·입력·라디오·탭·expander) modern화.
  - 카드 컴포넌트 `.card` / `.card-flat` / `.news-card` + 호버 시 파란 액센트.
  - 빠른 액션 그리드 `.quick-grid` / `.quick-tile`, 상태 배지 `.status-badge.*`.
- `ui/styles.py:page_header(title, sub, chat_toggle_key=..., extra_chips=...)` — 모던 헤더 + LLM 상태 chip + 우측 💬 채팅 토글 버튼. 반환값으로 채팅 패널 활성 여부.
- `ui/styles.py:section_label(text)` — 카드 그룹 위 작은 섹션 레이블 헬퍼.
- `ui/layout.py` 신설 — `main_and_chat(chat_key, page_context_fn, persona, ...)` 컨텍스트 매니저로 메인 + (옵션) 우측 사이드 채팅 패널. 페이지 컨텍스트(현재 화면 내용)를 LLM 시스템 메시지에 자동 주입.
  - `render_chat_panel(chat_key, page_context, persona, ...)` — 페이지별 분리된 히스토리(`_sidechat_<key>`), 초기화 버튼, pending flag 패턴.
- `ui/sidebar.py` — modern 사이드바: 브랜드 마크, 영역 네비 라디오, 페르소나 패널, 시스템 상태 칩.
- `ui/home_tab.py` — 새 디자인 적용 (demo). 페르소나 welcome 카드, 메트릭 3개, 부서 매칭 뉴스 + AI 인사이트(채팅 열리면 세로 배치), 빠른 행동 그리드.
- 채팅 패널 토글 ON 시 메인 3:2 분할, OFF 시 전체폭. 컨텍스트는 lazy(토글 ON 일 때만 계산).

### Added (docs — 작업 완료 보고 규칙)
- `CLAUDE.md` 절대 규칙 8번 — 모든 개발 지시 완료 후 (1) 무엇이 개발됐는지 (2) 어떻게 조치됐는지 (3) 다음 단계 3가지를 한 메시지로 의무 보고. 사용자가 매 PR 결과를 동일 포맷으로 확인 가능.

### Added (M4-η — 채택된 제안서를 채팅 컨텍스트에 자동 노출)
- `store/bookmarks.list_adopted_proposals(*, limit=5)` — 채택 제안서를 `decided_at` 내림차순으로 N건 반환.
- `sola/chat_ctx.build_context_block(..., adopted_proposals=...)` — 주어지면 "이전 사이클에서 채택된 제안서" 섹션으로 컨텍스트에 자동 포함 (제목 + 메모만, 본문 X → 토큰 부담 최소).
- 배치 순서: 첨부 제안서 → 채택 제안서 → 오늘 뉴스 → 로드맵.
- `ui/sola_tab._render_chat` — 채팅 호출 시 자동으로 채택 제안서 5건 주입.
- `ui/proposal_workbench._do_discuss` — 대화 모드도 동일 (활성 제안서 자신은 중복 제거).
- 사이클 효과: 이번 사이클 LLM 이 **지난 사이클의 결정**(채택된 제안서 + 메모)을 자연스럽게 참조 → 새 결정이 과거 결정과 일관됨.
- `tests/test_bookmarks.py` 2건 + `tests/test_sola.py` 3건 추가 (adopted-only / limit / 배치 순서 / 빈 리스트 무시). 전체 84/84 통과.

### Added (M4-ζ — 북마크 의사결정 상태 + 자동 만료)
- `store/bookmarks.Bookmark` 에 `status` (`pending`/`adopted`/`rejected`) + `decision_note` + `decided_at` 필드 추가. `from_dict` 가 옛 record 도 안전하게 backfill.
- `store/bookmarks.set_status(bm_id, status, note="")` — 상태 + 메모 + decided_at 갱신.
- `store/bookmarks.expire_old(days=30, types=("proposal",), now=None)` — 미채택 제안서 만료 정리. **adopted 는 영구 보존**.
- `app.py` — 세션당 1회 `expire_old()` 진입 시 자동 호출 (`_did_expire_check` 플래그).
- `ui/bookmarks_tab.py` — 제안서 카드마다 상태 셀렉터 + 결정 메모 입력 + 💾 저장 버튼. 상태 배지(⏳/✅/✖) + 정책 안내 캡션.
- `ui/proposal_workbench.py` — 북마크 출처 제안서에 좌측 상단 상태 셀렉터(즉시 저장).
- `tests/test_bookmarks.py` 9건 추가 (기본 status, from_dict 호환, set_status, expire_old: pending 만료 / adopted 보존 / 타입 한정 / 파싱 실패 보존). 전체 79/79 통과.

### Added (M4-ε — 제안서 작업장: 살아있는 제안서)
- `sola/refine.py:refine_proposal(current_md, instruction, persona=None)` — 활성 제안서 MD + 사용자 지시 → 수정된 전체 MD 반환.
- `sola/prompts.SYSTEM_PROPOSAL_REFINE` — "출력은 완성된 제안서 전체 MD만, 기존 섹션 구조 유지" 가정.
- `ui/proposal_workbench.py` 신설 — 2열 레이아웃(좌: 카드 뷰 / 우: SOLA 패널).
  - 입력 소스: 직전 작성 제안서 **또는** 북마크된 제안서.
  - 모드 라디오: **💬 대화** (활성 제안서를 컨텍스트로 일반 채팅) / **✏️ 수정** (지시 → in-place 교체 + 1단계 undo).
  - 액션: ↶ 되돌리기 / ★ 작업장 버전 북마크 저장 / ⬇️ MD 다운로드.
- `app.py` — 작업실에 "📝 제안서 작업장" sub-tab 추가.
- `tests/test_refine.py` 4건 (MD·지시 전달 / 페르소나 주입 / 페르소나 None / 낮은 temperature). 전체 70/70 통과.

### Added (M4-δ — 제안서 채팅 컨텍스트 첨부)
- `sola/chat_ctx.build_context_block(..., proposal=...)` — 채팅 시스템 프롬프트에 제안서 본문을 최우선 컨텍스트로 첨부. None/공백이면 자동 무시.
- `ui/sola_tab._build_proposal_context` — 채팅 탭에서 (1) 직전 작성 제안서 토글 + (2) 북마크된 제안서 selectbox 두 경로로 컨텍스트 첨부.
- `ui/sola_tab._render_chat` — "📎 제안서 컨텍스트 첨부" expander 신설. 직전 제안서 없으면 토글 자동 disable.
- `tests/test_sola.py` proposal 케이스 3건 추가 (앞쪽 배치 / proposal-only / None·빈문자열 무시). 전체 66/66 통과.

### Added (chore — CI + 라우팅 정정)
- `.github/workflows/ci.yml` 신설 — PR/main push 마다 자동 검증.
  - py_compile (모든 `git ls-files '*.py'`)
  - `on_click=` 금지 패턴 검사 (app.py + ui/)
  - `requests.{get,post,Session}(` 직접 호출 금지 (`scraping/http.py` 만 예외)
  - `pytest -q`
- 라우팅 문서 실제 디렉터리 구조 반영:
  - `CLAUDE.md` 도메인/규칙/라우팅 표/검증 명령 — `scraper.py/insights.py/cardnews.py` 옛 이름 제거.
  - `DEV_GUIDELINES.md` §2/§3/§4/§6/§8 — 패키지 단위 라우팅, invariant 갱신, 스택 갱신.
  - `README.md` 도메인 설명·검증·테스트 섹션 갱신.

### Security
- `.env.example` 의 실제 Groq API 키를 `your-api-key-here` placeholder 로 교체. (커밋된 키는 별도 rotate 필요)

### Added (M4-γ — 자동화 기회 매트릭스 + 북마크)
- `sola/opportunity.py` — 부서×공정(Lv3) 셀별 자동화 기회 점수.
  - `score_cells(news, roadmap, cell_level)` — 매칭 점수 누적 + 샘플 작업/뉴스.
  - `llm_commentary(dept, lv3, sample_news, sample_tasks)` — 셀당 한 줄 LLM 코멘트, 캐시.
- `sola/prompts.SYSTEM_OPPORTUNITY` 추가.
- `store/bookmarks.py` — JSONL 영구화 북마크 (`data/bookmarks/items.jsonl`).
  - 타입: `opportunity` / `proposal` / `news` / `task`.
  - `Bookmark` dataclass + `add/list_all/remove/has/clear/make_id`.
- `ui/board_tab.py` — 자동화 기회 매트릭스 섹션 (표 + 2열 카드 + 셀별 ☆ 북마크 버튼 + 페르소나 부서 강조).
- `ui/bookmarks_tab.py` 신설 — 타입별 필터 + 카드 리스트 + 삭제.
- `app.py` — 작업실에 "📌 북마크" sub-tab 추가.
- `ui/sola_tab.py` — 제안서 생성 결과에 ☆ 북마크 버튼.
- `tests/test_opportunity.py` 5건 + `tests/test_bookmarks.py` 6건. 전체 63/63 통과.
- `tests/conftest.py` — `store.bookmarks` 의 DATA_ROOT from-import 바인딩 동기 패치.

### Added (M4-β — 페르소나 + 3영역 UI 재편)
- `persona/` 패키지 — 사용자 부서·직무·관심 공정을 영구화하는 도메인 모델.
  - `schema.Persona` dataclass + `to_dict/from_dict`.
  - `store.load/save/reset` — `data/persona/profile.json` JSON 영구화.
  - `context.system_block(persona)` — LLM 시스템 프롬프트에 붙일 페르소나 안내.
- `ui/sidebar.py` — 사이드바에 페르소나 설정 패널(부서 select + 직무 자유 입력 + 관심 Lv3 멀티) + 영역 선택(홈/탐색/작업실) + LLM 상태.
- `ui/home_tab.py` — 페르소나 카드, 우리 부서 관련 뉴스, 우리 부서 AI 인사이트, 빠른 행동 안내.
- `ui/task_tree.py` — 부서→Lv1→Lv2→Lv3 단계적 드릴다운 위젯. board_tab·sola_tab 제안서에서 재사용.
- `app.py` 3영역 재편 — 홈 / 탐색(수집·로드맵·보드) / 작업실(SOLA·뉴스) + 사이드바.
- `sola.propose.propose_for_task(persona=...)` — 제안서 생성 시 페르소나 컨텍스트 자동 주입.
- `ui/sola_tab.py` 채팅·제안서에 페르소나 컨텍스트 주입, 제안서 작업 선택을 task_tree 드릴다운으로 교체.
- `ui/board_tab.py` — 사용자 부서 인사이트 카드 우선 정렬 + 강조 테두리, 매칭 필터를 task_tree로 교체.
- `tests/test_persona.py` 6건 + `test_sola.py` 페르소나 주입 검증 1건. 전체 52/52 통과.
- `tests/conftest.py` — `persona.store`, `store.cache`, `store.chat_log` 의 from-import 바인딩도 동기 패치.

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
