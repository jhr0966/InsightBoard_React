# Changelog

모든 주요 변경은 여기에 기록한다. 포맷: [Keep a Changelog](https://keepachangelog.com/) + SemVer.
릴리스 = `main` 머지 시점.

## [Unreleased]

### Added (수집 현황 모달 — [🔄 지금 뉴스 수집] 진행/결과 표시) — `feat-collect-progress-modal`
- **수집 현황 모달**(`ui/data_management_v2.py`): [🔄 지금 뉴스 수집] 클릭 시 render 도중 동기 수집 + 토스트 대신 **화면 중앙 st.dialog("📡 뉴스 수집 현황", dismissible=False)** 가 떠서 진행(st.status + st.progress, `collect_batch(on_step=)` 콜백으로 소스·키워드 단위 진행률/현재 단계 텍스트)과 결과 요약(수집 기사/저장 파일/키워드/RSS 출처 KPI 4 + 오류 목록, 전부 `html.escape`)을 보여준다. 결과는 `_sc_collect_modal_result` 세션에 저장 → rerun 에도 유지 + 재수집 가드(1회 실행). [✕ 닫기]가 플래그·결과를 비우고 rerun.
- **트리거 경로 정리**: 액션바/설정 수집 버튼은 `_sc_collect_modal_pending` 플래그 + `st.rerun()` 만. `_consume_refresh_if_any` 는 레거시 `?refresh=now` 딥링크·구 `_do_dm_collect` pending 을 모달 플래그로 **번역**(호환 유지, 동기 수집 제거). 실 수집·run_log 기록(trigger="manual")·캐시 무효화(`_invalidate_collect_caches` — `_dm_stats`/`_sc_browse_records`/`_board_kpis` 등, 실패 시에도 finally)는 `_run_collect_for_modal` 로 이동.
- **dialog 1개/run 가드**: 수집 모달 pending 중에는 기사 모달(`_render_news_modal_if_open`)을 띄우지 않는다.
- `assets/v2/screens/data_management.css`: 모달 결과 요약(`.sc-collect-modal` — 상태 배지/KPI 그리드/오류 목록) 스타일 추가.
- 테스트: `tests/test_collect_trigger.py` 모달 경로로 재작성(+16 — 플래그 번역, on_step 진행, 부분/전체 오류, run_log trigger, XSS escape, 재수집 가드, 닫기 정리), `test_v2_screens.py`·`test_custom_rss_scrape.py` 의 동기 수집 테스트를 `_run_collect_for_modal` 기준으로 갱신.
- 검증: pytest **892 passed** · 금지패턴 0 · 브라우저 실측(모달 진행→오류 요약 표시→닫기) OK.

### Changed (시스템 점검·리팩토링 1차 — 부분 갱신 + 성능)
- **뉴스 수집 브라우저를 `@st.fragment` 부분 rerun 경계로**(`ui/data_management_v2.py` `_render_browse_zone`): 보기 모드(카드/표)·대분류 탭·출처칩 전환, 카드 [기사 보기], 표 행 선택, 모달 ✕ 닫기가 **앱 전체 스크립트(topbar·사이드바·우측 채팅) 재실행 없이 해당 구역만** 다시 그린다 → 클릭 반응 즉각화. dialog-in-fragment 동작은 브라우저 실측(모달 열림/닫힘·카드↔표 왕복)으로 확인.
- **일자별 parquet 메모**(`store/news_db.py` `_day_frame_memo`): 보드 한 렌더가 3/14/30/56일 윈도우를 섞어 요청해도 **같은 날짜 parquet 은 1회만 디스크에서 읽는다**(직전: 윈도우마다 전체 재스캔 — 보드형 패턴 9×). `load_all_today` 도 공유. 새 수집 시 (mtime, 파일 수) 시그니처로 자동 무효화.
- **자산/헬퍼 캐시**: `ui/components.read_asset_text`((경로,mtime) 키) — CSS 6종 + 화면 템플릿 4종(board/insights/dm/archive)의 **매 rerun 디스크 재읽기 제거**(파일 수정 시 자동 갱신·핫리로드 유지). `_board_kw_mgr_html`·`_notif_count`·`chat_context_block_collect`(내부 `_chat_context_collect_cached` 분리)에 `@st.cache_data(ttl=60)`.
- **측정**: 보드 콜드 렌더 4.13s → **1.74s(-58%)** · 보드형 로드 패턴(콜드) 0.071s → 0.045s(소규모 시드 기준, 데이터 누적 시 격차 확대) · 워밍 렌더 0.04~0.10s 유지.
- **시나리오 시뮬레이션**: e2e **S8(부분 갱신)** 신설 — 표 전환→카드 복귀→모달 열기/닫기 상태 전이 한 세션 연속 검증 + `news_db` 일자 메모 디스크 읽기 횟수 회귀 테스트. 캐시 도입에 따른 테스트 격리(clear) 2건 보강.
- **채팅 빠른 작업 칩 reload 제거**(`ui/chat_panel.py`, `ui/sola_workshop_v2.py`, `streamlit-overrides.css`): SOLA 작업실 우측 채팅의 빠른 작업(제안서 생성/뉴스 요약/새 대화)이 `?sola_action=` 앵커라 **클릭마다 문서 전체 reload** 였던 것을 `st.button` 칩(`_render_quick_action_chips`) + `_sola_action_pending` 플래그로 전환 — 소켓 rerun 만 탄다. 인계 컨텍스트(dept/lv3/from) 보존, 소비자는 pending 우선 + 쿼리(딥링크) 호환 유지. 버튼 칩 CSS 추가.
- **작업 정의 관리 td_* 앵커 스위트 reload 제거**(`ui/task_def_manage.py`, `assets/v2/screens/data_management.css`): 목록 카드(`?td_view=`)·상세 액션 4종(목록/수정/이력/삭제 `?td_edit/td_hist/td_action=`)·[+ 새 작업 추가](`?td_add=`)·폼 취소/저장 redirect 가 모두 앵커/URL 조립이라 **클릭마다 문서 전체 reload** 였던 것을 위젯으로 전환 — 카드는 투명 오버레이 `st.button`(sc_card 하우스 패턴), 액션 바는 `st.button` 4종(+삭제는 JS confirm 대신 2-step 확정), 모두 `_td_nav_pending` 에 행선지를 담고 `_consume_td_nav_pending` 이 위젯 인스턴스화 전에 **query params 로 번역**(td_* 전체 교체 = 앵커와 동일 의미)해 기존 쿼리 주도 로직·딥링크(`?td_view=` 직접 입력) 호환 유지. 부수 수정: 구 `_td_redirect` 가 스테일 `td_edit/td_add` 를 안 지워 저장/취소 후 폼에 머물던 잠재 결함이 전체 교체 번역으로 해소. `_manage_href` URL 빌더 삭제(사용처 0).
- **보드 기회/키워드 액션 reload 제거**(`ui/board_v2.py`, `board_main.html`, `board.css`): 템플릿을 두 placeholder 경계로 분할 렌더하고, 기회 카드 보류/채택·키워드 ×(숨김/제거)·즉시 수집 CTA 를 `st.button`+pending 으로 전환(SOLA와 검토 인계 링크만 앵커 유지). 소비자는 pending 우선+쿼리 호환.
- **우측 채팅 패널 `@st.fragment` 부분 rerun**(`ui/chat_panel.py`, `app.py`): SOLA 작업실 외 화면에서 보내기/추천질문 pill 이 **채팅 컬럼만** 갱신(LLM 호출·영구화 포함). SOLA 작업실 송신·빠른 작업 칩은 중앙 작업대 동기화를 위해 `scope="app"`. 앱 상단 소비는 유지(인계 자동송신 경로·pop-once 라 이중 처리 없음).
- **잔여 로드맵**: 전체 reload 를 유발하는 same-screen 앵커(보드 kw/opp 액션·작업정의 td_* 스위트·채팅 칩·SOLA 스레드 전환 등) 전환 우선순위를 `docs/REFACTOR_PLAN.md` **Phase 4** 로 문서화.
- 검증: pytest **832 passed**(신규 2) · 금지패턴 0 · 브라우저 실측 OK.

### Fixed (thebell 본문·사진 — 실제 마크업 기반 정밀 수정)
- **본문 셀렉터 직결**(`scraping/enrich.py`): 사용자가 제공한 thebell 실페이지 HTML 로 확인 — 본문이 `<p>` 없이 `<br>` 구분 텍스트로 `div#article_main`(`.viewSection`) 에 직접 들어있어 셀렉터 미매칭이었음 → `_CONTENT_SELECTORS` 에 `div#article_main`·`div.viewSection` 추가(폴백이 아닌 정공 경로로 수집).
- **사진 오선택/누락 수정**(`scraping/extract.py`, `enrich.py`): 기사 사진보다 문서 앞에 나오는 **구글 선호 출처 아이콘(`google_icon.png`)·공유 아이콘이 junk 필터에 안 걸려** 대표 이미지로 잡히던 구조 → junk 조각에 `_icon.`/`icon_`/`/icons/`/`/banner/`(광고 배너)/`share_` 추가. 이미지 탐색 순서에 본문 컨테이너 스코프(`div[id*='article'] img` 등)를 문서 전체 `img` 보다 앞에 추가.
- **노이즈 차단**: `_NOISE_SELECTORS` 에 thebell 광고/UI 박스(`.article_content_banner`·`.newsADBox`·`.linkNews`·`.linkBox`·`.optionIcon`·`.googleSearch`), 보일러플레이트에 '무료로 공개된 기사입니다'·'구글 검색 선호 출처로 추가'·`^(책갈피|프린트|작게|크게)$` 추가.
- 검증: pytest **830 passed**(신규 2 — thebell 실마크업 본문/사진 추출·UI 아이콘/배너 junk 판정) · 금지패턴 0. ⚠ 단, **fetch 자체가 403 으로 막히면**(TLS/IP 차단) 이 수정으로도 수집 불가 — 배포 환경에서 `pip install -r requirements.txt`(curl_cffi) 후 `scripts/diagnose_article.py` 로 요청 단계 확인 필요.

### Fixed (조선닷컴 본문 미수집 — SPA 구조화 데이터 본문 추출)
- **조선닷컴 기사가 사진·제목만 되고 본문이 비던 문제**(`scraping/enrich.py`): 조선닷컴은 Arc Publishing(Fusion) 기반 SPA 라 **본문 문단이 DOM 에 없고**(JS 렌더) 페이지 내 JSON 에만 있다 → 셀렉터/문단 폴백이 빈손. 구조화 데이터 추출 2종 신설 — ① `_ldjson_article_body`: schema.org NewsArticle ld+json 의 `articleBody`(범용, `@graph` 중첩 지원) ② `_arc_fusion_body`: `Fusion.globalContent` JSON 의 `content_elements`(type=text/raw_html) 문단 복원(`raw_decode` 로 안전 파싱). `fetch_article` 에서 `_strip_noise` 가 script 를 지우기 **전에** 확보하고, DOM 셀렉터 본문보다 길 때만 채택(서버렌더 사이트는 기존 경로 유지 — ld+json 이 티저 요약뿐인 사이트 보호).
- `scripts/diagnose_article.py` 에 ⑥-b 구조화 데이터 본문(ld+json/Fusion 길이) 리포트 추가.
- 검증: pytest **828 passed**(신규 3 — SPA 전문 복원·서버렌더 DOM 우선 유지·마커 없음/불량 JSON 안전) · 금지패턴 0. ⚠ 조선닷컴 라이브는 샌드박스 망 차단으로 미검증 — 배포 환경 재수집/진단 스크립트로 확인.

### Fixed (카드 본문 제목 반복 + thebell TLS 차단 + slist 이미지 — 뉴스 수집 화면 점검)
- **카드/표/모달 본문 자리에 제목이 한 번 더 나오던 문제**: 두 경로가 겹친 원인 — ① 구글 뉴스 RSS 의 description(=`summary`)은 태그를 벗기면 '제목(+언론사)'만 남는데 카드가 `summary` 를 `content` 보다 우선 노출, ② 과거 수집분 `content` 가 '제목\n본문' 형태. → (소스 차단) `scraping/google.py` `_summary_echoes_title` — 제목 반복뿐인 description 은 summary 를 비워 저장(실제 스니펫 있는 건 보존). (렌더 방어) `ui/data_management_v2.py` `_news_body_src` — 카드·표·모달 공용 본문 선택 헬퍼: 라인 단위로 제목 라인을 제거하고, '제목(+언론사)' 한 줄뿐인 값은 건너뛰어 다음 폴백(content)으로. 모달 본문 단락에서도 제목 라인 스킵(레거시 데이터 대응). 브라우저 스크린샷으로 카드 발췌=본문만·제목 1회 확인.
- **뉴스 수집 화면 전체 점검 결과**: 카테고리(키워드/포탈) 분류·출처칩·검색 필터·표 행 선택 가드·캐시 무효화 로직은 정상. 추가 발견 1건 — `http://` 이미지가 https 앱에서 **혼합콘텐츠로 차단**되어 사진이 안 보일 수 있음 → 카드·표·모달 렌더에서 `_https_img` 로 https 승격.
- **thebell 본문·사진 여전히 미수집**: 직전의 헤더 강화 재시도로도 403 인 것은 WAF 가 **TLS 핑거프린트(JA3)** 로 python-requests 를 식별하는 케이스 → `scraping/http.py` `fetch_impersonated` 신설(curl_cffi 의 Chrome TLS 위장, **선택 의존성** — 미설치 시 None 폴백) + `enrich._get_article_response` 최후 폴백으로 연결. `requirements.txt` 에 `curl_cffi>=0.7` 추가(**배포 환경 `pip install -r requirements.txt` 재실행 필요**). ⚠ 샌드박스 망 차단으로 thebell 라이브는 미검증 — `scripts/diagnose_article.py` 로 배포 환경에서 확인.
- **slist.kr 사진만 미수집**: ND소프트/Froala 계열 CMS 의 lazy 속성 누락이 유력 → `_IMAGE_ATTR_ORDER` 에 `data-fr-src`·`data-echo`·`data-lazyload` 추가 + http→https 렌더 승격(혼합콘텐츠 케이스). 정확한 원인 확정용 **기사 1건 진단 스크립트 `scripts/diagnose_article.py` 신설** — 요청 단계(기본/워밍업/TLS 위장)·메타/본문 이미지 후보(+junk 판정)·본문 셀렉터 매칭을 단계별 리포트.
- 검증: pytest **825 passed**(신규 8 — 구글 summary 에코 차단·TLS 위장 폴백 2종·apparent_encoding 가드·Froala lazy 속성·본문 폴백/카드/모달 에코 방어·https 승격) · 금지패턴 0 · 카드/모달 브라우저 스크린샷 확인.

### Fixed (thebell 본문·사진 미수집 + 구글 뉴스 본문 노이즈 + 기사 모달 버튼 배치)
- **thebell.co.kr 기사 본문·사진이 통째로 비던 문제**(`scraping/enrich.py`): thebell 류 구형 ASP/WAF 사이트가 세션 쿠키 없는 직접 진입·약식 헤더를 403 으로 차단 → `fetch_article` 이 빈 값 반환. **차단 응답(401/403/406/412/429) 시 1회 강화 재시도** 추가 — ① 사이트 홈 워밍업으로 세션 쿠키 획득 ② sec-fetch 브라우저 시그널 + 네이버 검색 referer(검색 클릭 유입 위장)로 재요청(`_get_article_response`/`_full_browser_headers`). ⚠ 샌드박스 외부망 차단으로 thebell 실사이트 라이브 동작은 미검증 — 배포 환경 재수집으로 확인 필요.
- **구글 뉴스 본문에 제목 반복 + UI 버튼 텍스트(번역/beta/kaka i/닫기/작은·큰 폰트)·섹션명·날짜가 섞이던 문제**(`scraping/enrich.py`): 본문 셀렉터 미매칭 → 최대블록 폴백이 기사 wrapper 를 잡을 때 생기는 잔재. ① `_BOILERPLATE_PATTERNS` 에 퍼블리셔 UI 버튼(폰트/공유/번역/SNS)·섹션명 단독 라인·입력/수정 일시·날짜-only 라인 패턴 추가 ② `_strip_title_echo` 신설 — 본문에 제목과 동일한 라인이 반복되면 제거(8자 미만 제목은 오삭제 방지 위해 제외), `enrich_one` 경로에 적용.
- **기사 모달 — 원본 기사 열기·✕ 닫기 버튼을 같은 라인에 병렬 배치**(`ui/data_management_v2.py _news_modal_body`, `assets/v2/screens/data_management.css`): 링크를 모달 HTML 내부에서 빼내 `st.columns(2)` 행으로 — 1열 원본 링크(`sc-modal-link--row`: 컬럼 전폭·중앙 정렬), 2열 ✕ 닫기. 링크 없으면 닫기만 전폭. 브라우저 스크린샷으로 병렬 배치 확인.
- 검증: pytest **817 passed**(신규 6 — WAF 재시도 헤더/워밍업·정상시 미재시도·UI 버튼 라인 제거·제목 반복 제거 2종·모달 액션 행) · 금지패턴 0.

### Added (개발 자체검증 세팅 — 브라우저 + 웹크롤링)
- **크롤링 파이프라인 자체검증 스크립트 신설**(`scripts/verify_scrape.py`): 외부망이 allowlist 로 차단된 환경에서도 크롤링을 검증할 수 있게, **로컬 fixture HTTP 서버**(RSS 피드·사이트 목록·기사 페이지·네이버 검색결과 마크업)를 띄우고 실제 모듈 경로(`build_session()` HTTP 왕복 → 파싱)를 그대로 태운다. 검사 4종 — ① `rss.fetch`(필드·pubDate ISO 변환·이미지·태그 제거) ② `tech_sites.search_site`(제목 길이·도메인·`_NAV_BLOCKLIST` 필터) ③ `enrich.fetch_article`(본문 셀렉터 추출 + 헤더 chrome 미혼입 + og:image) ④ 네이버 검색결과 셀렉터(`_find_news_items`·제목/링크). `--live` 플래그로 실 외부 소스(네이버·구글·AI Times RSS)도 시도하며, 전 소스 실패 시 망 차단 가능성을 알리고 실패 처리.
- **Makefile 검증 타깃 추가**: `make verify-scrape`(크롤링 자체검증), `make verify-browser`(Playwright 화면 검증). `make test` 는 `python -m pytest` 로 변경 — PATH 의 uv 격리 pytest 가 프로젝트 의존성을 못 보던 환경 문제 회피.

### Fixed (브라우저 시각검증 스크립트 현행화)
- **`scripts/verify_browser.py` 구버전 영역명 수정**: `🧱 데이터 관리`(존재하지 않음 → 보드로 폴백돼 같은 화면 2번 캡처)를 현행 `🗞 뉴스 수집`·`📋 작업 정의` 로 교체 — 6장 → **7장** 캡처.
- **온보딩 모달 자동 해제**: `page.goto` 마다 새 Streamlit 세션이라 '반갑습니다' 모달이 모든 스크린샷을 가리던 문제 → 화면마다 '다음에 하기' 버튼을 클릭해 닫는 `_dismiss_onboarding` 추가.
- **chromium 경로 하드코딩 제거**: `/opt/pw-browsers/chromium-1194/...` 고정 → `chromium-*` glob 탐색 + 없으면 Playwright 기본 탐색 폴백.
- 검증: pytest **811 passed** · `verify_scrape` 4/4 · `verify_browser` 7/7 캡처(온보딩 미노출 확인) · 금지패턴 0.

### Removed (뉴스 수집 #133 재설계 잔재 — 미사용 레거시 일괄 정리, 코드 −1.2k줄)
- **옛 뉴스 라이브러리 필터 폼·3탭/그룹 라우팅·옛 카드 빌더를 전부 제거**(`ui/data_management_v2.py` −387, `ui/data_management_render.py` −223): #133 재설계로 **카드 브라우저·기사 모달·⚙ 수집 설정 서브뷰**가 대체한 뒤 화면 흐름에서 더는 호출되지 않던 레거시를, 호환·테스트용으로 남겨뒀던 것을 적극 정리. 제거 함수 — `_filter_news_by_query`·`_news_cards_html`·`_news_source_options`·`_render_news_filter_form`·`_render_jobs_split`·`_render_dm_tabs`·`_render_dm_tab_panel`·`_strip_dm_mockups`·`_dm_tab_href`·`_dm_tabs_html`·`_dm_group_of`·`_dm_groups_html`·`_dm_group_href`·`_dm_resolve_group_and_tab`·`_src_action_href` + 관련 상수(`_DM_TABS`·`_DM_GROUP_*`·`_DM_COLLECT_TABS`·`_MAX_NEWS_CARDS`·`_NEWS_PERIOD/SORT_OPTS` 등). `data_management_render.py` 는 카드·표·모달이 공유하는 **출처색 그라데이션 + 기사 나이 라벨** 헬퍼만 남겼다.
- **데이터 관리 화면 템플릿을 헤더(KPI 4종)만으로 축소**(`assets/v2/screens/data_management_main.html` −211): 가짜 필터바·페이저·서브카드 목업과 본문 placeholder(`{{NEWS_CARDS}}`·`{{INGEST_JOBS}}`·`{{INGEST_REFRESH_CTA}}` 등)를 모두 걷어내고, `{{DM_TABS}}` 는 `_render_dm_header` 가 헤더만 잘라 쓰는 split 마커로만 남겼다.
- **함께 고친 버그**: 템플릿 트림 중 주석에 `{{DM_TABS}}` 토큰을 그대로 적어, `_render_dm_header` 의 `split("{{DM_TABS}}")` 가 **첫 occurrence(주석)** 에서 잘려 헤더 KPI 4종이 통째로 사라지던 회귀를 주석 문구 교체로 해소(헤더 정상 렌더 — `test_render_dm_header_has_kpis_and_no_tab_bar` 로 고정).
- **죽은 테스트 정리**: `tests/test_dm_area_groups.py` 삭제(그룹/탭 라우팅 전량), `test_dm_cleanup.py`·`test_dm_news_filter.py` 재작성(템플릿 헤더화·카드 브라우저 회귀로 교체), `test_dm_tabs.py`·`test_task_def_manage.py`·`test_src_crud.py`·`test_task_def_upload.py`·`test_v2_screens.py`·`test_e2e_scenarios.py`·`test_collect_trigger.py` 에서 제거 심볼 참조 테스트를 삭제/대체. (상단 검색 필터 회귀는 `test_collect_browser.py::test_filtered_records_search_query`(`_sc_filtered_records`)가 이미 커버 — 커버리지 손실 없음.)
- 검증: pytest **811 passed** · 금지패턴(on_click/requests) 0 · 순변경 13파일 **−1193줄**.

### Fixed (본문에 포털 UI 텍스트가 섞이던 것 + AI Times 연재/목록 페이지 수집)
- **포털(다음·네이버) 기사 본문에 제목·TTS·글자크기·번역 위젯·관련기사·저작권 chrome 이 섞이던 문제**(`scraping/enrich.py`): 직전에 본문을 '가장 긴 텍스트 블록'으로 뽑게 바꿨더니, 포털 페이지에서 본문 컨테이너가 아니라 **본문+UI 전체 wrapper** 를 잡았다. → **본문 셀렉터를 신뢰(우선)** 하도록 복원(매칭 셀렉터 중 최장; 없을 때만 문단/최대블록 폴백). 포털 chrome 노이즈 셀렉터(`.tts_area`/`[class*='relate']`/`[class*='copyright']`/`.foot_view` 등) + 보일러플레이트 텍스트(음성재생·글자크기·번역 beta·무단전재·해당 언론사로 이동 등) 제거 추가. 다음 본문 컨테이너(`.article_view`/`[data-translation]`/`#harmonyContainer`) 셀렉터 보강.
- **AI Times '연재/섹션 목록 페이지'가 기사로 수집돼 같은 기본 이미지(예: VENDOR LOCK IN)가 반복되던 문제**(`scraping/tech_sites.py`): `_NAV_BLOCKLIST` 에 `articleList`·`sc_serial_code`·`sc_section_code`·`view_type=`·`/serial` 등 추가 → 기사 모음 페이지를 개별 기사에서 제외.
- 검증: pytest **851 passed** — 신규 `test_fetch_article_strips_portal_chrome_keeps_body`(다음 스타일 HTML → 본문만, chrome 제외)·`test_tech_sites_rejects_list_and_serial_pages`. 금지패턴 0.

### Fixed (구글 뉴스 카드 이미지가 전부 'Google News 로고'로 나오던 것)
- **원인**: 구글 RSS 링크(`news.google.com/rss/articles/<불투명토큰>`)가 원문으로 해석되지 않아, enrich 가 **구글 인터스티셜 페이지**를 열어 그 페이지의 og:image(= Google News 로고)를 가져옴 → 모든 구글 카드가 같은 로고.
- **안전망(확실)** `scraping/enrich.py`: **미해석 구글 링크(`news.google.com`)는 fetch 자체를 건너뛴다** → 로고가 안 들어오고, 원문이 풀린 퍼블리셔 링크만 본문·og:image 를 가져온다. (테스트로 검증 — 구글 미해석 링크 fetch 0회.)
- **신 포맷 링크 해석** `scraping/google.py`: 불투명 토큰을 구글 내부 **batchexecute API** 로 원문 URL 복원(`_batchexecute_decode`/`_parse_batchexecute`) — 구 base64 디코드 → batchexecute → 리디렉트 순. 링크 해석은 **병렬**(ThreadPool)로 처리해 수집 지연 최소화.
- 검증: pytest **849 passed** — batchexecute 응답 파싱·해석 우선순위·enrich 안전망(구글 미해석 fetch 스킵)·퍼블리셔 링크 fetch 테스트. 금지패턴 0. ⚠️ **샌드박스 외부망 차단으로 구글 batchexecute 라이브 동작은 미검증** — 배포 앱 재수집으로 확인 필요. 안전망 덕분에 **최악의 경우에도 로고 대신 그라데이션 플레이스홀더**(로고 일괄 표시 해소는 보장).

### Fixed (기사 모달 — 박스가 화면보다 커서 스크롤·버튼/사진 잘림)
- **모달을 뷰포트에 맞게 컴팩트화**(`assets/v2/screens/data_management.css`, `assets/v2/streamlit-overrides.css`): 본문이 길면 모달이 화면을 넘어 다이얼로그 전체가 스크롤되고 닫기/원문 버튼·사진이 잘리던 문제. 이미지 `max-height:280px·cover` → **`18vh·contain`**(잘리지 않게 전체 표시) + 배경, 본문 `max-height:60vh` → **`36vh`**(내부 스크롤로 가둠), 제목/여백 축소, 다이얼로그 `max-width:880px`(와이드 모니터 배너화 방지). 합계 ≈87vh 로 맞춰 **닫기·원문 버튼이 항상 보이게**.
- **모달 본문 중복 제거**(`ui/data_management_v2.py _news_modal_body`): content 가 있으면 본문만, 없을 때만 요약을 본문 자리에 노출(요약+본문 이중 노출 → 길이 증가 방지).
- 검증: pytest **844 passed**(모달 본문/요약 폴백 테스트 갱신·신규) · 금지패턴 0. (CSS 비율은 실배포 화면 확인 권장.)

### Fixed (★ 근본원인: 수집이 본문/이미지를 enrich 하지 않던 것 — 본문 전부 빈칸 해결)
- **`collect_batch` 가 enrich 를 호출하지 않아 모든 기사 `content` 가 빈 채로 저장되던 버그 수정**(`scraping/run_daily.py`): 검색 결과는 `content=""`·리스트 이미지만 가졌는데 수집 경로에 enrich 단계가 **아예 없었다** → 데이터 표 본문 전부 빈칸, 카드/모달 본문 없음, 이미지는 로고/썸네일뿐. 이제 소스별 수집 직후 **`enrich.enrich_parallel`(병렬)** 로 각 기사 링크에서 **본문·og:image·빈도 키워드**를 가져와 채운 뒤 저장한다. (그동안의 enrich/셀렉터 개선이 비로소 실제 수집에 반영됨.)
- **`scraping/enrich.py`**: `enrich_parallel`(ThreadPoolExecutor·기본 6 workers, 개별 실패 격리) 신규. `enrich_one` 이 본문 확보 시 **빈도 기반 키워드**(`extract_keywords`)도 채움(표/매칭용). `fetch_article` 이 **같은 출처(origin) referer** 를 실어 네이버 기사(referer 없으면 403)처럼 막던 사이트 대응.
- **구글 요약 정리**(`scraping/google.py`): RSS description 폴백이 `&nbsp;`·중복 공백·제목 포함으로 지저분하던 것 → 태그 제거 + **HTML 엔티티 해제(unescape)** + 공백 정규화.
- **수집 스피너**(`ui/data_management_v2.py`): enrich 로 수집이 길어져 '지금 뉴스 수집' 에 `st.spinner` 추가.
- 검증: pytest **843 passed** — 신규 `test_collect_batch_enriches_body_and_image`·`test_collect_batch_can_disable_enrich`. 기존 collect_batch 테스트는 enrich 네트워크 stub(autouse)으로 hermetic 유지. 금지패턴 0. ⚠️ 샌드박스가 외부 호스트(naver/aitimes/google)를 차단해 이 환경에선 라이브 수집 검증 불가 — 배포 앱에서 재수집 시 채워진다.

### Fixed (뉴스 수집 — 구글 사진·카드 사진 크기·본문 전체 추출, jhr0966/News scraper.py 참고)
- **구글 뉴스 사진 0건 완화**(`scraping/google.py`): RSS `description` 안의 **비-구글 원문 링크(`<a href>`)를 추출**해 원문 URL 로 저장(`_extract_original_link`) → enrich 가 실제 기사에서 og:image·본문을 가져온다. 우선순위: description 직링크 → base64 디코드 → 리디렉트 추적 → media:content/thumbnail·description 이미지. (참고 레포 `jhr0966/News` scraper.py 의 `_extract_original_link` 전략.)
- **카드 사진 확대**(`assets/v2/screens/data_management.css`): 카드 이미지 높이 128px→**190px**(`.sc-card` 300px→360px) — 첨부 시안처럼 사진이 크게 보이도록. `object-fit:cover` 유지로 왜곡 없음.
- **본문 전체 추출 개선**(`scraping/enrich.py`): ① CONTENT_SELECTORS 에 **AI Times·오토메이션월드(모우 계열 CMS) 본문 컨테이너**(`#article-view-content-div`·`.article-view-content` 등) + 참고 스크래퍼의 누락 셀렉터(`ab_text`·`aticle_txt`·`text_area`·`v_article`·`art_txt`) 추가. ② 본문 선택을 '첫 매치'가 아니라 **셀렉터·문단·최대텍스트블록 후보 중 가장 긴 것**으로 바꿔(링크 8개 초과 블록 제외) 셀렉터가 일부만 잡는 사이트에서도 전체 본문을 확보.
- 검증: pytest **841 passed**(신규 `_extract_original_link`·전체 본문 선택 테스트) · 금지패턴 0. (스크래퍼는 `scraping/http.py` 세션 사용 — §4 준수. 구글 신 포맷 불투명 링크는 서버 측 복원 한계로 일부 여전히 빌 수 있음 — 후속.)

### Fixed (뉴스 수집 후속 — 카드 클릭 무반응 · 카드 높이 불균일 · 표 본문/모달 · 사진 추출)
- **카드 클릭 무반응 수정**(`assets/v2/streamlit-overrides.css` + `screens/data_management.css`): ① 모달이 안 뜨던 주원인이었던 `st.dialog` 박스의 `display:flex`·`min-height` 강제 CSS를 제거하고 **오버레이 세로 중앙 정렬 + max-height 90vh** 만 남겨 모달이 정상 렌더되게 함(전 테마). ② 카드 오버레이 버튼을 `[data-testid="stButton"]` 직접 절대배치에서 **`stElementContainer:has(stButton)` 절대배치**로 바꿔(버튼 컨테이너 전체가 카드를 덮음) 클릭 적중률을 높임.
- **카드 높이 통일 + 본문 3줄**(`screens/data_management.css`): `.sc-card` 고정 높이(300px) + 이미지 `flex:0 0 128px`, 제목 `min-height:2.64em`(2줄 예약)·본문 `min-height:4.5em`+`line-clamp:3`(3줄 예약·클램프) → 본문 길이와 무관하게 모든 카드가 같은 높이·본문 3줄.
- **데이터 표에 본문 + 행 클릭 모달**(`ui/data_management_v2.py _render_news_table`): `본문` 컬럼 추가(content 280자), `st.dataframe(on_select="rerun", selection_mode="single-row")` 로 **행을 클릭하면 기사 모달**(reload 없는 소켓 rerun). 닫은 직후 재오픈 루프는 `_sc_table_sel`(직전 처리 link) 가드로 방지.
- **사진 추출 개선**(`scraping/{extract,enrich,naver,google}.py`): 공용 `is_junk_image`(로고·엠블럼·아이콘·플레이스홀더·data URI 판정) 신설. **네이버** 검색결과의 언론사 로고 img 를 건너뛰고 기사 썸네일을 고름(로고만 가져오던 문제). **enrich** 는 og:image 가 로고면 본문 이미지로 폴백하고, 리스트가 가져온 로고 이미지는 버려 og:image 가 채우게 함. **구글** 뉴스 리디렉트 링크를 base64 디코드(요청 없음) + 리디렉트 추적으로 원문 URL 복원 → enrich 가 og:image·본문을 가져옴(이미지 0건 완화) + RSS media 이미지 추출. (HTTP 단일 진입점 §4 준수 — 참고 코드의 직접 requests 미사용.)
- 검증: pytest **839 passed**(신규 `tests/test_scrape_images.py` 로고제외·구글 디코드·og 폴백 + 표 본문/행선택 모달·카드 클릭 테스트) · 금지패턴(on_click/requests) 0. (CSS(카드 클릭·모달 중앙)는 **실배포 시각 확인 권장** — 환경상 헤드리스 브라우저 미설치.)

### Changed (뉴스 수집 — 카드 클릭 reload 제거 · 모달 세로 중앙/확대 · 데이터 표 탭 · 본문/사진 추출 개선)
- **카드 클릭 시 문서 전체 reload(흰 깜빡임) 제거 → 즉시 모달**(`ui/data_management_v2.py`): 카드를 `?news=` 앵커(문서 네비게이션)에서 **카드 전체를 덮는 투명 `st.button` 오버레이**로 전환. 클릭은 소켓 rerun 으로 `_sc_open_news` 를 세팅해 reload 없이 기사 모달이 뜬다. 카드 시각은 `_sc_card_visual_html`(앵커 없음), 그리드는 `st.columns(3)` 행 + 카드별 컨테이너(`_render_card_grid`). `_sc_filtered_records` 로 필터 로직 분리. (구 `_sc_news_card_html`/`_sc_cards_html` 제거, `?news=` 딥링크 소비는 호환 유지.)
- **모달(기사·페르소나/온보딩)을 화면 세로 중앙 + 더 긴 형태로**(`assets/v2/streamlit-overrides.css`): `st.dialog` 오버레이를 flex 중앙 정렬 + 박스 `min-height:58vh`·`max-height:92vh`·`width:min(880px,94vw)` + 본문 flex 신장 → 상단에 붙고 짧던 문제 해소(전 테마). 기사 본문 `.sc-modal-body` 최대 높이 46vh→60vh.
- **📋 데이터 표 보기 추가**(`_render_news_table` + `sc_browse_mode` 토글 `🃏 카드`/`📋 데이터 표`): 수집한 **모든 뉴스**를 `st.dataframe`(사진 썸네일=`ImageColumn`, 링크=`LinkColumn`, 제목·대분류·출처·수집시각·키워드)로 표시. 상단 검색어로 좁힘.
- **기사 본문/사진 추출 개선**(`scraping/enrich.py`): 표준 셀렉터·`<p>` 폴백으로도 본문이 빈약하면(동적/비표준 마크업) **링크가 적은 '최대 텍스트 블록'을 마지막 폴백**으로 채택(`_FALLBACK_MIN_LEN`/`_FALLBACK_MAX_LINKS`, 사용자 제공 참고 스크래퍼 패턴). 노이즈·코드/보일러플레이트 제거 동일 적용. (사진은 og:image→본문 img 우선순위 + 리스트 이미지 폴백 유지.)
- 검증: pytest **827 passed**(카드 클릭→모달·데이터 표·필터 신구조 + enrich 최대블록 폴백 신규 테스트) · 금지패턴 0.

### Changed (뉴스 수집 화면 개편 — 카테고리 카드 브라우저 + 기사 모달 + ⚙ 수집 설정 서브뷰)
- **뉴스 수집을 '키워드 뉴스'(naver·google 검색 기반) / '포탈 뉴스'(tech 사이트 + 커스텀 RSS) 두 대분류로 정리**(`ui/data_management_v2.py`): source 값으로 대분류를 판정(`_news_category_of`)하고, 포탈은 매체(press)·키워드는 네이버/구글로 출처칩 라벨을 만든다(`_news_channel_of`).
- **메인 = 카드뷰**: 수집 현황 요약(KPI 4) → 액션바(`[🔄 지금 뉴스 수집]` + `[⚙ 수집 설정]`) → **대분류 탭(segmented) + 출처칩(segmented)** → **사진 카드 그리드**. 카드는 `image_url` 실사진(없으면 출처색 그라데이션) + 제목 + 본문 일부(summary_llm→summary→content)를 보여준다. `_sc_browse_records`(30일·_cat/_chan 주석·최신순 캐시) / `_sc_channels` / `_sc_cards_html`(카테고리·채널·검색 필터) / `_sc_news_card_html` 신규.
- **카드 클릭 → 기사 모달**: 카드 앵커가 `?news=<link>` 를 실으면 `_consume_news_modal_open_if_any` 가 세션 플래그로 옮기고(파라미터 1회 소비), `st.dialog(dismissible=False)` 로 **본문 전체 + 요약 + 대표 사진 + `원본 기사 열기 ↗`(새 탭) + ✕ 닫기**(소켓 rerun) 모달을 띄운다(`_news_modal_body`/`_render_news_modal_if_open`). 이미지·링크는 **http(s) 스킴만 허용**(XSS/data: 방어), 모든 외부 문자열 `html.escape`.
- **뉴스 라이브러리 필터 폼(출처·기간·정렬) 제거** — 상단 토픽 검색이 대체하고, 카테고리 탭/출처칩으로 원클릭 분류. (레거시 빌더 `_render_news_filter_form`/`_render_jobs_split`/`_render_dm_tabs`/`_news_cards_html` 은 호환·테스트용으로 유지하되 화면 흐름에서 호출하지 않음.)
- **⚙ 수집 설정 서브뷰**(`sc_collect_view`): 키워드 관리(`_dm_kw_body_html`) + 포탈/출처 관리(`_render_src_table`·`_render_src_add_form` — 토글·커스텀 RSS) + 수집 실행 + **수집 이력 상세(오늘의 수집잡·14일 추이·런 타임라인)**. `← 뉴스 목록` 으로 카드뷰 복귀.
- **CSS**(`assets/v2/screens/data_management.css`): `sc-grid`/`sc-card`/`sc-card-img`/`sc-modal*` 등 카드·모달 스타일 + 액션바/탭/칩 컨테이너 인셋(헤더·카드와 폭 정렬) 추가.
- 검증: pytest **825 passed**(+12 신규 `tests/test_collect_browser.py`, test_dm_tabs/test_dm_news_filter/E2E S5 신구조로 갱신) · 금지패턴(on_click/requests) 0.

### Added (작업 정의 flat-column 엑셀 — JSON 열 없이 개별 컬럼을 구조화 JSON 으로 자동 조립)
- **JSON 열이 없는 신 엑셀(flat 형식)을 그대로 업로드하면 16개 개별 컬럼이 자동으로 구조화 task_def JSON 으로 조립**된다: 분과·팀·부서·공정·작업·세부작업·Process_ID·공정설명·작업흐름·주요확인사항·안전주의사항·주요사용장비·품질리스크·자동화가능영역·이전공정·다음공정. (사용자 제공 컬럼 스펙대로.)
- **`roadmap/schema.py`**: `COLUMN_MAP` 에 flat 헤더 매핑 추가(`Process_ID→process_id`, `공정설명→process_description`, `작업흐름→work_flow`, `주요확인사항→key_check_points`, `안전주의사항→safety_notes`, `주요사용장비→main_equipment`, `품질리스크→quality_risks`, `자동화가능영역→automation_areas`, `이전공정→previous_process`, `다음공정→next_process`). `OPTIONAL_COLUMNS`/`RoadmapRow` 에 신 컬럼 9종 추가 → normalize 가 컬럼을 드롭하지 않고 보존.
- **`roadmap/task_def_json.py`**: `split_list_cell()`(셀을 줄바꿈/`;`/불릿으로 분리·중복 제거) + `assemble_from_columns()`(개별 컬럼 → JSON payload) 신규. 품질리스크·자동화가능영역은 **매칭/SOLA 가 읽는 표준 키**(`overall_quality_risks`/`automation_potential_areas`)로 매핑해 즉시 반영. `process_name` 컬럼이 없어 세부작업→작업으로 보강(보드 카드·검색·diff 표시명). `TaskDef`/`parse()`/`flatten_for_match()`/`to_chat_context_lines()` 에 신 필드(work_flow·key_check_points·safety_notes·main_equipment·previous/next_process) 반영 → 뉴스 매칭과 SOLA 컨텍스트가 새 신호를 실제로 활용.
- **`roadmap/ingest.py`**: `normalize_columns` 가 **task_def_json 이 빈 행에 한해** 조립을 수행(단일 진입점). 이미 JSON 열이 채워진 구 포맷 행은 그대로 두어 하위호환 유지. 이후 match/board/SQLite/query 는 포맷과 무관하게 `task_def_json` 만 읽으면 됨.
- **`roadmap/task_def_form.py` · `ui/task_def_manage.py`**: 수동 추가/수정 폼과 1건 상세 보기에 신 필드 위젯·섹션 추가(작업 흐름·주요 확인사항·안전 주의사항·주요 사용장비·이전/다음 공정). 상세 보기는 품질리스크/자동화영역이 **문자열 항목**(flat)일 때도 렌더(기존 dict 항목과 병행).
- **`ui/data_management_v2.py`**: 업로드 안내 문구에 flat 형식 컬럼 목록 명시(구 JSON 열 형식도 그대로 인식).
- **검증**: pytest **813 passed**(+18 `tests/test_roadmap_flat_columns.py` — split·assemble 게이팅·normalize 통합·ingest→SQLite org_meta 주입·parse/flatten/context·score_matches) · 금지패턴 0.

### Changed (데이터 관리 → '뉴스 수집' · '작업 정의' 두 화면으로 분리)
- **사이드바 '🧱 데이터 관리' 1개 → '🗞 뉴스 수집' + '📋 작업 정의' 2개로 분리**(`ui/sidebar.py` AREAS 5→6, `app.py` 디스패치): 정보구조를 수집 작업과 작업 정의 관리로 명확히 나눔.
- **`ui/data_management_v2.py`**: `render()` → `render_collect()`(헤더 수집 KPI + segmented 탭 jobs·kw·src) + `render_taskdef()`(작업정의 KPI 헤더 + 엑셀 업로드 + 작업 정의 관리를 **탭 없이 세로 배치**). `_render_dm_tabs(tabs=…)` 파라미터화, `_DM_COLLECT_TABS` 추가. `_taskdef_stats()`(등록 정의·부서·마지막 갱신)·`_render_taskdef_header()` 신규. `chat_context_block` → `chat_context_block_collect`/`_taskdef` 분리(우측 채팅이 화면별 데이터를 인식).
- **딥링크/카피 재배선**: 상단 검색·보드 "뉴스 라이브러리/첫 수집" → 🗞 뉴스 수집, `task_def_manage._manage_href` → 📋 작업 정의(구 `?dm_grp/dm_tab` 핸드오프 제거). `chat_panel` 안내 카드 2종 분리. 화면 템플릿 브레드크럼/설명을 '뉴스 수집'으로 갱신. insights/board 안내 문구 '데이터 관리에서 수집' → '뉴스 수집에서'.
- 검증: pytest **795 passed**(관련 9개 테스트 area·함수명·smoke 갱신) · 금지패턴 0 · playwright 실측(nav 6항목·뉴스 수집 3탭/수집 KPI·작업 정의 KPI 3종+업로드+관리, 탭 없음).

### Changed (사이드바 메뉴 이동 흰 깜빡임 제거 — 앵커 → `st.button` 재위젯화)
- **좌측 업무 흐름 5-nav 를 순수 HTML `<a href="?app_area=">` 앵커에서 `st.button` 위젯으로 복원**(`ui/sidebar.py`, `assets/v2/sidebar.css`, `ui/styles.py`): 앵커는 클릭 시 **문서 전체 reload(흰 깜빡임)**였다. 버튼은 **소켓 rerun**(세션 `app_area` 세팅 + `st.rerun()`, `on_click` 금지)이라 메뉴 이동에 깜빡임이 없다. look 은 `.st-key-sidebar_nav` 스코프가 기존 `.sidebar-nav-item`(인덱스=CSS counter·제목=`**strong**`·설명=`*em*`·활성=`button[kind="primary"]`)을 복제 — **디자인 동일**.
- **2026-06-05 되돌림 사유 재검토**: `.st-key-*` 스코프 CSS 는 데이터관리 필터·수집 버튼에서 사용자 환경 포함 정상 동작 중이라, 직전 '메뉴 깨짐'은 일시적 CSS FOUC 로 추정 → 사용자 요청으로 재위젯화. 컨텍스트 딥링크(`?app_area=`)는 `_consume_area_query` 가 그대로 처리(둘 다 지원). `docs/INVARIANTS.md` I-22 갱신. **실배포 렌더 최종 확인 권장.**
- **메뉴 항목 왼쪽맞춤 (들쭉날쭉 수정)**(`assets/v2/sidebar.css`): 위젯 nav 의 제목/설명 시작 위치가 항목 글자 수마다 달라 들쭉날쭉했다 — Streamlit 버튼 라벨이 `button > div`(+그 안 span) **두 겹의 flex 래퍼 `justify-content:center`** 로 가운데 몰렸기 때문. 래퍼를 `flex-start` 로 돌려 왼쪽 고정(emotion-cache 클래스 대신 구조 셀렉터 `button > div`). playwright 실측: 제목 시작 x 편차 **24.9px → 0px**(전 항목 38px 정렬).
- 검증(playwright 실측): nav 클릭 시 `window` 플래그 생존(**문서 reload 0 = 흰 깜빡임 없음**)·URL `?app_area=` 없음·활성 01→03 전환·라이트/다크 룩 동일(인덱스 01–05·제목·설명). pytest **793 passed**(앵커 HTML 테스트 → `_nav_label`+위젯 nav AppTest 로 교체) · 금지패턴 0.

### Fixed (데이터 관리 — 출처 탭 '무수집' 오표시 + 수집 버튼·필터 박스 폭 삐져나감 + 수집 referer)
- **출처 탭의 기본 출처 4개(AI Times·오토메이션월드·Google RSS·네이버 기술)가 실제로는 수집됐는데도 전부 '무수집'으로 표시되던 버그 수정**(`ui/data_management_v2.py`): 수집기는 `source` 를 `naver`/`google`/`tech` 로 저장하고 tech 는 AI Times·오토메이션월드를 **모두 `source="tech"`** 로 묶어 site 명을 `press` 에 둔다. 그런데 출처 탭(`_src_count_map`)은 **표시명으로 곧장 group** 해 매칭이 0건 → 전부 '7일 무수집', 동시에 `naver`/`google`/`tech` 원시값은 '기타' 행으로 누출됐다. `_DEFAULT_SOURCE_MATCH`(표시명 ↔ source 값 + tech 는 `press` 로 AI Times/오토메이션월드 구분, legacy 직접저장 호환)로 환산하도록 고쳐 표시명별 실 건수를 보이고 기타 누출을 제거. (사용자의 '수집 안 됨'은 실제론 이 **표시 버그** — 수집 자체는 정상.)
- **'지금 뉴스 수집' 버튼·뉴스 라이브러리 필터 박스가 본문보다 넓게 우측으로 삐져나가던 것 수정**(`assets/v2/screens/data_management.css`): Streamlit 이 `.st-key-*` 컨테이너를 `width:100%`(부모 724px)로 잡아 `margin:0 24px` 만으로는 폭이 줄지 않고 우측으로 밀려 본문(`.dm-shell` 콘텐츠 356–1024)을 넘어 1076 까지 갔다. `.st-key-dm_collect_cta`·`.st-key-dm_news_filter` 에 `width:calc(100% - 56px)` + `margin:0 28px` → 헤더·카드와 정확히 정렬(356–1024, playwright 실측).
- **수집 HTTP referer 교차도메인 버그 수정**(`scraping/http.py`, `scraping/naver.py`): `default_headers()` 가 모든 요청에 `Referer: https://search.naver.com/` 를 고정으로 실어, 구글 뉴스·AI Times·오토메이션월드·커스텀 RSS 같은 **타 도메인 요청에 네이버 referer** 가 붙어 anti-bot 403 을 유발할 수 있었다(별개 correctness 개선). referer 를 opt-in 으로 전환(기본 없음, 네이버 검색만 명시).
- 검증: 출처 탭 매칭 단위테스트(신규/legacy 포맷) + playwright 실측(AI Times 1·Google RSS 2·네이버 기술 1·오토메이션월드 0, 기타 누출 0) · pytest **792 passed** · 금지패턴 0.

### Added (E2E 전체 사용 시나리오 시뮬레이션 — `tests/test_e2e_scenarios.py`)
- **부품 단위가 아닌 '연결된 한 흐름'을 검증하는 E2E 7 시나리오 추가**: 조선소 사용자(도장1팀 홍길동) 워크플로를 수집→저장→매칭→자동화 기회→5화면 네비게이션→필터→SOLA LLM→보관함까지 한 줄기로 시뮬레이션. 외부 의존(네트워크=scraping search, LLM=`sola.*.chat`)만 mock, 데이터 파이프라인·매칭·UI 조립은 실제 코드 실행. conftest tmp 격리 + 시드 헬퍼(페르소나·작업정의 `sqlite_sync`·수집 fake search) + `_clear_ui_caches`(테스트 간 `st.cache_data` stale 제거).
- 시나리오: **S1** 수집 영속화 · **S2** 로드맵 SQLite 라운드트립(`sync_dataframe`→`load_latest`) · **S3** 매칭(`score_matches`)+자동화 기회 셀(`score_cells`) · **S4** `app.py` 5화면 무예외 렌더(`AppTest`, LLM graceful fallback) · **S5** 데이터관리 출처 필터 적용→배너 · **S6** SOLA 요약·보드 브리핑(LLM mock) · **S7** 보관함 제안 채택→카운트.
- **검증**: 7/7 시나리오 통과 · 전체 pytest **789 passed**(+7) · 금지패턴 0.

### Added (데이터 관리 — 뉴스 라이브러리 필터: 출처·기간·정렬)
- **죽은 필터 시안(`dm-filters` 출처/기간/정렬 셀렉트)을 실동작 `st.form` 으로 구현**(`ui/data_management_v2.py`, `assets/v2/screens/data_management.css`): jobs 탭 뉴스 라이브러리 위에 `st.form`(출처 멀티셀렉트 · 기간 3/7/30일 · 정렬 최신/오래된 + [적용]) 추가. 폼 위젯은 제출 전까지 rerun 을 일으키지 않아 **'적용' 눌렀을 때만** 라이브러리가 갱신된다(요청 방법론). `with st.form(...)` 단일 블록이라 topbar 와 달리 bare 'active form' 누수 없음(chat_panel 입력 폼과 동일 패턴).
- **`_news_cards_html(q, sources, days, sort)` 로 확장**: 상단 검색어(`q`) + 출처·기간·정렬을 조합해 필터. 모두 기본값이면 기존 동작(최근 3일 6장·첫 장 강조) 그대로, 하나라도 활성이면 선택 기간(검색만 있고 기간 미선택이면 30일 자동 확대) 안에서 출처·검색어로 좁혀 정렬 후 최대 24장 + 활성 필터 배너. 검색어·필터는 **인자**로 받아 `st.cache_data` 가 조합별 캐시 키를 잡는다(세션 직접참조 X).
- **활성 필터 배너 + 전체 해제**: 검색어·출처·기간·정렬 칩 + 결과 건수 + `✕ 필터 해제`(`?dm_clear_filters=1` → `_consume_news_filter_clear_if_any` 가 검색어·폼 위젯을 기본값으로 리셋). 배너는 `.dm-art-grid`(grid) 안에 들어가므로 `grid-column:1/-1` 로 전체 폭 차지. 출처 옵션은 `_news_source_options`(최근 30일 distinct 출처, 수집·업로드 시 캐시 무효화 목록에 추가).
- **검증(playwright 실측)**: 필터 바 렌더(출처 멀티셀렉트 + 기간·정렬 셀렉트 + accent '적용') · 'AI Times' 선택+적용 시 **결과 1건**으로 좁혀짐 + 배너 전체 폭(598/630px=95%). pytest **782 passed**(`_news_cards_html` 필터 로직 6 + 출처 옵션 + 폼 렌더 AppTest + 필터 해제 AppTest) · 금지패턴 0.

### Reverted (사이드바 메뉴 위젯화 + 메인 헤더 스크롤 고정 — 사용자 요청)
- **사이드바 5-nav 를 위젯(st.button) → 순수 HTML `<a>` 링크로 되돌림**(`ui/sidebar.py`, `assets/v2/sidebar.css`, `ui/styles.py`, `tests/test_sidebar_profile.py`): 위젯 nav 가 **사용자 환경에서 메뉴가 깨져** 보고됨. 원인 추정 — Streamlit 버전별 `st-key-*` 컨테이너 클래스/버튼 라벨 마크다운 렌더 차이(로컬 검증 환경에선 정상이라 재현 불가). 어디서나 동일하게 렌더되는 원래 `_sidebar_nav_html`(앵커 리스트)로 복원 — 메뉴 클릭 시 흰 깜빡임은 감수. `.st-key-sidebar_nav` 스코프 CSS·다크 오버라이드도 원복.
- **메인 헤더(`.db-topbar`) 스크롤 고정 제거**(`assets/v2/shell.css`, `assets/v2/streamlit-overrides.css`, `ui/styles.py`): sticky 처리(감싼 element-container 에 `position:sticky`)·불투명 배경·그림자·다크 헤더 배경을 모두 제거하고 `position:static`(in-flow)로 복원 — 헤더는 본문과 함께 스크롤. **우측 채팅 패널 고정(I-21)은 사용자 요청 대상이 아니라 그대로 유지.**
- **검증(playwright)**: 사이드바 = `a.sidebar-nav-item` 5개(위젯 `.st-key-sidebar_nav` 제거 확인) · 헤더 스크롤 시 ΔY=−400(고정 해제) · pytest **772 passed** · 금지패턴 0. invariant I-20(헤더 sticky)·I-22(nav 위젯)를 '되돌림'으로 갱신.

### Changed (산출물 보관함 칸반 카드 액션 위젯화 — 흰 깜빡임 제거)
- **칸반을 템플릿 HTML → `st.columns(3)` 위젯 렌더로**(`ui/archive_v2.py`, `assets/v2/screens/archive_main.html`, `assets/v2/screens/archive.css`): 카드 액션(채택/수정/기각·되돌리기)·"더 보기/접기"가 모두 `<a href="?action=…">`·`<a href="?expand=…">` 앵커라 클릭마다 문서 전체 reload(흰 깜빡임)였다. 칸반 보드를 `st.columns(3)` 으로 렌더하고 각 컬럼 컨테이너(`.st-key-oa_col_*`)를 구 `.oa-col` 룩(테두리·상단 accent·그림자)으로 스타일. 카드(`_card_html`)는 **표시 전용**(액션 앵커 제거)으로 두고, 1순위 카드 액션은 컬럼 상단 `st.button` 으로 렌더(`_render_card_actions`).
- **액션·expand 트리거를 세션/위젯으로**: 채택/기각/되돌리기 = `_do_archive_action`=(action, bm_id) pending → `_consume_action_if_any`(버튼 pending / 레거시 `?action=` 둘 다). 더보기/접기 = `?expand=` 앵커 → 세션(`_oa_expanded`) 토글(`_toggle_expanded`). 수정 = `_handoff_edit_to_sola` 가 세션 `app_area`=SOLA + `st.query_params`(from/bm_id/title) 세팅 — `st.query_params` 할당은 문서 reload 없이 URL 만 갱신하므로 **SOLA 측 소비 경로는 기존 그대로**(SOLA 코드 변경 0). `on_click` 미사용(CLAUDE.md #3).
- **렌더 구조 정리**: `_oa_stats_and_cards`(카드 HTML 캐시) → `_oa_data`(stats + 컬럼별 items). 카드 블록은 `_cards_block_html`(앵커 없는 `.oa-cards`). 템플릿 `archive_main.html` 은 보드 section 제거 → **헤더(통계) 전용**. 액션 버튼 색: 채택=녹(semantic-success)·기각=주황(semantic-warning)·더보기=점선 — 구 `.oa-act-good/.oa-act-warn` 톤 유지.
- **검증(playwright 실측)**: 3 컬럼 렌더 · 액션 버튼 5개(대기 채택/수정/기각 + 채택·기각 되돌리기) · '채택' 클릭 시 `window` 플래그 **생존(문서 reload 0=흰 깜빡임 없음)** + 카운트 즉시 갱신(대기 3→2·채택 1→2) · 다크 스크린샷에서 컬럼/녹·주황 버튼 룩 기존 유지. pytest **773 passed**(expand 세션 토글·카드블록·`_oa_data`·액션 pending·수정 핸드오프 테스트로 교체) · 금지패턴(on_click) 0.

### Changed (데이터 관리 '지금 뉴스 수집' + 출처 토글/제거 위젯화 — 흰 깜빡임 제거)
- **'지금 뉴스 수집' CTA 를 앵커→버튼**(`ui/data_management_v2.py`, `assets/v2/screens/data_management.css`): 수집잡 헤더의 `<a href="?refresh=now">`(클릭 시 문서 전체 reload=흰 깜빡임)를 `_refresh_cta_html` 제거 + `_render_collect_button`(`st.button`)으로 교체. 클릭 시 `_do_dm_collect` pending 세팅 → `st.rerun()`(on_click 미사용) → `_consume_refresh_if_any` 가 `collect_batch` 실행. `_consume_refresh_if_any` 는 **버튼 pending / 레거시 `?refresh=now` 둘 다** 처리(북마크 호환). 버튼은 본문 위 우측 정렬(컨테이너 column flex 라 `align-items:flex-end`)·accent 채움 — 빈 수집잡 안내의 "우측 상단 [지금 뉴스 수집]" 문구와 위치 일치.
- **출처 토글/제거를 앵커→행 버튼**(`ui/data_management_v2.py`, `assets/v2/screens/data_management.css`): `_dm_src_body_html`(토글/제거 `<a href="?src_action=…">` 가 박힌 HTML `<ul>`)를 제거하고 `_render_src_table`(헤더 HTML + 출처 행별 위젯)로 교체. 각 행 = `st.columns([시각 pill | 토글/제거 버튼])`, 컨테이너(`.st-key-_src_row_*`)가 테두리/배경(구 `.dm-src-row` 룩), pill(`_src_row_pill_html`)이 마크/이름/건수/최신/상태 격자. 버튼 클릭 → `_do_src_action`=(action, name) pending → `_consume_src_action_if_any`(버튼 pending / 레거시 `?src_action=` 둘 다 처리). 기본=토글, 커스텀=제거, 기타(내부 ID)=토글 불가(—).
- **검증(playwright 실측)**: 출처 토글 클릭 → `window` 플래그 **생존(문서 reload 0=흰 깜빡임 없음)** · URL 깨끗 · 6행/4토글버튼 렌더 · 수집 버튼 우측 정렬(right edge=컨테이너 우단) · 라이트/다크 스크린샷 기존 룩 유지. 수집 버튼은 표준 `st.button`(소켓 rerun)이라 reload-free, 수집 실행은 `_do_dm_collect`→`collect_batch` 단위 테스트. pytest **777 passed**(수집 pending·출처 pending·pill·헤더 테스트로 교체) · 금지패턴(on_click) 0.

### Changed (사이드바 메뉴 이동 위젯화 — 화면 전환 흰 깜빡임 제거)
- **사이드바 5-nav 를 앵커→위젯으로**(`ui/sidebar.py`, `assets/v2/sidebar.css`, `ui/styles.py`): 좌측 업무 흐름 메뉴(오늘의 보드/데이터 관리/인사이트 분석/SOLA 작업실/산출물 보관함)가 `<a href="?app_area=…">` 앵커라, 메뉴를 누를 때마다 **브라우저 문서 전체 reload**(빈 화면→프론트 재부팅→CSS 재주입)로 화면 전환 시 흰 깜빡임이 났다. `_sidebar_nav_html`(앵커 빌더)를 제거하고 `_render_sidebar_nav` 가 `st.button` 5개로 렌더 → 클릭이 **소켓 rerun**(부분 갱신·문서 reload 없음)이라 깜빡임이 사라진다. `on_click` 미사용 — `if st.button(): app_area 세팅 → st.rerun()`(CLAUDE.md #3). 활성 항목은 `type="primary"`.
- **룩 100% 보존**(`assets/v2/sidebar.css`): 컨테이너 `.st-key-sidebar_nav` 스코프로 버튼을 기존 카드형 nav 항목으로 복제 — 인덱스(01·02…)는 CSS `counter` `::before`, 제목은 라벨 `**…**`(`<strong>`), 설명은 `*…*`(`<em>`, `display:block`+ellipsis 둘째 줄), 활성은 `button[kind="primary"]`(accent 배경·테두리·인덱스/제목색). 다크는 일반 secondary 버튼 dark 규칙(#1E293B 채움)이 nav 까지 먹지 않게 투명 유지 + 활성 틴트/글자색 다크화(`ui/styles.py` `_DARK_CSS`).
- **컨텍스트 딥링크는 유지**: 보드→SOLA·히트맵·알림 벨 등 `?app_area=` 교차 링크는 그대로(`_consume_area_query`) — 이번 작업은 **사이드바 메뉴 이동**만 위젯화(딥링크 위젯화는 후속).
- **검증(playwright 실측)**: 보드에서 '인사이트 분석' nav 클릭 → `window` 플래그 **생존(=문서 reload 0, 흰 깜빡임 없음)** · URL 에 `?app_area=` 없음 · 활성 하이라이트 01→03 이동 · 헤더 타이틀 '인사이트 분석' 전환 확인 · 라이트/다크 사이드바 스크린샷이 기존 디자인과 동일. pytest **775 passed**(신규 nav 위젯 AppTest 포함) · 금지패턴(on_click) 0.

### Fixed (메인 헤더 스크롤 고정 + 채팅 패널 모든 화면 고정)
- **메인 헤더(`.db-topbar`)가 스크롤하면 사라짐 → 모든 화면 상단 고정**(`assets/v2/streamlit-overrides.css`, `assets/v2/shell.css`): 헤더는 본문(메인 컬럼) 안의 첫 요소라 `position:static` 으로 콘텐츠와 함께 스크롤돼 올라가 버렸다. `.db-topbar` 자체에 `sticky` 를 걸면 `st.html` 래퍼(`stHtml`)가 헤더 높이에 딱 맞게 shrink-wrap 돼 이동 여유가 0 → 안 붙는다. 그래서 **헤더를 감싼 Streamlit element-container**(`[data-testid="stElementContainer"]:has(> [data-testid="stHtml"] > .db-topbar)`)에 `position:sticky; top:0; z-index:20` 을 걸었다 — 이 컨테이너의 컨테이닝 블록은 '메인 컬럼 전체 높이'(콘텐츠만큼 큼)라 헤더가 상단에 계속 붙는다(채팅 컬럼을 sticky 로 만드는 것과 같은 원리). 헤더 배경은 라이트 `--v2-bg(#F3F5F8)`·다크 `#0F172A`(`ui/styles.py` `_DARK_CSS`) 로 앱 배경과 맞춰 **아래로 스크롤되는 카드가 헤더 밑으로 비치지 않게** 불투명 처리 + 하단 그림자(`box-shadow`)로 본문과 분리.
- **SOLA 작업실·산출물 보관함·데이터 관리에서 스크롤하면 채팅창이 같이 밀림 → 모든 화면 고정**(`assets/v2/streamlit-overrides.css`): 채팅 패널 높이가 `calc(100vh - 24px)` 로 컨테이닝 블록(컬럼 row)과 거의 같아, sticky '이동 여유'(`row − panel − top`)가 페이지 최대 스크롤보다 작았다. `block-container` 하단 padding(36px)·`stMain` 상단 padding(8px)이 **row 밖에서** 추가 스크롤을 만들어, 본문이 짧은 화면(SOLA·보관함)의 바닥에서 패널이 row 끝에 닿아 ~32px 같이 밀렸다(긴 화면 board/insights 는 스크롤이 바닥까지 안 가 안 보였을 뿐). 패널 높이를 `calc(100vh - 72px)` 로 낮춰 **이동 여유가 항상 페이지 스크롤을 초과**하게 만들어 모든 화면에서 고정.
- **검증(playwright 실측, 1440×900)**: board·data·insights·sola·archive **5개 화면 전부** — 스크롤 후 헤더 ΔY=0(이전 −600/−195/−40)·채팅 ΔY=0(이전 sola/archive −32, data −5) · 헤더 래퍼 `computed position=sticky, top=0, z=20` 확인 · 라이트/다크 배경 일치 스크린샷 확인. pytest **774 passed** · 금지패턴(on_click/requests) 0.

### Fixed (데이터 관리 탭 간격 + 탭 전환 시 채팅 패널 흔들림)
- **탭 칩이 붙어 답답함**(`assets/v2/streamlit-overrides.css`): segmented_control 의 실제 flex 컨테이너는 `[role="radiogroup"]`(이전 CSS 는 `[role="group"]` 을 잡아 미적용) + 각 버튼에 `margin-right:-1px`(테두리 공유)이 걸려 칩이 맞붙어 있었다. 셀렉터를 `[role="radiogroup"]` 으로 고치고 `gap:6px`+버튼 `margin:0` 으로 **칩 사이 6px 간격** 확보(개별 pill 로 분리).
- **탭 이동 시 우측 LLM 채팅창이 위아래로 12px 튐**: 채팅 컬럼이 `position:sticky` 라, 본문(좌측) 높이가 탭마다 달라 페이지가 안 스크롤되는 짧은 탭(예: 작업 정의)에서 sticky flow 위치가 어긋났다. 본문 컬럼에 `min-height: calc(100vh - 4px)` 를 줘 **항상 채팅 패널보다 살짝 크게** 만들어 sticky 가 늘 같은 위치에 고정되게 했다. **검증(playwright): 6개 탭 전부 채팅 top=20px 동일**(이전 작업 정의 탭만 8px) · 칩 간격 6px 균일 · pytest 774 passed.

### Changed (UX: 탭 룩 복원(segmented_control) + 채팅 입력창 하단 고정 + 조건부 렌더)
- **배경**: 직전 변경(st.tabs)으로 무깜빡임은 확보했으나 사용자 피드백 — ① 탭이 **밋밋한 기본 컴포넌트**로 바뀌었고, ② 채팅 **입력창·보내기가 영역 중앙으로 떠서** 하단에 있어야 한다, ③ st.tabs 는 **비활성 탭까지 매 런 eager 렌더**(무거운 화면 불리).
- **데이터 관리 탭 → 스타일드 `st.segmented_control` + 조건부 렌더**(`ui/data_management_v2.py`): `st.tabs` 를 제거하고 `_render_dm_tabs` 를 `@st.fragment` 로 — 탭 바는 아이콘 단축 라벨(`🗞 수집잡`·`🔑 키워드`·`⚙️ 출처`·`📊 엑셀 업로드`·`✏️ 작업 정의`)의 segmented_control(`key=_dm_active_tab`), 본문은 **활성 탭만 `_render_dm_tab_panel` 로 조건부 렌더**(비활성 탭 본문은 계산 안 함). 탭 전환은 **이 fragment 만 rerun**(헤더·사이드바·우측 채팅 그대로 → 부분 갱신) · 활성 탭은 `session_state` 보존이라 **출처 토글·수집 등 앵커 리로드 후에도 같은 탭 유지**(st.tabs 의 첫 탭 복귀 문제 해소). CSS 로 탭 바를 카드형 pill(활성=accent 채움)로 스타일.
- **채팅 입력창 하단 고정 + 칩 분리**(`ui/chat_panel.py`, `assets/v2/streamlit-overrides.css`): `_chat_composer`(칩+입력 한 fragment) 를 **상단 추천칩(`_render_chat_suggestions`)** 과 **하단 입력 form(`_render_chat_input`)** 으로 분리. 입력 form 래퍼 `margin-top:auto` 로 **입력창·보내기를 컬럼 하단에 고정**, 추천칩은 안내문 바로 밑(상단). 칩 클릭은 `{key}__prefill` pending → `st.rerun()` → `_apply_pending_prefill` 이 다음 run 에 하단 입력창 값으로 주입(**`on_click` 미사용 — CLAUDE.md #3/CI 준수**, `value=` 대신 `key`+`session_state` 연결 원칙은 유지). 칩↔입력이 별도 영역이라 fragment 스코프 대신 소켓 full rerun(문서 reload·흰 깜빡임 없음).
- **검증(계측+playwright 실측)**: 탭 클릭 → 서버 `XRUN:DMTABS` 만(앱 레벨 `XRUN:APP` 0) = fragment 스코프 확정 · 기본은 jobs 본문만 렌더(`키워드 관리` 부재)·키워드 탭 전환 시 kw 본문만 = 조건부 렌더 확정 · textarea bottom=858/950px = 하단 고정 확인 · 칩 클릭 → 하단 입력창 자동 채움 확인(스크린샷). pytest **774 passed** · 금지패턴(on_click) 0.

### Changed (UX: 탭 전환 진짜 무깜빡임 — st.tabs 클라이언트사이드 + 채팅칩 위치 복구)
- **왜 Phase 1+2 가 부족했나(계측으로 규명)**: 서버에 실행 카운터를 심고 playwright 로 실측한 결과, fragment 는 **rerun 을 제대로 격리**하고 있었다(탭 클릭→`_dm_body_fragment` 만, 칩→`_chat_composer` 만, 문서 reload 0). 그런데도 "전체 새로고침"으로 보인 건 **시각적** 이유였다 — ① 데이터 관리 본문 전체(헤더 KPI + 수집잡 + 히스토그램 + 탭 본문)가 **하나의 거대한 `st.html` 덩어리**라 탭 전환 시 그 덩어리가 통째로 다시 칠해졌고, ② 추천 칩(`st.pills`)이 채팅 컬럼 **맨 아래로 밀려 안내문과 칩 사이에 큰 빈 공간**이 생겼다(`margin-top:auto` 바텀 핀).
- **데이터 관리 탭 → 네이티브 `st.tabs`**(`ui/data_management_v2.py`): `st.segmented_control`+`@st.fragment`(`_dm_body_fragment`) 와 monolithic `_render_main` 을 제거. 헤더(KPI)는 `_render_dm_header` 로 **탭 위에 1회만** 그리고, 5개 탭 본문을 `st.tabs` 패널(`_render_dm_tabs`)에 나눠 담았다(`_render_jobs_split` = 수집잡+뉴스 라이브러리). **탭 전환은 100% 클라이언트사이드(JS) → 서버 rerun·문서 reload·리페인트 전부 0.** 헤더·다른 탭·우측 채팅은 손도 안 탄다. legacy 앵커 빌더(`_dm_tabs_html` 등)는 테스트 호환용 보존. 단, `st.tabs` 는 코드로 탭을 못 고르므로 레거시 `?dm_grp/?dm_tab` 핸드오프는 1회 정리만 한다(출처 토글 앵커는 새로고침 후 첫 탭으로 복귀 — 토글 자체는 정상).
- **채팅 추천 칩 위치 복구**(`assets/v2/streamlit-overrides.css`): 입력 form 래퍼의 `margin-top:auto`(칩+입력을 컬럼 바닥으로 밀던 핀)를 `margin-top:4px` 로 바꿔 **추천 칩이 안내문 바로 밑에 다시 붙도록** 했다(큰 빈 공간 제거). 칩 클릭=fragment rerun 으로 입력창만 채우는 동작은 그대로. `st.tabs` 라이트·다크 가독성 토큰 스타일 추가.
- **검증(계측+playwright 실측)**: 데이터 관리에서 "출처 설정"·"키워드" 탭 연속 클릭 → 서버 `XRUN:APP` **0건 추가**(=클라이언트사이드 확정) · `window` 플래그 생존(문서 reload 0) · 5개 탭(`수집잡 · 뉴스 라이브러리`/`키워드`/`출처 설정`/`📊 엑셀 업로드`/`✏️ 작업 정의 관리`) 모두 렌더 · 칩이 안내문 바로 밑 배치 확인(스크린샷). pytest **774 passed** · 금지패턴 0.

### Changed (UX: 클릭/탭 시 전체 흰 깜빡임 제거 — fragment 스코프 전환 · Phase 1+2)
- **근본 원인**: 앱의 거의 모든 네비게이션이 `<a href="?param=…">` 앵커였다. 앵커 클릭은 **브라우저 문서 전체 reload**(빈 화면→프론트 재부팅→전 CSS 재주입→리페인트) → 클릭/탭/이동마다 흰 깜빡임. `@st.fragment`·`st.tabs`·`st.pills` 미사용이라 부분 갱신 수단이 전혀 없었다.
- **Phase 1 — 채팅 프롬프트 예시칩**(`ui/chat_panel.py`): 추천 질문을 전체 리로드 앵커(`?sola_prefill=`)에서 **입력창 바로 위 `st.pills`로 이동**하고, pill+입력 form 을 `@st.fragment`(`_chat_composer`)로 묶었다. 칩 클릭은 **이 fragment 만 rerun**(소켓) → 입력창에 텍스트만 채우고(`_apply_pending_prefill`), 채운 뒤 선택 즉시 해제(`__reset_pills`)해 편집/재선택해도 값이 안 덮인다. 북마크 `?sola_prefill=` URL 호환은 `_consume_prefill` 로 유지. **검증(playwright): 칩 클릭 → textarea 에 정확히 그 텍스트 + `window` 플래그 생존 = 문서 reload 없음.**
- **Phase 2 — 데이터 관리 탭**(`ui/data_management_v2.py`): 앵커 탭 바(`{{DM_TABS}}` 의 `<a ?dm_tab=>`)를 제거하고, 그룹·하위탭을 **`st.segmented_control` × 2 위젯**으로 바꿔 본문 전체를 `@st.fragment`(`_dm_body_fragment`)로 감쌌다. 탭 전환은 **fragment 만 rerun** → 본문만 교체, 우측 채팅·상단 topbar 재렌더·흰 깜빡임 없음. 본문은 기존 `_render_main`(활성 탭만 lazy 렌더) 유지. 핸드오프/북마크(`?dm_tab=src` 출처 토글·`?dm_grp=news` 상단검색)는 `_dm_sync_tab_from_query` 가 위젯 세션으로 1회 동기화. legacy 빌더(`_dm_tabs_html`/`_dm_groups_html`/`_dm_tab_href`)는 테스트·호환용으로 보존. **검증(playwright): "키워드" 탭 클릭 → kw 본문 전환 + `window` 플래그 생존 = reload 없음.**
- **다크 모드 가독성**(`assets/v2/streamlit-overrides.css`): Streamlit 이 native pills·segmented_control 의 비활성 배경을 정적 라이트로 하드코딩 → 다크에서 흰 글자가 흰 배경에 묻혔다. `.st-key-side_chat_suggest`/`.st-key-dm_tabbar` 스코프로 토큰(`--surface-card`·`--accent-ring`·`--text-secondary`) 강제 → 라이트·다크 모두 라벨 노출. 구 `.side-chat-chip(s)` 앵커 CSS 는 pills 스타일로 교체.
- 검증: pytest **775 passed**(빈 키워드/탭 테스트 갱신 + fragment 탭전환 e2e 3건 추가, `_apply_pending_prefill` 단위 2건) · 금지 패턴(on_click/raw requests) 0 · py_compile OK · playwright 로 두 화면 다크 스크린샷 + 무(無)reload 인터랙션 실측. (on_click 금지[I-3]는 fragment 내 위젯+`st.rerun(scope="fragment")` 로 준수.)

### Changed (수집 버튼: 빈 페르소나에서도 동작 + "지금 뉴스 수집"으로 개명)
- **문제**: "지금 새로고침" 버튼이 페르소나 관심사 키워드가 **0개면 수집을 통째로 건너뛰고**(`if not kws and not extra_feeds:` 가드) 캐시만 비워, 버튼을 눌러도 뉴스가 안 들어오는 것처럼 보였다. (별개로, 샌드박스 환경은 아웃바운드 HTTP 가 403 으로 차단됨 — `example.com` 까지 403 — 이는 환경 네트워크 정책이라 코드와 무관.)
- **수정 — 기본 키워드 폴백 + 키워드 무관 소스 항상 수집**: `board_v2`에 `DEFAULT_COLLECT_KEYWORDS=("자동화","AI")` 와 `_collect_keywords_with_default()`(관심사 비면 폴백 + 사용여부 플래그) 추가. `_consume_refresh_if_any`(데이터 관리)와 `consume_kw_action_if_any`의 `collect` 분기(보드) 모두 **스킵 가드를 제거**하고 폴백 키워드로 `collect_batch` 를 호출 → 네이버/구글은 자동화·AI 로 검색, tech 사이트(AI Times·오토메이션월드)·커스텀 RSS 는 키워드 무관하게 함께 수집. 토스트도 폴백 시 "관심사가 비어 기본 키워드(자동화·AI)로 N건 수집" 으로 안내.
- **개명**: 버튼 문구 **"지금 새로고침" → "지금 뉴스 수집"**(`_refresh_cta_html` 라벨·툴팁), 빈 상태 안내 문구 `[지금 새로고침]→[지금 뉴스 수집]`, 수집 런 로그 trigger 라벨 `수동 새로고침→수동 수집`.
- 검증: pytest **770 passed**(빈 키워드 skip 테스트 3건 → 폴백 호출 검증으로 교체, 버튼 라벨 테스트 갱신) · 금지 패턴(on_click/직접 requests) 0 · `collect_batch(['용접'])` 실측으로 원인(403/빈 키워드) 규명.

### Changed (상단 검색을 진짜 키워드 검색으로 — 가짜 ⌘K 팔레트 제거)
- **문제**: 상단 "검색창"이 클릭하면 타이핑 대신 **빠른 이동 메뉴(CSS-only ⌘K 팔레트)** 가 떴고, 입력이 불가능했으며 윈도우에 무의미한 `⌘K` 배지가 노출됐다.
- **수정(결정: 데이터 관리에서 필터)** — 가짜 검색 라벨/⌘K 팔레트(`render_command_palette`·`_NAV_ITEMS`·`v2-cmdk*`)를 **전부 제거**하고, `_render_topbar_search` 로 **실제 `st.text_input`** 을 헤더 아래에 렌더(커서·타이핑 O). Enter 또는 🔎 버튼으로 제출하면 `_news_search_q` 설정 + **🧱 데이터 관리** 뉴스 라이브러리로 이동해 제목·본문·요약·키워드에 그 단어가 든 뉴스만 필터(`_filter_news_by_query`, 30일, 대소문자 무시) + 결과 칩(`N건` · ✕ 해제). `.db-topbar` 그리드 3→2열(제목 | 액션).
- **함정 회피**: `st.form` 은 bare 모드(스모크)에서 전역 'active form' 상태를 남겨 이후 AppTest 가 nested-form 으로 깨지므로 **미사용** — `text_input`(Enter=rerun)+button+`_topbar_q_seen` 변화감지로 제출 검출. `_news_cards_html(q)` 는 검색어를 **인자**로 받아 `st.cache_data` 가 q 별 캐시 키를 잡음(세션 직접참조 시 stale + `.clear()` 깨짐 회피).
- 검증: playwright 시드 뉴스 4건 중 "용접" 검색 → 2건 정확 필터·데이터관리 이동·⌘K 부재 확인 · pytest **770 passed**(cmdk 테스트→검색 테스트 교체) · 금지 패턴 0.

### Fixed (다크 팔레트 점검 + LLM 채팅 패널 크기/sticky)
- **다크모드 ⌘K 팔레트·드롭다운 허옇게** — ⌘K 모달이 `background:#fff` 하드코딩이라 다크에서 흰 배경+밝은 글자로 안 읽혔다(`app_shell` `.v2-cmdk-modal`→`var(--surface-card)`). 추가로 다크에서 색이 안 잡히던 표면 보강: 네이티브 selectbox **드롭다운 팝오버**(body 루트 포털 `[data-baseweb="popover"]` 메뉴/옵션), `st.dialog` 모달, 토스트 → 다크화. `data_management_v2` 인라인 `background:#fff` 3곳 → `var(--surface-card)`.
- **LLM 채팅 패널이 한 화면에 안 들어오고 스크롤 시 따라 움직임** — 근본 원인: 스타일 주입용 `st.markdown("<style>")` 컨테이너(전역·테마·화면 CSS) 3개가 **보이지 않지만 루트 flex 자식**이라 본문/채팅 컬럼을 ~48px(top 56) 아래로 밀어 패널 하단(입력창)이 뷰포트 밖으로 넘쳤다. → `[data-testid="stElementContainer"]:has([data-testid="stMarkdown"] style)` 를 `display:none`(스타일은 숨겨진 요소에서도 전역 적용 → 안전, st.html=stHtml 미해당이라 cmdk/배너 영향 0). 효과: 채팅 컬럼 top **56→24px**, 700px 스크롤 시 이동 **−36→−4px**(사실상 고정), 입력창까지 한 화면에. 패널에 `align-self:flex-start`(stretch 로 늘어나 sticky 무력화되던 것 방지)+`height:calc(100vh-24px)`+내부만 스크롤+배경 토큰화.
- **부수**: 위 collapse 로 테마 토글 레이아웃 밀림도 더 견고히 차단(숨겨진 블록은 개수 무관 gap 0).
- 검증: playwright 다크 스크린샷(⌘K·채팅) + 스크롤/좌표 측정 · pytest **769 passed** · 금지 패턴 0.

### Fixed (사이드바 간격 · 테마 토글 레이아웃 밀림 · 다크 placeholder)
- **테마 토글 시 레이아웃 밀림** (`ui/styles.py inject_user_prefs`) — light(빈 CSS)는 `st.markdown(<style>)` 를 **안 그리고** dark/ocean/sunset 은 그려서, Streamlit 루트 수직 블록의 자식(=주입 블록) 개수가 테마마다 달라졌다. 그 차이만큼 flex `gap` 이 하나 더/덜 생겨 **색뿐 아니라 위치가 밀렸다**. → 내용이 비어도 **항상 단일 `<style>` 블록**을 주입해 DOM 개수를 고정. playwright 측정으로 light↔dark 시 `.db-topbar`·브랜드 좌표 Δ=0(이전엔 어긋남) 확인.
- **다크모드 입력 placeholder 안 보임** (`_DARK_CSS`) — 입력 배경만 다크화(#0F172A)하고 placeholder 색은 안 잡아, 기본 회색 placeholder 가 어두운 배경에 묻혔다. → native `stTextInput`/`stTextArea` + baseweb 래퍼의 `::placeholder` 를 밝은 muted(`rgba(241,245,249,.5)`)로(+`-webkit-text-fill-color`·`opacity:1`). 세션 검색·SOLA 채팅창 등 가시화 확인.
- **사이드바 섹션 간격** (`assets/v2/sidebar.css`) — 블록 간 구분감이 없던 것: 수직 블록 `gap` 0.4→0.7rem, `stSidebarUserContent` padding-top 14→16px, 메뉴(`.sidebar-section-nav`) 위 여백 확대로 타이틀·페르소나·통계·메뉴 영역을 분명히 분리.
- 검증: playwright 라이트/다크 스크린샷·좌표 측정 · pytest **769 passed**(ui_prefs 계약 테스트 갱신) · 금지 패턴 0.

### Changed (사이드바 메인 로고 — 더 크고 멋지게)
- **메인 로고 리디자인** (`ui/sidebar.py` + `assets/v2/sidebar.css`) — 작던 "IB" 텍스트 배지(30px)를 **그라데이션 마크(44px) + 인사이트 글리프 + 두-톤 워드마크 + 태그라인** 로 격상.
  - 마크: `linear-gradient(135deg, #2563EB→#4F46E5→#7C3AED)` 라운드 스퀘어 + soft glow 그림자, 안에 흰색 SVG 글리프(상승 막대 3개 + 인사이트 스파크).
  - 워드마크: "Insight **Board**" 19px(기존 15.5px), "Board" 만 accent 컬러로 두-톤.
  - 태그라인: "조선소 작업 인사이트"(uppercase muted) 추가.
- **SVG 렌더 함정 처리** — 인라인 `<svg>` 는 `st.html` 이 sanitize 하므로 `prepare_screen_html` 로 data-URI `<img>` 변환(보드 topbar 패턴). 변환 시 `<svg>` 에 **`xmlns` 필수**(없으면 data-URI img 가 broken) — 추가함.
- 검증: playwright 사이드바 스크린샷으로 글리프·그라데이션·워드마크 정상 렌더 확인 · pytest **769 passed** · 금지 패턴 0.

### Changed (사이드바 — 대표 브랜드를 최상단으로)
- **사이드바 순서 재배치** (`ui/sidebar.py`) — `render()` 가 페르소나 카드를 맨 위에 그리던 것을, **사이트 대표 로고(IB)+타이틀 "Insight Board" 를 최상단 헤더로** 올림(브랜드 → 프로필 → 통계 → 네비 → 푸터). 사이드바 정체성이 맨 위에 오는 일반적 패턴.
- `assets/v2/sidebar.css` — `.sidebar-brand-top` 신규: 최상단 브랜드를 약간 강조(로고 26→30px·타이틀 14→15.5px) + 하단 구분선으로 아래 프로필 카드와 분리. (구 `.sidebar-brand.compact` 중간 배치 클래스 대체.)
- 검증: playwright 사이드바 스크린샷으로 브랜드 최상단·프로필 그 아래 시각 확인 · pytest **769 passed**(sidebar 6 green) · 금지 패턴 0.

### Fixed (오늘의 보드 상단 헤더 ↔ 사이드바 간섭 — 전 화면 통일)
- **board 상단 헤더가 네이티브 사이드바를 침범/가리던 문제** — `assets/v2/screens/board.css` 가 `.db-topbar { position: fixed; left:0; right:0 }` 로 **재정의**해, 보드에서만 헤더가 풀폭 fixed 로 튀어나와 좌측 `st.sidebar` 와 겹쳤다(다른 화면은 전역 `shell.css` 의 `position: static` in-flow 헤더를 그대로 사용). 이 override 는 제거된 구 v2 셸(고정 좌/우 패널 `.app-side`/`.app-sola`) 시절의 잔재였고, `.db-topbar-*` 내부 스타일까지 다른 값으로 덮어써(제목 28px·eyebrow 숨김 등) 보드 헤더만 다르게 보였다.
- **수정** — board.css 상단의 stale topbar + 제거-패널 레이아웃 블록(160줄: `.db-topbar` fixed override · `.db-topbar-*` 중복 · `.v2-scroll-fade` · `.app-with-*`/`.app-side`/`.app-sola` · `.hub-back` · `.db-app{padding-top}`)을 전부 삭제. 보드도 이제 전역 `shell.css` 의 in-flow `.db-topbar` 를 써 **5개 화면 헤더가 완전 동일**(WORKFLOW eyebrow + 제목 + 갱신시각 + 검색, 사이드바와 겹침 0).
- 검증 — playwright 전 화면 스크린샷(`scripts/verify_screens.py`)으로 board/data/insights/sola/archive 헤더가 동일 in-flow 임을 시각 확인. pytest **769 passed**(CSS only) · 금지 패턴 0.

### Refactor (오버사이즈 모듈 분할 — data_management_v2 프레젠테이션 추출)
- **`ui/data_management_render.py` 신규(259줄)** — `data_management_v2.py`(1623줄, 오버사이즈)에서 **부작용 없는**(st·데이터 I/O 없는) 순수 프레젠테이션/라우팅 빌더를 분리: 뉴스 카드(`_news_age_label`/`_news_card_html`/`_news_empty_html`), 탭·그룹 라우팅+HTML(`_dm_group_of`/`_dm_resolve_group_and_tab`/`_dm_tab_href`/`_dm_group_href`/`_dm_groups_html`/`_dm_tabs_html`/`_src_action_href`) + 관련 상수(그라데이션·탭/그룹 정의·아이콘 SVG). 데이터를 읽거나 `st.*` 를 호출하는 빌더(수집 헬스·타임라인·탭 본문)는 화면 모듈에 잔류.
- **하위호환** — `data_management_v2` 가 이 심볼들을 re-import(`# noqa: F401`)해 기존 참조(테스트 `test_dm_tabs` 포함)·내부 호출 전부 무변경. 동작 100% 동일(769 passed). 스테일 `import pandas as pd`(이동 후 미사용) 제거.
- **효과** — `data_management_v2` 1623→**1406줄**(−217), 순수 빌더가 테스트하기 쉬운 독립 모듈로. (board_v2 분할은 후속 — 빌더가 데이터-결합도가 높아 별도 신중 PR.)
- 검증: pytest **769 passed**(불변) · 금지 패턴 0 · py_compile OK.

### Added (render() 스모크 테스트 — 화면 조립 경로 커버리지)
- **`tests/test_screen_smoke.py` (+13)** — 6개 화면(board/data/insights/sola/archive/persona)의 `render()` 가 빈 데이터(conftest tmp 격리)에서 **예외 없이 끝까지 통과**하는지 + 각 `chat_context_block(persona)` 가 문자열 반환 + SOLA 작업실 인계(`?from=opp`) 경로까지 스모크. 개별 `_*_html` 빌더·pending consumer 는 단위 테스트가 덮지만 render() **조립**(topbar→핸드오프→본문+pending 소비)은 무커버리지였음. Streamlit 이 ScriptRunContext 없이 위젯 기본값 반환(st.button→False)이라 실제 render() 호출로 조립 깨짐(빠진 속성·잘못된 호출·빌더 예외)을 싸게 잡음(mock 은 `st.rerun` no-op 하나뿐 — brittle 회피). 빈 데이터에서 6 render 전부 clean 통과 확인.
- **conftest sola_threads 격리 (테스트 인프라 버그픽스)** — 스모크가 노출: `store.sola_threads` 는 `from config import SOLA_DIR` 를 import 시점에 가져가는데 conftest 가 `cache`/`chat_log` 만 동기화하고 `sola_threads` 는 빠뜨려, `sola_workshop.render()` 가 **실제** `data/sola/threads.json` 에 쓰려다 fresh clone(CI)에서 `FileNotFoundError`. conftest 에 `sola_threads.SOLA_DIR` tmp 동기화 추가(cache/chat_log 와 동일 패턴) → 모든 thread-touch 테스트가 tmp 격리.
- 검증: pytest **756→769 passed**(+13) · 금지 패턴 0 · py_compile OK · CI(#110) 재확인.

### Added/Changed (개선 백로그 잔여 — 의미매칭 엣지 테스트 + guard 확대)
- **[의미매칭 엣지케이스]** `tests/test_match_semantic.py` +6 — 내부 TF-IDF 헬퍼 직접 검증: `_build_idf`(빈 코퍼스→{} · 흔한 토큰도 smoothed 양수 idf · 희소어>흔한어), `_tfidf_vec`(빈 counter→norm 1.0 · idf 없는 토큰 제외), `_cosine`(disjoint=0 · 자기자신=1 · **작은쪽 순회 최적화의 대칭성** a·b==b·a). 신경망 임베딩 스왑 시 회귀 가드.
- **[#3 guard 확대]** `board_v2` 의 silent 데이터-로드 6곳(`try: x=load() except: x=None`)을 `ui._safe.guard` 로 — 기회 매트릭스(html·svg)·보드 KPI·키워드 관리·채팅 컨텍스트의 뉴스/작업 로드. 실패 시 None 폴백은 유지하되 WARN+스택트레이스가 로그에 남아 "보드가 왜 비었나" 추적 가능. (의도적 graceful empty-state·cache-clear except 은 미변경.)
- 검증: pytest **750→756 passed**(+6) · 금지 패턴 0 · py_compile OK.

### Changed (SOLA UX — 채팅 단일 진입점 통합 + 인계 자동 실행)
SOLA 작업실의 LLM 상호작용이 중앙 작업대 버튼과 우측 채팅 두 곳에 분산돼 헷갈리던 것과, 보드/인사이트 인계 배너가 prefill 만 하고 멈추던 것을 해소(사용자 결정 반영, 719+ 누적 → **750 passed**).
- **[SOLA 채팅 통합]** 중앙 작업대의 액션(📝 제안서 생성 · 📰 뉴스 요약 · ➕ 새 대화)을 우측 채팅 상단 **빠른 작업** quick-action 칩으로 흡수 → 채팅 단일 진입점. `chat_panel._quick_actions_html(area_key)` 가 SOLA 작업실 area 에만 칩을 그리고(`?sola_action=<name>` 링크, on_click 미사용, dept/lv3/from 인계 컨텍스트 보존), `sola_workshop_v2._consume_sola_action_from_query_if_any` 가 기존 pending flag(`_do_generate_proposal`/`_do_summarize`/`_do_new_thread`/`_do_save_proposal`)로 매핑해 같은 run 의 후속 consumer 가 처리(LLM 호출·rerun 위임). 작업대의 중복 버튼 3개(`wb_gen_proposal`/`wb_summarize`/`wb_new_thread`) 제거 → 채팅으로 안내. 문서 산출물·저장/다시생성·세션 목록은 작업대에 유지.
- **[handoff LLM 자동 실행 배선]** 그간 휴면(테스트만 트리거)이던 `_do_ask_prefill` 흐름을 인계에 배선. `_auto_run_handoff_if_any` 가 `?from=brief/opp/matrix/ia_map/edit` 인계 도착 시 prefill 이 있으면 **자동으로** 새 thread 생성 + LLM 전송까지 1회 실행(`_handoff_signature` 로 같은 인계 재전송 차단, prefill 빈 인계는 무시). 배너에 "✓ SOLA 가 자동으로 검토를 시작했어요" 확인 줄 추가(우측 채팅으로 시선 유도). 배너 docstring 의 "LLM wire 후속 PR" 인정 문구 제거.
- `assets/v2/streamlit-overrides.css` — `.side-chat-actions`/`.side-chat-action`(primary 톤 quick-action 칩, 추천질문 chip 과 시각 구분) + 배너 `.ws-brief-autorun`(점선 구분 confirm 줄) 스타일.
- 테스트 +8 — `test_chat_panel`(quick-action 노출/area 한정/컨텍스트 보존 2), `test_sola_composer`(action→flag 매핑 3 · handoff 자동실행 1회성/빈prefill/비인계 3).
- 검증: pytest **742→750 passed**(+8) · 금지 패턴 0(on_click/requests) · py_compile OK.

### Performance/Changed (개선 백로그 저위험 잔여 마무리)
- **[2.3] `match.score_matches` iterrows 제거** — news/tasks 를 `df.iterrows()`(행마다 Series 생성) 로 4회 순회하던 것을 `to_dict("records")` 1회 변환으로 대체. 결과 불변(기존 매칭 테스트 green), 큰 프레임에서 체감.
- **[2.4] `run_log._trim` 사이즈 게이트** — `record_run` 마다 전체 JSONL 을 읽어 줄 수 세던 것을, 파일 크기가 확실히 `max_keep` 미만(`size < max_keep*80B`)이면 읽기 스킵. 트림 동작은 동일.
- **[#3 guard 확대]** — `insights_v2` 데이터-로드 3곳(news 30d/7d·tasks)을 `ui._safe.guard` 로. (insights/board 의 `except: return empty` 형 graceful 빈-상태 except 는 의도적 유지.)
- 검증: pytest **740→742 passed**(+2 trim) · 금지 패턴 0 · py_compile OK.

### Added/Changed (개선 백로그 잔여 — LLM 회복력·템플릿 검증·guard 확대)
- **[4.4] LLM 타임아웃/재시도** (`sola/client.py`) — OpenAI 클라이언트에 `timeout=45s` + `max_retries=2` 명시. 행이 걸린 백엔드가 Streamlit rerun 을 무한정 멈추던 것 방지(SDK 기본 무한 대기 → 명시 한계). `scraping.http` 단일-진입 회복력과 동일 철학.
- **[4.3] 템플릿 placeholder 소비 검증** (`tests/test_template_placeholders.py`) — `screens/*_main.html` 의 `{{TOKEN}}` 이 대응 `ui/*_v2.py` 에서 모두 소비되는지 정적 교차검증(4화면). placeholder 리네임 드리프트가 silent 빈/리터럴 렌더로 새는 것을 차단.
- **[#3 guard 확대]** — `board_v2` 데일리 브리핑 데이터-로드(news/tasks) 2곳을 `ui._safe.guard` 로 전환. board/insights 잔여 ~38 site 는 후속.
- 검증: pytest **735→740 passed**(+5) · 금지 패턴 0 · py_compile OK.

### Added/Changed (개선 백로그 최우선 3건 — 관측성·성능)
완성도 점검 후 forward-looking 리뷰로 도출한 high-priority 3건 착수(719→**735 passed**).
- **[#1 관측성] 수집 degraded 가시화** — cron 0건/실패가 화면·CI 모두 무신호던 것: ① `data_management` 상단 경고 배너(`_collect_alert_html`) — 최근 런 실패(빨강)·24h+ 정체(주황) 시 prominent 알림(`run_log.latest_run()` 기반, 런 없으면 무알림). ② `daily_scrape --fail-on-empty` — 0건 저장 시 `exit 1` 로 GitHub Actions 가 silent starvation 을 빨갛게 표면화(`scrape-daily.yml` 이 플래그 ON, 기본은 여전히 exit 0).
- **[#2 성능] `load_news_for_days` 디스크 재읽기 memo** — 같은 뉴스 윈도가 한 렌더에서 여러 `@st.cache_data` wrapper 로 각각 parquet 재읽기·재concat 하던 것 dedup. 디렉토리별 키 + 일별 mtime/parquet수 시그니처(새 수집 시 자동 무효화·stale 없음), `.copy()` 반환(캐시 보호). 호출부 34곳 무변경. *(매칭 결과 캐시 2.1 은 캐시키 위험 커 보류.)*
- **[#3 관측성] silent except 로깅 가드** — `ui/_safe.guard(label)` 컨텍스트매니저 신규(예외 삼키되 WARN+스택트레이스 로깅, UX 무변화). `data_management_v2` 데이터-경로 silent 로드 5곳 전환(패턴 확립). 남은 ~40 site 롤아웃은 후속.
- 검증: pytest **735 passed**(+11: 배너 4·fail-on-empty 2·news memo 1·guard 4) · 금지 패턴 0 · py_compile OK.

### Docs (최신화·정리 + 개선 백로그 캡처)
- **README** 셸 설명 최신화 — 삭제된 구 고정패널(`app-side` nav · `app-sola` 패널) 서술을 현행(좌 네이티브 `st.sidebar` + 본문 in-flow 헤더 + `st.columns([2.3,1])` 중앙/우측 채팅 `render_side`)으로 교체. 테스트 수 `60+`→`720+`(69파일).
- **SESSIONS** '다음 세션 시작점' 블록 갱신 — stale 한 현재상태(`main 7debc32`·PR #90/#91)를 `main e87f6e7`·이 세션 누적(#97~#103) + 완성도 점검 결론으로 교체. 남은 일을 외부 의존/결정(RAG·PR #49)으로 정리.
- **REFACTOR_PLAN** — `post-M3 완성도 하드닝(완료)` 섹션 + **개선 백로그(forward-looking)** 추가. 점검 후 도출한 개선포인트 16건을 우선순위(🔴 high / 🟡 med / ⚪ low / 🚧 외부)로 캡처 — 수집 degraded 가시화·매칭/뉴스 캐시 통합·silent except 로깅가드가 최우선.
- 코드 변경 없음(docs only) — pytest 724 passed 유지.

### Fixed (완성도 점검 잔여 — 문서/코드 드리프트 A3 + 다크 sparkline)
- **A3 문서/코드 드리프트** — `docs/ARCHITECTURE.md`·`docs/INVARIANTS.md` 가 "SOLA 작업실은 풀스크린·우측 채팅 컬럼 미렌더" 라고 적었으나, `app.py` 는 **모든 화면 통일**로 작업실도 `chat_panel.render_side` 를 우측에 렌더(작업실 중앙=산출물 작업대, 우측=글로벌 채팅). 코드가 현재 의도이므로 **문서를 코드에 맞춤**(작업실 예외 제거). 부수로 `st.columns([2.7,1])`→실제 `[2.3,1]` 도 정정. *(작업실에서 우측 채팅을 억제하려면 별도 코드 변경 — 현재는 의도적 미억제로 명시.)*
- **다크 sparkline** (`data_management_v2._hist_html`) — 14일 수집량 SVG 가 data-URI img 라 CSS 변수를 못 써 고정 라이트색(#2563EB/#CBD5E1/#E5E7EB)이던 것 → `dark` 파라미터(캐시 키)로 테마별 색 분기(다크: #60A5FA/#475569/#334155). 호출부가 `ui_prefs` 테마를 읽어 전달.
- 검증: pytest **724 passed** · 금지 패턴 0 · py_compile OK · 다크/라이트 SVG 색 분기 스모크 확인.

### Fixed (완성도 점검 후속 — 데이터-계약·관측성·목업·SQLite 견고성)
시스템 완성도 점검에서 발견한 잠재 결함 4건을 순차 수정(719→**724 passed**).
- **[C1/C2/D4] 데일리 브리핑 매칭경로 부활 + null 안전** (`store/news_db.py`) — `board_v2` 가 select 하던 `collected_at` 컬럼이 **어떤 스크래퍼·스토어도 안 쓰던** 컬럼이라 매번 KeyError→broad except 로 삼켜져 '아침 7분' 브리핑의 매칭-뉴스 분기가 **조용히 죽어** '최근 3건' 폴백만 돌던 것 → `collected_at` 을 `_ARTICLE_COLS` 에 추가하고 저장 시 `enriched_at→published_at` 폴백으로 채움(단일 '수집 시각'). `_to_df`/`_normalize_loaded` 에 `fillna("")` — null `image_url` 이 `astype(str)` 로 `"nan"` 문자열이 돼 `if image_url:` 가 truthy→깨진 `<img src=nan>` 나던 것 차단.
- **[B4] 데이터-경로 silent 실패 로깅** — broad except 가 진짜 오류를 무로깅 삼켜 '무데이터'와 '코드 깨짐'을 구분 못 하던 문제. 데이터-계층 핵심 3곳에 `logging` 추가: `board_v2` 브리핑 매칭조인(C1 을 가렸던 자리)·`news_db` 깨진 parquet(파일명)·`enrich` 기사 파싱(URL). 122개 UI 렌더 except 는 best-effort 라 제외.
- **[D1/D2] archive 정적 목업 영구 제거** (`assets/v2/screens/archive_main.html`) — 죽은 컨트롤 스트립 + '전체 산출물 45건' 표 + 'PRO-2026…₩1.4억' 가짜 제안서가 매 렌더 `_strip_oa_mockups` 문자열 슬라이스로만 가려져 마커 드리프트 시 재등장 위험이던 것 → 템플릿에서 직접 삭제(23KB→3.6KB) + 스트리퍼 제거. 테스트를 '템플릿에 목업 부재' 직접 검증으로 전환.
- **[C3/C4] SQLite 견고성** — ① 로드맵 엑셀 업로드의 SQLite 동기화 실패가 `except: pass` 로 묻혀, Parquet 만 갱신되고 SQLite-우선 reader(`query.load_latest`)가 stale 데이터를 읽어 분기되던 위험 → `IngestResult.sqlite_error` + `logger.warning` 로 표면화. ② `task_defs_db` 가 `CREATE IF NOT EXISTS` 만이라 기존 `*.db` 에 새 컬럼이 반영 안 되던 것 → `_migrate`(`user_version` + 누락 컬럼 `ALTER ADD`) forward-마이그레이션.
- 검증: pytest **724 passed**(+5: news_db 2·ingest 1·task_defs_db 2) · 금지 패턴 0 · py_compile OK.

### Fixed (UI 다크 모드 2차 — 작업 정의 상세 뷰 · 콜아웃 배너 일관성)
- **작업 정의 상세/카드 뷰**(`ui/task_def_manage.py`)가 고정 라이트색(흰 카드 `#fff`·`#0F172A` 등)이라 다크에서 밝은 섬으로 떠 보이던 것 → 스타일 상수 전체를 토큰화(`var(--surface-card/soft)`·`var(--text-primary/secondary/muted)`·`var(--surface-divider)`·danger 는 `var(--semantic-danger)` 틴트). 토큰 라이트값이 기존 hex 와 동일/근접이라 **라이트 무변경**(테스트 78건 green).
- **콜아웃 배너 다크 변형**(`_DARK_CSS`) — LLM 미설정 배너(`.app-llm-banner`, amber)·브리프 핸드오프(`.ws-brief-handoff`, blue)가 라이트 고정색이라 다크에서 밝게 떠 보이던 것 → 다크 틴트(반투명 amber/blue + 밝은 텍스트) 오버라이드.
- 메인 5화면(보드/데이터관리/인사이트/작업실/보관함)은 1차로 이미 다크 정상 확인(playwright). 잔여: sparkline SVG(data-URI라 CSS var 불가, 현재도 라이트 바라 다크에서 가독은 됨) — 필요 시 테마별 색 생성으로 후속.
- pytest **719 passed** · 금지 패턴 0 · py_compile OK.

### Fixed (UI 다크 모드 — 입력창·카드 배경이 다크에서 하얗게 남던 문제)
- **입력창(검색·채팅 textarea·select) 흰색** — `_DARK_CSS` 가 안쪽 `input`/`textarea` 만 다크화하고 baseweb 래퍼는 안 칠해, Streamlit 1.58 의 `[data-baseweb="base-input"]` 래퍼가 흰색으로 남아 다크에서 입력창이 하얗게 보였다. 래퍼(`base-input`/`input`/`textarea`)까지 다크화. (playwright 로 textarea 래퍼 `rgb(255,255,255)→rgb(15,23,42)` 확인)
- **카드 배경 흰색** — 화면 CSS 8곳(`board.css`·`card.css`·`archive.css`·`sola.css`)이 카드 배경에 고정 `#FFFFFF`/`#FAFBFD` 그라데이션을 써서 다크에서 흰 카드로 남았다(특히 보드 인사+KPI `.db-greet`). `var(--surface-card)`/`var(--surface-soft)`/`var(--surface-inset-bg)` 로 토큰화 → 다크 추종. **라이트 토큰값이 원래 hex 와 동일**(`--surface-card`=#FFFFFF, `--surface-soft`=#F5F7FB)이라 라이트 모드 무변경(playwright 회귀 확인).
- 검증: 다크/라이트 보드 스크린샷 대조 — 다크에서 입력창·카드 모두 다크, 라이트 무변경. pytest **719 passed** · 금지 패턴 0 · py_compile OK.
- 후속: 잔여 인라인 hex(상태 배지·일부 텍스트색)·sparkline SVG(data-URI 라 CSS var 불가, 테마별 색 생성 필요)는 다음 패스.

### Added (match — TF-IDF 코사인 의미유사도 하이브리드 매칭)
- `store/match.score_matches` 에 `semantic_weight` 파라미터 추가(기본 0 = 순수 토큰 매칭, **하위호환**). >0 이면 작업·뉴스 문서를 **TF-IDF 벡터화**해 코사인 유사도를 `weight*cosine` 만큼 점수에 가산. 토큰 '교집합'은 같은 단어가 정확히 겹쳐야 점수가 났지만, TF-IDF 는 **흔한 단어는 낮게·희소한 핵심어는 높게** 가중 + 길이 정규화 → 표현이 달라도 주제가 가까운 매칭을 끌어올린다. `_build_idf`/`_tfidf_vec`/`_cosine`(순수, 네트워크·모델다운로드 불필요).
- **호출처 활성화** — 보드 탑스토리·인사이트 공정매핑·SOLA 작업실·자동화 기회 매트릭스(`opportunity`)가 `semantic_weight=DEFAULT_SEMANTIC_WEIGHT`(=4.0)로 호출. `_SEM_MIN_COS`(0.05) 미만 코사인은 잡음으로 무시(공유 토큰 0 → 매칭 안 됨).
- **설계 메모**: 신경망 임베딩(RAG)은 임베딩 백엔드(groq 미지원·이 환경 네트워크 차단)가 필요해 지금은 classical TF-IDF 로 구현 — `_tfidf_vec`/`_cosine` 시ジ를 임베딩 벡터로 교체하면 그대로 확장 가능.
- `tests/test_match_semantic.py`(+4: 하위호환·idf 동점변별·무공유 무시·빈입력). pytest 715→**719 passed** · 금지 패턴 0.

### Added (data-mgmt — 수집 헬스: 14일 sparkline 일별 런 성공/실패 오버레이)
- `store/run_log.daily_status(days)` 신규(순수) — 최근 N일 각 날짜의 런 상태(`ok`/`fail`/`None`, 하루 중 하나라도 실패면 `fail`). `data_management_v2._runstatus_strip_html` 가 14일 볼륨 sparkline 아래에 14칸 스트립으로 겹침(성공 초록/실패 주황/런없음 divider, hover 날짜·상태). 볼륨(news_db)은 '몇 건', 스트립(run_log)은 '그날 런이 돌고 성공했나' → **cron 이 조용히 실패한 날**(볼륨 0 + fail/런없음)을 한 줄로 구분. 런 기록 없으면 빈 문자열(무변경). CSS `.dm-runstatus`(토큰).
- `tests/test_run_log.py`(+2)·`tests/test_collect_health.py`(+2). pytest 711→715 passed.

### Fixed (UI — 사이드바 접기/펼치기 버튼 · 채팅 패널 안내·추천·입력)
- **사이드바 펼치기 버튼 복구** — `streamlit-overrides.css` 가 상단 `stHeader` 를 통째로 `display:none` 해서, 사이드바를 한 번 접으면 펼치기 버튼(`stExpandSidebarButton` — Streamlit 1.58 에선 헤더 toolbar 안에 렌더)까지 함께 사라져 **다시 펼칠 방법이 없던** 문제. 헤더를 flow 에서 빼고(absolute·height:0·투명·pointer-events 통과) toolbar 노이즈(메뉴/배포/상태/장식)만 숨기되 펼치기 버튼은 좌상단 고정으로 항상 노출. 접힘 시 페이지 헤더(`.db-topbar`)를 46px 밀어 버튼이 첫 글자를 가리지 않게.
- **사이드바·본문 겹침** — 정상 폭(≥768px)에선 겹침 0 확인(playwright 실측). 좁은 폭(<768px)에서 Streamlit 이 사이드바를 오버레이로 띄우던 것이, 펼치기 버튼 복구로 **접어서 본문을 볼 수 있게**(dismiss 가능) 개선.
- **채팅 패널 — 안내/추천 영속** — 메시지가 하나라도 생기면 안내 카드+추천 질문이 사라지던 것을, 채팅 스크롤 **최상단에 항상** 두고 그 아래로 대화가 쌓이게(위로 스크롤하면 안내가 그대로). `render_side` 가 `_intro_card_html`+메시지를 한 `.side-chat-scroll` 컨테이너로 묶음.
- **채팅 패널 — 추천 질문 클릭 미동작** — 추천 질문이 정적 `<span>` 이라 클릭해도 입력창에 안 들어가던 버그. `?sola_prefill=<질문>` 링크로 바꾸고 `_consume_prefill` 이 위젯 생성 전 입력창 값으로 주입(사이드바 nav 와 동일한 query_params 패턴, on_click 미사용).
- **채팅 패널 — 표시 영역 확대** — 채팅 컬럼 비율 `[2.7,1]→[2.3,1]`, 메시지 버블 폭 `75%→92%`(+word-break), 안내·버블·칩 색을 토큰화(다크 추종).
- **검증**: 사전설치 chromium + playwright 라이브 — 접기→펼치기 버튼 보임·클릭·재펼침 **PASS**, 추천칩→입력창 채움 **PASS**, 대화 후 안내 최상단 유지 **PASS**. `tests/test_chat_panel.py`(+3). pytest 708→**711 passed** · 금지패턴 0 · py_compile OK.

### Added (수집 헬스 고도화 — 최근 N회 런 미니 타임라인, run_log 기반)
- **`data_management_v2._run_timeline_html()` 신규** — 🧱 데이터 관리 '수집 히스토리' 카드에 최근 12회 수집 런을 미니 막대 타임라인으로 노출(왼쪽=과거, 오른쪽=최신). 각 셀 높이=기사량(상대), 색=성공(`--semantic-success`)/오류(`--semantic-warning`), hover=`트리거 · 날짜 시각 · N건 · 정상/오류`. 헤더 `N/M 정상`(성공률) + foot(가장 오래된 날짜 / 최신 시각). 이전엔 '수집 헬스' 1행이 **마지막 런만** 보여줘서 **연속 실패·런 누락 패턴**이 안 보이던 것을 보완. `run_log.load_runs()` 기반이라 "cron이 돌았지만 0건"(정상 셀, 높이 최소)과 "런 자체가 없음"(셀 부재)을 구분.
- `_hist_html()` 반환 dict 에 `"runs"` 키 추가(기존 캐시 60초 + 새로고침 무효화 경로 재사용 → 별도 캐시 등록 불필요) · 템플릿 `data_management_main.html` `{{HIST_RUNS}}` placeholder · CSS `.dm-runs/.dm-run-track/.dm-run-cell/.dm-run-fill`(토큰 기반 — 다크 추종).
- **볼륨 14일 sparkline 은 news_db 유지** — run_log 는 Phase F 부터라 14일 히스토리가 아직 없어 즉시 전환 시 빈 차트 회귀. '일별 수집량'은 news_db(`collected_at`)가 정확한 소스이고, 런 헬스(성공/cadence)는 새 타임라인이 담당하도록 역할 분리.
- `tests/test_collect_health.py`(+4: empty·런당 셀·ok/오류 색·N 상한) · `tests/test_dm_tabs.py` mock 에 `"runs"` 키 반영. 검증: pytest 704→**708 passed** · 금지 패턴 0 · py_compile OK.

### Added (test — 네이버 검색 파서 회귀 테스트 + 라이브 수집 검증)
- **`tests/test_naver.py` 신규(+6)** — 4개 수집 소스 중 유일하게 단위테스트가 없던 네이버 리스트 파서(`naver.search`)를 고정. 현행 네이버 결과 구조(`div.fds-news-item-list-tab > div`) 기반 합성 HTML 로 ① 제목·언론사·날짜·요약 추출, ② `n.news.naver.com` '네이버뉴스' 앵커 **링크 우선**(없으면 언론사 원문 폴백), ③ 썸네일 `data-src`>`src` 우선, ④ `max_results` 제한, ⑤ 빈 키워드 short-circuit, ⑥ HTTP 오류→`RuntimeError` 전파를 단언. `time.sleep` 은 patch 로 무력화.
- **라이브 수집 재검증(요청)** — 네이버/구글 키워드검색·AI Times·오토메이션월드의 제목/본문전체/사진 수집을 라이브로 확인 시도. **이 원격 환경의 네트워크가 여전히 제한적 allowlist** 라(pypi.org 200, 그 외 news 도메인·google.com·example.com 전부 403 `Host not in allowlist`; WebFetch 동일 차단) 라이브 fetch 불가. 대신 파서 로직을 오프라인으로 검증: `fetch_article` 가 본문 전체(문단 결합·코드/저작권 노이즈 제거)+대표사진(og:image)을, 구글 RSS 파서가 제목/언론사/썸네일을 정확히 추출함을 확인(파서 회귀 45건 green). 라이브 점검은 환경 네트워크 정책=전체 도메인 허용 + **새 세션** 에서 재시도 필요.

### Fixed (scraping — tech 사이트 HTTP 실패를 '수집 헬스'에 표면화, Phase F 후속)
- 라이브 수집 검증 중 발견 — `tech_sites.search_site` 가 HTTP 상태를 체크하지 않아 403/500 응답을 받아도 본문을 파싱해 **조용히 0건** 반환 → 방금 추가한 '수집 헬스'에 AI Times/오토메이션월드 장애가 안 잡히던 빈틈.
- `search_site`: `resp.raise_for_status()` 추가 → naver/google 과 일관되게 HTTP 오류를 `RuntimeError` 로 표면화.
- `search_all`: `on_error(site, msg)` 콜백(후방호환) — 사이트별 실패를 통보(콜백 없으면 기존처럼 조용히 격리).
- `collect_batch` tech 분기: `on_error` → `report.errors` → `run_log`/'수집 헬스' 에 오류 소스로 노출.
- `tests/test_tech_sites.py`(+2: bad-status raise·on_error 통보)·`test_run_daily.py` 페이크 호환. 검증: pytest 696→**698 passed** · 금지 패턴 0.

### Added (Phase F — 수집 관측성: 런 로그 + 데이터 관리 '수집 헬스')
- **`store/run_log.py` 신규** — 매 수집 런을 `data/logs/runs.jsonl` 에 구조화 영속(run_id·시각·트리거·소스별 건수·성공/실패·duration). `record_run`/`load_runs`/`latest_run`/`entry_from_report`(순수). `config.DATA_ROOT` 를 호출 시점 참조해 conftest 격리와 호환(from-import 고정 footgun 회피).
- **3개 수집 경로에 기록 연결** — cron(`scripts/daily_scrape.py`, trigger=cron + duration 측정)·데이터 관리 새로고침(trigger=manual)·보드 수집(trigger=board). 로깅 실패가 수집 자체를 깨지 않도록 모두 try/except 격리.
- **데이터 관리 '수집 헬스' 1행**(`data_management_v2._collect_health_li`) — `run_log.latest_run()` 의 성공/건수/파일/시각/트리거/오류 소스를 수집잡 목록 최상단에 노출 → 매일 자동 수집이 **조용히 실패해도** 화면에서 바로 드러난다. 런 기록이 없으면 빈 문자열(기존 동작 무변경).
- `tests/test_run_log.py`(+7)·`tests/test_collect_health.py`(+3). 검증: pytest 686→**696 passed** · 금지 패턴 0 · py_compile OK.

### Removed (Phase 3 잔여 — no-op 패널 · 레거시 채팅 · 미사용 템플릿 · batch helper)
- **`app_shell.render_app_side`/`render_app_sola` 완전 제거** — Phase A 에서 no-op 으로 바뀐 뒤 5개 화면(board/insights/archive/data_management/persona_page)이 계속 호출하던 것을 호출부 + 함수(~300줄) + 부수 패널-토글 클러스터(`consume_panel_toggle`·`_toggle_href`·`_side_collapsed`·`_sola_collapsed`)까지 삭제. 좌측은 네이티브 `st.sidebar`, 우측은 `chat_panel.render_side` 단일 경로.
- **`chat_panel.render`**(구 bottom expander) 제거 — `render_side`(우측 컬럼 실채팅)가 대체. 공유 헬퍼(`_intro_card_html`/`_format_recent_messages`/`_AREA_INTROS`)는 render_side 가 계속 사용하므로 보존. 모듈 docstring 갱신.
- **`sola_workshop_v2._SOLA_TEMPLATE` + `assets/v2/screens/sola_main.html`(11KB)** 제거 — 정의만 있고 read 0. 부수 `ASSETS_DIR` import 정리.
- **`store/task_defs_db.upsert_many`** 제거(재판정→데드) — production 은 단건 `upsert`(`task_def_manage`·`sqlite_sync` 루프)만 사용, batch helper 는 테스트 전용이었음. `Iterable` import 정리.
- **`persona_page._archive_stats`** + 전용 `bookmarks` import 제거 — render_app_side 호출이 유일 사용처였음.
- 테스트: `test_chat_panel`(render 1건)·`test_task_defs_db`(upsert_many 1건) 정리. 검증: pytest 688→**686 passed** · 잔여 import 0(`grep -rn`) · 금지 패턴 0 · py_compile OK.

### Removed (Phase 3 — 데드 코드 삭제: layout·task_tree·sola/{insight,chat_ctx})
- production import 0 으로 확인된 데드 모듈 4종 삭제 + 테스트 동반 정리:
  - `ui/layout.py`(`main_and_chat`/`render_chat_panel`/`split_with_chat` — v3 셸 전환으로 호출 0) · `ui/task_tree.py`(드릴다운 위젯, 호출 0) · `sola/insight.py`(부서 인사이트, 호출 0) · `sola/chat_ctx.py`(구 채팅 컨텍스트 빌더, 호출 0).
  - 테스트: `tests/test_sola_insight.py` 삭제 · `tests/test_sola.py`(chat_ctx 9건)·`tests/test_preview.py`(insight 2건)·`tests/test_chat_log.py`(main_and_chat 1건)·`tests/test_task_def_upload.py`(task_tree 경로 1줄) 수술적 정리.
- **보존**: `sola/{propose,summarize}` 는 결정-1 A 로 SOLA 작업실에 연결돼 **부활**(삭제 대상 아님). `sola/side_context.py` 는 `ui/layout` 삭제로 orphan 이나 사이드 채팅 컨텍스트 일원화 연결 대상으로 보존(docstring 갱신).
- 문서 동기화: `docs/ARCHITECTURE.md`(데드 목록·모듈 트리)·`docs/INVARIANTS.md`·`CLAUDE.md` 라우팅·`docs/REFACTOR_PLAN.md`(진행표·데드 대장·Phase 3) 갱신.
- **후속**: `app_shell.render_app_side`/`render_app_sola` no-op 호출부(5화면) 제거 · `chat_panel.render` 레거시 · `task_defs_db.upsert_many` 재판정.
- 검증: pytest 702→**688 passed**(삭제 테스트 14건) · 잔여 import 0(`grep -rn`) · 금지 패턴 0.

### Changed (Phase E — enrich LLM 키워드 매칭 가중, 결정-2 A)
- `store/match.score_matches` — enrich 된 기사의 `keywords_llm`(LLM 추출 핵심 키워드)를 매칭에 반영. 작업 토큰과 겹치는 고유 LLM 키워드 1건당 `_LLM_KW_WEIGHT`(=2.0) 보너스를 base 점수(title/summary/keywords 토큰 중첩)에 더한다 → **enrich 된 기사가 동일 작업에 대해 더 높은 점수**. base 매칭이 없어도 LLM 키워드만으로 매칭되면 발견.
- 후방호환: `keywords_llm` 컬럼이 없거나 비어있으면 보너스 0 → 기존 점수와 동일.
- `tests/test_match_enrich_weight.py` (+5: 가중 부스트·후방호환·LLM-only 매칭·빈 값 무보너스·상수). 검증: pytest 702/702 · 금지 패턴 0.

### Added (UI Phase D — 설정 메뉴: 테마 + 글자 크기) — 사용자 6대 UI/UX 요구 완결
- `store/ui_prefs.py` 신규 — 표시 설정(theme·font)을 `data/ui_prefs.json` 에 영구화.
- `ui/styles.inject_user_prefs()` — 저장된 테마/글자 크기를 `inject_global_styles` 직후 주입(베이스 토큰 이후 → `:root` 오버라이드 우선). `app.py` 에서 호출.
  - **테마**: 라이트(기본) / **다크** / 오션(틸 강조) / 선셋(로즈 강조). 다크는 토큰 + `.stApp`·사이드바·우측 채팅·네이티브 위젯(input·textarea·select·버튼) 오버라이드.
  - **글자 크기**: 작게(0.92) / 보통 / 크게(1.12) — `stMain`·사이드바 `zoom`.
- 설정 UI: `persona_page._render_display_settings` — 🎨 표시 설정(테마·글자 크기 라디오). **변경 즉시 저장·적용**(on_click 없이 diff 감지 → rerun). topbar ⚙·아바타로 진입.
- **다크모드 활성화용 색 토큰 일괄화**: 화면 CSS 고정 `background:#fff` 89곳 → `var(--surface-card)`, `#E5E7EB` 테두리 6곳 → `var(--surface-divider)` (라이트 무변경·다크 추종). 내가 추가했던 인라인 색(chat_panel·sidebar 통계·sola workbench)도 토큰화.
- `tests/test_ui_prefs.py` (+7). 검증: pytest 697/697 · 금지 패턴 0 · playwright 라이트/다크/오션/큰글자 — 다크 사이드바·KPI·본문·채팅 일관, 라이트 무변경.
- **사용자 6대 UI/UX 요구 완결**: ① 화면 역할·연계(Phase C) ② 모든 화면 좌 사이드바+우 채팅(Phase A) ③ 3영역 분리(Phase A) ④ 죽은 버튼 와이어/삭제(Phase C+전역 SVG) ⑤ 컨텐츠 정리(Phase C) ⑥ 설정 메뉴 테마·폰트(Phase D).

### Changed (UI Phase C-4 — 보관함 정리: 하단 목업·컨트롤 스트립 제거) — Phase C 완료
- `archive_v2._strip_oa_mockups` — 렌더 시 ① 죽은 컨트롤 스트립(seg 탭·검색·필터칩·묶음 내보내기) ② 하단 "전체 산출물 45건" 표 + 미리보기 패널(PRO-2026-…·₩1.4억·근거 뉴스 8건·결정/내보내기 — 전부 하드코딩 목업, 위 칸반 카운트와 모순) 제거.
- 템플릿: 칸반 "+ 새로 만들기"(가짜 버튼)·"+6 (전월 대비)"(가짜 트렌드) 제거.
- **보존**: 헤더 4 stats·칸반 3열(대기/채택/기각) 실데이터 + 채택/기각/되돌리기/수정 액션. 빈 칸반은 "SOLA 작업실에서 제안서를 만들면 여기 모입니다" 안내.
- `tests/test_archive_cleanup.py` (+3). 검증: pytest 690/690 · 금지 패턴 0 · playwright 보관함 — 컨트롤스트립/하단표/가짜ID 0, 칸반 유지, 깨진img 0.
- **Phase C(5화면 컨텐츠 정리) 완료** — 인사이트(C-1)·보드(C-2)·데이터관리(C-3)·보관함(C-4) + SOLA 작업실(재설계). 모든 화면: 가짜 목업 제거 · 죽은 링크 실네비 재배선 · 심플 세로 스크롤.

### Fixed (UI 전역 — 모든 화면 SVG 아이콘 깨짐 + 차트 누락 일괄 수정)
- **전수 진단(playwright)**: 모든 화면에 깨진 이미지(board 5·insights 5·sola 3·**archive 14**·data 3)와 `inlineSVG=0`(차트 누락) 발견. 원인 2종:
  ① `data:image/svg+xml;utf8,<svg ... fill='#…'>` 미인코딩 data-URI — 색상 `#`·공백이 잘려 **아이콘 전부 깨짐**.
  ② `st.html` 의 sanitizer 가 **인라인 `<svg>` 를 통째로 제거** — 차트(보드 트렌드·인사이트 매트릭스/히트맵 등)가 안 보임.
- **`ui/components.prepare_screen_html()` 신규** — `st.html` 직전 통과: ① `;utf8,` data-URI → URL 인코딩(`#`→`%23`) 재작성, ② 인라인 `<svg>` → class/style/width/height 보존한 인코딩 data-URI `<img>` 로 래핑. `render_screen_html()` 도 함께 제공.
- 적용: `app_shell.render_topbar`(전 화면 topbar 아이콘) + board/insights/data/archive 메인 템플릿 렌더 → **전 화면 깨진 이미지 0** 확인(playwright 재진단).
- `tests/test_ui_components.py` (+3). 검증: pytest 687/687 · 금지 패턴 0 · playwright board/data/insights/sola/archive 모두 broken=0.

### Fixed (UI 버그 — 데이터 관리 + 우측 채팅, 사용자 보고 4건)
- **빈 수집잡 문구 세로 깨짐**: 빈 상태 `<li class="dm-job">` 가 `.dm-job` 의 `grid(5px 1fr auto)` 를 상속해 "오늘 실행된 수집잡이 없습니다" 가 글자마다 줄바꿈되던 것을 `display:block; word-break:keep-all` 로 수정.
- **"지금 새로고침" 버튼 문구 중앙정렬**: `justify-content:center` + 아이콘을 URL 인코딩 data-URI `<img>` 로 교체.
- **14일 수집량 차트 깨짐**: `st.html` 이 인라인 `<svg>` 를 sanitize 로 제거하고, 비인코딩 `data:image/svg+xml;utf8,<svg ... fill='#…'>` 의 색상 `#` 가 fragment 로 잘려 이미지가 깨지던 것을 **URL 인코딩 data-URI `<img>`**(`#`→`%23`)로 정상 렌더. 새로고침 아이콘도 동일 처리.
- **우측 채팅 높이/하단 공간**: 입력창 height 78→130, 패널을 `height:calc(100vh-28px)` 로 뷰포트 높이 채움 + 내부 flex column 으로 입력 form 을 하단 고정(`stLayoutWrapper:has(stForm){margin-top:auto}`) → 하단 빈 공간 제거 + 채팅 영역 확대.
- `tests/test_dm_cleanup.py` (+3 회귀). 검증: pytest 684/684 · 금지 패턴 0 · playwright — 차트/아이콘 `<img>` 로드 True, 입력 form 이 패널 하단 배치 확인.

### Changed (UI Phase C-3 — 데이터 관리 정리 + 심플 세로 스크롤)
- `data_management_v2._strip_dm_mockups` 신규 — 렌더 시 정적 목업 제거: ① 죽은 필터바(검색 input·필터칩·출처/기간/정렬 셀렉트) ② 죽은 페이저(1–6 / 1,247 … 208) ③ **가짜 서브카드 3종**(키워드 매니저 "활성8·56건/일"·작업 정의 "3파일·86항목"·출처 설정 "1 셀렉터 오류" — 실제 탭이 대체하는 가짜 통계/목록). 마커 슬라이스(필터→기사그리드, 페이저→섹션닫힘, 서브그리드→셸닫힘)라 div 균형 카운트 비의존.
- 템플릿 편집: 가짜 "06:00 정기 실행 · 5개 작업" → "정기 수집 · 매일 새벽 자동 실행", disabled "스케줄" 버튼 제거, 가짜 news-meta(전체 1,247·매칭 32·북마크 17) 제거.
- 심플 세로 스크롤: `dm-split`(수집 잡 | 뉴스 라이브러리)를 단일 컬럼 스택(`scale.css` D1).
- **기능/실데이터 보존**: 헤더 4 stats·그룹/탭 nav·수집 잡·뉴스 카드·새로고침 CTA·작업 정의 CRUD·키워드/출처 탭 모두 유지.
- `tests/test_dm_cleanup.py` (+3). 검증: pytest 681/681 · 금지 패턴 0 · playwright 데이터관리 — 죽은 필터/페이저/가짜서브카드/가짜카운트 0, 우측 채팅 노출.

### Changed (UI Phase C-2 — 보드 정리 + 심플 세로 스크롤)
- **죽은/가짜 제거**: hero CTA 2개("브리핑 듣기"/"빠른 질문" — 우측 채팅과 중복), soon 탭(강한매칭/출처별/월별 — 미구현 필터), 가짜 brief-meta("06:08 생성·32건·1.4s"), "검토 대기 4건" 리터럴 → "자동화 기회".
- **죽은 `*.html` 링크를 실제 area 네비(`?app_area=`)로 재배선**(`board_v2._clean_board_html`) — 기능 보존: 뉴스 라이브러리→데이터 관리, 전체/트렌드/매트릭스 작업장→인사이트. 없는 화면 링크(keyword-manager.html)는 제거.
- **뉴스 카드 클릭 → 원문 열기**(`_lead_story_html`/`_side_story_html` 를 `<a target="_blank">` 로 래핑, 링크 escape).
- **심플 세로 스크롤**(사용자 지시): 2-컬럼 셸로 좁아진 main_col 에서 섹션 내부 2단 그리드(`db-greet`/`db-stories`/`db-trend`)를 단일 컬럼으로 스택(`scale.css §11`). 모든 콘텐츠/기능 보존, 레이아웃만 세로화.
- `tests/test_board_cleanup.py` (+6). 검증: pytest 678/678 · 금지 패턴 0 · playwright 보드 — 죽은 CTA/soon탭/가짜meta/리터럴 0, 우측 채팅 노출.

### Changed (UI Phase C-1 — 인사이트 화면 정리: 가짜 패널·죽은 필터 제거)
- `insights_v2._strip_mockup_blocks` 신규 — 렌더 시 `insights_main.html` 의 정적 목업 2블록 제거: ① **가짜 우측 `ia-sola` 패널**(SOLA 분석 모드·가짜 인용·"도장 부스 #3 비전 PoC"·액션/컴포저 — Phase A 로 모든 화면에 실제 우측 채팅이 생겨 중복·가짜였음) ② **죽은 `ia-filters` 스트립**(기간 7/30/90일·공정범위·기술칩·"저장한 뷰" — 전부 핸들러 없는 시안). 마커 슬라이스 방식(`<aside class="ia-sola">…</aside>`, `ia-filters`→`ia-grid` 사이)이라 div 균형 카운트에 의존 안 함.
- `insights_v2._ia_stats` — **PoC 후보 중복집계 수정**: 자동화 기회 셀에 채택 대기(pending) 제안서를 더하던 버그 제거(두 개념 혼동). 이제 PoC 후보 = 기회 셀만.
- `tests/test_insights_cleanup.py` (+4). 검증: pytest 672/672 · 금지 패턴 0 · playwright 인사이트 — 가짜 패널·필터·가짜 PoC문구 0, 우측 실채팅 노출.

### Changed (UI Phase B 후속 — SOLA 작업실 3영역 통일: 산출물 캔버스)
- **SOLA 작업실을 다른 화면과 동일한 [좌 사이드바 │ 중앙 콘텐츠 │ 우 LLM 채팅] 3영역으로 통일.** 기존엔 이 화면만 자체 3열 `ws-shell`(스레드│채팅│ctx)이라 우측 채팅이 없고 채팅·결과·버튼이 중앙에 뒤섞여(버튼 줄바꿈·쏠림, 채팅/결과 경계 불명) 있던 문제 해소(사용자 지적).
- `app.py` — SOLA 작업실 풀폭 예외 제거, `main_col + chat_col` 에 편입. 우측 = `chat_panel.render_side`(대화), 중앙 = 작업대.
- `ui/sola_workshop_v2.render()` 재작성 → `_render_workbench`(중앙 산출물 캔버스): ① 액션 바 `📝 제안서 생성`·`📰 뉴스 요약`·`➕ 새 대화` ② 현재 산출물(마지막 SOLA 답변을 `st.container(border)`+`st.markdown` 문서 카드로 + `📦 보관함에 저장`·`🔄 다시 생성`) ③ 세션 목록(검색·고정·삭제) ④ 저장한 산출물. 자체 `ws-shell` 템플릿·중앙 `chat_input` 제거(대화는 우측 채팅이 담당).
- `_consume_summarize_if_any` 신규(`📰 뉴스 요약` → `sola.summarize`), `chat_context_block` 신규(우측 채팅에 작업실 컨텍스트 자동 첨부). `_msg_html`/`_render_messages_html` 은 테스트 의존이라 보존.
- 검증: pytest 668/668 · 금지 패턴 0 · playwright SOLA 빈/인계 화면 — 3영역 분리·우측 채팅 노출·액션 버튼 정렬 확인.

### Added (UI Phase B — 제안서 엔진 복원: 생성 → 보관함 저장 루프)
- 끊겨 있던 제품 핵심(자동화 기회 → 제안서 → 산출물)을 SOLA 작업실에 배선:
  - `ui/sola_workshop_v2._consume_generate_proposal_if_any` — 인계(dept/lv3) 컨텍스트 + 관련 뉴스(`_related_news_df`: 최근 14일 뉴스 중 작업 매칭 상위 N, 매칭 없으면 최근 폴백)를 **`sola.propose.propose_for_task`(전용 제안서 시스템 프롬프트)** 에 넘겨 구조화 제안서를 assistant 메시지로 생성. LLM 미설정 시 입력 미리보기, 호출 오류 시 안내 메시지로 무중단.
  - `ui/sola_workshop_v2._consume_save_proposal_if_any` — 현 thread 의 마지막 제안서(assistant)를 **proposal 북마크로 저장(실 content, status=pending)**. thread 당 안정 id → 재저장은 갱신(중복 방지). 저장 후 보드/사이드바 '채택 대기' 카운트 캐시 무효화.
  - `_render_main` 버튼: 핸드오프 시 **"📝 제안서 생성"** + "💬 컨텍스트로 물어보기", assistant 메시지 존재 시 **"📦 이 제안서 보관함에 저장"**. 액션 피드백은 `_render_sola_action_toasts`.
- **이전 상태**: 보드 '채택' 은 `content=""` 빈 제안서만 생성하고 `sola/propose`·`bookmarks.update_content` 는 production 호출 0(데드)이라 사용자가 실제 제안서를 받을 경로가 없었음 → 이제 기회에서 인계받아 **실제 제안서 본문이 보관함 산출물로 저장**된다.
- `tests/test_sola_propose_loop.py` (+12) — `_related_news_df` 폴백 2 · generate(append 순서/persona·task 전달/noop/오류 표면화) 4 · save(실 content/재저장 갱신/no-content warn/noop/handoff tags) 5 · toast 1회 소비 1.
- 검증: pytest 668/668 · 금지 패턴 0 · playwright 핸드오프 화면에서 '📝 제안서 생성' 버튼 노출 확인.

### Fixed (CI — flaky 테스트 결정화)
- `tests/test_sola_composer.py::test_append_message_persists_to_chat_log` — 첫 user 메시지의 thread 제목 자동생성이 LLM 가용성에 의존(가용 시 압축 제목, 미설정 시 raw fallback)해 CI 에서 간헐 실패(`assert '인사 분석하기' == 'hello'`)하던 것을 `sola.thread_title.generate` 목으로 결정화. 제목 생성기 동작 자체는 `test_thread_title_llm` 가 검증하고, 본 테스트는 chat_log 영속+message_count+제목 wiring 에 집중. (UI 셸/CSS/사이드바 변경과 무관한 기존 취약점.)

### Changed (UI Phase A 후속 — 사이드바 프로필 카드 재설계)
- `ui/sidebar._persona_card_html` 깔끔한 프로필 카드로 재설계. **설정 시**: 아바타 + 이름/역할 + 편집펜(✎) + 팀/관심 구분선. **미설정 시**: 👤 프로필 이모지 + "프로필 미설정" + 안내 문구 + "＋ 프로필 설정하기" CTA. 카드 전체가 `?persona_editor=1` 링크라 **이모지·이름·안내 문구 어디를 눌러도 설정 화면이 열림**(playwright 클릭 검증).
- `assets/v2/sidebar.css` 프로필 카드 스타일을 새 구조(`.persona-profile-row`/`-id`/`-head-empty`/`-edit`/`-empty-hint`/`-cta`)로 교체.
- `tests/test_sidebar_profile.py` 2건 새 마크업에 맞춰 갱신(XSS escape·클릭 링크·미설정 CTA 검증 보존).
- 검증: pytest 656/656 · 금지 패턴 0 · playwright 설정/미설정 카드 + 미설정 클릭→설정창 열림 확인.

### Removed (UI Phase A 후속 — V1 잔재·레거시 스타일시트 제거)
- **레거시 `assets/styles.css`(1463줄, V1 디자인 시스템) 삭제 + 로드 중단**. 이 스타일시트가 매 페이지 unconditional 로 주입돼 `.stApp`/`.block-container` 등 ungated 전역 규칙이 v2 와 충돌, 새로고침 시 V1 UI 가 잠깐 보이던 FOUC 원인. 유일한 라이브 소비처였던 네이티브 사이드바 스타일(`.sidebar-*`/`.persona-profile-*`)을 신규 `assets/v2/sidebar.css`(v2 토큰 기반)로 이전.
- `ui/persona_page.py` — V1 `page_header`(`.app-header` 마크업) + `section_label` 호출 제거. topbar 가 이미 제목을 담당하므로 중복 V1 헤더가 페르소나 화면에 남던 문제 해소. v2 인라인 인트로/레이블로 교체.
- 죽은 V1 빌더(`components.metric_card`/`status_card`/`action_card`)·`data_health`(둘 다 라이브 호출 0)는 styles.css 없이도 무방 — 확인 후 보존(테스트 의존). `page_header`/`section_label` 정의는 `ui/layout.py`+`test_chat_log` 의존이라 유지(Phase C 에서 layout 과 함께 삭제).
- `CLAUDE.md` 라우팅 표 CSS 항목을 `assets/v2/*.css` 로 갱신.
- 검증: pytest 656/656 · 금지 패턴 0 · playwright 보드/페르소나 캡처 — 사이드바 v2 스타일 정상, 페르소나 화면 V1 헤더 제거 확인.

### Changed (UI Phase A — 셸 v3: 3영역 레이아웃 네이티브 재건)
- **레이아웃 소유권을 `app.py` 로 이전**: 좌측은 Streamlit 네이티브 `st.sidebar`(nav 단일 소스), 본문은 `st.columns([2.7, 1])` 의 메인/채팅 2-컬럼. 우측 채팅 컬럼은 `chat_panel.render_side()` 가 **실제 작동하는** 채팅(form text_area + 보내기 → `_do_sola_send` → `consume_send_if_any`)을 렌더. SOLA 작업실만 자체 풀스크린(스레드+채팅+ctx)이라 우측 컬럼 없이 풀폭.
- **제거된 근본 원인**: ① 좌측 패널 이중화(네이티브 `st.sidebar` 를 CSS 로 숨기고 고정 HTML `.app-side` 를 따로 그리던 구조 → nav 정의 2벌) ② 본문 매직 패딩(`padding-left:344px`/`padding-right:480px` 가 고정 패널 폭에 수동 정합 → 어긋나면 겹침) ③ 우측 `.app-sola` 패널 전체가 `disabled` 목업(입력창·보내기·빠른질문 전부 비활성)이라 진짜 채팅은 본문 끝에 따로 있던 이중 채팅.
- `ui/app_shell.render_app_side` / `render_app_sola` → **no-op**(호출부 호환 유지, 본문은 Phase C 에서 함수째 삭제). `render_topbar` 는 in-flow 페이지 헤더로 전환(fixed → static), `.v2-scroll-fade` 숨김.
- `ui/sidebar.py` — 네이티브 사이드바에 통계 3칸(오늘 매칭/자동화 기회/채택 대기, `board_v2._archive_stats` 실데이터 위임) 추가해 구 `.app-side` 정보 보존.
- CSS: `streamlit-overrides.css` 네이티브 사이드바 노출 + 매직 패딩 제거 + 우측 채팅 컬럼 sticky(`[data-testid="stColumn"]:has(.side-chat-marker)`). `shell.css` `.db-topbar` static 화. `scale.css` 패널 폭/본문 패딩 규칙 제거.
- `docs/INVARIANTS.md I-13` · `docs/ARCHITECTURE.md` — 네이티브 셸 기준으로 갱신.
- **검증**: pytest 656/656 · 금지 패턴(on_click/raw requests) 0 · py_compile OK · playwright 5화면 캡처 — 3영역(사이드바·본문·채팅) 겹침 없이 분리 확인, SOLA 작업실도 동일 네이티브 사이드바로 일관.

### Docs (다음 세션 준비)
- `docs/REFACTOR_PLAN.md` 끝에 "다음 세션 시작점" 섹션 — Phase 1b/1c 의 브랜치명·진입 파일·UX 안 3개·완료 기준·시작 명령 명시.
- 옛 계획·블루프린트 7건(`DEVELOPMENT_PHASES`/`MILESTONE_1`/`TASK_DEF_PLAN`/`UX_QA_CHECKLIST`/`UX_REDESIGN_PLAN`/`VIBE_CODING_BLUEPRINT`/`WORKFLOW`)에 역사적 기록 표식 + `REFACTOR_PLAN`/`CLAUDE.md` 로의 redirect 헤더.

### Fixed (Phase 2 회귀 — Codex P2)
- `ui/data_management_v2._consume_refresh_if_any` / 작업정의 업로드 후 캐시 무효화 루프에 `board_v2._board_kpis.clear()` 추가. Phase 2 에서 `_archive_stats_dm` 가 `board_v2._archive_stats()` 위임으로 바뀌면서 데이터 관리 새로고침 직후 좌측 nav 의 match/opportunity 카운트가 60초 TTL 만료까지 stale 로 남던 회귀 수정.

### Changed (Phase 2 — UI 중복 제거: `get_persona` 승격 + `app_side_stats` 단일화)
- `ui/app_shell.get_persona()` 신규 — 5개 v2 화면(`board`/`insights`/`archive`/`sola_workshop`/`data_management`)이 동일 구현하던 `_load_persona` 를 단일 진입점으로 통합. 호출처 일괄 교체.
- `archive_v2._archive_stats_oa` / `insights_v2._archive_stats_ia` / `data_management_v2._archive_stats_dm` 세 사본을 `board_v2._archive_stats()` 위임으로 교체. `board_v2._board_kpis` 60초 캐시 단일 소스로 일원화 → 좌측 nav 카운트와 보드 KPI 가 항상 일관됨. 4중 캐시 → 1중 캐시.
- 동반 정리: `archive_v2` 에서 `_load_tasks`/`_news_db`/`_score_matches`/`_score_cells` unused import 제거, `data_management_v2` 에서 `_score_matches`/`_score_cells` unused import 제거.
- 효과: -114줄(161 삭제/47 추가) · 사용 가치가 낮아 `ui/toast.py`·`ui/url_state.py` 통합은 보류(REFACTOR_PLAN 기록).
- 검증: pytest 656/656 · 금지 패턴(on_click/raw requests) 0 · py_compile OK.

### Fixed (Phase 1a — 무논쟁 correctness: F5·F7·F11·F12)
- **F5 토스트 부재** (`ui/archive_v2.py`): 북마크 채택/보류/복구(`?action=`) 소비 후 `st.toast` 미호출 → 액션 성공 피드백이 없던 문제. `_STATUS_TOAST` 맵 + `render()` 에서 `_consume_action_if_any()` 결과가 있으면 토스트 노출.
- **F7 chat ts 미영속** (`store/chat_log.py`): `save_history`/`load_history` 가 role/content 만 처리해 `sola_workshop_v2` 가 메시지에 붙인 `ts`(timestamp)가 저장/복원되지 않던 문제. ts 가 있으면 함께 영속·복원(없으면 생략 — 후방 호환). 회귀 테스트 2건 추가(`tests/test_chat_log.py`).
- **F11 거짓 원자성 주장** (`store/task_defs_db.py::upsert_many`): docstring 이 "개별 항목 실패 시 전체 rollback" 을 주장하나 실제로는 행마다 즉시 commit(부분 적용 가능). docstring 을 실제 동작으로 정정 + 진짜 트랜잭션은 호출부 책임 명시. (함수는 테스트 의존이라 보존 → 데드 여부는 Phase 3 재판정.)
- **F12 하드코딩 통계** (`ui/sola_workshop_v2.py::_archive_stats`): `match_today=32, opportunities=4` 상수 → `board_v2._archive_stats()`(60초 캐시 `_board_kpis` 실데이터) 위임. 보드와 동일 소스 공유, 실패 시 0 폴백.
- 과진단 기각: F3(news_cols 동적 필터)·F8(토큰 단위 교집합)·F9(데드 정렬 없음) — 코드 재확인 결과 결함 아님.
- `docs/REFACTOR_PLAN.md` 신규 — 결함 대장(F-번호)·데드 코드 대장·Phase 0~3 로드맵·결정 대기 항목. Phase 0 문서들이 참조하던 source-of-truth 파일.
- 검증: pytest 656/656(신규 2) · 금지 패턴 0 · py_compile OK.

### Changed (문서 정합성 — Phase 0: ARCHITECTURE / CLAUDE / DEV_GUIDELINES / INVARIANTS v2 정렬)
- `docs/ARCHITECTURE.md` 전면 재작성 — 5영역 디스패치(`app.py` if/elif), v2 셸(`app_shell`·`sidebar`·`chat_panel`), SQLite `task_defs` + Parquet news 이중 저장, `roadmap/query` SQLite 우선 fallback, 데이터 플로우 4단계, 알려진 데드 코드 목록. 옛 5탭 라디오·`ui/*_tab.py` 기술 전부 제거.
- `CLAUDE.md` 읽기 라우팅 표 → 실제 `ui/*_v2.py` 경로. 절대 규칙 §2 의 `ui/*_tab.py` → v2 셸 모듈 명시.
- `DEV_GUIDELINES.md §2·§3` 동기화. v2 셸 + 5영역 + 보조 모듈 라우팅으로 일원화. 데드 모듈 경고 추가.
- `docs/INVARIANTS.md I-13` 정정 — `ui/layout.py::main_and_chat` (데드) → `ui/chat_panel.{render,consume_send_if_any}` 단일 진입점 + area_key 슬러그 + SOLA 작업실 풀스크린 예외 명시. 데드 인터페이스 경고로 마무리.
- 코드 변경 0. `docs/REFACTOR_PLAN.md` 의 Phase 0 (D1~D4) 완수.

### Changed (변수명 통일 — `roadmap_df`/`load_roadmap` → `tasks_df`/`load_tasks`)
- UI 9파일 + 테스트 11파일에서 "로드맵" 잔여 변수·식별자를 "작업(tasks)" 으로 통일 (사용자 노출 라벨은 이미 "작업 정의" 로 통일됨, 이번엔 내부 코드 식별자 정리).
  - import alias: `load_latest as load_roadmap` / `_load_roadmap` → `load_tasks` / `_load_tasks`.
  - 지역 변수: `roadmap_df`/`_roadmap_df` → `tasks_df`/`_tasks_df`, DataFrame 변수 `roadmap` → `tasks` (attr/index 접근 `roadmap.empty`·`roadmap["dept"]` 포함).
  - **모듈 경로는 보존**: `from roadmap.query import ...`, `roadmap.task_def_json`, `ROADMAP_DIR`, `roadmap/` 데이터 디렉토리(디스크상 실명) 모두 그대로. `roadmap/` 패키지 rename 은 별도 작업.
  - 테스트의 `patch.object(..., "_load_roadmap")` 등도 lockstep 업데이트.
- 검증: pytest 654/654 · 금지 패턴 0 · 변경 23파일 (170/170 균형).

### Fixed (screen-CSS 근본 수정 — st.html → st.markdown(unsafe_allow_html) · v2 셸 전 화면 복구)
- `ui/styles.py::inject_global_styles` / `inject_screen_css` — `st.html("<style>...")` 를 `st.markdown("<style>...", unsafe_allow_html=True)` 로 전환. `st.html` 이 수만 자 `<style>` 블록을 sanitize/collapse 해 DOM 에서 전체 누락되던 기존 이슈 근본 해결 (전역 v2 토큰부터 screen CSS 까지 모두 영향).
- 검증 (playwright headless · 5 area): board/data/insights/sola/archive 모두 `total_css ≥ 100KB`, `--accent-primary` v2 토큰 50~99회, screen 마커 8~25회 mount 확인 (이전 0회). `.dm-tab` border-radius `0px → 8px`.
- `tests/test_html_rendering.py` — `styles.py` 를 `st.markdown(unsafe_allow_html=True)` 금지 invariant 의 명시적 예외에 추가 (`components.py` 와 동일 패턴). CSS 자산은 사용자 입력이 아니라 안전.
- `docs/MILESTONE_1.md` — screen-CSS 이슈를 ✅ 해결로 업데이트.
- `ui/task_def_manage.py` 의 inline style 보강(이전 PR)은 **안전망으로 유지** — Streamlit 버전 회귀 시 fallback 으로 동작.

### Fixed (작업 정의 관리 UI 스타일 — inline style 보강 + 1차 완성 보고서)
- `ui/task_def_manage.py` — 동적 `st.html` (카드·상세·버튼·history·메타) 에 inline style 박음. `inject_screen_css` 의 `st.html("<style>")` 가 mid-render 에서 DOM 에 주입되지 않아 `.td-*`/`.dm-*` screen CSS 클래스가 실제 적용되지 않는 **기존 이슈** 확인 (전역 `inject_global_styles` 는 정상) → PR-5 diff·토스트와 동일하게 inline style 사용으로 우회. 클래스도 유지 (screen-CSS 근본 수정 시 호환).
- 실제 구동 검증 (playwright headless): 목록·검색·상세·추가폼 4화면 Python traceback 0, CRUD 액션 버튼 렌더 확인.
- `docs/MILESTONE_1.md` 신규 — 1차 완성(M1~M3) 보고서. 화면별 역할·사용 흐름, 검증 결과, screen-CSS 이슈, 남은 작업.

### Added (작업 정의 관리 UI — PR-6: M3 1차 완성)
- `ui/task_def_manage.py` 신규 — 검색 / 1건 상세 / 추가·수정·삭제 폼 / history 패널. 평탄 모듈 분리 (`data_management_v2` 평탄 디스패치 유지).
- `roadmap/task_def_form.py` 신규 — `TaskDefForm` 데이터클래스. `from_db_row(row)` (`task_defs_db.get` 결과 → 폼), `to_json()` (검증 + `ingest_org_meta` 직렬화). objectives/risks/automation 리스트 [+추가][-삭제] 헬퍼. 빈 값/공백 자동 제거.
- `ui/data_management_v2.py` — `tasks` 그룹에 `manage` sub-탭 추가 (기본 탭이 `task`→`manage` 로 이동, **PR-6 가 1차 완성 UI**). `_consume_td_action_if_any` / `_consume_td_save_if_any` 위젯 인스턴스화 전에 호출. `task` 탭 라벨도 "작업 정의" → "📊 엑셀 업로드"로 명확화.
- URL (stateless): `?dm_grp=tasks&dm_tab=manage&td_q=<검색어>&td_view=<pid>&td_edit=<pid>&td_add=1&td_hist=<pid>&td_action=delete&td_pid=<pid>`. 기존 `?dm_tab=task` 북마크는 그대로 동작 (PR-A 의 그룹 추론).
- 삭제 확인: `<a onclick="return confirm(...)">` 브라우저 JS (Streamlit `on_click=` 금지 invariant 준수).
- XSS 방어: 모든 사용자 입력 (process_name/description/objectives/risks/automation) `_html.escape()` 후 렌더.
- `assets/v2/screens/data_management.css` — `.td-list/.td-card/.td-detail/.td-meta/.td-actions/.td-btn-{primary,secondary,danger}/.td-history` 스타일 추가.
- `tests/test_task_def_manage.py` (+41) — `TaskDefForm` 9건 (defaults, from_db_row 정상/None/str-risk 정규화, to_json round-trip, 검증 실패 2종, 빈 값 제거, add/remove helpers) · URL 빌더 3건 · 검색·리스트 5건 (empty 2종, 매칭, 카드 렌더) · 상세 4건 (전 섹션·XSS escape·history empty·history 다회 누적) · 액션 consumer 6건 (delete 성공/missing/noop, save create/update/검증 실패) · manage 탭 통합 5건 (등록/기본 탭/resolve/body placeholder/active 마킹) · **end-to-end round-trip 8건** (create→load→modify→save→reload, 한국어/이모지 보존, 빈 필드 제거, URL 인코딩, 카드 링크, legacy URL 호환, redirect 분리).
- `tests/test_dm_area_groups.py` — `tasks` 기본 탭이 `task` → `manage` 로 변경된 것에 맞춰 5건 업데이트.

### Added (엑셀 업로드 diff 미리보기 + 사용자 확인 — PR-5)
- `roadmap/sqlite_sync.py::DiffPreview` 신규 dataclass — `added/updated/unchanged/kept/skipped` + `total_apply` 프로퍼티. `kept` 는 DB 에는 있지만 이번 업로드에 없는 (유지될) 항목 — 결정사항 §4.
- `roadmap/sqlite_sync.py::compute_diff(df) -> DiffPreview` — read-only. 행마다 `row_to_task_def` → DB 와 비교해 added/updated/unchanged 분류. DB 의 잔여는 kept, pid/team/dept 누락 행은 skipped.
- `roadmap/sqlite_sync.py::_display_name(json, pid)` — `process_name` 우선, 없으면 `process_id` (diff 카드 표시용).
- `ui/data_management_v2.py::_render_task_def_diff_preview(pending)` 신규 — 추가/수정/유지/제외 카운트 요약 + 각 카테고리별 expand (최대 200개, 초과 시 "외 N건") + [← 취소] / [✅ N건 적용] 버튼. apply=0 이면 버튼 disabled.
- `ui/data_management_v2.py::_render_task_def_upload` 변경 — 직접 ingest 대신 `[📊 변경 사항 미리보기]` 버튼 → `_task_def_pending` 페이로드 저장 → 다음 rerun 에서 미리보기 카드 노출. 적용 클릭 시 기존 `_do_task_def_ingest` 경로 재사용 (이중 코드 없음).
- `ui/data_management_v2.py::_compute_pending_diff(data, sheet)` — 바이트 → 정규화 DF → `compute_diff` 한 단계 헬퍼. 예외는 `(None, msg)` 로 안전 반환.
- `tests/test_excel_diff_preview.py` (+17) — `DiffPreview` 데이터클래스 2건 / `compute_diff` 7건 (전부 신규·updated·unchanged·kept·skipped·빈 업로드·read-only) / `_display_name` 2건 / `_compute_pending_diff` 2건 (fixture / invalid bytes) / UI 3건 (버튼 라벨 변경·적용→ingest 페이로드·취소→pending 제거·apply=0 disabled).

### Changed (데이터 관리 area 2 그룹 segmented 재편 — PR-A)
- `ui/data_management_v2.py` — `_DM_GROUPS=("news","tasks")` + `_DM_GROUP_TABS` (news: jobs/kw/src · tasks: task) + `_DM_GROUP_LABEL` (📰 뉴스 데이터 / 📋 작업 데이터). PR-6 에서 `tasks` 그룹에 `manage` 추가 예정.
- `_dm_resolve_group_and_tab(grp, tab)` — URL 정규화 헬퍼. 기존 `?dm_tab=` 단독 북마크 URL 도 자동 그룹 추론으로 호환 (예: `?dm_tab=task` → `(tasks, task)`). grp/tab 어긋나면 `tab` 의 그룹이 진실.
- `_dm_tab_href(tab)` — sub-탭 URL 에 `dm_grp` 자동 포함. news/jobs 는 둘 다 생략 (기존 깔끔한 URL 유지), task 는 `dm_grp=tasks` 만 (tasks 그룹 기본 탭이므로 `dm_tab` 생략), kw/src 는 `dm_grp=news&dm_tab=...` 명시.
- `_dm_group_href(grp)` / `_dm_groups_html(selected_grp)` 신규 — 그룹 segmented control (`<a role="tab">` 2개, `dm-group-active` 마킹).
- `_dm_tabs_html(...)` — 현재 그룹의 sub-탭만 렌더 (news 그룹 3개 / tasks 그룹 1개). 활성 마킹 동작 유지.
- `render()` — `selected_tab` 단일 파싱 → `_dm_resolve_group_and_tab` 로 그룹·탭 동시 결정.
- `assets/v2/screens/data_management.css` — `.dm-groups` / `.dm-group` / `.dm-group-active` 스타일 추가 (inline-flex segmented).
- `tests/test_dm_area_groups.py` (+14) — 상수 sanity / `_dm_group_of` / `_dm_resolve_group_and_tab` 6건 (legacy `dm_tab` 호환·둘 다 비음·grp 만·잘못된 값·grp 와 tab 불일치 시 tab 우선) / `_dm_tab_href` 3건 (clean default·dm_grp 자동 포함·tasks 기본 탭은 dm_tab 생략) / `_dm_group_href` / `_dm_groups_html` 2건 / `_dm_tabs_html` 그룹별 필터링 4건.
- `tests/test_dm_tabs.py` — 기존 4 탭 가정을 news 그룹 3 탭으로 수정 (`task` 는 tasks 그룹).

### Changed (로드맵 reader → SQLite 우선 + Parquet fallback — PR-4)
- `roadmap/query.py::load_latest(*, prefer="sqlite")` — SQLite `task_defs` 가 비어있지 않으면 그쪽에서 빌드, 비어있으면 기존 Parquet (호환). `prefer="parquet"` 로 명시 시 Parquet 만 사용.
- SQLite → DataFrame 빌드: `org_meta` 우선, scalar 미러로 보강. `lv1/lv2/lv3` 가 `org_meta` 에 없으면 `division/process/task` 자동 fallback (`ingest.normalize_columns` 와 동일 동작). 반환 컬럼 셋은 `ALL_COLUMNS` 그대로 — 보드/인사이트/데이터관리/매칭 호출처 무변경.
- `scripts/migrate_roadmap_to_sqlite.py` — 자기 자신이 SQLite 를 채우므로 `prefer="parquet"` 명시.
- `tests/test_roadmap_query_sqlite.py` (+7) — empty/Parquet fallback/SQLite prefer/explicit parquet/org_meta 보존/by_dept·filter_hierarchy 호환/roundtrip.

### Added (로드맵 Parquet → SQLite 동기화 + 마이그 도구 — PR-3)
- `roadmap/sqlite_sync.py` 신규 — 정규화된 로드맵 DataFrame → `store.task_defs_db` UPSERT. `row_to_task_def(row)` (행 → `(process_id, json)` 또는 None), `sync_dataframe(df, *, changed_by=, source=)` → `SyncResult(created/updated/skipped/errors)`.
- process_id 결정 우선순위: `process_id` 컬럼(신 9 컬럼 폼 "공정ID") → 없으면 `task_def_json` 내부 `process_id`. 둘 다 없으면 skip. org_meta(team/dept/division/process/task/sub_task/lv1~3) 자동 주입, team/dept 없는 행은 skip.
- `roadmap/ingest.py::ingest_excel` — `to_sqlite=True` (기본) 시 Parquet 저장 후 SQLite 에도 UPSERT (best-effort, 실패해도 ingest 성공 유지 — M1 단계에서 Parquet 이 SOT). `IngestResult` 에 `sqlite_created/updated/skipped` 추가.
- `roadmap/schema.py` — `공정ID`/`공정 ID`/`공정아이디` → `process_id` COLUMN_MAP 추가, `OPTIONAL_COLUMNS`·`RoadmapRow` 에 `process_id` 필드.
- `scripts/migrate_roadmap_to_sqlite.py` 신규 — 1회성 마이그 CLI. `--file`/`--dry-run`/`--changed-by` 옵션. 최신 Parquet → SQLite, 1건 이상 쓰면 exit 0.
- `tests/test_roadmap_sqlite_sync.py` (+16) — schema 9 컬럼·`row_to_task_def` 5건(컬럼 우선/JSON fallback/org_meta 주입/process_id 없음/team 없음)·`sync_dataframe` 4건(create+update/skip invalid/empty/source 기록)·`ingest_excel`→SQLite 3건·마이그 CLI 3건.

### Added (작업 정의 SQLite 저장소 — PR-1: schema + CRUD API)
- `store/task_defs_db.py` 신규 — sqlite3 기반 작업 정의 저장소. `task_defs` (process_id PK + JSON SOT + scalar 미러 + created/updated 메타) + `task_def_history` (json_before/after + action + source) 2 테이블 자동 생성, conftest 의 `ROADMAP_DIR` 격리 그대로 호환.
- API: `get(process_id)`, `upsert(process_id, json_str, *, task_def_text=, changed_by=, source=)`, `delete(process_id, *, changed_by=, source=)`, `list_all(*, team=, dept=, process=, limit=)`, `search(query, *, limit=50)`, `history(process_id, *, limit=)`, `count()`, `upsert_many(items, *, changed_by=, source="excel_upload")`.
- 검증: invalid JSON, non-object JSON, missing `org_meta`, missing `org_meta.team/dept`, `process_id` mismatch (인자 vs JSON 내) 모두 `ValueError` 로 거부. upsert 1회마다 history 1건 자동 기록 (history 는 무한 누적).
- `tests/test_task_defs_db.py` (+23) — schema 자동 생성·upsert 신규/갱신·validation 6건·get/delete·list_all 필터·search (process_id/JSON 본문)·history 누적·upsert_many.
### Added (작업 정의 JSON `org_meta` 확장 — PR-2: v1.0 스키마 + helper)
- `roadmap/task_def_json.py` 확장 — `SCHEMA_VERSION="1.0"`, `ORG_META_KEYS` 9개(`team/dept/division/process/task/sub_task/lv1/lv2/lv3`), `ORG_META_REQUIRED=("team","dept")` 상수 공개. 기존 `parse/TaskDef/automation_keywords/to_chat_context_lines/flatten_for_match/first_objective` API 무변경.
- `ingest_org_meta(json_text, org_meta, *, process_id=None, version="1.0")` — 기존 JSON 에 `org_meta` 주입. 빈/깨진 입력은 새 dict 로 시작, unknown key silent drop, 빈 값 자동 누락, `process_id` 인자로 top-level 동기화, `version` setdefault (기존 값 보존).
- `org_meta_of(json_text)` — JSON 에서 `org_meta` 만 안전 추출. 알려진 키만 strip 해서 반환, 빈 값/타입 미스매치는 모두 빈 dict.
- `validate_task_def_json(json_text)` — `store.task_defs_db.upsert` 입력 사전 검증 (top-level `process_id` + `org_meta.team/dept`). 통과 시 파싱된 dict 반환.
- 새 예외 `TaskDefJsonError(ValueError)` — 모든 검증 실패가 이 타입 (호출자가 `ValueError` 로도 잡을 수 있음).
- `tests/test_task_def_json_org_meta.py` (+18) — 상수 sanity / `ingest_org_meta` 9건 (신규 주입·빈 입력·깨진 JSON·process_id 덮어쓰기·version 보존·strip+drop·unknown ignore·team 누락·dept 누락·non-dict) / `org_meta_of` 2건 / `validate_task_def_json` 4건.

### Docs (작업 정의 데이터 시스템 마이그 계획 — Parquet → SQLite + JSON)
- `docs/TASK_DEF_PLAN.md` 신규 — 작업 정의 데이터 저장·관리·CRUD 마이그 plan. 결정사항 9개, 데이터 모델(엑셀 9 컬럼 / `task_def_json` `org_meta` 확장 / SQLite 스키마 + history), 8 PR 의존성 그래프 + 규모 추정, 화면 시뮬레이션 5 시나리오, 마일스톤 M1~M5, 리팩토링 시점 표 포함. 컨텍스트 압축 후에도 단일 source 로 복원 가능.
- `docs/SESSIONS.md` — 중간 점검 세션 + 결정사항 요약 추가.

### Added (SOLA workshop thread 제목 LLM 생성 — 단순 truncation → 5~12자 압축)
- `sola/thread_title.py` 신규 — `generate(user_message, *, force=False)` API. 첫 user 메시지를 `SYSTEM_THREAD_TITLE` 프롬프트로 LLM 호출 → 5~12자 한국어 제목 압축. `store.cache` 디스크 캐시 (sig = 메시지 앞 100자 + 모델). `LLMNotConfigured` / 일반 예외 / 빈 또는 너무 짧은 응답 → `store.sola_threads.title_from_first_user_message` truncation fallback.
- `sola/prompts.py::SYSTEM_THREAD_TITLE` 신규 프롬프트 — "한국어 5~12자, 따옴표/이모지/장식 금지, 입력 외 사실 만들지 말 것".
- `sola/thread_title.py::_clean_title()` — 양끝 따옴표(`"'“”‘’`「」`)·코드 블록(\`)·마침표 제거, 첫 줄만, 이모지(U+1F300~U+1FAFF + Misc Symbols) 제거, `_MAX_LEN=20` 자르기.
- `ui/sola_workshop_v2.py::_append_message` — 첫 user 메시지(thread 제목이 "새 대화" 또는 빈 값)일 때 `sola.thread_title.generate(content)` 호출, 실패 시 기존 `title_from_first_user_message` fallback.
- `tests/test_thread_title_llm.py` (+16) — `_clean_title` 6건(quotes·첫 줄·trailing 구두점·길이 제한·이모지 제거·빈 입력) + `generate` 7건(LLM 응답 사용·`LLMNotConfigured` fallback·일반 예외 fallback·너무 짧은 응답 fallback·캐시 hit·force 우회·빈 메시지) + `_append_message` UI 통합 3건(첫 user 메시지에 generate 호출·assistant 메시지 skip·기존 제목이 있을 때 skip).
- `tests/test_sola_composer.py::clean_chat_log` fixture — `store.cache._cache_dir` 격리 + `sola.client._client.cache_clear()` 추가로 LRU 캐시 오염 차단(다른 테스트의 fake OpenAI 잔여 영향 제거).

### Added (인사이트 SECTION C 히트맵 cell 클릭 wire — 정적 mockup → 동적 + 클릭)
- `ui/insights_v2.py::_hm_select_href(process, tech)` — `?app_area=🔎+인사이트+분석&hm_select=<process>|<tech>` URL 빌더 (빈 값 → 토글 해제).
- `ui/insights_v2.py::_hm_selected_key()` — `?hm_select=` 1회 stateless 읽기.
- `ui/insights_v2.py::_hm_count_in_news(news_df, process, tech)` — title/summary/keywords/content 6 컬럼 substring(case-insensitive)으로 process AND tech 모두 매칭되는 row 수.
- `ui/insights_v2.py::_hm_cell_class(v)` — 5단계 강도 분류 (empty 0 / low ≤3 / normal 4-7 / mid 8-15 / strong 16+).
- `ui/insights_v2.py::_hm_top_news(news_df, process, tech, limit)` — 선택 셀의 매칭 뉴스 top N (collected_at desc).
- `ui/insights_v2.py::_ia_heatmap_html(selected_key=None)` — 동적 히트맵 빌드. 행 = `_score_cells` 상위 7개 unique lv3(등장순), 열 = 고정 `_HM_TECH_COLS` 7개(비전/협동 로봇/예지보전/디지털 트윈/AGV/AI/외골격). 각 셀은 `<a class="ia-hm-c..." href="?hm_select=...">` — 토글 해제 href 포함. 선택 시 `ia-hm-c-on` outline + 하단 detail strip (top 3 뉴스 + SOLA 인계 + 닫기).
- `ui/insights_v2.py::_ia_heatmap_empty()` — 빈 데이터 상태 안내.
- `assets/v2/screens/insights_main.html` — 정적 mockup(7행 × 7열 + "빈 칸 클릭" 트리거) 약 95줄 → `{{IA_HEATMAP}}` 단일 placeholder.
- `ui/insights_v2.py::render()` — `_hm_selected_key()` 읽어 `_ia_heatmap_html` 에 전달.
- `assets/v2/screens/insights.css` — `a.ia-hm-c` I-19 + `.ia-hm-c-on` accent outline + `.ia-hm-total` / `.ia-hm-detail*` (head/clear/news-list/sola CTA/empty) 신규.
- `tests/test_heatmap_click.py` (+15) — URL 빌더(인코딩/토글) / `_hm_selected_key` / count(case-insensitive·AND·empty 가드) / cell_class 5단계 / top_news 정렬·필터 / 히트맵 동적 셀 `<a>` 전환·옛 mockup 자취 0 / selected_key 활성 표시·detail strip / 토글 해제 href / detail 0건 안내 / 빈 데이터 / 합계 카운트 / 템플릿 placeholder 존재.
### Changed (cron daily scrape — 커스텀 RSS 통합 + 입력/출력 강화)
- `scripts/daily_scrape.py` — PR #71 의 커스텀 RSS 수집을 cron 경로에도 통합. `_load_extra_feeds()` 신규 (store.sources 로드, 실패 시 stderr 경고 + 빈 리스트). `--skip-custom-rss` 플래그 추가. `collect_batch(..., extra_feeds=...)` 호출에 반영. 시작 로그에 "커스텀 RSS N건" + 종료 로그에 일부 오류 첫 1건 출력.
- `.github/workflows/scrape-daily.yml` — `workflow_dispatch.inputs.skip_custom_rss` 신규 입력. Run step 에서 `EXTRA_FLAGS` 변수로 CLI 에 전달. 주석에 cron 시간대(KST 09:00 = UTC 00:00) + 커스텀 RSS 통합 명시.
- `tests/test_daily_scrape_rss.py` (+9) — `_load_extra_feeds`(빈/등록 N개/store 예외 swallow) / main 이 extra_feeds 를 collect_batch 에 전달 / `--skip-custom-rss` 가 None 전달 / errors 보고 / 0건 시 stderr 경고 / workflow yml 의 `skip_custom_rss` 입력 + `--skip-custom-rss` 전달 / cron 표현식 + KST 주석 검증.
- `tests/test_run_daily.py::test_cli_default_keywords_used` — fake collect_batch signature 에 `extra_feeds` 인자 수용.


### Added (SOLA 오늘의 브리핑 LLM 강화 — 가짜 한 줄 → 실 1~2문장 압축)
- `sola/board_brief.py` 신규 — `brief(items, persona_label, *, force=False)` API. 매칭 뉴스 top 3 + 부서 라벨을 `SYSTEM_BOARD_BRIEF` 시스템 프롬프트로 LLM 호출 → 1~2문장 평문 압축. `store.cache` 디스크 캐시 (sig = title@source 들 + persona_label + model). `LLMNotConfigured` / 일반 예외 / 빈 응답 → 룰 기반 fallback ("N건 두드러집니다").
- `sola/prompts.py::SYSTEM_BOARD_BRIEF` 신규 프롬프트 — "30초 부서장 브리핑" 톤, 굵은 키워드(`**...**`) 1~2개, 입력 외 사실 금지, 평문 1~2문장.
- `ui/board_v2.py::_brief_html(persona_label="")` — persona 라벨이 캐시 키. 매칭 items 에 news.summary 컬럼 보강(LLM 압축 품질↑) 후 `sola.board_brief.brief()` 호출. 빈 응답 fallback. LLM 응답의 `**굵은 키워드**` 마크다운만 `<b>` 로 변환.
- `ui/board_v2.py::_md_bold_to_html(text)` 신규 — 안전 변환기. `**...**` 매치는 `<b>` 로, 그 외는 모두 `html.escape()`. 다른 마크다운(헤더/리스트/링크)은 처리 안 함(프롬프트가 금지).
- `ui/board_v2.py::render()` — `_brief_html(persona_label=persona.label() or "")` 로 호출.
- 모듈 상단 `import re` 추가 (`_md_bold_to_html` 용).
- `tests/test_board_brief_llm.py` (+15) — `board_brief` 단위 8건: 빈 items / LLMNotConfigured fallback / 일반 예외 fallback / LLM 응답 사용 / 캐시 hit (1회 호출) / persona_label 분리 키 / force / 빈 응답 fallback. `_md_bold_to_html` 4건: `**` 변환 / HTML escape / 혼합 / 빈 문자열. `_brief_html` UI 통합 3건: LLM 응답이 summary 에 노출 + `<b>` 변환 / 빈 응답이면 룰 fallback / persona 라벨이 Streamlit 캐시 키.

### Added (인사이트 매트릭스 셀 클릭 wire — SVG 버블 → SOLA 작업실 인계 + 동적 PoC 리스트)
- `ui/insights_v2.py::_ia_mx_select_href(dept, lv3)` — `?app_area=🔎+인사이트+분석&ia_mx_select=<dept>|<lv3>` 빌더. 빈 dept/lv3 → 토글 해제.
- `ui/insights_v2.py::_ia_mx_selected_key()` — `?ia_mx_select=` 1회 stateless 읽기.
- `ui/insights_v2.py::_ia_matrix_svg(selected_key=None)` — SVG 버블 8개 각각을 `<a xlink:href="?ia_mx_select=dept|lv3">` 로 wrap (SVG 표준 링크). `<title>` 으로 hover tooltip. selected_key 매칭 셀에 `ia-mtx-bubble-on` + halo + 두꺼운 stroke + 토글 해제 href. 미매칭 fallback → 1위. `xmlns:xlink` 네임스페이스 추가.
- `ui/insights_v2.py::_ia_mtx_rank_html(selected_key=None)` — 우측 PoC 후보 리스트(5개 max)를 score_cells 로 동적 빌드. 옛 정적 mockup(도장 비전 검사 / 14명/일 / 9.2 등) 완전 제거. 각 항목 `<a class="ia-poc-link" href=...>` + `aria-current`. effort/impact 는 1-ease/eff norm 으로 高中低 자동 분류, score 는 max 기준 10점 만점 환산. 빈 상태 안내 `_ia_mtx_rank_empty`.
- `assets/v2/screens/insights_main.html` — 5개 정적 `<li class="ia-poc">` + "7건 전체 보기" 버튼 블록을 `{{IA_MTX_RANK}}` 단일 플레이스홀더로 교체.
- `ui/insights_v2.py::render()` — `selected_mx = _ia_mx_selected_key()` 읽어 `_ia_matrix_svg(selected_key=)` / `_ia_mtx_rank_html(selected_key=)` 전달.
- `assets/v2/screens/insights.css` — `.ia-poc-link` flex grid + I-19 (`a:visited` 색 inherit) / `.ia-mtx-bubble` cursor + hover brightness.
- `tests/test_insight_matrix_click.py` (+11) — URL 빌더(인코딩/토글) / `_ia_mx_selected_key` / SVG `<a>` wrap·`<title>`·disabled 자취 0·기본 1위 활성 / `selected_key` 활성 표시·토글 해제 href / 미지 키 fallback / PoC 리스트 동적 cells(5개 max)·기본 활성·옛 mockup 제거·실 score 10점 환산 / `selected_key` 매칭 항목 `ia-poc-on`·`aria-current` / 빈 상태 안내 / 템플릿 placeholder 존재 + 옛 mock `li` 자취 0.

### Added (커스텀 RSS 실 수집 wire — store.sources → scraping.run_daily 통합)
- `scraping/rss.py` 신규 — 범용 RSS 2.0 / Atom 피드 파서. `scraping.http.build_session()` 단일 진입점(§4 유지). RFC822 / ISO 8601 날짜 모두 인식, 중복 링크 제거, `description` 에서 이미지 URL 추출, 잘못된 URL/파싱 실패/HTTP 오류 시 `RuntimeError`.
- `scraping/run_daily.py::collect_batch(extra_feeds=None)` — 신규 인자. `(name, url)` 튜플 시퀀스를 받아 키워드와 무관하게 각 피드를 fetch → `save_articles(source=name)` 으로 별도 파일 저장(stamp 충돌 회피). 실패는 `errors` 에 누적.
- `ui/board_v2.py::_collect_extra_feeds()` — `store.sources.custom_sources()` 를 `(name, url)` 튜플 리스트로 변환. 실패 시 빈 리스트.
- `ui/board_v2.py::consume_kw_action_if_any` (collect 분기) — `extra_feeds` 전달. 키워드/피드 모두 비면 안내, 둘 중 하나라도 있으면 실행.
- `ui/data_management_v2.py::_consume_refresh_if_any` — `extra_feeds` 전달. ok 토스트에 "RSS N건" 카운트 노출.
- `tests/test_custom_rss_scrape.py` (+14) — `rss.fetch` 단위(RSS 2.0/Atom/max_results/dedupe/잘못된 URL/파싱 실패/HTTP 오류) + `collect_batch` extra_feeds 통합(저장/오류/None 기본) + UI 통합(`_collect_extra_feeds` / dm refresh 가 extra_feeds 전달 / 토스트에 RSS 카운트).

### Added (보드 음성으로 듣기 (TTS) — Web Speech API 인라인 재생)
- `ui/board_v2.py::_tts_button_html(text, label, cls)` — `data-tts` 속성에 `json.dumps` + HTML escape 로 안전 인코딩. 클릭 시 인라인 `onclick` 핸들러가 `SpeechSynthesisUtterance` (lang `ko-KR`) 로 즉시 재생. 새 재생은 직전 재생을 cancel. 빈 텍스트 → 버튼 미노출. HTML `onclick` 은 브라우저 JS 속성이라 Streamlit `on_click=` callback 금지 invariant 와 무관.
- `ui/board_v2.py::_tts_disabled_html()` — 재생 대상 텍스트 없을 때 disabled 버튼.
- `_brief_html` — 빈 키 `tts_btn` 추가. 본문 = "최근 매칭 N건…" + 번호 매긴 제목들. 빈 상태에는 disabled 버튼.
- `_board_matrix_html` — detail 패널에 `mx_tts_text` 페이로드("dept · lv3. 종합 점수 N점. 매칭 뉴스 N건. 매칭 작업 N건. why_text") + `db-mx-tts` 버튼을 `db-mx-cta` 옆 `db-mx-detail-actions` flex 컨테이너에 노출.
- `assets/v2/screens/board_main.html` — 기존 `<button class="db-act" disabled title="TTS 미구현 — 다음 PR">음성으로 듣기 · 준비 중</button>` 를 `{{BRIEF_TTS_BTN}}` 플레이스홀더로 교체.
- `ui/board_v2.py::render()` — `brief.get("tts_btn", "")` 로 치환.
- `assets/v2/screens/board.css` — `.db-act-tts` hover/disabled 스타일, `.db-mx-detail-actions` flex, `.db-mx-tts` 작은 inline TTS 버튼 스타일.
- `tests/test_board_tts.py` (+9) — `_tts_button_html` XSS 안전 인코딩(`<script>` escape) / 빈 텍스트 / label escape / disabled HTML / `_brief_html` `tts_btn` 키 포함·빈 상태 disabled / 매트릭스 detail TTS 버튼 + dept·lv3·점수 페이로드 검증 / `board_main.html` 에 placeholder 존재 + 옛 disabled 자취 0.
- `tests/test_v2_screens.py::test_board_empty_state_helpers_dont_raise` — brief 키 집합 검사에 `tts_btn` 포함.
- `tests/test_matrix_click.py::test_matrix_each_bubble_has_clickable_href` — `_board_matrix_html.clear()` 추가로 캐시 격리.

### Changed (수집 트리거 실 실행 — `?refresh=now` 가 collect_batch 동기 호출)
- `ui/data_management_v2.py::_consume_refresh_if_any` — 기존엔 캐시만 무효화하던 동작을 페르소나 관심사 키워드(`_collect_keywords_for_persona`)로 `scraping.run_daily.collect_batch` 동기 호출 후 캐시 무효화로 정직화. 결과는 토스트로 안내(`N개 키워드로 M건 수집`).
- 분기 토스트 — ok(`saved>0`) / warn(키워드 없음 → 수집 스킵) / error(전부 실패 또는 예외). 캐시는 collect 실패와 무관하게 항상 무효화.
- `_render_refresh_toast_if_needed` — `(kind, message)` 튜플 분기 + 구버전 `True` payload 호환. warn 색 추가(노란색).
- `_refresh_cta_html` — 툴팁이 "캐시 무효화 (실제 수집은 06:00 스케줄러)" → "페르소나 관심사 키워드로 지금 수집 + 캐시 갱신" 으로 변경.
- `tests/test_collect_trigger.py` (+9) — CTA 툴팁(수집 안내·"06:00" 제거) / collect_batch 호출 인자 검증 / 부분 실패 시 ok 토스트의 "일부 오류 N건" / 전부 실패 시 error 토스트 / 키워드 없을 때 collect 스킵·warn / collect 예외 시에도 캐시 clear · error 토스트 / 토스트 색상 (ok/warn) + True payload 호환.
- `tests/test_v2_screens.py::test_data_management_refresh_clears_caches_and_sets_toast` — collect_batch mock 추가 + 토스트가 튜플 형식으로 갱신됐는지 검증. 추가 2 케이스(warn/error).

### Added (출처 설정 CRUD — 기본 출처 활성/비활성 토글 + 커스텀 RSS 추가/제거)
- `store/sources.py` 신규 — `data/sources/config.json` 영구화. API: `disabled_set()`, `is_enabled()`, `toggle_disabled()`, `custom_sources()`, `add_custom()`, `remove_custom()`, `all_active()`. `DEFAULT_SOURCES` 4개(AI Times/오토메이션월드/Google RSS/네이버 기술)는 토글만, 커스텀은 add/remove.
- `ui/data_management_v2.py::_src_action_href` — `?dm_tab=src&src_action=toggle|remove&src_name=` 빌더.
- `ui/data_management_v2.py::_consume_src_action_if_any()` — toggle/remove 1회 소비 → store 호출 → toast set + query strip. 알 수 없는 action 은 무시(쿼리 유지).
- `ui/data_management_v2.py::_consume_src_add_if_any()` — Streamlit 폼 pending(`_do_src_add`)으로부터 `add_custom` 실행. `ValueError` → error toast.
- `ui/data_management_v2.py::_render_src_action_toast_if_needed()` — ok/error inline toast.
- `ui/data_management_v2.py::_render_src_add_form()` — src 탭 전용 Streamlit `text_input` × 2 (이름/URL) + "출처 등록" 버튼.
- `ui/data_management_v2.py::_dm_src_body_html` — 기본 출처 4행(토글 링크 포함) + 커스텀 출처 행(URL mini + 제거 링크) + 기타(news.source 의 미지 ID, 토글 불가) 행. 비활성 행은 흐림 + "비활성" 라벨.
- `ui/data_management_v2.py::render()` — `_consume_src_action_if_any()` + `_consume_src_add_if_any()` + `_render_src_action_toast_if_needed()`. src 탭일 때 `_render_src_add_form()` 위젯 렌더.
- `assets/v2/screens/data_management.css` — `.dm-src-row-off` 흐림, `.dm-src-st-off` 비활성 라벨, `.dm-src-act` 토글 링크, `.dm-src-act-rm` 제거 강조, `.dm-src-row-custom` accent bg, `.dm-src-url-mini` URL 보조 텍스트.
- `tests/test_src_crud.py` (+18) — store 단위(default empty/toggle/unknown/add 검증·중복·duplicate/remove/all_active 결합) + URL 빌더 + consume(toggle·remove·noop) + add form(success/error) + body HTML(토글 링크·비활성 라벨·커스텀 행·제거 링크·활성 카운트).

### Added (산출물 칸반 "+N건 더 보기" wire — 컬럼별 expand/collapse 토글)
- `ui/archive_v2.py::_expanded_cols_from_query()` — `?expand=pending,adopted` CSV 파싱(유효 컬럼만 통과). 빈 frozenset 가드.
- `ui/archive_v2.py::_archive_expand_href(col, current)` — 토글 URL 빌더. col 포함 시 제거(접기), 미포함 시 추가(펴기). expand 결과가 비면 파라미터 자체 생략(깨끗한 URL). 출력 순서는 항상 (pending, adopted, rejected).
- `ui/archive_v2.py::_build_cards_html(..., col_key, expanded, expanded_set)` — `<button disabled>` "+N건 더 보기" → `<a class="oa-col-more">` 전환. expanded=True 면 모든 카드 + "− 접기 (N건)" 링크(4건 이하면 접기 링크 미노출). 토글 링크는 다른 컬럼 expand 상태 보존.
- `ui/archive_v2.py::_oa_stats_and_cards(expanded_csv)` — CSV 인자 캐시 키. 컬럼별 expand 상태에 따라 visible 분기.
- `ui/archive_v2.py::render()` — `expanded_csv = ",".join(sorted(_expanded_cols_from_query()))` 로 호출.
- `assets/v2/screens/archive.css` — `a.oa-col-more` I-19 패턴(text-decoration:none + `:visited` 색 회복) + `.oa-col-more-collapse` 접기 강조(accent border/bg).
- `tests/test_archive_more.py` (+14) — 쿼리 파서(CSV/유효성/빈 값) / 토글 URL(추가·제거·다른 컬럼 보존·정렬) / `<a>` 전환·disabled 자취 0 / expand 시 전체 노출·접기 링크 / 4건 이하 접기 미노출 / `_oa_stats_and_cards` CSV 캐시 키 + 컬럼별 분기 + 다른 컬럼 보존.

### Added (보드 ⑥ 매트릭스 버블 클릭 wire — 셀 선택 → 상세 패널 갱신)
- `ui/board_v2.py::_mx_select_href(dept, lv3)` — `?app_area=📊+오늘의+보드&mx_select=<dept>|<lv3>` URL 빌더. 빈 값 → mx_select 생략(토글 해제).
- `ui/board_v2.py::_mx_selected_key()` — `?mx_select=` 1회 stateless 읽기, 빈 값 → None.
- `ui/board_v2.py::_board_matrix_html(selected_key=None)` — `<button disabled>` 6 버블 → `<a class="db-mx-bubble">` 전환. selected_key 가 셀 키(`"dept|lv3"`)와 매칭되면 그 셀에 `db-mx-on` 활성 + aria-current + href 는 토글 해제(빈 mx_select), 비활성 셀은 그 셀로 새 선택. 매칭 실패 시 1위 cell fallback. 상세 패널(`.db-mx-detail`) 의 eyebrow 가 `선택됨 · {rank}위` 로 동적, 통계·이유·CTA 도 선택 셀 기준.
- `ui/board_v2.py::render()` — `_board_matrix_html(selected_key=_mx_selected_key())` 호출.
- `assets/v2/screens/board.css` — `a.db-mx-bubble` I-19 패턴(text-decoration:none + `:visited` 색 inherit) + `.db-mx-on .db-mx-bsize` 강한 ring + `.db-mx-on .db-mx-blabel` 라벨 강조.
- `tests/test_matrix_click.py` (+9) — URL 빌더(인코딩/토글 해제) / `_mx_selected_key` 읽기·None / `<a>` 전환·disabled 자취 0·기본 1위 / 선택 셀 표시(`db-mx-on` 1개·`aria-current` 1개)·상세 패널 갱신·rank 라벨 / 미지 선택값 fallback / 비선택 버블 href 정상.

### Added (인사이트 트렌드 키워드 클릭 wire — 키워드 선택 → 공정 매핑 필터)
- `ui/insights_v2.py::_tkw_select_href(keyword)` — `?app_area=🔎+인사이트+분석&tkw=<keyword>` URL 빌더. 빈 keyword 면 토글 해제(필터 클리어).
- `ui/insights_v2.py::_tkw_list_html(selected_kw=None)` — `<button disabled>` → `<a class="ia-tkw-item">` 전환. `selected_kw` 지정 시 그 키워드만 `ia-tkw-on` + `aria-current` + href 는 토글 해제. 비활성 항목은 그 키워드로 새 선택. 미지정 시 기존 동작(rank 1 활성) 유지.
- `ui/insights_v2.py::_ia_process_map_html(selected_kw=None)` — `selected_kw` 지정 시 30일 뉴스를 `_news_filter_by_keyword` 로 필터(title/summary/keywords/content substring · case-insensitive)한 뒤 `_score_cells` 에 전달. "선택된 키워드" chip 도 사용자 선택값으로 표시. 필터 후 0건이면 "X 키워드에 매핑되는 공정이 없어요" + 전체 보기 링크.
- `ui/insights_v2.py::_news_filter_by_keyword(df, keyword)` — 신규 helper(다른 키워드 필터 화면도 재사용 가능).
- `ui/insights_v2.py::render()` — `selected_kw = st.query_params.get("tkw")` 읽어 두 helper 에 전달. URL stateless 유지(area 이동 시 자동 클리어 — `<a href>` 가 query 전체 재작성).
- `assets/v2/screens/insights.css` — `a.ia-tkw-item` I-19 패턴(text-decoration:none + `:visited` 색 회복).
- `tests/test_insight_tkw_click.py` (+11) — URL 빌더 / `<a>` 전환·disabled 자취 0 / `selected_kw` 활성 클래스·aria-current·toggle off href / process map 필터 chip / 필터 0건 안내·전체 보기 링크 / `_news_filter_by_keyword` substring·case-insensitive·None·빈 df 가드.

### Changed (topbar 알림/설정 버튼 정직화 — disabled no-op → 실제 동작)
### Added (B.5 데이터관리 4 탭 본문 — 키워드 / 작업 정의 / 출처 설정 wire)
- `assets/v2/screens/data_management_main.html` — 4 `<button disabled>` 탭 바를 `{{DM_TABS}}` 플레이스홀더로, `<div class="dm-split">` 블록을 `{{DM_MAIN_BODY_OPEN}}` / `{{DM_MAIN_BODY_CLOSE}}` 마커로 래핑(탭 별 전환).
- `ui/data_management_v2.py::_dm_tab_href(tab)` — `?app_area=🧱+데이터+관리&dm_tab=<tab>` 빌더. 기본(jobs)은 dm_tab 생략.
- `ui/data_management_v2.py::_dm_tabs_html(selected_tab, dm_stats)` — `<a class="dm-tab">` 4개 동적 빌드. 활성 탭에 `dm-tab-active` + `aria-current`. jobs 탭에 활성 출처/오늘 수집 카운트 동적 노출.
- `ui/data_management_v2.py::_dm_tab_body_html(tab, persona, dm_stats)` — 디스패치:
  - `_dm_kw_body_html(persona)` — 키워드 탭: SOLA 자동 추출 top 6(muted 제외) + 내가 추가(페르소나 관심사) + 숨김 키워드 + "보드 ⑦ 카드"/"관심사 편집" 진입.
  - `_dm_task_body_html()` — 작업 정의 탭: 안내 카드 + 현재 저장 건수.
  - `_dm_src_body_html(dm_stats)` — 출처 설정 탭: 7일 출처별 수집 카운트 + 마지막 시각 + 상태(OK / 7일 무수집). 누락 출처(AI Times/오토메이션월드/Google RSS/네이버 기술)는 0건으로 회색 노출.
- `ui/data_management_v2.py::_render_main(dm_stats, selected_tab, persona)` — jobs 외 탭에서 `dm-split` 블록을 `display:none` wrapper 로 숨기고 탭 본문 HTML 을 그 자리에 inline 렌더.
- `ui/data_management_v2.py::render()` — `?dm_tab=` 읽어 `selected_tab` 결정. `_render_task_def_upload()` (Streamlit file_uploader) 는 `task` 탭에서만 렌더.
- `assets/v2/screens/data_management.css` — `a.dm-tab` I-19 패턴 + `.dm-tab-body` / `.dm-tb-head` / `.dm-tb-desc` / `.dm-tb-link` / `.dm-tb-cta` / `.dm-kw-section*` / `.dm-kw-chip*` / `.dm-src-table` / `.dm-src-row` 신규.
- `tests/test_dm_tabs.py` (+14) — URL 빌더 / `<a>` 전환·disabled 자취 0·"B.5 PR" 텍스트 0 / 활성 탭 마킹 + aria-current / 미지 탭 fallback / kw body 페르소나·muted·자동 추출 / task body 현재 카운트 / src body 출처별 카운트 + 누락 출처 회색 / 디스패치 4 분기 / `_render_main` jobs vs non-jobs 분기.
- `tests/test_task_def_upload.py::test_data_mgmt_renders_upload_section_with_helpful_text` — task 탭 진입(`?dm_tab=task`) 후 업로드 섹션 확인하도록 업데이트.

### Added (인사이트 트렌드 키워드 클릭 wire — 키워드 선택 → 공정 매핑 필터)
- `ui/app_shell.py::render_topbar` — 알림/설정 `<button disabled>` 두 개를 `<a class="db-hdr-btn">` 로 전환.
  - 🔔 **알림** → `?app_area=📦+산출물+보관함`. `_notif_count()`(채택 대기 pending 제안서 수)가 0 보다 클 때만 빨간 점 + 개수 배지(99+ 캡) 노출 + 툴팁 "채택 대기 N건". 0 이면 점/배지 없이 "새 알림 없음" 툴팁 — 가짜 알림 표시 제거(정직).
  - ⚙ **설정** → `?persona_editor=1` (프로필/페르소나 편집).
- `ui/app_shell.py::_notif_count()` 신규 — `store.bookmarks.summary_counts()["proposal_status"]["pending"]`, 실패 시 0.
- `assets/v2/shell.css`, `assets/v2/screens/board.css` — `a.db-hdr-btn` I-19 패턴(text-decoration:none + `:visited` 색 회복) + `.db-hdr-badge` 카운트 배지 스타일.
- `tests/test_topbar_actions.py` (+8) — `_notif_count` 3 케이스(pending/0/예외) + `<a>` 전환·disabled 자취 0 / 알림→보관함·설정→persona_editor URL / pending>0 일 때만 점·배지·툴팁 / 0 이면 "새 알림 없음" / 99+ 캡.

### Added (보드 ⑦ 키워드 관리 wire — × 삭제 + 즉시 수집)
- `persona/schema.py::Persona` — `muted_keywords: list[str]` 필드 추가. `to_dict`/`from_dict` 라운드트립. 기본 빈 리스트(기존 프로필 호환).
- `ui/board_v2.py::_kw_action_href(action, keyword)` — `?app_area=📊+오늘의+보드&kw_action=del_user|mute|collect&keyword=` URL 빌더.
- `ui/board_v2.py::consume_kw_action_if_any()` — 1회 소비. (a) `del_user` → persona.interest_tasks/lv3 에서 제거 + save, (b) `mute` → persona.muted_keywords 에 추가(중복 제거) + save, (c) `collect` → `scraping.run_daily.collect_batch(persona keywords)` 동기 실행. 토스트 set + query strip + `_board_kpis.clear()`. 알 수 없는 액션 무시(쿼리 유지).
- `ui/board_v2.py::render_kw_action_toast_if_needed()` — ok/error inline toast (1회). 공용 `_render_inline_toast()` 추출(opp/kw 공유).
- `ui/board_v2.py::_board_kw_mgr_html` — 자동 추출/사용자 그룹의 × 를 `<a class="db-kchip-x" href=...>` 로 wire. "지금 즉시 수집 실행" 버튼도 `<a class="db-kw-sum-cta" href=...>`. `persona.muted_keywords` 가 자동 추출 결과에서 필터링(여유 N+muted 만큼 가져온 뒤 top 6).
- `ui/board_v2.py::render()` — 위젯 이전에 `consume_kw_action_if_any()` 호출 + 토스트 렌더.
- `assets/v2/screens/board.css` — `.db-kchip-x` / `.db-kw-sum-cta` I-19 패턴(text-decoration:none + `a:visited` 색 회복). `.db-kchip-x` 를 inline-flex 정렬로 보정.
- `tests/test_kw_actions.py` (+16) — URL 빌더 / persona muted_keywords 라운드트립 / del_user · mute · collect 3 경로 + dedup / 알 수 없는 액션 무시 / 키워드 없을 때 collect no-op / 카드 HTML `<a>` 전환 + muted 필터 / toast 렌더·clear.

### Added (자동화 기회 카드 보류/채택 wire — 산출물 보관함 연동)
- `ui/board_v2.py::_opp_card_html` — `db-prop-hold` / `db-prop-accept` `<button disabled>` → `<a href>` 로 wire. URL 패턴 `?app_area=📊+오늘의+보드&opp_action=accept|hold&dept=&lv3=&title=` (CTA 인계와 일관). 시안 가운데 "SOLA와 검토 →" 는 그대로.
- `ui/board_v2.py::_opp_action_href(action, dept, lv3, title)` 신규 — URL 빌더.
- `ui/board_v2.py::consume_opp_action_if_any()` — 1회 소비. `Bookmark(type="proposal", status="adopted"/"pending", tags=[dept, lv3])` 추가 + 성공/실패 toast set + query strip (재실행 방지). 알 수 없는 action 무시.
- `ui/board_v2.py::render_opp_action_toast_if_needed()` — ok/error inline toast (1회).
- `ui/board_v2.py::render()` 최상단 — pending 소비 + `_archive_stats` 캐시 invalidate (KPI/사이드 통계 즉시 갱신).
- `assets/v2/screens/board.css` — `<a class="db-prop-hold|accept">` text-decoration · :visited 색 회복 (I-19).
- `tests/test_opp_actions.py` (+10) — URL 빌더 / consume accept→adopted / hold→pending / 알 수 없는 action 무시·query 유지 / 기본 title 자동 채움 / 카드 HTML `<a>` 전환 검증 (disabled 자취 0) / toast 렌더 + clear.


### Added (작업 정의 엑셀 Phase 3 — 업로드 UI + 용어 통일 "로드맵" → "작업 정의")
- `ui/data_management_v2.py::_render_task_def_upload` 신규 — 본문 끝 "📂 작업 정의 데이터 업로드" 섹션. 컬럼 안내 + 현 저장 건수 + `st.file_uploader` + 시트 선택 + 5행 미리보기 + "✅ 이 파일로 업로드 + 저장" 버튼. 클릭 → `_do_task_def_ingest` pending flag → rerun.
- `_consume_task_def_upload_if_any` — pending 1회 소비. `ingest_excel(BytesIO, sheet_name, save_raw=True)` → 성공 시 `_dm_stats`/`_ingest_jobs_html`/`_hist_html`/`_news_cards_html`/`_archive_stats_dm` + `load_latest` 캐시 invalidate + 성공 toast. 실패 시 error toast.
- `_render_task_def_toast_if_needed` — ok/error inline toast (녹/적) 1회.
- **용어 일괄 변경 "로드맵" → "작업 정의"** (사용자 노출만): 데이터관리 탭 / 보드·인사이트 빈 안내 / 페르소나·온보딩 안내 / data_health / task_tree. 코드 식별자(`roadmap/`, `RoadmapRow`, `load_roadmap`)는 호환 유지.
- `tests/test_task_def_upload.py` (+7) — consume 4 케이스 (noop/성공/잘못된 엑셀/validate 실패) + AppTest 업로드 섹션 렌더 + pending payload e2e + 회귀 가드 (사용자 노출에 "로드맵" 잔존 없음).
- `tests/test_data_health.py` — wording 단언 갱신.

### Added (작업 정의 엑셀 Phase 2 — 매칭 정확도↑ + 카드 objective + SOLA 컨텍스트)
- `roadmap/task_def_json.py` — 신규 helper `flatten_for_match(json_text)` + `first_objective(json_text)`.
- `store/match.py::score_matches` — roadmap_df 의 `task_def_json` 컬럼이 있으면 `flatten_for_match` 결과를 task_text 에 합산. 자동화 영역·품질 리스크·objectives 토큰이 매칭 정확도 향상. 예: "RFID OCR 부재번호 자동 인식" 뉴스 → "판넬 선별" 작업과 매칭 (이전엔 매칭 안 됨).
- `sola/opportunity.py::score_cells` — `sample_objectives` 컬럼 추가. 각 cell 의 첫 매칭 task 의 `task_def_json` 에서 첫 objective 추출. 없으면 빈 값(호환).
- `ui/board_v2.py::_opp_card_html` — 카드에 "🎯 목표 한 줄" 노출. XSS escape.
- `ui/board_v2.py::chat_context_block` — 자동화 기회 top 4 에 목표 라인 + **1위 cell 의 작업 정의 상세** (process_id/name/desc/objectives/품질 리스크/자동화 영역) 첨부. SOLA 가 "1위 자동화 기회의 품질 리스크는?" 같은 질문에 답 가능.
- `tests/test_roadmap_phase2.py` (+11) — flatten / first_objective / score_matches task_def_json 활용·미사용 호환 / sample_objectives 컬럼 / card HTML.

### Added (작업 정의 엑셀 Phase 1 — 신규 컬럼 + JSON 정의서 파서)
- `roadmap/schema.py` — 신규 OPTIONAL 컬럼 `division`(분과) · `process`(공정) · `task_def_json`(Structured JSON 텍스트). `COLUMN_MAP` 에 한글 헤더 추가 (`분과 → division`, `공정 → process`, `공정정의서(줄글) → task_def`, `공정정의서(JSON) → task_def_json`). `RoadmapRow` dataclass 도 동기.
- `roadmap/ingest.py::normalize_columns` — 신엑셀 호환 fallback. lv1/2/3 컬럼이 통째로 비어있으면 division/process/task 로 자동 채움 (기존 사용처: 보드 ④/⑥, 인사이트, persona interest_lv3 모두 호환). 부분 혼합 케이스에서도 안전.
- `roadmap/task_def_json.py` 신규 — `TaskDef` dataclass + `parse(s)` (안전 파싱, 잘못된/빈/non-dict JSON 모두 빈 TaskDef 반환) + `automation_keywords(task, max_n)` (매칭용 키워드 추출) + `to_chat_context_lines(task)` (LLM 시스템 메시지 첨부용 다중 라인). `automation_potential_areas` / `overall_quality_risks` 의 dict 리스트 구조(`{area, technology, expected_effect}`, `{risk, consequence}`) 자동 평탄화 — head_keys 우선순위로.
- `tests/fixtures/sample_task_def.xlsx` 추가 — 사용자 제공 샘플 (가공팀 32행, 신엑셀 형식).
- `tests/test_roadmap_task_def.py` (+17) — schema 신규 컬럼 / COLUMN_MAP 한글 매핑 / round-trip ingest (32행) / lv fallback / 기존 lv 보존 / 부분 혼합 안전 / parser 빈·잘못된·non-dict 입력 안전 / dict 리스트 평탄화 / `automation_keywords` 토큰 분리·dedupe·max_n / `to_chat_context_lines` 전 필드 노출 / 32행 전체 안전 파싱.
- 기존 `roadmap.query.load_latest` / `sola.opportunity.score_cells` 호출 호환 검증 — 신규 컬럼 추가에도 모든 사용처 동작.
### Added (SOLA workshop 우측 ws-ctx 패널 실데이터 wire)
- `assets/v2/screens/sola_main.html` ws-ctx 4 카드 정리:
  - **페르소나 스냅샷** — 편집 버튼 `<button>` → `<a href="?persona_editor=1">` (실 wire). `{{PERSONA_TEAM_SIZE}}="5–15명"` 정적 → `{{PERSONA_TEAM}}` 실 페르소나 `team` 필드. `{{KEYWORDS_COUNT}}="8개"` 정적 → `len(interest_lv3)+len(interest_tasks)` 실 카운트.
  - **고정된 출처 (3)** 시안 정적 → 빈 안내 ("아직 고정한 출처가 없어요" + "후속 PR"), `+` 버튼 `disabled`.
  - **연결된 제안서 (1)** 시안 정적 → **산출물 보관함** 카드로 의미 재정의. `bookmarks_store.list_all` pending 카운트 + 가장 최근 1건 미리보기 (`{{ARCHIVE_PENDING}}`+`{{LINKED_PROPOSALS}}`). "보관함 열기 (N건 대기) →" 링크가 `?app_area=📦+산출물+보관함` 으로 라우팅.
  - **이 스레드의 산출물 (2)** 시안 정적 → 빈 안내.
- `ui/sola_workshop_v2.py::_ctx_archive_summary` — 보관함 pending 카운트+최근 1건 HTML. 예외 시 빈 카드 폴백. 제목 `html.escape` (XSS).
- `_ctx_age_label` — ISO → "오늘"/"어제"/"N일 전"/"M월 D일" 친화 라벨.
- `assets/v2/screens/sola.css` — `<a class="ws-ctx-edit">`, `<a class="ws-ctx-link">` 의 text-decoration·:visited 색 회복 (I-19).
- `tests/test_sola_ctx_panel.py` (+7) — `_ctx_archive_summary` 5 케이스(empty / pending 노출+카운트+링크 / adopted·rejected 제외 / XSS / store 예외 폴백) + `_ctx_age_label` 2 케이스.
### Added (글로벌 SOLA 채팅 + 화면별 안내 + SOLA workshop 좌측 fix)
- **모든 화면 본문 하단에 SOLA 채팅 패널** — `ui/chat_panel.py` 신규. 활성 thread 의 최근 6개 메시지(역할별 버블) + Streamlit `st.chat_input`(화면 하단 자동 고정). 빈 thread 진입 시 area 별 **안내 카드**(headline + 추천 질문 5건 chip). SOLA workshop area 는 자체 풀스크린 채팅이라 미렌더.
- LLM 호출 인프라는 `sola_workshop_v2` 의 `_consume_send_if_any` / `_build_llm_messages` / `_load_messages` 그대로 재사용 — chat_panel 입력→pending flag→다음 run 에서 LLM 호출+영구화→rerun (단일 thread/chat_key 공유).
- **`ui/persona_page.py::chat_context_block`** 신규 — 페르소나 편집 화면의 채워진/비어있는 필드 + 관심 공정/작업을 LLM 컨텍스트로 packaging. 페르소나 설정 중에도 SOLA 가 "내 부서에 맞는 관심 공정 추천해줘" 같은 질문에 답 가능.
- **`app.py`** — 페르소나 페이지 분기에 `_chat_context_for_sola` set 추가, 모든 area render 후 `chat_panel.render(persona, area_key)` 호출 (SOLA workshop 제외). `consume_send_if_any` 를 화면 분기 전 최상단에서 호출 → 어느 area 에서든 송신 처리.
- **SOLA workshop 좌측 fix** — `app_shell.render_app_side()` 호출 제거. 좌측에 글로벌 `.app-side` (280px) + ws-threads (256px) 두 패널이 겹쳐 보이던 문제 해결. `assets/v2/streamlit-overrides.css` 에 `body:has(.ws-shell)` 분기 추가하여 block-container 의 padding-left 도 16px 로 축소. 다른 area 이동은 topbar / ⌘K 팔레트로.
- **6 area 안내 정의** (`_AREA_INTROS`): 보드 / 데이터 관리 / 인사이트 분석 / SOLA 작업실 / 산출물 보관함 / 프로필 설정. 각 area 마다 headline + 추천 질문 3~5건 (XSS 방어 위해 모두 `html.escape`).
- 보안 — `st.markdown(unsafe_allow_html=True)` 대신 `st.html` 사용 (CLAUDE.md §5, I-19, test_html_rendering 통과). 검색어 / area_key / 메시지 본문 / 페르소나 데이터 모두 escape.
- `tests/test_chat_panel.py` (+10) — intro 카드 헤드라인·chip·XSS · 모든 area 정의 검증 · 메시지 렌더 cap·escape·역할 스타일 · `consume_send_if_any` 위임 · SOLA workshop area skip.
- `tests/test_chat_context_blocks.py` (+2) — persona_page chat_context (채워진/빈 필드, 관심 공정·작업).


### Added (B.4 후속 2 — SOLA thread 검색 wire)
- `ui/sola_workshop_v2.py::_filter_threads_by_query` 신규 — 제목 substring 매칭(대소문자 무시·공백 strip·빈 query 패스스루).
- `_render_thread_list_html(search_query="")` 시그니처 확장 — 검색 모드면 일반 그룹(★고정/오늘/어제/이번 주/이전) 우회하고 **단일 평탄 "검색 결과 N건" 그룹**으로. 0 매칭 시 친화 빈 카드 (검색어 escape 노출 + "지우면 전체로" 안내).
- `_render_main` 에 `st.text_input(key="_sola_search_q")` 추가 — Streamlit native (시안 좌측 `<input>` 은 HTML 내부라 wire 불가, placeholder "아래 검색창에서 입력하세요"로 정직화). 검색어는 session_state 에 자동 보존, 비우면 즉시 전체 목록 복귀.
- XSS 방어 — 검색어를 빈 결과 카드에 노출할 때 `html.escape`.
- `tests/test_sola_thread_search.py` (+10) — 필터 (빈/매칭/대소문자/없는키워드/빈 title) · 렌더 (검색 모드 평탄 그룹 / 빈 결과 안내 / 검색어 escape / 일반 모드 그룹 유지 / 긴 검색어 cap).

### Added (B.4 후속 — 인계 새 thread 진입 + pin 토글 + 대화 삭제)
- `ui/sola_workshop_v2.py::_consume_prefill_ask_if_any` — 보드/인사이트 CTA 인계(`?from=...`)가 기존 대화에 섞이지 않도록 **전용 새 thread 생성** 후 prefill 전송. thread 제목은 인계 종류로 시드(자동화 기회 검토 / 매트릭스 후보 검토 / 공정 매핑 분석 / 보드 브리핑 검토 / 제안서 이어서 수정).
- 활성 thread 액션 버튼 확장 (본문 위 Streamlit, HTML 내부 클릭 불가 우회): [➕ 새 대화] · [📌 상단 고정 / 고정 해제] · [🗑 대화 삭제]. 삭제는 메시지 0 이면 즉시(빈 대화 정리), 메시지 있으면 2-click 확인(⚠️ 정말 삭제).
- pending 핸들러 `_consume_thread_actions_if_any` 에 `_do_toggle_pin` 추가 (`sola_threads.update(pinned=not cur.pinned, touch=False)` — 고정 토글은 updated_at 안 건드림).
- `tests/test_sola_composer.py` — `test_ask_prefill_creates_new_thread_and_sets_send_payload` (인계 새 thread + 시드 제목 + 송신 페이로드), `test_toggle_pin_action_flips_pinned`, `test_delete_action_removes_thread_and_resets_active`.

### Added (B.4 — SOLA thread 영구화 + 좌측 thread list 실데이터)
- `store/sola_threads.py` 신규 — `Thread` dataclass + CRUD (`create`/`get`/`update`/`delete`/`list_threads`) + `ensure_active` (id 없거나 미존재면 최근/신규로 폴백) + `title_from_first_user_message` (자동 제목, 36자 cap) + `migrate_legacy_main_if_needed` (A.3 의 `sola_main` chat_key 누적분을 첫 thread 로 자동 마이그). 메타데이터 단일 파일 `data/sola/threads.json`, 메시지는 기존 `chat_log` 의 `chat_key=thread.id` 활용 (chat_key 별 파일 분리는 기존 기능 재사용).
- `ui/sola_workshop_v2.py` — `_load_messages`/`_append_message` 가 활성 thread (`session_state["_sola_thread_id"]`) 의 chat_key 로 작동. 좌측 thread list 시안 24블록을 `{{THREAD_LIST}}` placeholder 로 교체하고 `_render_thread_list_html` 가 그룹(★ 고정/오늘/어제/이번 주/이전) + active 강조 + thread item 링크(`?switch_thread=<id>`) 동적 생성. 본문 위에 [➕ 새 대화] Streamlit 버튼 + 빈 thread (메시지 0, 다른 thread 있음) 일 때만 [🗑 빈 대화 정리] 노출. 첫 user 메시지로 thread 제목 자동 설정.
- pending 핸들러 추가: `_consume_thread_actions_if_any` (new/switch/delete), `_switch_thread_from_query_if_any` (URL `?switch_thread=` 1회 소비 + strip — 재방문 재실행 방지). 순서: thread 액션 → URL switch → prefill ask → send.
- 마이그레이션: A.3 이후 `sola_main` chat_key 에 누적된 메시지가 있고 threads.json 이 비어있으면 첫 user 메시지 제목 + message_count 채워 자동 thread 1개 생성 (legacy 파일은 보존 — 안전).
- `assets/v2/screens/sola_main.html` — 시안 미리보기 노트("B.4 PR") 제거. 검색 placeholder 는 disabled 유지 (검색 wire 는 후속 PR).
- `tests/test_sola_threads.py` (+15) — CRUD / 정렬(pinned 우선·updated_at 내림차순) / 자동 제목 (줄바꿈 처리 + 36자 cap + 빈 입력 폴백) / `ensure_active` 3 분기 / 마이그 3 케이스 (happy / no legacy / threads 이미 있음).
- `tests/test_sola_composer.py` — 기존 영구화 fixture + happy/미설정/예외 흐름을 B.4 thread 기반(`_sola_messages_<id>` cache key + active thread chat_log)으로 갱신. `test_append_message_persists_to_chat_log` 가 자동 제목·message_count 도 검증.

### Added (A.3 후속 — "보고있는 화면 콘텐츠" 자동 LLM 컨텍스트 주입)
- 각 v2 area 모듈에 `chat_context_block(persona) -> str` 함수 신규: `ui/board_v2`(7섹션: KPI·브리핑·탑스토리·자동화 기회·트렌드·매트릭스·키워드), `ui/data_management_v2`(헤더 stats·14일 일별 추이·출처별 분포·뉴스 라이브러리 6), `ui/insights_v2`(헤더·트렌드 키워드·5주 series·매트릭스 8·공정 매핑), `ui/archive_v2`(헤더 stats·칸반 3컬럼 각 카드 제목/본문/연령/태그).
- `app.py` — 각 area 의 render() 직후 그 area 의 `chat_context_block()` 호출 → `session_state["_chat_context_for_sola"]` 에 저장. SOLA 작업실 area 자체는 skip (chat history 가 이미 컨텍스트).
- `ui/sola_workshop_v2.py::_build_llm_messages` — system 블록에 화면 컨텍스트 첨부 ("SOLA 프롬프트 + 페르소나 블록 + 직전 화면 콘텐츠"). 사용자가 "탑 스토리 1위?", "⑥ 매트릭스 뭐 있어?" 같은 질문을 해도 LLM 이 답할 수 있음.
- 비용: 캐시된 helper 들이 같은 데이터 계산해두므로 컨텍스트 생성 비용 거의 0 (캐시 hit). 토큰량은 빈 데이터 80~150 자, 데이터 채워졌을 때 500~1500 자 (~ 1.5k 토큰, Groq 무료 티어에서 충분).
- `tests/test_chat_context_blocks.py` (+13) — 4 area 각각의 컨텍스트가 화면 마커 + 핵심 데이터(KPI/카드/키워드/카드 본문) 포함하는지 검증. 빈 상태에서도 예외 없이 헤더 반환. `tests/test_sola_composer.py` (+2) — `_build_llm_messages` 가 컨텍스트 set 시 첨부 / unset 시 미포함.

### Added (A.3 — SOLA composer 실 LLM 호출 wire)
- `ui/sola_workshop_v2.py` — 채팅 영역 시안 15블록(`ws-msg`)을 `{{WS_MESSAGES}}` placeholder 로 교체하고 `_render_messages_html()` 가 session/chat_log 의 실 메시지를 렌더. 첫 진입 시 `chat_log.load_history("sola_main")` 로 복원, 빈 상태에선 친화 카드("대화를 시작해보세요…").
- 송신 wire: 시안 footer의 `<textarea>` + send 버튼은 readonly + disabled로 시각 보존만, 실제 입력은 화면 하단 자동 고정되는 `st.chat_input` 사용. 인계 컨텍스트(`?from=brief/opp/matrix/ia_map/edit`)가 있으면 composer 위에 "📨 이 컨텍스트로 SOLA에게 물어보기" 버튼이 나타나 한 번에 prefill 송신.
- LLM 호출 흐름: pending flag(`_do_sola_send`) → `_consume_send_if_any(persona)` → user 메시지 추가 → `sola.client.chat(messages)` 호출 → assistant 메시지 추가 → `chat_log.save_history` 영구화 → `st.rerun`. messages 빌드는 SOLA system prompt + `persona.context.system_block(persona)` + 기존 히스토리.
- 폴백: LLM 미설정 시 `sola.preview.format_messages_preview(messages)` 결과를 assistant 메시지로 노출 (이미 다른 곳에서 쓰는 패턴 재사용). 일반 예외는 "⚠️ 응답 생성 실패: {ExcName}: {msg}" 친화 메시지.
- 보안: `_msg_html` 이 user/assistant 본문을 `html.escape` 후 `\n→<br>` 치환 — XSS 차단.
- `tests/test_sola_composer.py` (+16) — 메시지 HTML role/escape/newline · empty/ordered render · build_llm_messages persona 주입 + 잘못된 히스토리 skip · chat_log roundtrip + first-load · happy path / LLMNotConfigured 폴백 / 일반 예외 / 빈 payload noop · prefill ask가 composer_prefill 의 from kind별 텍스트로 전송 페이로드 set.
- 미배선 정직화: 시안 send 버튼 `disabled` + title "아래 입력창에서 전송하세요", 음성 입력 `disabled` + title "다음 PR".

### Added (페르소나 온보딩 마법사 — 미설정 사용자 단계별 프로필 설정)
- `ui/onboarding.py` 신규 — 페르소나 미설정 사용자에게 **중앙 모달(+backdrop 딤)** 환영 화면 + 4단계 마법사(이름 → 부서·팀 → 직무 → 관심 공정). `st.dialog(width="large", dismissible=False)` 라 backdrop/ESC/X 로 안 닫히고 "다음에 하기"/"완료" 로만 종료. app.py 는 실제 화면(보드 등)을 먼저 렌더한 뒤 모달을 그 위에 띄움. 각 단계 [이전]/[다음], 마지막 [완료], 어느 단계든 [다음에 하기].
- 단계 전환 시 위젯 unmount → state GC 함정 방지: `_onb_data` 안정 저장소에 매 전환마다 `_snapshot_inputs()` 로 보존, 위젯은 거기서 seed. 뒤로 가도 입력 유지.
- `persona/store.py` — `is_onboarding_dismissed` / `dismiss_onboarding` / `clear_onboarding_dismiss` (`data/persona/.onboarding_dismissed` 마커). "다음에 하기" 영구화 → 재접속 시 강제로 안 띄움. 완료 시 마커 제거.
- `app.py` — sidebar 후 화면 분기 전에 온보딩 게이트. `show_persona_editor` 중에는 미개입.
- v2 Azure 토큰 기반 중앙 카드 CSS (배지·진행 점·질문 헤더). 모든 인터랙션 pending flag + `st.rerun()` (on_click 0).
- `tests/test_onboarding.py` (+9) — should_show 4분기 · dismiss 마커 roundtrip · 완료 흐름(저장 확인) · skip(dismiss 영구화) · 뒤로가기 값 보존 · 편집 중 마법사 억제.
- `scripts/verify_browser.py` — Playwright + 사전설치 chromium(`/opt/pw-browsers`) 으로 6 화면 자동 캡처 헬퍼.

### Changed (v2 머지 준비 — persona_page 셸 통일 + 미배선 탭 정직화 + README)
- `ui/persona_page.py` — v2 글로벌 셸 적용. `render()` 가 `app_shell.render_topbar` + `render_app_side` + `render_setup_banner_if_needed` 로 감싸 다른 5 화면과 시각 통일. 폼 본문은 실 Streamlit 위젯(편집 입력 필요) 유지. `active_area=""` 로 5-nav 강조 없음. `_archive_stats()` 헬퍼 추가 (app-side 통계).
- `assets/v2/screens/data_management_main.html` — 미배선 탭 3개(키워드/내부 로드맵/출처 설정) `disabled` + title "B.5 PR", 카운트 "B.5 PR" 로 정직화. 활성 탭(수집잡·뉴스 라이브러리)만 클릭 가능.
- `assets/v2/screens/board_main.html` + `board.css` — 트렌드 "월별" 탭 + 탑스토리 "강한 매칭"/"출처별" 필터를 `db-tab-soon` (opacity 0.4 + line-through + cursor not-allowed) + title 로 정직화. 하드코딩 카운트("전체 32" 등) 제거.
- `README.md` — UI 설명을 v1 (`ui/<name>_tab.py`) → v2 셸 구조 (`ui/<name>_v2.py` + `assets/v2/screens/` 템플릿 + `?app_area&from=` 인계 패턴) 로 갱신.

### Added (v2 — archive "수정" → SOLA 인계 + SOLA 미배선 요소 정직화)
- `ui/archive_v2.py::_edit_handoff_href` — 칸반 1순위 카드 "수정" 버튼 (`<button disabled>` → `<a href="?app_area=🤖+SOLA+작업실&from=edit&bm_id=&title=">`). bm_id + title 을 stateless URL 로 SOLA 작업실에 인계.
- `ui/sola_workshop_v2.py` — `_HANDOFF_LABELS` 에 `edit` 추가, handoff banner + `_composer_prefill` 이 `?from=edit&title=` 처리 ("기존 제안서 '…' 를 이어서 수정… 검토하고 개선할 점 제안" prefill + 📦 기존 제안서 pin).
- `assets/v2/screens/sola_main.html` — 미배선 요소 정직화: "새 스레드" 버튼 `disabled` + title "B.4 PR", "스레드 검색" input `disabled` + placeholder "(B.4 PR)", thread list 상단에 노란 미리보기 노트 ("스레드 목록은 시안 미리보기 — 영구화·검색은 B.4 PR").
- `docs/INVARIANTS.md::I-16` — `edit` from kind + 1회-소비 액션 패턴 (`?action=` / `?refresh=now`) 문서화.
- `tests/test_v2_screens.py` (+2) — `_edit_handoff_href` URL 검증, `_composer_prefill` edit 케이스.

### Added (v2 — 중간 작업: archive 카드 액션 + 데이터 관리 refresh + 회귀 테스트)
- `ui/archive_v2.py::_archive_action_href`, `_consume_action_if_any` 신규 — 칸반 카드 위 "채택"/"기각"/"되돌리기" 버튼이 `<button disabled>` → `<a href="?action=adopt|reject|restore&bm_id=...">` 로 wire. `render()` 첫 단계에서 query 1회 소비 → `bookmarks_store.set_status` 호출 + 캐시 invalidate + query strip (재실행 방지). 채택/기각 컬럼 1순위 카드에도 "↶ 대기로 되돌리기" CTA 추가.
- `ui/data_management_v2.py::_refresh_cta_html`, `_consume_refresh_if_any`, `_render_refresh_toast_if_needed` 신규 — "지금 실행" 정적 버튼 → `<a href="?refresh=now">지금 새로고침</a>`. 클릭 시 모든 dm 캐시(`_dm_stats`/`_ingest_jobs_html`/`_hist_html`/`_news_cards_html`/`_archive_stats_dm`) invalidate + 녹색 inline toast "✓ 캐시를 새로 그렸어요 (실제 수집은 06:00 KST 스케줄러)". `body:has(.db-topbar)` scoped. 또한 `render_setup_banner_if_needed` 호출 누락 보완.
- `assets/v2/screens/data_management_main.html` — 정적 "지금 실행" 버튼 → `{{INGEST_REFRESH_CTA}}` placeholder, "스케줄" 버튼 `disabled` + title "다음 PR".
- `assets/v2/screens/archive.css`, `data_management.css` — `.oa-act{,-good,-warn}` / `.dm-btn-primary` 의 `<a>` 변형용 text-decoration · :visited 회복 (I-19 패턴 적용).
- `tests/test_v2_screens.py` (+6) — `_archive_action_href` URL 빌더, `_consume_action_if_any` happy/noop/unknown, `_consume_refresh_if_any` 캐시 clear + toast, board matrix 라벨 ellipsis, MATRIX_DEPT_COLORS 공유 dict 검증.

### Changed (v2 — 마무리: 차트 callout clamp · dept 색 공유 · v1 4모듈 -1366줄)
- `ui/insights_v2.py::_ia_chart_parts` — callout box 좌표를 viewBox 540×230 안으로 clamp: x = `max(0, min(cx - 39, 540 - 78))`, y = 점 위 우선 (`cy - 32`) 또는 점이 너무 높으면 점 아래 (`cy + 10`). 마지막 점이 우측 끝일 때 box 가 잘리던 회귀 해결.
- `ui/board_v2.py` + `ui/insights_v2.py` — 매트릭스 라벨 cap 14 → 12자 + ellipsis(`…`). `_IA_MATRIX_COLORS_BY_DEPT` 제거하고 `board_v2.MATRIX_DEPT_COLORS` / `MATRIX_DEPT_FALLBACK` 공유. 두 매트릭스의 dept 색상 단일 진실.
- `assets/v2/screens/board_main.html` — "음성으로 듣기 · 3:42" → "음성으로 듣기 · 준비 중" + `disabled` + title "TTS 미구현 — 다음 PR". 정적 가짜 시간 라벨 제거.
- `docs/INVARIANTS.md` — I-16 (handoff URL `?from=...` 단일 진입점), I-17 (sticky banner stacking 규칙), I-18 (MATRIX_DEPT_COLORS 공유), I-19 (`<a>` CTA CSS 회복 3-rule) 4건 추가.
- **v1 데드코드 1366줄 제거** — `ui/board_tab.py` (-645), `ui/home_tab.py` (-603), `ui/sola_tab.py` (-312), `ui/bookmarks_tab.py` (-206) + 대응 테스트 3개 (`test_board_flow.py`, `test_home_trend_widget.py`, `test_sola_workspace.py`) 제거. v2 에 동등 기능이 모두 있고 외부 참조 0건 확인. `data_health` 만 보존 (테스트 + 유틸로 미래 활용 가능).
- `app.py` — 4개 noqa 임포트 제거. 남은 v1 모듈은 `data_health` 1개.

### Added (v2 — A.7 후속 + A.4 ⌘K 모달 wire + CTA 스타일 회복)
- `ui/sola_workshop_v2.py::_composer_prefill()` 신규 — `?from=brief/opp/matrix/ia_map` 에 따라 textarea 자동 prefill + placeholder + pins 마크업 생성. brief 는 session_state 3건 제목, 나머지는 URL dept · lv3 로 작성된 한국어 초안 (제안서 / 비교 분석).
- `assets/v2/screens/sola_main.html` — composer 정적 `<textarea rows="1">` + 가짜 pins → `{{COMPOSER_PINS}}` / `{{COMPOSER_PLACEHOLDER}}` / `{{COMPOSER_PREFILL}}` 3 placeholder. rows=3 으로 prefill 표시 영역 확장.
- `ui/sola_workshop_v2.py::_render_brief_handoff_banner_if_needed` — sticky top 을 stacked 로 변경: 단독 시 76px, LLM banner 동시 노출 시 132px (`body:has(.app-llm-banner)` 분기).
- `app.py` — `app_shell.render_command_palette()` 호출 추가. v2 셸의 topbar 검색창 라벨이 모달을 토글. 5-nav + 페르소나 편집 6 row 노출, 각 row 는 `?app_area=` 링크.
- `assets/v2/shell.css` — `<a class="db-hdr-search">` 전환 후 새 자식 `db-hdr-search-ph` (placeholder text) + `db-hdr-search-kbd` (⌘K 키캡) 스타일 추가. text-decoration 제거.
- `assets/v2/screens/board.css` — `.db-prop-discuss` / `.db-mx-cta` / `.db-act` / `.db-act-primary` 의 `<a>` 변형용 `text-decoration: none` + `:visited` 색상 회복 (button → a 전환 시 시각 회귀 방어).
- `assets/v2/screens/insights.css` — `.ia-pc-detail` 동일 `<a>` 보강.
- `tests/test_v2_screens.py` — composer prefill 6 케이스 (default / opp / matrix / ia_map / brief with items / brief without items) + ⌘K 팔레트 렌더 검증 (5-nav + 페르소나 row + checkbox/backdrop/modal 마크업 존재). +7 tests.

### Added (v2 — A.7 확장: 4 CTA 모두 SOLA 작업실로 라우팅 통일)
- `ui/board_v2.py::_sola_handoff_href(from_kind, **payload)` 신규 헬퍼 — `?app_area=🤖+SOLA+작업실&from=<kind>&dept=X&lv3=Y` URL 빌더. payload 자동 quote, 빈값 생략. `_brief_html` 도 헬퍼 사용으로 통일.
- `ui/board_v2.py::_opp_card_html` — `<button class="db-prop-discuss" disabled>SOLA와 검토</button>` → `<a href="?...from=opp&dept=X&lv3=Y">SOLA와 검토 →</a>`. 카드 4개 모두 dept/lv3 인계.
- `ui/board_v2.py::_board_matrix_html` — detail aside `<button class="db-mx-cta" disabled>` → `<a href="?...from=matrix&dept=X&lv3=Y">`. 1위 cell 자동 인계.
- `ui/insights_v2.py::_ia_process_map_html` — 3 카드 `<button class="ia-pc-detail" disabled>상세 →</button>` → `<a href="?...from=ia_map&dept=X&lv3=Y">`. 각 cell 별 별도 인계.
- `ui/sola_workshop_v2.py::_render_brief_handoff_banner_if_needed` 일반화 — 4 from kind (brief/opp/matrix/ia_map) 모두 처리. brief 는 session_state 3건 제목, 나머지는 URL query 의 dept · lv3. `_HANDOFF_LABELS` 테이블로 라벨/sub 관리.
- `tests/test_v2_screens.py` — +4 tests (handoff URL 빌더, opp/matrix/ia_map CTA 검증). 총 13 v2 tests / 210 total.

### Added (v2 — A.7: 보드 ② SOLA 브리핑 → SOLA 작업실 라우팅)
- `assets/v2/screens/board_main.html` — "이 3건으로 제안서 만들기" `<button>` (정적) → `{{BRIEF_CTA}}` placeholder. `_brief_html()` 이 `<a href="?app_area=🤖+SOLA+작업실&from=brief">` 동적 생성. 빈 데이터 시 CTA 도 빈 문자열.
- `ui/board_v2.py::_brief_html` — items 를 `st.session_state["_board_brief_items"]` 에 저장(다음 area 에서 소비). 빈 데이터 시 키 삭제로 stale 인계 방지.
- `ui/sola_workshop_v2.py::_render_brief_handoff_banner_if_needed` 신규 — `?from=brief` 일 때만 sticky 파란 banner 렌더 ("📊 보드 브리핑에서 인계됨 — N건의 뉴스를 컨텍스트로 사용") + 3 제목 ol 노출. 실제 LLM 입력 와이어는 후속 PR.
- `ui/sola_workshop_v2.py::render` — `render_setup_banner_if_needed()` + `_render_brief_handoff_banner_if_needed()` 호출.
- `tests/test_v2_screens.py` — A.7 라우팅 테스트 1건 추가 (cta href / session_state 인계 검증).

### Added (v2 — 회귀 베이크 + v1 데드코드 925줄 제거)
- `tests/test_v2_screens.py` 신규 (+8 tests) — 보드/인사이트 9개 placeholder helper 의 ① 빈 데이터 friendly empty 검증 + ② 합성 데이터 시안 클래스 보존 검증 (`db-mx-bubble`, `ia-pcard-top`, `★ 최적 매칭`, callout pill `▲/▼` 등). Streamlit runtime 의존 없이 helper 단위 회귀 방어.
- `ui/ingest_tab.py` (-284), `ui/news_tab.py` (-121), `ui/proposal_workbench.py` (-364), `ui/roadmap_tab.py` (-156) 삭제 — 총 -925줄. 외부 참조 0건 (app.py 의 noqa 임포트 외) 확인 후 제거.
- `app.py` — 위 4 모듈의 `# noqa: F401` 임포트 제거. 남은 v1 모듈(board_tab/bookmarks_tab/data_health/home_tab/sola_tab)은 테스트가 직접 import 하므로 보존 + noqa 사유를 "테스트 의존" 으로 갱신.
- `sola/refine.py` — `build_refine_messages` docstring 의 stale `ui/proposal_workbench.py` 호출자 언급 제거.

### Added (v2 인사이트 — 트렌드 → 공정 매핑 3 카드 + LLM 미설정 전역 banner)
- `ui/insights_v2.py::_ia_process_map_html` (cached) — SECTION A 우측 `.ia-map` 빌더. from chip = top trending kw (`_weekly_keyword_series(5)` 1순위), 카드 3개 = `_score_cells.head(3)`. fit% = cell_score/max × 36 + 60 (60~96 범위), 현재 = sample_tasks 첫 항목 fallback, 신호 = sample_news 첫 헤드라인 fallback. 1위는 `ia-pcard-top` 강조 + ★ 최적 매칭 라벨. 상단 메타 = 매칭 개수 · 평균 적합도 · 매칭 뉴스 합.
- `assets/v2/screens/insights_main.html` — `.ia-map` 하드코딩 ~115줄 → `{{IA_PROCESS_MAP}}` placeholder.
- `ui/app_shell.py::render_setup_banner_if_needed` 신규 — `llm_ready()=False` 일 때 본문 상단 sticky 노란 banner ('LLM 미설정 · 백엔드 X · 키 없음 — 미리보기만'). 설정 시 no-op. `body:has(.db-topbar)` scoped CSS 라 v1 화면 영향 없음.
- `ui/board_v2.py` / `ui/insights_v2.py::render()` — `render_app_side()` 직후 `app_shell.render_setup_banner_if_needed()` 호출.

### Added (v2 인사이트 — 트렌드 차트 + 기회 매트릭스 실데이터)
- `ui/insights_v2.py::_ia_chart_parts` (cached) — 5주 × top-5 키워드 라인 차트. 보드의 `_weekly_keyword_series(5)` + `_delta_pct` 재사용. 1순위는 gradient fill + 큰 marker + callout box ('비전 검사 12건 · +162%'), 2-3순위는 컬러 라인 + 점, 4-5순위는 mute. Y label 동적 nice round, X label 'W−4..이번주', vertical highlight 마지막 컬럼. Legend / pill 동시 생성.
- `ui/insights_v2.py::_ia_matrix_svg` (cached) — 600×420 viewBox, score_cells head(8) → 좌상단 = PoC 후보 (쉽고 효과 큰). x = 40+(1−ease)·520 · y = 20+(1−effect)·360 · r = 14+score·22. dept 별 5색 팔레트 (도장/용접/의장/조립/절단), 1위 cell halo dasharray.
- `assets/v2/screens/insights_main.html` — 트렌드 차트 SVG(~75줄) → `{{IA_CHART_SVG}}` + `{{IA_CHART_LEGEND}}` + `{{IA_CHART_PILL}}` / 매트릭스 SVG(~115줄) → `{{IA_MATRIX_SVG}}` placeholder.
- 빈 상태: 두 차트 모두 안내 카드 (min-height 유지하여 레이아웃 흔들림 방지).

### Added (v2 보드 — ⑦ 내 키워드 관리 실데이터)
- `ui/board_v2.py::_board_kw_mgr_html(persona)` — Group 1 (SOLA 자동 추출 top-6) + Group 2 (페르소나 `interest_tasks` + `interest_lv3` 최대 4) 동적 chip 리스트. Group 1 tier dot 은 빈도 비율(0.5↑ good / 0.2↑ mid / 그 외 low). Group 2 hits 는 title/summary/keywords 등 30d 본문 substring count. Summary = 키워드 총 개수 + 30일 평균 일별 수집량 + 출처 수.
- `assets/v2/screens/board_main.html` — 키워드 관리 ⑦ 하드코딩 chip + summary(~85줄) → `{{BOARD_KW_MGR}}` placeholder.

### Added (v2 보드 — 기회 매트릭스 ROI×난이도 산점도 실데이터)
- `ui/board_v2.py::_board_matrix_html` 신규 — `sola.opportunity.score_cells` 상위 6개를 ROI(matched_news) × 난이도(matched_tasks) 평면에 매핑. top% = 90 − roi_norm·78, left% = 10 + ease_norm·80, 버블 크기 14~32px. 우상단 quadrant(쉬움+ROI높음) → `db-mx-strong` 토글, 좌하단 → `db-mx-soft`. detail panel 은 1위 cell (종합점수·매칭뉴스·매칭작업 + 1줄 why).
- `assets/v2/screens/board_main.html` — 매트릭스 섹션 ⑥ 의 하드코딩 버블 6개 + detail aside(~65줄) → `{{BOARD_MATRIX}}` placeholder.

### Added (v2 보드 — 트렌드 차트 + 키워드 리스트 실데이터)
- `ui/board_v2.py::_weekly_keyword_series`, `_board_trend`, `_board_trend_block_html` 신규 — `news_db.load_news_for_days(56)` → top-6 키워드 추출 → 8주차 버킷별 출현 빈도 집계 → SVG `<path>` 4 series + 6-row 키워드 리스트(스파크라인 포함) 동적 생성. Y-축 라벨은 데이터 max 의 1.25× 5단위 nice round, 어노테이션은 첫 1/3 vs 마지막 1/3 평균 변화율(`_delta_pct`) 최대값 키워드.
- `assets/v2/screens/board_main.html` — 트렌드 섹션 ⑤ 의 하드코딩 차트(SVG + 6 li, ~108줄)를 `{{BOARD_TREND}}` 단일 placeholder 로 치환.
- 빈 상태: 데이터 부족 시 "30일 이상 수집 후 표시" 안내 카드로 대체.

### Added (v2 디자인 시스템 — InsightBoard 핸드오프 Phase 0+1)
- `assets/v2/tokens.css`, `assets/v2/card.css`, `assets/v2/shell.css`, `assets/v2/streamlit-overrides.css` — Azure 라이트 테마 디자인 토큰 + 공유 컴포넌트(.app-side / .app-sola / .db-topbar) + Streamlit 크롬 무력화. 셸 활성 분기는 `body:has(.db-topbar)` 로 화면별 점진 마이그레이션.
- `static/fonts/PretendardVariable.woff2`, `static/fonts/JetBrainsMono.woff2` + `.streamlit/config.toml [server] enableStaticServing = true` — CDN 의존 제거, 사내망/오프라인 환경에서 폰트 깨짐 방지.
- `ui/app_shell.py` 신규 — 모든 v2 화면이 공유할 글로벌 크롬 3종 헬퍼: `render_topbar(page_title, eyebrow_current, refresh_label, fresh_kind)`, `render_app_side(active_area, persona, stats)`, `render_app_sola(context_label, quick_prompts, last_q, last_a_html, ...)`. 인터랙션은 후속 PR (disabled 상태로 시각만 완성).
- `ui/board_v2.py` + `assets/v2/screens/board_main.html`, `assets/v2/screens/board.css` — 오늘의 보드 v2 풀 셸 적용. 헤더·좌측 네비·우측 SOLA·7섹션(인사·SOLA 브리핑·탑 스토리·자동화 기회·트렌드·매트릭스·키워드) 마크업/스타일 완성. 페르소나 이름·갱신 시각만 동적 치환.
- `app.py` 의 `📊 오늘의 보드` 분기를 `home_tab.render()` → `board_v2.render()` 로 교체. `home_tab` 은 롤백용 보존(`# noqa: F401`).
- `ui/styles.py::inject_global_styles()` — v2 CSS 4개 파일을 `tokens → card → shell → streamlit-overrides` 순으로 로드 후 legacy `assets/styles.css` 를 마지막에 inject (v1 화면 호환 유지).
- `.streamlit/config.toml [theme]` — primaryColor/backgroundColor 를 v2 토큰(#2563EB / #F3F5F8 / #0F172A) 으로 맞춤.

### Added (LLM 미설정 — 입력 컨텍스트 미리보기)
- `sola/preview.py` 신규 — `format_messages_preview(messages, *, header, footer_hint)` 헬퍼. system/user/assistant 역할별로 코드블록(`text`)에 본문을 그대로 보존해 마크다운 렌더에 안전.
- `sola/summarize.py::summarize_news`, `sola/propose.py::propose_for_task`, `sola/insight.py::insight_for_dept` — LLM 미설정 시 빈 에러 메시지 대신 호출에 사용될 입력 messages 를 그대로 노출. 캐시에 미리보기는 저장하지 않음 (키 세팅 후 재호출하면 실제 응답으로 대체).
- `ui/layout.py::render_chat_panel`, `ui/proposal_workbench.py::_do_discuss`, `::_do_refine` — 채팅·작업장에서도 동일 패턴. 특히 `_do_refine` 은 좌측 본문을 덮어쓰지 않고 채팅에 미리보기만 노출 (`refine.build_refine_messages` 로 동일 컨텍스트 재사용).
- 회귀 가드 8건 — `tests/test_preview.py`: 역할별 출력, custom header, summarize/propose/insight 미리보기, 캐시 미오염, refine 좌측 본문 보호, build_refine_messages 동등성.

### Fixed (scraping/enrich — `_strip_noise` AttributeError + 단일 페이지 실패 흡수)
- `scraping/enrich.py::_strip_noise` 의 `tag.get("style", "")` 가 bs4 4.14+/py3.14 (Streamlit Cloud) 일부 환경에서 `AttributeError` 를 던지는 회귀 수정 — `getattr(tag, "attrs", None)` + `isinstance(dict)` 가드로 비-Tag 노드를 안전하게 스킵.
- `fetch_article` 의 HTML 파싱 블록을 `try/except` 로 감싸 단일 페이지의 파싱 예외가 수집 batch 전체를 중단시키지 않도록 안전망 추가 (실패 시 `{"content": "", "image_url": ""}` 반환).
- 회귀 가드 3건 — `tests/test_enrich.py`: `_strip_noise` 가 `attrs=None` Tag 를 건너뛰며 살아남는지, `fetch_article` 가 파싱 예외 시 빈 dict 를 반환하는지, `enrich_articles` 가 일부 기사 실패에도 나머지를 처리하는지.

### Added (Streamlit Cloud — Secrets fallback + 배포 가이드)
- `config.py` 에 `_env_or_secret(name, default)` 헬퍼 추가 — 환경변수 우선, 없으면 `st.secrets` fallback. `llm_backend()` / `llm_base_url()` / `llm_api_key()` / `llm_model()` 모두 적용. Streamlit Community Cloud(`share.streamlit.io`) 배포 시 App settings → Secrets 의 TOML 값을 자동 인식.
- `README.md` 에 "☁️ Streamlit Community Cloud 배포" 섹션 추가 — 키 발급 → Secrets TOML 입력 → Deploy 3-step. 이미 `.env` 가 history 에 있을 때 키 revoke + filter-repo 안내.
- `.env` 가 main 에 잘못 커밋된 상태(commit `6998c86`) tracking 제거. 로컬 파일은 유지, `.gitignore` 의 `.env` 규칙은 이미 적용됨.
- 회귀 가드 6건 — `tests/test_config_secrets.py`: env 우선, secrets fallback, 둘 다 비었을 때, Groq 디폴트, streamlit 미설치/secrets 속성 미존재 시 fallback 안전성.

### Changed (UX — 채팅 패널 기본 펼침)
- `ui/layout.py::main_and_chat` 에 `default_open=True` 인자 추가 — 첫 진입에서 우측 사이드 채팅 패널이 펼쳐진 상태로 시작. 사용자가 헤더 토글로 닫으면 `_chat_open_{key}` session_state 가 저장되어 다음 진입에서도 그 선호 보존.
- `ui/styles.py::page_header` 의 토글 디폴트도 `True` 로 정렬해 라벨이 첫 진입부터 "💬 채팅 닫기" 로 표시.
- 모든 main_and_chat 호출 탭(home/board/news/ingest/roadmap/bookmarks/sola)이 자동으로 펼친 상태로 시작.
- 회귀 가드: `tests/test_chat_log.py::test_main_and_chat_defaults_to_open` — `inspect.signature` 로 `default_open=True` 잠금.

### Changed (UX Phase 5 — 제안서 워크벤치 모드 배너 + 버튼 카피 통일)
- `ui/proposal_workbench.py` 의 "💬 대화" / "✏️ 수정" 라디오 아래에 모드 시각 배너 추가 — 대화 모드는 파란 톤(컨텍스트로만 사용), 수정 모드는 앰버 톤(좌측 본문이 LLM 으로 교체됨)으로 즉시 인식 가능.
- 버튼 카피 명확화: "★ 북마크 저장" → "📌 새 버전으로 저장" (새 북마크 추가), "💾 원본 업데이트" → "💾 원본 덮어쓰기" (선택된 원본 in-place 교체). 모든 버튼에 `help` 보강.
- `assets/styles.css` 에 `.wb-mode-banner`, `.wb-mode-talk`, `.wb-mode-edit` 추가.

### Added (chat_log — 사이드 채팅 영구화 + chat_key 분리)
- `store/chat_log.py` 를 `chat_key` 별 파일 분리 지원으로 확장. 기존 인자 없는 호출은 `chat_key="default"` 로 매핑되어 `data/sola/chat_history.jsonl` 경로 유지 (후방 호환). 그 외 키는 `data/sola/chat/{slug}.jsonl` 에 저장, 파일명은 안전한 슬러그로 정규화 (디렉토리 traversal 차단).
- `ui/layout.py::render_chat_panel` 에 `persist=True` 옵션(디폴트) 추가 — 첫 진입 시 `chat_log.load_history(chat_key)` 로 복원, 사용자 입력/응답 시 `chat_log.save_history(history, chat_key)` 로 영구화, "초기화" 클릭 시 `chat_log.reset(chat_key)`. SOLA 사이드 채팅이 새로고침 후에도 보존됨.
- 회귀 가드 4건: `tests/test_chat_log.py` — 기본 키 후방 호환, chat_key 격리, reset 범위, 슬러그 검증.

### Changed (UX Phase 4 — SOLA 채팅 UI 단일화)
- `ui/sola_tab.py` 의 메인 영역 채팅 모드(`_render_chat`)와 `_build_proposal_context()` 헬퍼 제거 — `render_chat_panel` 이 이미 `include_session_proposal=True`, `include_adopted=True` 로 동일 컨텍스트를 자동 첨부.
- SOLA 작업실에 `main_and_chat("sola", ...)` 추가 — 우측 사이드 채팅 패널이 다른 탭과 동일 패턴으로 표시. `chat_toggle_key="sola"` 로 헤더 토글 노출.
- `sola_mode` 라디오에서 "채팅" 옵션 제거. 작업실은 [뉴스 요약, 자동화 과제 제안서] 2개 모드로 좁힘. `board_tab` 의 SOLA 라우팅(`prop_dept`, `prop_lv3`) 영향 없음.
- `_build_page_context()` 신규 — 현재 모드/필터/데이터 카운트를 사이드 패널 컨텍스트로 압축.
- 미사용 import 정리 (`chat_ctx`, `chat_log`, `persona_ctx`, `SYSTEM_CHAT`, `chat`).
- 회귀 가드 2건 — `tests/test_sola_workspace.py::test_build_page_context_summarizes_mode_and_counts`, `::test_sola_tab_no_longer_exposes_main_chat_helpers`.

### Added (LLM 빠른 시작 — Groq 키 발급 CTA)
- `README.md` 상단에 "🚀 빠른 시작 (Groq 무료 API)" 섹션 추가 — 키 발급 링크 + 3단계 설치 흐름. 기본 LLM 백엔드(`config.py` 디폴트 `groq` / `llama-3.3-70b-versatile`)를 즉시 사용 가능하도록 안내.
- `ui/sidebar.py` 푸터의 LLM 상태 카드가 미설정 시 안내 카드로 확장 — 🔑 [Groq 키 발급](https://console.groq.com/keys) 외부 링크 + `.env` `LLM_API_KEY=gsk_…` 한 줄 안내. `_llm_footer_html()` 헬퍼로 분리해 단위 테스트 가능.
- `assets/styles.css` 에 `.sidebar-footer-empty`, `.sidebar-llm-empty-hint` 스타일 추가 (앰버 톤 안내 카드).
- 회귀 가드 2건 — `tests/test_sidebar_profile.py` 에서 ready/empty 두 상태의 푸터 HTML 검증.

### Changed (UX Phase 3 — IA 정리 + 인사이트 탭화 + 부서 인사이트 자동 표시)
- `app.py` 메뉴 재구성: `news_tab` 을 산출물 보관함 → 데이터 관리로 이동. 데이터 관리는 `[1. 뉴스 수집, 2. 뉴스 둘러보기, 3. 로드맵 업로드]` 3-탭, 산출물 보관함은 단일 페이지 (북마크만).
- `ui/sidebar.py` `_AREA_DESCRIPTIONS` 업데이트 — "수집 · 본문 확보" → "수집 · 둘러보기 · 로드맵", "북마크 · 재사용" → "북마크 · 채택".
- `ui/board_tab.py` 인사이트 분석 페이지를 `st.tabs(["📈 트렌드", "⚙️ 자동화 기회", "🤖 부서 인사이트", "🔗 계층 매칭"])` 로 분할 — 6섹션 스크롤 피로 해소. 메트릭/흐름 가이드는 탭 위에 그대로.
- `_render_dept_insights` 자동 표시로 전환 — 수동 "AI 인사이트 생성·갱신" 버튼 제거. LLM 미설정 시 status_card 안내. "🔄 다시 생성" 버튼은 캐시 무시 강제 갱신용으로 분리. 부서별 `st.spinner` 로 진행 표시.

### Changed (UX Phase 2 — 온보딩 + 페르소나 로드맵 의존성 해결)
- `ui/home_tab.py` 에 `_onboarding_steps_html()` 추가 — 페르소나·로드맵·뉴스 중 하나라도 비어있으면 홈 상단에 3단계 시작 가이드(step_guide)가 자동 표시되고 각 단계가 완료되면 active(녹색) 토글. `_persona_welcome` 의 미설정 카피를 "처음 시작하시나요?" 환영 카드로 강화.
- `ui/persona_page.py` 가 로드맵이 비어있을 때 selectbox 대신 `text_input` 으로 자동 fallback (부서·팀). 관심 공정도 옵션이 없을 때 안내 caption + 기존 값 유지. 상단에는 "로드맵 업로드 시 드롭다운으로 바뀝니다" 안내.
- `ui/sidebar.py` 의 프로필 카드가 페르소나 미설정 시 `persona-profile-card-empty` 클래스 적용 + hint 문구 "👋 클릭해서 프로필 설정 시작" 로 강화. `assets/styles.css` 에 점선 테두리 + 펄스 애니메이션 추가.
- 회귀 가드: `tests/test_home_trend_widget.py::test_onboarding_steps_marks_active_per_state` — 3가지 상태에서 step_item active 카운트가 0/1/3 으로 토글되는지 검증.

### Changed (UX Phase 1 — Next-Best-Action 카피 통일)
- 빈 상태 안내(`status_card`)를 "다음 → [메뉴] → [액션]" 패턴으로 통일 — `home_tab` (자동화 기회 / 데이터 부족), `board_tab` (기회 / 필터 / 매칭 / 데이터 부족 4곳), `news_tab`, `bookmarks_tab`, `sola_tab` (실행 전 준비), `ingest_tab` (수집 전).
- 사용자 시각 라벨로 카피 정리: `ui/ingest_tab.py` 페이지 제목 "뉴스 수집 + 본문 Enrich" → "뉴스 수집" (서브타이틀에 "본문·이미지 자동 fetch" 명시), 버튼 "✨ 본문 Enrich (LLM 키워드/요약)" → "✨ LLM 키워드·요약 추가", `step_item` 3단계 라벨 "본문 Enrich" → "LLM 키워드·요약 (선택)", 슬라이더/체크박스에 `help` 추가.
- `ui/persona_page.py` 의 "관심 공정(Lv3)" → "관심 공정", help 보강 (로드맵 Lv3 기반임을 안내).
- `ui/board_tab.py` 자동화 기회 섹션 caption 에 score 의미 설명 추가, "상위 셀 개수" 슬라이더 / "LLM 코멘트" 체크박스에 `help` 추가.

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

### Added (글로벌 SOLA 채팅 + 화면별 안내 + SOLA workshop 좌측 fix)
- **모든 화면 본문 하단에 SOLA 채팅 패널** — `ui/chat_panel.py` 신규. 활성 thread 의 최근 6개 메시지(역할별 버블) + Streamlit `st.chat_input`(화면 하단 자동 고정). 빈 thread 진입 시 area 별 **안내 카드**(headline + 추천 질문 5건 chip). SOLA workshop area 는 자체 풀스크린 채팅이라 미렌더.
- LLM 호출 인프라는 `sola_workshop_v2` 의 `_consume_send_if_any` / `_build_llm_messages` / `_load_messages` 그대로 재사용 — chat_panel 입력→pending flag→다음 run 에서 LLM 호출+영구화→rerun (단일 thread/chat_key 공유).
- **`ui/persona_page.py::chat_context_block`** 신규 — 페르소나 편집 화면의 채워진/비어있는 필드 + 관심 공정/작업을 LLM 컨텍스트로 packaging. 페르소나 설정 중에도 SOLA 가 "내 부서에 맞는 관심 공정 추천해줘" 같은 질문에 답 가능.
- **`app.py`** — 페르소나 페이지 분기에 `_chat_context_for_sola` set 추가, 모든 area render 후 `chat_panel.render(persona, area_key)` 호출 (SOLA workshop 제외). `consume_send_if_any` 를 화면 분기 전 최상단에서 호출 → 어느 area 에서든 송신 처리.
- **SOLA workshop 좌측 fix** — `app_shell.render_app_side()` 호출 제거. 좌측에 글로벌 `.app-side` (280px) + ws-threads (256px) 두 패널이 겹쳐 보이던 문제 해결. `assets/v2/streamlit-overrides.css` 에 `body:has(.ws-shell)` 분기 추가하여 block-container 의 padding-left 도 16px 로 축소. 다른 area 이동은 topbar / ⌘K 팔레트로.
- **6 area 안내 정의** (`_AREA_INTROS`): 보드 / 데이터 관리 / 인사이트 분석 / SOLA 작업실 / 산출물 보관함 / 프로필 설정. 각 area 마다 headline + 추천 질문 3~5건 (XSS 방어 위해 모두 `html.escape`).
- 보안 — `st.markdown(unsafe_allow_html=True)` 대신 `st.html` 사용 (CLAUDE.md §5, I-19, test_html_rendering 통과). 검색어 / area_key / 메시지 본문 / 페르소나 데이터 모두 escape.
- `tests/test_chat_panel.py` (+10) — intro 카드 헤드라인·chip·XSS · 모든 area 정의 검증 · 메시지 렌더 cap·escape·역할 스타일 · `consume_send_if_any` 위임 · SOLA workshop area skip.
- `tests/test_chat_context_blocks.py` (+2) — persona_page chat_context (채워진/빈 필드, 관심 공정·작업).


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
