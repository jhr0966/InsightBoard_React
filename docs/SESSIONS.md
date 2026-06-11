# SESSIONS — 작업 세션 로그

> **최신 세션이 상단.** 다음 세션은 상단 1개만 읽고 복원한다.
> 완료된 세션은 "✅ merged"로 닫는다.

---

## 2026-06-11 — feat: 페르소나 개편 — 관심 키워드 · SOLA 관심사 분석 · 온보딩/설정 정돈 (`feat-persona-overhaul`)

**무엇을**: 페르소나 5종 개편 — ① 입력 항목 검토(유지 + interest_keywords 보강, 직급/연차는 매칭 신호 아님·미추가) ② 자유 입력 관심 키워드 → 수집·보드 합류 ③ LLM 관심사 추출 + 작업정의 매칭(`persona/derive.py`) ④ 온보딩 모달 세로 중앙 + 단계 정돈 ⑤ 설정 페이지에서 표시 설정 분리·카드 재구성.

**어떻게**:
1. `persona/schema.py`: `interest_keywords` + derived 4필드(`derived_interests`/`matched_processes`/`derived_at`/`derived_source`) + `parse_keywords_input`(쉼표/엔터, 중복 제거, max20). `from_dict` 하위호환.
2. `persona/derive.py`(신규): LLM(`sola.client` 경유, `SYSTEM_PERSONA_INTERESTS`) 추출 → `store/cache` 캐시 → 실패 시 입력 토큰 폴백 → `task_defs_db.list_all` 토큰 매칭(공정별 점수·추천 작업) → persona 저장. 온보딩 완료/프로필 저장/[다시 분석] 에서 호출.
3. 수집 반영: `board_v2._collect_keywords_for_persona`/`del_user`/⑦칩, `data_management_v2._dm_kw_body_html` 에 interest_keywords 합류.
4. 온보딩: step4 = 관심 공정+키워드, 입력 단계 중복 skip 버튼 제거. **중앙 정렬 근본 원인** — 1.58 DialogContainer(자식 div)가 `alignItems:start` → `streamlit-overrides.css` 에 `[data-testid="stDialog"] > div { align-items:center }` 추가.
5. `ui/persona_page.py`: 기본 정보/관심사/SOLA 분석 카드 3섹션 + 표시 설정 expander 분리. 저장 시 muted/derived 보존(기존 muted 유실 결함 수정) + derive 자동 실행. 분석 카드 전 문자열 escape, 재분석은 pending+rerun.
6. 테스트: `test_persona_derive.py` 신규 11 + persona/kw_actions/onboarding 갱신(+8). 온보딩 fixture 가 `derive._call_llm` 차단 — 테스트 중 실 LLM/네트워크 0. pytest **918 passed** · 금지패턴 0.
7. 브라우저 실측: 중앙 모달 `/tmp/persona-onboarding.png` · 설정 페이지 `/tmp/persona-page.png` · 분석 카드(규칙 폴백 라벨) `/tmp/persona-derived.png`.

**상태**: 🔄 push — PR 은 오케스트레이터가 생성.

---

## 2026-06-10 — feat: 수집 현황 모달 ↔ 런 이력 연동 — 마지막 수집 결과 재열람 (`feat-collect-history-link`)

**무엇을**: 수집 현황 모달의 결과를 ⚙ 수집 설정의 런 이력과 연동 — [📡 마지막 수집 결과 보기] / 런별 [보기] 로 과거 수집 결과를 모달로 재열람(재수집 없음).

**어떻게** (`ui/data_management_v2.py`):
1. `_run_log_to_modal_result`: run_log 엔트리 → 모달 결과 dict 단일 변환 헬퍼(순수). 필드 누락 방어(ok 유추, 키워드 합집합, feeds 근사, errors dict/str 수용), `from_log=True` 마커.
2. `_render_run_history_view_buttons`(설정 서브뷰 이력 아래): [📡 마지막 수집 결과 보기] + 최근 5런 행별 [보기]. 클릭 → `_open_run_result_modal` 이 `_sc_collect_modal_result` 주입 + `_sc_collect_modal_pending` + rerun → 기존 '결과 존재 시 collect 스킵' 가드로 모달이 요약만 표시.
3. `_run_collect_for_modal`: `record_run(..., duration_s=실측)` 보강(스키마 내 필드).
3-1. 소스별 건수 표: `_collect_source_rows` 헬퍼 + 결과 요약 KPI 아래 소스별 표(0건/오류 소스 포함, escape) — 라이브/런 로그 결과 dict 모두 `sources` 포함, CSS `.sc-cm-srcs` 추가. 테스트 +3, pytest 901 passed.
4. 테스트 +6(test_collect_trigger.py — 변환 정상/오류/누락, 플래그 세팅, 재수집 금지 단언, 런 없음 noop). pytest **898 passed** · 금지패턴 0.
5. 브라우저 실측: ⚙ 수집 설정 → 보기 버튼 → 모달 결과 요약(지난 런 22:47 표시, collect 미실행). `/tmp/collect-history.png`.

**상태**: 🔄 push — PR 은 오케스트레이터가 생성.

---

## 2026-06-10 — feat: 수집 현황 모달 — [🔄 지금 뉴스 수집] 진행/결과 (`feat-collect-progress-modal`)

**무엇을**: [지금 뉴스 수집] 클릭 시 화면 중앙에 **수집 현황 모달**(st.dialog) 을 띄워 진행 상황(st.status+st.progress, `collect_batch(on_step=)` 콜백)과 결과 요약(KPI 4 + 오류 목록)을 보여준다. 기존 `_consume_refresh_if_any` 의 render-도중 동기 수집 + 토스트 경로를 대체.

**어떻게** (`ui/data_management_v2.py`):
1. 버튼(액션바/설정) → `_sc_collect_modal_pending=True` + `st.rerun()`. `_consume_refresh_if_any` 는 `?refresh=now`/구 `_do_dm_collect` 를 모달 플래그로 **번역만**(딥링크 호환).
2. `_render_collect_modal_if_open`(dismissible=False, 기사 모달과 동일 패턴) → `_collect_modal_body`: 결과 없으면 1회 수집(`_run_collect_for_modal` — collect_batch + run_log(trigger="manual") + 캐시 무효화 finally), 결과는 `_sc_collect_modal_result` 세션 유지(재수집 가드). [✕ 닫기]가 플래그·결과 정리 + rerun.
3. 결과 요약 HTML(`_collect_result_summary_html`) 전부 escape. 수집 모달 pending 중 기사 모달 스킵(dialog 1개/run). CSS `.sc-collect-modal` 추가.
4. 테스트: test_collect_trigger.py 재작성(16) + test_v2_screens/test_custom_rss_scrape 갱신. pytest **892 passed** · 금지패턴 0.
5. 브라우저 실측: 수집 클릭 → 모달 진행 → (망 차단이라) 오류 요약 표시 → 닫기 정상. `/tmp/collect-modal.png`.

**상태**: 🔄 push — PR 은 오케스트레이터가 생성.

---

## 2026-06-10 — refactor: 시스템 점검 1차 — 부분 갱신(fragment) + 성능 (`refactor-partial-updates`)

**무엇을**: 전체 점검("클릭 시 전체 새로고침 제거 + 느린 부분 발굴") — 에이전트 감사 2건(데이터/캐시, reload 앵커 전수) + 벤치마크로 진단 후 단계 커밋 3개.

**어떻게**:
1. `store/news_db.py`: 일자별 parquet 메모 — 윈도우(3/14/30/56일) 섞어 불러도 날짜당 디스크 1회. (보드형 패턴 9×→1× 스캔)
2. 자산/헬퍼 캐시: `components.read_asset_text`(CSS 6종+템플릿 4종 매 rerun 재읽기 제거), `_board_kw_mgr_html`·`_notif_count`·`_chat_context_collect_cached` ttl=60.
3. `data_management_v2._render_browse_zone(@st.fragment)`: 탭/칩/모드/카드/모달이 구역만 부분 rerun — 브라우저 실측으로 dialog-in-fragment 확인.
4. e2e S8(부분 갱신 시나리오) + 일자 메모 회귀 테스트.
5-2. (병렬 에이전트 3건) 보드 기회/키워드 액션 버튼화(템플릿 3분할), 작업정의 td_* 위젯 내비(_consume_td_nav_pending — 딥링크 호환), 우측 채팅 패널 @st.fragment(SOLA 외 화면 부분 rerun, 작업실은 scope='app' 유지). 전체 864 passed.
5. 채팅 빠른 작업 칩(`?sola_action=` 앵커) → `st.button`+pending 전환(reload 제거, 딥링크 호환 유지) — 브라우저 칩 렌더 확인. 잔여 앵커 전환은 REFACTOR_PLAN **Phase 4** 로 우선순위화(보드 kw/opp P1, taskdef td_* P1, 채팅 칩·스레드 P2, SVG 히트맵 P3).
6. 작업 정의 td_* 앵커 스위트(P1) → 위젯 전환(`task_def_manage.py`): 목록 카드=투명 오버레이 버튼, 상세 액션/추가/폼 취소·저장=`st.button`+`_td_nav_pending`, `_consume_td_nav_pending` 이 위젯 전에 query 로 번역(td_* 전체 교체 — 딥링크 호환, 스테일 td_edit 잔류 결함도 해소). 삭제는 2-step confirm. AppTest e2e 3종(pending→상세, 오버레이 버튼 렌더, 카드 클릭→상세) 추가, taskdef CSS zone 추가. pytest 대상 5파일 104 passed.

**측정**: 보드 콜드 4.13s→1.74s(-58%), 워밍 0.04~0.10s. pytest 832 passed · 금지패턴 0.

**상태**: 🔄 진행 — 푸시·PR 예정.

---

## 2026-06-10 — fix: thebell 본문·사진 — 실마크업 기반 정밀 수정 (`fix-thebell-extract`)

**무엇을**: thebell 여전히 본문·사진 미수집. 사용자가 실페이지 HTML 제공 → 정확 진단 가능해짐.

**어떻게**: ① 본문이 `div#article_main` 에 `<br>` 구분 텍스트 → `_CONTENT_SELECTORS` 에 `div#article_main`/`div.viewSection` 추가. ② 기사 사진보다 앞에 있는 `google_icon.png`/광고 배너가 대표 이미지로 오선택되는 구조 → junk 조각(`_icon.`·`/banner/`·`share_` 등) + 본문 컨테이너 스코프 img 셀렉터 우선. ③ 노이즈(`.optionIcon`·`.googleSearch`·광고 박스)와 보일러플레이트('무료로 공개된'·'책갈피/프린트/작게/크게') 차단.

**검증**: pytest 830 passed(신규 2 — 실마크업 fixture) · 금지패턴 0. fetch 403 여부는 배포 환경 diagnose_article.py 로 확인 필요(파싱은 이제 보장).

**상태**: 🔄 진행 — 커밋·푸시·PR 예정.

---

## 2026-06-10 — fix: 조선닷컴 본문 미수집 — SPA 구조화 데이터 추출 (`fix-spa-article-body`, PR #144 ✅ merged)

**무엇을**: 구글 수집된 조선닷컴 기사 2건이 사진·제목만 되고 본문이 빔.

**어떻게**: 조선닷컴=Arc Publishing SPA(본문이 DOM 아닌 JSON). `scraping/enrich.py` 에 `_ldjson_article_body`(NewsArticle articleBody, @graph 지원) + `_arc_fusion_body`(Fusion.globalContent content_elements 문단 복원) 신설 → `fetch_article` 이 script 제거 전에 확보, DOM 셀렉터 본문보다 길 때만 채택(서버렌더 사이트 보호). `diagnose_article.py` 에 구조화 데이터 길이 리포트 추가.

**검증**: pytest 828 passed(신규 3) · 금지패턴 0. ⚠ 라이브는 배포 환경에서 재수집/진단 필요.

**상태**: 🔄 진행 — 커밋·푸시·PR 예정.

---

## 2026-06-09 — fix: 카드 제목 반복·thebell TLS 차단·slist 이미지 (`fix-collect-body-echo-images`, PR #143 ✅ merged)

**무엇을**: ① 카드 본문 자리에 제목 반복(구글) ② 뉴스 수집 화면 전반 점검 ③ thebell 여전히 미수집 ④ slist 사진만 미수집.

**어떻게**:
- 제목 반복: `google.py` `_summary_echoes_title`(description=제목뿐이면 summary 비움) + `data_management_v2.py` `_news_body_src`(카드·표·모달 공용 — 제목 라인 제거·에코 스킵 후 폴백). 모달 단락도 제목 라인 스킵.
- 화면 점검: 분류·칩·검색·표 선택 가드 정상. 추가 발견 — http:// 이미지 혼합콘텐츠 → `_https_img` 승격(카드/표/모달).
- thebell: TLS 지문(JA3) 차단으로 판단 → `http.fetch_impersonated`(curl_cffi Chrome 위장, 선택 의존성) + enrich 최후 폴백. requirements 에 curl_cffi. **배포에서 pip install 재실행 + `scripts/diagnose_article.py` 로 확인 필요.**
- slist: Froala lazy 속성(`data-fr-src` 등) 추가 + 진단 스크립트 신설.

**검증**: pytest 825 passed(신규 8) · 금지패턴 0 · 카드/모달 스크린샷 확인. ⚠ thebell·slist 라이브는 망 차단으로 미검증(진단 스크립트 제공).

**상태**: 🔄 진행 — 커밋·푸시·PR 예정.

---

## 2026-06-09 — fix: thebell 미수집·구글 본문 노이즈·모달 버튼 배치 (`claude/dev-setup-testing-i4f082`, PR #142 ✅ merged)

**무엇을**: ① thebell.co.kr 만 본문·사진 미수집 ② 구글 뉴스 본문에 제목 반복 + UI 버튼 텍스트 혼입 ③ 기사 모달의 원본/닫기 버튼 병렬 배치 요청.

**어떻게**:
- `scraping/enrich.py`: ① thebell 류 WAF 403 → `_get_article_response` 신설(차단 응답 시 홈 워밍업 쿠키 + sec-fetch 헤더·네이버 referer 1회 재시도). ② `_BOILERPLATE_PATTERNS` 확장(폰트/공유/번역 버튼·섹션명·날짜 단독 라인) + `_strip_title_echo`(본문 내 제목 반복 라인 제거, enrich_one 적용).
- `ui/data_management_v2.py` + `data_management.css`: 모달 하단을 `st.columns(2)` 액션 행으로 — 원본 링크(`sc-modal-link--row` 전폭) ∥ ✕ 닫기. 브라우저 스크린샷 검증 완료.

**검증**: pytest 817 passed(신규 6) · 금지패턴 0 · 모달 시각검증 OK. ⚠ thebell 라이브는 샌드박스 망 차단으로 미검증(배포 환경 재수집 필요).

**상태**: 🔄 진행 — PR #142 에 추가 커밋.

---

## 2026-06-09 — chore: 개발 자체검증 세팅 — 브라우저 + 웹크롤링 (`claude/dev-setup-testing-i4f082`)

**무엇을**: 개발 준비 요청("브라우저 띄워 자체검증 + 웹크롤링 자체 테스트 세팅"). 의존성 설치·pytest 811 통과 확인 후, 환경 제약 2가지를 해결 — ① `verify_browser.py` 가 구버전 영역명(`🧱 데이터 관리`)을 쓰고 온보딩 모달이 모든 캡처를 가림, ② 외부망이 allowlist 차단이라 실 사이트 크롤링 테스트 불가.

**어떻게**:
- `scripts/verify_browser.py`: 영역명 현행화(뉴스 수집·작업 정의 → 7장), `_dismiss_onboarding`(화면마다 '다음에 하기' 클릭), chromium 경로 glob 폴백.
- `scripts/verify_scrape.py` 신설: 로컬 fixture HTTP 서버(RSS·사이트·기사·네이버 마크업) + 실 모듈 경로(rss/tech_sites/enrich/naver 셀렉터) 스모크 4종, `--live` 로 실 외부 소스 시도.
- `Makefile`: `verify-browser`/`verify-scrape` 타깃, `test` 를 `python -m pytest` 로(uv 격리 pytest 회피).

**검증**: pytest 811 passed · verify_scrape 4/4 · verify_browser 7/7(온보딩 미노출 스크린샷 확인) · 금지패턴 0. 참고: 이 샌드박스에서 외부 크롤링은 `Host not in allowlist` 로 차단 — live 검증은 배포/로컬 환경에서.

**상태**: 🔄 진행 — 커밋·푸시·PR 예정.

---

## 2026-06-09 — refactor: 뉴스 수집 #133 재설계 잔재 일괄 제거 + 세션 정리 (`claude/kind-volta-IWxix`)

**무엇을**: #133~#140 으로 뉴스 수집을 **카드 브라우저 + 기사 모달 + ⚙ 설정 서브뷰**로 재설계한 뒤, 옛 필터 폼·3탭/그룹 라우팅·옛 카드 빌더를 호환/테스트용으로 남겨뒀던 것을 적극 제거(요청: "코드 최적화 — 레거시 제거"). 데이터 관리 화면 템플릿도 헤더(KPI 4)만으로 축소.

**어떻게**:
- `data_management_v2.py` −387 / `data_management_render.py` −223 / `data_management_main.html` −211: 미호출 레거시(`_render_news_filter_form`/`_render_jobs_split`/`_render_dm_tabs`/`_render_dm_tab_panel`/`_news_cards_html`/`_filter_news_by_query`/`_news_source_options`/`_strip_dm_mockups`/`_dm_tab_href`/`_dm_tabs_html`/`_dm_group_*`/`_dm_resolve_group_and_tab`/`_src_action_href` + 상수)를 일괄 삭제. render.py 는 출처색 그라데이션 + 기사 나이 라벨 헬퍼만 잔존.
- **버그 동반 수정**: 템플릿 주석에 `{{DM_TABS}}` 토큰이 그대로 있어 `_render_dm_header` 의 split 이 **헤더 KPI 를 첫 occurrence(주석)에서 잘라먹던** 회귀 → 주석 문구 교체로 해소.
- 테스트: `test_dm_area_groups.py` 삭제, `test_dm_cleanup`/`test_dm_news_filter` 재작성, 7개 파일에서 제거 심볼 참조 테스트 삭제/대체. 검색 필터 회귀는 `test_collect_browser.py` 가 커버.

**검증**: pytest **811 passed** · 금지패턴 0 · 순변경 13파일 **−1193줄**.

**상태**: 🔄 진행 — 커밋·푸시·PR·머지 예정.

---

## 2026-06-09 — fix: 본문에 포털 UI 텍스트 섞임 + AI Times 연재/목록 페이지 수집 (`claude/kind-volta-IWxix`)

**무엇을**: 구글 이미지는 batchexecute 로 정상화됨(✓). 남은 2건 — ① 다음/네이버 본문에 제목·TTS·글자크기·번역·관련기사·저작권 chrome 이 다 섞임, ② AI Times '연재/섹션 목록 페이지'(조금원의 디지털 세상 이야기 등)가 기사로 수집돼 동일 기본 이미지(VENDOR LOCK IN) 반복.

**어떻게**:
- ①: `enrich.fetch_article` 를 '최대 텍스트 블록' → **본문 셀렉터 우선(최장 셀렉터 매칭)** 으로 복원(없을 때만 문단/최대블록 폴백). 포털 chrome 노이즈 셀렉터(`.tts_area`/`[class*='relate']`/`[class*='copyright']`/`.foot_view`)+보일러플레이트(음성재생·글자크기·번역·무단전재·언론사 이동) 추가. 다음 본문 컨테이너(`.article_view`/`[data-translation]`/`#harmonyContainer`) 보강.
- ②: `tech_sites._NAV_BLOCKLIST` 에 `articleList`·`sc_serial_code`·`sc_section_code`·`view_type=`·`/serial` 추가.
- 테스트: `test_fetch_article_strips_portal_chrome_keeps_body`(다음 스타일 → 본문만), `test_tech_sites_rejects_list_and_serial_pages`.

**검증**: pytest **851 passed** · 금지패턴 0. ①은 샘플 HTML 로 직접 검증(chrome 제외 확인). 라이브 사이트별 셀렉터는 배포 확인 권장.

**상태**: ✅ merged (#140).

---

## 2026-06-09 — fix: 구글 카드 이미지가 전부 'Google News 로고'이던 것 (`claude/kind-volta-IWxix`)

**무엇을**: 구글 카드 이미지가 전부 동일한 Google News 로고. 원인 — 구글 RSS 링크(불투명 토큰)가 원문으로 안 풀려 enrich 가 **구글 인터스티셜 페이지의 og:image(로고)** 를 가져옴. (이 환경은 외부망 차단이라 라이브 확인 불가 → 코드/테스트로 검증.)

**어떻게**:
- 안전망(확실): `enrich.enrich_one` — **미해석 `news.google.com` 링크는 fetch 스킵** → 로고 안 들어옴(그라데이션 폴백). 원문 풀린 퍼블리셔 링크만 fetch.
- 신 포맷 해석: `google._batchexecute_decode`/`_parse_batchexecute` — 구글 내부 batchexecute API 로 불투명 토큰 → 원문 URL. `_resolve_link` 우선순위 base64→batchexecute→리디렉트. 링크 해석 **병렬**(ThreadPool) 처리.
- 테스트: batchexecute 파싱·해석 우선순위·enrich 안전망(구글 fetch 0회)·퍼블리셔 fetch.

**검증**: pytest **849 passed** · 금지패턴 0(`session.post` 사용). ⚠️ batchexecute 라이브는 미검증(외부망 차단) — 배포 재수집 필요. 안전망으로 **로고 일괄 표시는 확실히 해소**.

**상태**: ✅ merged (#139).

---

## 2026-06-09 — fix(UI): 기사 모달이 화면보다 커서 스크롤·버튼/사진 잘림 → 컴팩트화 (`claude/kind-volta-IWxix`)

**무엇을**: enrich 수정으로 본문/사진은 잘 들어옴(✓). 남은 문제 — 본문이 길면 모달이 뷰포트를 넘어 다이얼로그 전체가 스크롤되고 닫기/원문 버튼·사진이 잘림.

**어떻게**: `screens/data_management.css` — `.sc-modal-img` 280px·cover → **18vh·contain**(전체 표시)+배경, `.sc-modal-body` 60vh → **36vh**(내부 스크롤), 제목/여백 축소. `streamlit-overrides.css` 다이얼로그 `max-width:880px`(배너화 방지). `_news_modal_body` content 있으면 본문만(요약 중복 제거). 합계 ≈87vh 로 버튼 항상 보이게.

**검증**: pytest **844 passed**(모달 본문/요약 폴백 테스트 갱신·신규) · 금지패턴 0. CSS 비율은 실배포 화면 확인 권장.

**상태**: ✅ merged (#138).

---

## 2026-06-09 — fix(★근본원인): 수집이 enrich 를 호출 안 해 본문/이미지 전부 빈칸이던 것 (`claude/kind-volta-IWxix`)

**무엇을**: 사용자가 "본문 하나도 못 가져옴, AI Times/구글 사진 없음, 구글 본문에 제목+&nbsp;" 보고. **이 환경은 외부 호스트 차단(Host not in allowlist)** 이라 라이브 스크래핑 불가 → 코드 흐름 추적으로 근본원인 발견: **`collect_batch` 가 enrich 를 전혀 호출하지 않아 content 가 항상 빈 채 저장**(검색 결과 content=""). 그동안의 enrich/셀렉터 개선이 실제 수집에 안 쓰였음(= 토큰 낭비 원인).

**어떻게**:
- `run_daily.collect_batch`: 소스별 수집 직후 `enrich.enrich_parallel(bucket, with_llm=False)` 호출(naver/google/tech/rss 모두). `do_enrich` 파라미터(기본 True).
- `enrich.enrich_parallel`(ThreadPool 6workers) 신규. `enrich_one` 본문 확보 시 빈도 키워드 채움. `fetch_article` 같은 origin referer(네이버 403 대응).
- `google` summary unescape(&nbsp; 정리). `_consume_refresh_if_any` 에 `st.spinner`.
- 테스트: `test_collect_batch_enriches_body_and_image`(수집이 content·image·keywords 채움 검증) + `can_disable_enrich`. 기존 collect_batch 테스트는 enrich fetch stub(autouse)으로 hermetic·고속 유지. e2e seed 도 stub.

**검증**: pytest **843 passed** · 금지패턴 0 · py_compile OK. ⚠️ 샌드박스 네트워크 차단으로 라이브 수집은 미검증 — **배포 앱에서 재수집 필요**. 코드 흐름·테스트로 "이제 enrich 가 돈다"는 검증함.

**상태**: ✅ merged (#137).

---

## 2026-06-09 — fix: 뉴스 수집 — 구글 사진·카드 사진 크기·본문 전체 추출 (jhr0966/News 참고) (`claude/kind-volta-IWxix`)

**무엇을**: ① 구글뉴스 사진 0건, ② 카드 사진 너무 작음, ③ 본문 전체 미수집. 사용자 레포 `jhr0966/News` scraper.py(WebFetch) 와 제공 코드 참고.

**어떻게**:
- ①: `google._extract_original_link` — RSS description 의 비-구글 `<a href>` 를 원문 링크로 채택(우선) → enrich 가 og:image/본문 확보. 이후 base64 디코드→리디렉트→media 순.
- ②: `.sc-card-img` 128→190px(`.sc-card` 300→360px).
- ③: enrich `_CONTENT_SELECTORS` 에 AI Times/모우 CMS(`#article-view-content-div` 등) + 참고 누락 셀렉터 추가. 본문 선택을 '첫 매치'→**후보(셀렉터·문단·최대블록) 중 최장**으로 변경(전체 본문 확보).

**검증**: pytest **841 passed**(google `_extract_original_link`·전체 본문 선택 신규 테스트) · 금지패턴 0 · py_compile OK. 카드/사진 CSS·구글 신포맷 한계는 실배포 확인 권장.

**상태**: ✅ merged (#136).

---

## 2026-06-09 — fix: 뉴스 수집 후속 — 카드 클릭 무반응·높이 통일·표 본문/행모달·사진 추출 (`claude/kind-volta-IWxix`)

**무엇을**: 직전 PR(#134) 사용 중 발견된 5건 — ① 카드 눌러도 모달 안 뜸, ② 카드 높이 불균일(본문 3줄로 통일), ③ 데이터 표에 본문, ④ 표 행 클릭 시 모달, ⑤ 사진 추출(오토메이션월드만 정상, AI Times 미흡·구글 0건·네이버 로고만).

**어떻게**:
- ①: `st.dialog` 박스 강제 `display:flex`/`min-height` CSS(모달 깨짐 주범 추정) 제거 → 오버레이 세로중앙+max-height 만. 카드 오버레이 버튼을 `stElementContainer:has(stButton)` 절대배치로(클릭 적중↑).
- ②: `.sc-card` 고정 300px + 이미지 `flex:0 0 128px`, 제목 2줄·본문 3줄 `min-height` 예약 → 카드 높이 통일.
- ③④: `_render_news_table` 에 `본문` 컬럼 + `st.dataframe(on_select="rerun", single-row)` → 행 선택 시 `_sc_open_news` 세팅(소켓 rerun 모달), `_sc_table_sel` 가드로 재오픈 루프 방지.
- ⑤: `extract.is_junk_image` 신설(로고/아이콘/placeholder). naver 로고 img skip. enrich og:image 로고면 본문 img 폴백·리스트 로고 버리고 og 우선. google 리디렉트 링크 base64 디코드+리디렉트추적으로 원문 복원 + RSS media 이미지. (직접 requests 미사용 — §4.)

**검증**: pytest **839 passed**(신규 `tests/test_scrape_images.py` + 표 본문/행선택·카드클릭 테스트) · 금지패턴 0 · py_compile OK. CSS(카드클릭·모달중앙)는 실배포 시각 확인 권장(헤드리스 미설치).

**상태**: ✅ merged (#135).

---

## 2026-06-08 — fix/feat: 뉴스 수집 — 카드 클릭 reload 제거 · 모달 중앙/확대 · 데이터 표 · 본문/사진 추출 개선 (`claude/kind-volta-IWxix`)

**무엇을**: 사용자 4개 요청 — ① 카드 클릭 시 전체 새로고침 없이 즉시 모달, ② 기사·페르소나 모달을 화면 세로 중앙 + 더 길게, ③ 수집한 모든 뉴스를 보는 데이터 표 탭, ④ 본문·사진을 더 잘 가져오게(참고 스크래퍼 코드 반영).

**어떻게**:
- ①: 카드를 `?news=` 앵커(문서 reload)에서 **카드 전체를 덮는 투명 `st.button` 오버레이**(소켓 rerun)로 전환 → `_sc_open_news` 세팅·reload 없이 모달. `_sc_card_visual_html`(앵커 없음)·`_render_card_grid`(`st.columns(3)` + 카드별 컨테이너)·`_sc_filtered_records`. 구 `_sc_news_card_html`/`_sc_cards_html` 제거(딥링크 소비는 호환 유지).
- ②: `assets/v2/streamlit-overrides.css` — `st.dialog` 오버레이 flex 중앙 + 박스 `min-height:58vh`/`max-height:92vh`/`width:min(880px,94vw)` + 본문 신장. `.sc-modal-body` 46vh→60vh.
- ③: `_render_news_table` + `sc_browse_mode` 토글(`🃏 카드`/`📋 데이터 표`) — `st.dataframe`(ImageColumn 사진·LinkColumn 링크·제목·대분류·출처·수집·키워드), 상단 검색 적용.
- ④: `scraping/enrich.py` — 셀렉터·`<p>` 폴백도 빈약하면 **링크 적은 최대 텍스트 블록**을 마지막 폴백으로(`_FALLBACK_MIN_LEN`/`_FALLBACK_MAX_LINKS`). http.py UA풀·retry 는 이미 참고 코드와 동등.

**검증**: pytest **827 passed**(카드 클릭→모달·데이터 표·필터 신구조 + enrich 최대블록 폴백 신규) · 금지패턴 0 · py_compile OK. (모달 세로중앙은 CSS — 실배포 시각 확인 권장.)

**상태**: ✅ merged (#134).

---

## 2026-06-08 — feat: 뉴스 수집 화면 개편 — 카테고리 카드 브라우저 + 기사 모달 + ⚙ 수집 설정 (`claude/kind-volta-IWxix`)

**무엇을**: 뉴스 수집을 '키워드 뉴스'/'포탈 뉴스' 두 대분류로 정리. 메인은 수집 현황 요약 + 대분류 탭(키워드/포탈) + 출처칩 + **사진 카드**(제목·본문 일부), 카드 클릭 시 **기사 모달**(본문 전체 + 원본 링크). 키워드·포탈 설정은 **⚙ 수집 설정 서브뷰**로. 뉴스 라이브러리 필터 폼 제거(상단 검색이 대체). (사용자 4개 결정: #132 먼저 머지 / 설정=서브뷰 / 대분류 탭+출처칩 / 요약은 메인·상세는 설정.)

**어떻게**:
- `data_management_v2`: `_news_category_of`(naver·google=키워드, 그 외=포탈)·`_news_channel_of`(네이버/구글·press·커스텀) + `_sc_browse_records`(30일·_cat/_chan·최신순 캐시)·`_sc_channels`·`_sc_cards_html`·`_sc_news_card_html`(사진 카드 앵커, http 스킴만·escape). `_render_news_browser`(대분류 segmented + 출처칩 segmented + 카드) / `_render_collect_actionbar` / `_render_collect_settings`(키워드+출처표+이력) / 기사 모달(`_consume_news_modal_open_if_any`→`_sc_open_news`→`st.dialog(dismissible=False)`·`_news_modal_body`). `render_collect` 재배선(카드뷰↔설정뷰 `sc_collect_view`).
- 레거시(`_render_news_filter_form`/`_render_jobs_split`/`_render_dm_tabs`/`_news_cards_html`)는 유지하되 미호출(호환·테스트). 캐시 무효화 목록에 `_sc_browse_records`/`_sc_cards_html` 추가.
- CSS: `sc-grid`/`sc-card`/`sc-card-img`/`sc-modal*` + 컨테이너 인셋.
- 테스트: 신규 `tests/test_collect_browser.py`(+12), test_dm_tabs·test_dm_news_filter 2건씩 신구조로 교체, E2E S5(필터→카테고리 브라우저)·`_clear_ui_caches` 갱신.

**검증**: pytest **825 passed** · 금지패턴 0 · py_compile OK · 정적 미리보기 HTML 생성(playwright 브라우저는 네트워크 정책상 미설치 → 스크린샷 대신 HTML 전달).

**상태**: ✅ merged (#133).

---

## 2026-06-08 — feat: 작업 정의 flat-column 엑셀 → 구조화 JSON 자동 조립 (`claude/kind-volta-IWxix`)

**무엇을**: JSON 열이 없는 신 엑셀(분과·팀·부서·공정·작업·세부작업·Process_ID·공정설명·작업흐름·주요확인사항·안전주의사항·주요사용장비·품질리스크·자동화가능영역·이전공정·다음공정 16열)을 업로드하면 개별 컬럼을 구조화 task_def JSON 으로 자동 조립. (사용자 제공 컬럼 스펙.)

**어떻게**:
- `schema.COLUMN_MAP` flat 헤더 매핑 + `OPTIONAL_COLUMNS`/`RoadmapRow` 신 컬럼 9종(normalize 가 드롭 안 하게).
- `task_def_json`: `split_list_cell()`(줄바꿈/`;`/불릿 분리·dedup) + `assemble_from_columns()`(컬럼→payload). 품질리스크·자동화가능영역 → 표준 키(`overall_quality_risks`/`automation_potential_areas`)로 매핑(매칭/SOLA 즉시 반영). 신 컬럼에 내용 있을 때만 조립(빈 dict 게이팅 → 구 포맷 보존), process_name 은 세부작업→작업으로 보강. `TaskDef`/`parse`/`flatten_for_match`/`to_chat_context_lines` 에 신 필드(work_flow·key_check_points·safety_notes·main_equipment·prev/next) 반영.
- `ingest.normalize_columns`: task_def_json 빈 행에 한해 조립(단일 진입점) → match/board/SQLite/query 무변경. 구 JSON 행은 그대로(하위호환).
- `task_def_form`/`task_def_manage`: 폼 위젯 + 상세 보기 섹션 추가, 문자열 항목(flat) 렌더 병행. `data_management_v2` 업로드 안내 갱신.

**검증**: pytest **813 passed**(+18 신규 `tests/test_roadmap_flat_columns.py`) · 금지패턴 0 · py_compile OK.

**상태**: ✅ merged (#132).

---

## 2026-06-08 — feat: 데이터 관리 → '뉴스 수집' · '작업 정의' 두 화면 분리 (`claude/kind-volta-IWxix`)

**무엇을**: 사이드바 '🧱 데이터 관리'(5탭) 를 '🗞 뉴스 수집'(수집잡·키워드·출처 3탭) + '📋 작업 정의'(엑셀 업로드+관리, **탭 없이 세로**) 두 화면으로 분리. (사용자 결정: 작업 정의는 탭 없이 단일 화면 + 작업정의용 KPI.)

**어떻게**:
- `sidebar.AREAS` 5→6, `app.py` 디스패치 2분기 + 화면별 chat context.
- `data_management_v2`: `render()` → `render_collect()`/`render_taskdef()`. `_render_dm_tabs(tabs=_DM_COLLECT_TABS)` 파라미터화. `_taskdef_stats()`(task_defs_db.list_all → 등록·부서·updated_at)·`_render_taskdef_header()`·`_fmt_taskdef_ts()` 신규. `chat_context_block`→`_collect`/`_taskdef`.
- 딥링크 재배선: app_shell 검색·board(2)·task_def_manage `_manage_href`(구 dm_grp/dm_tab 제거)·dm 내부 clear href. chat_panel 안내 2종. 템플릿 브레드크럼/설명·insights/board 카피.
- 테스트 9개 갱신(area·함수명·screen smoke 4-tuple). 레거시 `_dm_tab_href`/`_dm_tabs_html`/그룹 nav(data_management_render)는 segmented_control 도입 후 이미 dead → 유지(그 테스트도 그대로 통과).

**검증**: pytest **795 passed** · 금지패턴 0 · playwright 실측 — nav 6항목, 뉴스 수집(브레드크럼·수집 KPI 4·탭 3), 작업 정의(KPI 3종·업로드 섹션·관리·탭 없음), 화면별 우측 채팅 안내.

**상태**: ✅ merged (#131).

---

## 2026-06-08 — feat: 사이드바 메뉴 이동 흰 깜빡임 제거 (앵커 → st.button 재위젯화) (`claude/kind-volta-IWxix`)

**무엇을**: 좌측 5-nav 를 앵커(`<a href=?app_area=>`)에서 `st.button` 위젯으로 복원 → 메뉴 이동 시 문서 전체 reload(흰 깜빡임) 제거. (사용자 방법론: 위젯+세션+소켓 rerun — 데이터관리 탭에 이미 적용된 패턴을 사이드바에도.)

**왜 다시 위젯화**: 2026-06-05 위젯→앵커 되돌림은 "사용자 환경에서 메뉴 깨짐" 보고 때문이었으나 **원인 미재현**. `.st-key-*` 스코프 CSS 는 이후 데이터관리 필터·수집 버튼에서 사용자 환경 포함 정상 동작 확인 → 직전 깨짐은 일시적 CSS FOUC 로 추정. 사용자 요청으로 재위젯화.

**어떻게**: `_sidebar_nav_html`(앵커) → `_nav_label`+`_render_sidebar_nav`(st.button 5개, `on_click` 금지). `.st-key-sidebar_nav` 스코프 CSS 가 인덱스(CSS counter)·제목(`**strong**`)·설명(`*em*`)·활성(`button[kind="primary"]`)으로 `.sidebar-nav-item` 룩 복제. `styles.py` 다크 active 규칙에 button 추가. `quote` import 제거. I-22 invariant 갱신.

**검증**: playwright 실측 — 클릭 시 `window` 플래그 생존(reload 0)·URL `?app_area=` 없음·활성 01→03 전환·라이트/다크 룩 동일(인덱스 01–05·제목·설명 표시). pytest **793 passed**(앵커 HTML 테스트 → `_nav_label`+위젯 nav AppTest 교체) · 금지패턴 0.

**후속(왼쪽맞춤 — 사용자 '들쭉날쭉' 보고)**: 위젯 nav 제목 시작 x 가 글자 수마다 달라짐(들쭉날쭉) — 원인은 Streamlit 버튼 라벨의 `button > div`(+span) **두 겹 flex 래퍼가 `justify-content:center`** 라 라벨 블록이 가운데로 몰린 것(`stMarkdownContainer` 보다 위 래퍼라 기존 셀렉터가 못 잡음). `button > div`/`> span` 을 `flex-start` 로 돌려 왼쪽 고정. playwright 실측 제목 시작 x **24.9px 편차 → 0px**(전 항목 38px). #129 머지 후 후속 커밋.

**상태**: ✅ #129 머지(232c991). 왼쪽맞춤은 후속 커밋·PR.

---

## 2026-06-06~08 — fix: 데이터 관리 출처 탭 '무수집' 오표시 + 수집버튼·필터박스 폭 + referer (`claude/kind-volta-IWxix`)

**무엇을**: ① **출처 탭 기본 4출처가 수집됐는데도 전부 '무수집' 표시** 버그(사용자가 보고한 '수집 안 됨'의 실제 원인) 수정. ② 수집 버튼·필터 박스 폭 삐져나감 수정. ③ 수집 referer 교차도메인 correctness 개선.

**①왜/어떻게(핵심)**: 수집기는 `source`=naver/google/tech 로 저장, tech 는 AI Times·오토메이션월드를 **모두 source="tech"** 로 묶고 site 명은 `press` 에 둔다. 출처 탭 `_src_count_map` 은 **표시명으로 곧장 group** → 매칭 0건(전부 무수집) + naver/google/tech 원시값이 '기타'로 누출. `_DEFAULT_SOURCE_MATCH`(표시명↔source값 + tech 는 press 로 구분, legacy 직접저장 호환)로 환산. playwright 실측: AI Times 1·Google RSS 2·네이버 기술 1·오토메이션월드 0, 기타 누출 0. **수집 자체는 정상이었음**(이전 세션의 403 진단은 이 세션 sandbox 의 outbound 전면차단 아티팩트).

**②왜/어떻게**: Streamlit 이 `.st-key-*` 를 width:100%(부모 724px)로 잡아 margin 이 폭을 못 줄이고 우측 밀림(본문 356–1024 → 위젯 352–1076). `width:calc(100% - 56px) !important` + `margin:0 28px` → 정확 정렬.

**③왜/어떻게**: `default_headers()` 가 전 요청에 네이버 referer 고정 → 타 도메인 403 유발 가능. referer opt-in 전환(네이버 검색만 명시). 별개 correctness 개선.

**검증**: 출처 탭 매칭 단위테스트(신규/legacy) + UI 정렬·출처 탭 playwright 실측 · pytest **792 passed** · 금지패턴 0.

**상태**: 🔄 진행 — 커밋·푸시·PR(#128) 갱신 예정.

---

## 2026-06-06 — 검증: E2E 전체 사용 시나리오 시뮬레이션 (`claude/kind-volta-IWxix`)

**무엇을**: 시스템 전체 사용 시나리오 7개를 세우고 시뮬레이션으로 유효 동작 검증. `tests/test_e2e_scenarios.py` 신규.

**어떻게**: 외부 의존(네트워크=`scraping.*.search` mock, LLM=`sola.*.chat` mock)만 격리, 나머지(`collect_batch`→`news_db`→`score_matches`→`score_cells`, `sqlite_sync`→`load_latest`, `app.py` 5화면, 데이터관리 필터, `bookmarks`)는 실제 코드 실행. `AppTest.from_file("app.py")` 로 5화면 네비게이션. 시드 헬퍼로 페르소나(+온보딩 dismiss)·작업정의·수집. UI `st.cache_data` 는 `_clear_ui_caches` 로 테스트 간 stale 제거.

**결과**: 7/7 시나리오 통과 · 전체 **789 passed** · 금지패턴 0. 수집부터 보관함까지 한 줄기로 유효 동작 확인. (발견·수정: fake 기사에 `source` 키 누락 → 출처 컬럼 빈값 / S7 stale 캐시 → `_clear_ui_caches` 에 archive 캐시 추가.)

**상태**: 🔄 진행 — 커밋·푸시·PR 예정.

---

## 2026-06-05 — 추가: 데이터 관리 뉴스 라이브러리 필터(출처·기간·정렬) (`claude/kind-volta-IWxix`)

**무엇을**: 데이터 관리 jobs 탭의 죽은 필터 시안(출처/기간/정렬 셀렉트 — 핸들러 없어 `_strip_dm_mockups` 가 제거하던 잔재)을 실동작 `st.form` 필터로 구현. **'적용' 눌렀을 때만** 뉴스 라이브러리 갱신(요청 방법론).

**어떻게**: `_render_news_filter_form`(st.form: 출처 멀티셀렉트·기간 3/7/30일·정렬 최신/오래된 + 적용) → 반환값을 `_news_cards_html(q, sources, days, sort)` 인자로. 필터 모두 기본이면 기존 6장 동작 유지, 활성이면 기간 내 출처·검색 좁혀 정렬 후 24장 + 배너(`_news_filter_banner_html`, grid-column:1/-1 로 전체 폭). 전체 해제 `?dm_clear_filters=1`→`_consume_news_filter_clear_if_any`. 출처 옵션 `_news_source_options`(30일 distinct, 캐시 무효화 목록 추가).

**왜 st.form OK**: CHANGELOG 의 'st.form 금지'는 topbar 한정(self-close 불가). `with st.form()` 단일 블록은 chat_panel 입력 폼처럼 누수 없음. bare 단위 테스트(`_render_jobs_split`)는 폼 helper 를 patch.

**검증**: playwright — 'AI Times' 적용 시 결과 1건 + 배너 전체 폭(598/630px=95%). pytest **782 passed**(+10 신규) · 금지패턴 0.

**상태**: 🔄 진행 — 커밋·푸시·PR 예정.

---

## 2026-06-05 — 되돌림: 사이드바 메뉴 위젯화 + 메인 헤더 스크롤 고정 (사용자 요청) (`claude/kind-volta-IWxix`)

**무엇을**: ① 사이드바 5-nav 위젯화가 **사용자 환경에서 메뉴가 깨져** 순수 HTML 앵커로 되돌림. ② 메인 헤더 스크롤 고정(sticky) 제거. (채팅 패널 고정은 요청 대상 아님 → 유지.)

**왜/원인 추정**: 위젯 nav 는 `st.container(key=…)` 의 `st-key-*` 클래스 + 버튼 라벨 마크다운에 룩을 의존하는데, Streamlit 버전/환경 차이로 클래스/마크다운이 안 먹으면 기본 회색 버튼으로 깨질 수 있다. playwright(chromium·streamlit 1.58) 에선 정상 렌더라 재현 불가 → 환경 호환성이 확실한 원래 앵커 HTML 로 복원(흰 깜빡임은 감수).

**어떻게**: `sidebar._render_sidebar_nav`/`_nav_label` 제거 → `_sidebar_nav_html`(앵커) 복원, `quote` import 복원, render 호출 복원. `sidebar.css` `.st-key-sidebar_nav`→`.sidebar-nav-item` 복원. `_DARK_CSS` 의 nav 위젯 다크룰→`.sidebar-nav-item.active` 복원. `.db-topbar` static·투명·그림자 제거. `streamlit-overrides.css` 헤더 sticky 룰 삭제. 테스트는 `test_sidebar_nav_html_uses_link_list_not_radio_buttons` 복원.

**검증**: playwright — nav=`a.sidebar-nav-item`×5(위젯 제거 확인)·헤더 스크롤 ΔY=−400(고정 해제). pytest **772 passed** · 금지패턴 0. INVARIANTS I-20·I-22 '되돌림' 으로 갱신.

**교훈**: Streamlit 위젯 룩을 `st-key-*` 풀-CSS 로 갈아끼우는 건 **실배포 환경 검증 없이 머지 금지**(로컬 chromium 만으론 부족). 데이터 관리·산출물 보관함 위젯화는 유지됐으나(작동), 항상 노출되는 사이드바는 깨짐이 즉시 눈에 띈다.

---

## 2026-06-05 — 산출물 보관함 칸반 카드 액션 위젯화 (흰 깜빡임 제거) (`claude/kind-volta-IWxix`)

**무엇을**: 산출물 보관함 칸반의 카드 액션(채택/수정/기각·되돌리기)·더보기/접기가 앵커라 클릭마다 문서 reload(흰 깜빡임)였던 것을 위젯화. (UX 안정화 — 컨텍스트 딥링크 슬라이스 中 사용자 선택 "산출물 보관함 카드 액션".)

**어떻게**:
- 칸반 보드를 템플릿 HTML(`{{OA_CARDS_*}}`) → `st.columns(3)` 위젯 렌더(`_render_kanban_column`). 컬럼 컨테이너 `.st-key-oa_col_*` 가 구 `.oa-col` 룩. 카드(`_card_html`)는 표시 전용(액션 앵커 제거), 1순위 액션은 컬럼 상단 `st.button`(`_render_card_actions`).
- 채택/기각/되돌리기 = `_do_archive_action` pending → `_consume_action_if_any`(pending/레거시 쿼리 둘 다). expand = `?expand=` 앵커 → 세션 `_oa_expanded` 토글. 수정 = `_handoff_edit_to_sola`(세션 app_area=SOLA + `st.query_params` from/bm_id/title — **reload 없이 URL 갱신이라 SOLA 소비 경로 무변경**).
- `_oa_stats_and_cards`→`_oa_data`(stats+items), `_build_cards_html`→`_cards_block_html`(앵커 없음). 템플릿 `archive_main.html` = 헤더 전용(보드 section 제거).

**검증**: playwright — 3컬럼·액션 5버튼·'채택' 클릭 시 window 플래그 생존(reload 0)+카운트 즉시 갱신·다크 룩(녹 채택/주황 기각) 유지. pytest **773 passed**(expand 세션·카드블록·`_oa_data`·액션 pending·수정 핸드오프로 테스트 교체) · 금지패턴 0.

**핵심 함정/패턴**: ① **`st.query_params[k]=v` 할당은 문서 reload 없이 URL 만 갱신** → 컨텍스트 딥링크(수정→SOLA)는 버튼이 같은 쿼리를 세팅+`st.rerun()` 하면 소비자(SOLA) 코드 변경 0. ② HTML 블록에 박힌 액션은 카드를 표시 전용으로 두고 **컬럼 컨테이너에 .oa-col 룩**을 줘 위젯 버튼을 위/아래에 배치. ③ 템플릿 일부만 쓰면 `test_template_placeholders`/`test_archive_cleanup` 가 미소비 토큰을 잡으니 **죽은 section 은 템플릿에서 삭제**.

**파일**: `ui/archive_v2.py`, `assets/v2/screens/{archive_main.html,archive.css}`, `tests/{test_archive_more,test_archive_cleanup}.py`.

---

## 2026-06-05 — 데이터 관리 '지금 뉴스 수집' + 출처 토글/제거 위젯화 (흰 깜빡임 제거) (`claude/kind-volta-IWxix`)

**무엇을**: 데이터 관리의 남은 앵커 액션(① '지금 뉴스 수집' ② 출처 토글/제거)을 위젯화해 클릭 시 문서 reload(흰 깜빡임) 제거. (UX 안정화 — 사용자 승인: "둘 다 위젯화 + 스샷 확인".)

**어떻게**:
- '지금 뉴스 수집': `_refresh_cta_html`(`<a ?refresh=now>`) 제거 → `_render_collect_button`(st.button). 클릭=`_do_dm_collect` pending→`st.rerun()`→`_consume_refresh_if_any`(버튼 pending/레거시 쿼리 둘 다). 우측 정렬은 **column flex 라 `align-items:flex-end`**(justify 는 세로축이라 무효 — 함정).
- 출처 토글/제거: `_dm_src_body_html`(앵커 박힌 `<ul>`) → `_render_src_table`(헤더 HTML + 행별 `st.columns([pill | 버튼])`). 컨테이너 `.st-key-_src_row_*` 가 테두리(구 `.dm-src-row` 룩), `_src_row_pill_html` 이 시각 격자. 클릭=`_do_src_action`=(action,name) pending→`_consume_src_action_if_any`(pending/레거시 쿼리 둘 다).

**검증**: playwright — 출처 토글 클릭 시 `window` 플래그 생존(reload 0)·URL 깨끗·6행/4버튼·수집버튼 우측정렬·라이트/다크 룩 유지. pytest **777 passed**(`_dm_src_body_html`/`_refresh_cta_html` 테스트 → pill/header/pending 테스트로 교체) · 금지패턴 0.

**핵심 함정**: ① Streamlit 컨테이너는 기본 **column flex** → 자식 우측 정렬은 `align-items:flex-end`(`justify-content` 아님). ② HTML 블록에 박힌 액션은 위젯으로 못 넣으므로 `st.columns([시각 HTML | 버튼])` 로 분리하고 **컨테이너에 테두리**를 줘 한 행처럼 보이게. ③ 레거시 쿼리 소비 경로(`?refresh=now`/`?src_action=`)는 유지해 북마크/딥링크 + 기존 테스트 호환.

**파일**: `ui/data_management_v2.py`, `assets/v2/screens/data_management.css`, `tests/{test_collect_trigger,test_src_crud,test_dm_tabs,test_dm_cleanup}.py`.

---

## 2026-06-05 — 사이드바 메뉴 이동 위젯화 (화면 전환 흰 깜빡임 제거) (`claude/kind-volta-IWxix`)

**무엇을**: 좌측 업무 흐름 5-nav 를 누를 때 나던 **화면 전환 흰 깜빡임** 제거. (UX 안정화 다음 단계 — 마지막 큰 흰 깜빡임 출처였던 사이드바 메뉴.)

**어떻게**:
- `_sidebar_nav_html`(앵커 `<a href=?app_area=>` 빌더) 제거 → `_render_sidebar_nav` 가 `st.button` 5개. 앵커=문서 reload(흰 깜빡임), 버튼=소켓 rerun(부분 갱신). `on_click` X — `if st.button(): app_area 세팅+st.rerun()`. 활성=`type="primary"`.
- 룩 보존: `.st-key-sidebar_nav` CSS 가 카드형 nav 항목 복제 — 인덱스=CSS `counter` `::before`, 제목=`**…**`(strong), 설명=`*…*`(em, block+ellipsis), 활성=`button[kind="primary"]`. 다크는 secondary 버튼 dark 규칙이 nav 까지 안 먹게 투명 유지 + 활성 틴트(`_DARK_CSS`).
- 컨텍스트 딥링크(`?app_area=` from 보드/히트맵/알림)는 `_consume_area_query` 로 유지 — 이번엔 사이드바 메뉴만.

**검증**: playwright — nav 클릭 시 `window` 플래그 생존(문서 reload 0=흰 깜빡임 없음)·URL 에 app_area 없음·활성 01→03 이동·헤더 타이틀 전환·라이트/다크 사이드바 스크린샷 기존과 동일. pytest **775 passed**(nav 위젯 AppTest 추가) · 금지패턴 0.

**핵심 함정**: ① st.button 라벨은 `**strong**`/`*em*` 등 **핵심 markdown 만**(색·코드 directive 의존 X) 써야 안전. ② 다크에서 일반 `button[kind="secondary"]` dark 규칙(0-2-2)이 `.st-key-sidebar_nav button`(0-1-1)보다 specificity 높아 nav 까지 #1E293B 로 채워짐 → `_DARK_CSS` 에 `body:has(.db-topbar) .st-key-sidebar_nav button[kind="secondary"]{ background:transparent }`(0-3-2)로 이김. ③ 인덱스 01·02 는 라벨이 아니라 CSS `counter(navidx, decimal-leading-zero)` 로 생성(라벨엔 제목·설명만).

**파일**: `ui/sidebar.py`(위젯 nav), `assets/v2/sidebar.css`(나브 버튼 룩), `ui/styles.py`(다크 nav), `tests/test_sidebar_profile.py`(앵커 테스트→위젯 AppTest).

---

## 2026-06-05 — 메인 헤더 스크롤 고정 + 채팅 패널 모든 화면 고정 (`claude/kind-volta-IWxix`)

**무엇을**: ① 모든 화면에서 메인 헤더(`.db-topbar`)가 스크롤해도 상단에 고정. ② SOLA 작업실·산출물 보관함·데이터 관리에서 스크롤 시 우측 채팅 패널이 같이 밀리던 것 → 모든 화면 고정.

**어떻게**:
- **헤더 sticky**: `.db-topbar` 직접 sticky 는 `st.html` 래퍼가 헤더 높이로 shrink-wrap 돼 이동 여유 0 → 안 붙음. 대신 **헤더를 감싼 element-container**(`[data-testid="stElementContainer"]:has(> [data-testid="stHtml"] > .db-topbar)`)에 `position:sticky; top:0; z-index:20`. 컨테이닝 블록이 메인 컬럼 전체 높이라 콘텐츠만큼 길게 고정됨(채팅 컬럼 sticky 와 동일 원리). 배경 라이트 `--v2-bg`/다크 `#0F172A` 불투명 + box-shadow.
- **채팅 패널 고정**: 패널 높이 `calc(100vh-24px)` → `calc(100vh-72px)`. sticky '이동 여유'(`row−panel−top`)가 `block-container`(36px)·`stMain`(8px) **row 밖 padding** 이 만든 추가 스크롤보다 작아, 짧은 화면 바닥에서 패널이 ~32px 밀렸던 것 해소(72px 로 여유 확보).

**검증**: playwright 실측(1440×900) 5개 화면 전부 헤더 ΔY=0·채팅 ΔY=0(이전 헤더 −600~−40, 채팅 sola/archive −32) · 헤더 래퍼 computed `sticky/top:0/z:20` · pytest **774 passed** · 금지패턴 0.

**핵심 함정(재학습 방지)**: Streamlit `st.html` 요소는 **그 자체가 아니라 감싼 element-container 에 sticky** 를 걸어야 한다(자체 sticky 는 shrink-wrap 으로 무력화). sticky 패널은 높이가 컨테이닝 블록과 비슷하면 row 밖 padding 만큼 바닥에서 떨어지므로, 패널을 충분히(여기선 72px) 낮춰야 '이동 여유 > 페이지 스크롤'.

**파일**: `assets/v2/shell.css`(.db-topbar 배경·그림자), `assets/v2/streamlit-overrides.css`(헤더 래퍼 sticky + 채팅 패널 높이), `ui/styles.py`(다크 헤더 배경).

---

## 🚩 다음 세션 시작점 (2026-06-02 기준) — 여기부터 읽으세요

**현재 상태**
- **`main e87f6e7` 기준 — M1~M3 완성 + post-M3 완성도 하드닝 완료.** `pytest 724 passed` · 금지패턴 0 · 70 모듈·69 테스트·13.6k LOC. 3대 축 end-to-end 완전 배선, graceful degradation(무데이터/LLM미설정/네트워크실패) 우수.
- **이 세션(`claude/kind-volta-IWxix`) 누적 머지** — #97 수집헬스 런 타임라인+네이버 파서 테스트 · #98 사이드바 펼치기버튼 복구+채팅패널(안내 영속·추천 클릭·표시영역) · #99 의미유사도(TF-IDF) 하이브리드 매칭+sparkline 런 오버레이 · #100 다크 1차(입력창·카드) · #101 다크 2차(작업정의 뷰·배너) · #102 완성도 점검 결함 4건(collected_at 계약·데이터-경로 로깅·archive 목업 제거·SQLite 마이그/표면화) · #103 A3 문서드리프트+다크 sparkline. (#95·#96 verify CLI 중복 close.)
- **완성도 점검 결론**: 구조적 결함 없음. 과거 잠재 데이터-계약 버그(`collected_at` 미존재 → 데일리 브리핑 매칭경로 silent death 등) 전부 수정. 라이브 수집은 환경 네트워크 allowlist 로 여전히 차단(파서는 정상).

**바로 할 일 (남은 건 외부 의존/결정)**
1. **임베딩 RAG** — 의미 매칭이 현재 TF-IDF 코사인(`store/match.semantic_weight`). 신경망 임베딩은 백엔드(groq 미지원·환경 네트워크 차단) 확보 시 `_tfidf_vec`/`_cosine` 스왑으로 확장.
2. **PR #49** — 글래스모피즘 TS 프로토타입 채택(현 v2 셸 반영)/close 디자인 결정 대기.
3. **개선포인트** — 별도 forward-looking 리뷰로 발굴(테스트 커버리지·성능·UX·기술부채·관측성). 결과는 본 문서 상단 세션 기록 참조.

**핵심 함정 (재학습 방지)**
- `st.html` 은 **인라인 `<svg>` 를 sanitize 로 제거** + `data:image/svg+xml;utf8,<svg…#…>` 는 `#`/공백이 잘려 깨짐 → 화면 템플릿은 `ui/components.prepare_screen_html()` 통과 필수(아이콘 인코딩 + 인라인 svg→data-URI img). 각 화면 메인 렌더·`render_topbar` 가 이미 적용.
- **Streamlit 네이티브 위젯은 `.streamlit/config.toml`(정적 라이트) 종속** → 런타임 다크는 토큰 + 위젯 오버라이드(`styles.inject_user_prefs` `_DARK_CSS`)로 처리. 새 인라인 색은 반드시 `var(--token)` 사용(고정 hex 금지 — 다크 깨짐).
- 화면 CSS 카드 배경은 `var(--surface-card)` 토큰화됨(다크 추종). 새 카드도 토큰 사용.
- **다크에서 입력창 흰색 = baseweb 래퍼** — `_DARK_CSS` 가 안쪽 `input`/`textarea` 만 칠하면 Streamlit 1.58 의 `[data-baseweb="base-input"]` 래퍼가 흰색으로 남는다. 래퍼(`base-input`/`input`/`textarea`)까지 다크화해야 함(이미 반영). 카드 흰색은 화면 CSS 의 고정 `#FFFFFF`/`#FAFBFD` 그라데이션 → `var(--surface-card)`/`var(--surface-soft)` 토큰화(라이트값 동일이라 라이트 무변경).
- 레이아웃: `app.py` 가 소유 — 좌 네이티브 `st.sidebar` + `st.columns([2.3,1])` 메인/채팅. 우측 채팅 = `chat_panel.render_side`. (`docs/ARCHITECTURE.md` 갱신됨.)
- **사이드바 헤더 절대 `stHeader{display:none}` 금지** — Streamlit 1.58 은 사이드바 '펼치기' 버튼(`stExpandSidebarButton`)을 헤더 toolbar 안에 렌더하므로 헤더를 통째 숨기면 접은 뒤 못 펼친다. `streamlit-overrides.css` 처럼 헤더는 absolute·height:0·투명·pointer-events:none 로 죽이고 toolbar 노이즈(`stToolbarActions`/`stMainMenu`/`stAppDeployButton`/`stStatusWidget`/`stDecoration`)만 숨기고 펼치기 버튼은 좌상단 고정으로 살린다. 좁은 폭(<768px)은 Streamlit 이 사이드바를 오버레이로 띄움(접기로 dismiss).
- **로컬 라이브 UI 검증 가능**: `pip install playwright` + 사전설치 `/opt/pw-browsers/chromium-1194/chrome-linux/chrome` → `python -m streamlit run app.py --server.port 8765 --server.headless true` 띄우고 playwright 로 DOM/스크린샷 검사. ⚠ Python 모듈 변경은 fileWatcher 꺼져 있으면 서버 재시작 필요(CSS 는 매 run 파일을 읽어 즉시 반영).

**검증 베이스라인**: `pytest -q` = **724 passed** · 금지 패턴(on_click/raw requests) 0 · `py_compile` OK · playwright `scripts/verify_screens.py`(+ 페르소나 `data/persona/profile.json` 미리 저장해야 온보딩 모달 회피).

**⚠ 라이브 수집은 여전히 막힘**: 사용자가 "전체 도메인 허용 + 새 세션"을 했다 했으나, 이 컨테이너의 네트워크는 아직 **제한적 allowlist**(pypi.org만 200, news 도메인·google.com·example.com 전부 403 `Host not in allowlist`, WebFetch 동일). 네트워크 정책은 **환경 생성 시점에 고정**되므로 이 세션은 정책 변경 전 환경. → 정책=전체 허용으로 설정된 환경에서 **진짜 새 세션**을 열어야 라이브 검증 가능. 라이브 시 허용 필요 호스트: `search.naver.com`·`www.naver.com`·`n.news.naver.com`·`news.google.com`·구글 RSS 가 링크하는 **임의 언론사 도메인**(그래서 '전체 허용'이 맞음)·`www.aitimes.com`·`automation-world.co.kr`.

---

## 2026-06-05 · fix: 데이터 관리 탭 간격 + 탭 전환 시 채팅 패널 흔들림 (CSS only)

**브랜치:** `claude/kind-volta-IWxix`. **맥락:** "탭들 사이 갭 없어 답답 + 탭 이동할 때 LLM 채팅창 위치 달라지는 경우 있음."

**진단(playwright 실측):** ① 탭 칩: 실제 flex 컨테이너가 `[role="radiogroup"]`(직전 CSS 는 `[role="group"]` 오타로 미적용) + 버튼 `margin-right:-1px`(테두리 공유) → 칩 맞붙음(gap=-1). ② 채팅: 컬럼 `position:sticky;top:12px` 인데 본문 높이가 탭마다 달라(작업정의 926 < 뷰포트 950 → 페이지 미스크롤) sticky flow 위치가 8px, 다른 탭은 20px 로 어긋남(12px 점프).

**수정(`streamlit-overrides.css` 한 파일):** ① `[role="radiogroup"]{gap:6px}` + 버튼 `margin:0` → 칩 6px 간격. ② 본문 컬럼(`stHorizontalBlock:has(.side-chat-marker) > stColumn:not(:has(marker))`)에 `min-height:calc(100vh-4px)` → 항상 채팅(calc(100vh-24px))보다 커서 sticky 위치 고정.

**검증:** 6개 탭(jobs/kw/src/task/manage/수집잡) 전부 채팅 top=20px 동일(이전 작업정의만 8→16→20 으로 min-height 튜닝) · 칩 gap 6px 균일(스크린샷) · pytest 774 passed.

**팁:** min-height 를 calc(100vh-16px)=934 로 하면 작업정의 탭이 16px(4px 잔여) → calc(100vh-4px)=946(>본문 자연높이 939 한계) 에서 완전 일치. 채팅 컬럼 sticky top 은 본문 컬럼이 채팅보다 확실히 커야 안 튐.

---

## 2026-06-05 · UX: 탭 룩 복원(segmented_control) + 채팅 입력창 하단 고정 + 조건부 렌더

**브랜치:** `claude/kind-volta-IWxix`.

**맥락:** st.tabs 머지(#120) 후 사용자 — "새로고침 없는 건 확인. 근데 UI 볼품없어짐: ① 채팅 입력창·보내기는 영역 하단에 있어야, ② 탭이 기본 컴포넌트로 바뀜. + 긴 방법론 문서(session_state/callback/fragment/cache/form, st.tabs eager 렌더 지적, segmented_control+조건부 권장)."

**충돌 처리(중요):** 사용자가 `on_click` 콜백을 명시 요청했으나 **CLAUDE.md #3 + CI 가 on_click 금지**. → 동일 UX 를 `pending(__prefill)+st.rerun()`+`_apply_pending_prefill` 로 구현(체감 동일, `key`+session_state 원칙 유지). 사용자에게 "꼭 on_click 이면 CI 규칙 자체를 푸는 별도 결정"이라고 안내함.

**수정:**
- `data_management_v2`: `st.tabs`→`@st.fragment _render_dm_tabs`(segmented_control, `key=_dm_active_tab`, 단축 아이콘 라벨 `_DM_TAB_SHORT`) + `_render_dm_tab_panel`(활성 탭만 **조건부 렌더**). 탭 전환=fragment rerun(부분 갱신) · 활성 탭 session_state 보존 → 앵커 리로드 후에도 같은 탭(#120 출처토글 첫탭복귀 해소).
- `chat_panel`: `_chat_composer`(칩+입력 묶음) → 상단 `_render_chat_suggestions` + 하단 `_render_chat_input` 분리. CSS `margin-top:auto` 로 입력 form 하단 고정. 칩 클릭=full rerun(칩↔입력 별도 영역) → 하단 입력창 채움.
- `streamlit-overrides.css`: 입력폼 `margin-top:auto`(하단핀) + `.st-key-dm_tabbar` 카드형 pill 스타일(활성=accent) + stTabs 룰 제거.
- 테스트: `test_dm_tabs.py` st.tabs eager 테스트 2건 → segmented 조건부 렌더(기본=jobs만/활성=kw만) 2건 교체. `test_task_def_upload.py` 탭선택 `?dm_tab=task`→`session_state["_dm_active_tab"]="task"`.

**검증(playwright 실측):** 탭클릭 → `XRUN:DMTABS`만(앱 `XRUN:APP` 0)=fragment 스코프 · 기본 jobs본문만(`키워드 관리` 부재)·kw탭 전환시 kw본문만=조건부 렌더 · textarea bottom 858/950px=하단고정 · 칩클릭→입력창 자동채움(스크린샷 확인). pytest **774 passed** · on_click 0.

**남은 앵커(다음 단계):** 사이드바 메뉴(`?app_area=`)·출처 토글(`?src_action=`)·"지금 뉴스 수집"(`?refresh=now`)·SOLA quick-action 은 아직 앵커=문서 reload. 위젯화하면 마지막 흰 깜빡임 제거. (segmented_control+session_state 라 이제 in-tab 앵커 액션도 탭은 유지됨.)

---

## 2026-06-04 · UX: 탭 진짜 무깜빡임 (st.tabs) + 채팅칩 위치 복구 — Phase 1+2 후속

**브랜치:** `claude/kind-volta-IWxix`.

**맥락:** Phase 1+2 머지(#119) 후에도 사용자: "여전히 데이터관리 탭(키워드/출처설정) 누르면 화면 전체 새로고침. 채팅 예시칩도 표시가 이상해졌고 눌러도 전체 새로고침. 누른 개체만 갱신돼야." → 질문 후 "탭=네이티브 st.tabs / 칩=스타일 복구" 선택.

**진단(계측으로 확정 — 핵심 교훈):** app.py·fragment 에 `print("XRUN:…")` 카운터를 심고 playwright 로 클릭→로그 상관분석. 결과 **fragment 는 rerun 을 제대로 격리하고 있었다**(탭클릭=`_dm_body_fragment`만, 칩=`_chat_composer`만, 문서 reload 0). "전체 새로고침"은 **시각 현상**이었음: ① 데이터관리 본문 전체가 **하나의 거대한 `st.html`** → 탭 전환 시 통째 리페인트(헤더 KPI 까지 깜빡), ② `st.pills` 가 `margin-top:auto` 로 컬럼 **맨 아래로 밀려** 안내문과 칩 사이 큰 빈 공간(= "이상해짐"). → **rerun 격리만으론 부족, 시각 단위까지 쪼개야 함.**

**수정:**
- `data_management_v2`: `segmented_control`+`_dm_body_fragment`+monolithic `_render_main` 제거 → 헤더 `_render_dm_header`(탭 위 1회) + `st.tabs` 5패널(`_render_dm_tabs`/`_render_jobs_split`). 탭 전환 **100% 클라이언트사이드(서버 rerun 0)**. 템플릿은 `{{DM_TABS}}` 기준으로 split(헤더/본문). `st.tabs` 는 프로그램적 탭선택 불가 → 레거시 `?dm_grp/?dm_tab` 는 1회 정리만(출처 토글 앵커는 새로고침 후 첫 탭 복귀, 토글은 동작).
- `streamlit-overrides.css`: 입력 form 래퍼 `margin-top:auto→4px`(칩을 안내문 밑으로 복귀) + `[data-testid="stTabs"]` 라이트/다크 토큰 스타일.
- `tests/test_dm_tabs.py`: `_render_main`/`_dm_tab_seg` 테스트 5건 → `_render_dm_header`/`_render_jobs_split`/st.tabs eager-render 검증으로 교체.

**검증:** playwright 실측 — "출처설정"·"키워드" 연속 탭클릭 → `XRUN:APP` 0건 추가(클라이언트사이드 확정) + window 플래그 생존 + 5탭 모두 렌더 + 칩 안내문 밑 배치(스크린샷). pytest **774 passed** · 금지패턴 0.

**남은 것:** 사이드바 메뉴 이동(`?app_area=`)·출처 토글(`?src_action=`)·"지금 뉴스 수집"(`?refresh=now`)·SOLA 작업실 quick-action·보드 액션 등은 아직 앵커(문서 reload). 다음 단계로 위젯화(소켓 rerun) 하면 마지막 흰 깜빡임도 제거. (st.tabs 와 함께 쓰려면 in-tab 액션은 반드시 위젯이어야 탭 상태 유지.)

**라이브 검증 환경 메모:** `pip install playwright` 후 버전 불일치 → `executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome"` 로 기존 빌드 직접 지정. 서버는 `--server.fileWatcherType none` 로 띄우고 코드 변경 시 재시작. 페르소나(`data/persona/profile.json`) 있으면 온보딩 모달 회피. 데이터관리 화면은 첫 렌더가 느리니 7s+ 대기.

---

## 2026-06-04 · UX: 전체 흰 깜빡임 제거 (fragment 스코프) — Phase 1+2

**브랜치:** `claude/kind-volta-IWxix`.

**맥락:** "버튼/메뉴/탭 누를 때마다 전체가 하얗게 깜빡였다 다시 뜸. 기존 렌더 유지하고 변동분만 갱신해라. 예) 채팅 예시칩=입력창만 채워야, 데이터관리 탭=그 탭만 바뀌어야." → 계획 후 사용자 선택 "예시 2개 먼저(Phase 1+2)".

**근본 원인(확정):** 앱의 거의 모든 네비가 `<a href="?param=">` 앵커 → 클릭 = **브라우저 문서 전체 reload**(빈화면→프론트 재부팅→CSS 재주입→리페인트)가 흰 깜빡임. `@st.fragment`/`st.tabs`/`st.pills` 한 곳도 미사용(1.58 인데). 상단 검색만 `st.query_params+st.rerun`(소켓, 리로드 아님) 써서 정답 방향이었음.

**핵심 전략:** query-param 소비자(`_consume_*`)·테스트 계약·invariant 는 유지하고 **트리거만** 앵커→위젯/fragment 로, **변하는 영역만** fragment 로 감쌈.

**수정:**
- **Phase 1 채팅칩**(`chat_panel.py`): 추천질문 `?sola_prefill=` 앵커 → 입력창 위 `st.pills`, pill+form 을 `@st.fragment _chat_composer` 로. 칩 클릭=fragment rerun→`_apply_pending_prefill` 가 입력창만 채우고 `__reset_pills` 로 선택 해제(편집/재선택 안 덮임). 북마크 URL 은 `_consume_prefill` 유지.
- **Phase 2 데이터관리 탭**(`data_management_v2.py`): `{{DM_TABS}}` 앵커 바 제거(""), 그룹·하위탭 = `st.segmented_control`×2, 본문 전체 `@st.fragment _dm_body_fragment` → 탭 전환=fragment rerun(본문만, 채팅·topbar 안 건드림). 본문은 기존 `_render_main`(활성 탭 lazy) 유지. `_dm_sync_tab_from_query` 가 `?dm_grp/?dm_tab`(출처토글·상단검색) → 위젯 세션 1회 동기화. legacy `_dm_tabs_html/_dm_groups_html/_dm_tab_href` 보존(테스트·호환).
- **다크 가독성**(`streamlit-overrides.css`): Streamlit 이 pills·segmented_control 비활성 배경을 정적 라이트로 박아 다크에서 흰 글자가 흰 배경에 묻힘(playwright 로 확인: inactive `color #F1F5F9` on `bg #F3F5F8`). `.st-key-side_chat_suggest`/`.st-key-dm_tabbar` 스코프 토큰 강제로 라이트·다크 모두 노출.

**검증:** pytest **775 passed**(빈키워드/탭 단언 갱신 + fragment 탭전환 e2e 3건·`_apply_pending_prefill` 2건 추가) · 금지패턴 0 · **playwright 실측**: 칩 클릭→textarea 정확 채움 + `window` 플래그 생존(=문서 reload 없음), "키워드" 탭 클릭→kw 본문 전환 + 플래그 생존. 두 화면 다크 스크린샷 라벨 정상.

**핵심 함정(재학습 방지):**
- **`<a href="?x">` = 풀 문서 reload(흰 깜빡임)**, `st.query_params=…;st.rerun()`·위젯 상호작용 = 소켓 rerun(리로드 아님). 부분 갱신은 `@st.fragment`(그 조각만 rerun)·`st.tabs`(클라 전환)·`st.pills/segmented_control`(fragment 안). on_click[I-3] 금지는 fragment 내 위젯+`st.rerun(scope="fragment")` 로 준수.
- **native pills/segmented_control 은 다크에서 흰배경 하드코딩** → 컨테이너 key 클래스(`.st-key-<key>`)로 토큰 강제 필요(입력창·드롭다운 다크화와 동류).
- segmented_control single 모드는 **활성 세그 재클릭 시 None(해제)** 반환 → 위젯 재생성 전 유효값 보정해 '탭 빔' 방지.
- AppTest 는 `st.pills/segmented_control` 을 이름으로 노출 안 함(`at.get("pills")`=0) → 세션키(`_dm_tab_seg`) 세팅+본문 단언으로 검증. `at.exception` 은 빈 `ElementList()` 가 정상(no error).

**다음 단계(미진행 — 사용자 결정 대기):** Phase 3(사이드바 `?app_area=` nav→소켓 rerun, 메인 영역 fragment) · Phase 4(보드 CTA·`kw_action`·`src_action`·`?sola_action=` 등 잔여 앵커→위젯/fragment, I-19 CTA 스타일 회복). 효과 확인 후 진행.

---

## 2026-06-04 · "지금 뉴스 수집" — 빈 페르소나 폴백 + 버튼 개명

**브랜치:** `claude/kind-volta-IWxix`.

**맥락:** "지금 새로고침 누르면 수집이 바로 되는 거 아냐? 수집이 안 돼." + "버튼을 '지금 뉴스 수집'으로 바꿔" + (질문 후 결정) "관심사 비면 '자동화'·'AI' 두 키워드로 수집하고 키워드 무관 소스도 수집해."

**원인 규명(실측):** `collect_batch(['용접'])` 직접 실행 → ① 네이버·구글·AI Times·오토메이션월드 **전부 403**(심지어 `example.com` 도 403 → 환경 egress 프록시 차단, 코드 무관 = 위 🚩 라이브 차단과 동일). ② 이 컨테이너 페르소나는 부서만 있고 **관심사 키워드 0개** → `_consume_refresh_if_any`/`consume_kw_action_if_any` 의 `if not kws and not extra_feeds:` 가드가 **수집을 통째 스킵**(캐시만 비움) → "버튼 눌러도 수집 안 됨"의 직접 원인.

**수정:**
- `ui/board_v2.py`: `DEFAULT_COLLECT_KEYWORDS=("자동화","AI")` + `_collect_keywords_with_default(persona)->(kws, used_default)` 추가(관심사 비면 폴백). `collect` 분기에서 스킵 가드 제거 → 항상 `collect_batch` 호출(tech·RSS 는 키워드 무관 수집). 토스트 폴백 시 "기본 키워드(자동화·AI)" 표기.
- `ui/data_management_v2.py`: `_consume_refresh_if_any` 동일하게 폴백+항상 수집. 버튼/툴팁/빈상태/런로그 라벨 **"지금 새로고침"→"지금 뉴스 수집"**, trigger 라벨 `수동 새로고침→수동 수집`.
- 테스트: 빈 키워드 skip 단언 3건(`test_collect_trigger`·`test_v2_screens`·`test_kw_actions`) → 폴백 호출(`call_args.args[0]==["자동화","AI"]`) 검증으로 교체, `test_dm_cleanup` 라벨 단언 갱신.

**검증:** pytest **770 passed** · 금지 패턴 0 · py_compile OK.

**주의:** ②는 코드로 고쳐 빈 페르소나에서도 버튼이 수집을 *실행*한다. 단 ①(환경 403)이 남은 환경에서는 실제 기사 0건 + error 토스트가 정상 동작이다 — 인터넷 열린 배포에서 실수집된다.

---

## 2026-06-04 · 오늘의 보드 헤더↔사이드바 간섭 수정 (전 화면 통일)

**브랜치:** `claude/kind-volta-IWxix` (origin/main `2862c20` 기준).

**맥락:** "오늘의보드 화면 상단 메인헤더가 사이드바와 간섭되어 가려진다. 다른 화면들과 통일. + 나머지 화면 UI 점검."

**원인:** `board.css` 가 `.db-topbar { position: fixed; left:0; right:0; z-index:50 }` 로 재정의 → 보드에서만 헤더가 풀폭 fixed 로 튀어 네이티브 `st.sidebar` 와 겹침. 구 v2 셸(고정 패널 `.app-side`/`.app-sola`) 잔재. 다른 화면은 전역 `shell.css` 의 `position: static` in-flow 헤더 사용(정상).

**한 일:** board.css 상단 stale 블록 160줄(fixed topbar override + `.db-topbar-*` 중복 + `.v2-scroll-fade`/`.app-with-*`/`.app-side`/`.app-sola`/`.hub-back`/`.db-app{padding-top}`) 삭제 → 보드도 shell.css in-flow 헤더 상속 → 5화면 헤더 완전 동일.

**검증:** playwright 전 화면 스크린샷(`verify_screens.py`)으로 board/data/insights/sola/archive 헤더 in-flow 동일 + 사이드바 겹침 0 시각 확인. 나머지 화면 UI 구성도 `[사이드바│본문(in-flow 헤더+콘텐츠)│SOLA 채팅]` 으로 일관·건강. pytest **769 passed**(CSS only).

**함정:** 화면 CSS(`screens/<name>.css`)는 전역 `shell.css` 뒤에 주입돼 **override 가능** — `.db-topbar` 같은 공유 셸 셀렉터를 화면 CSS 에서 재정의하면 그 화면만 깨진다. 공유 헤더는 shell.css 단일 소유 유지.

---

## 2026-06-04 · 잔여 백로그 — 스모크 테스트 · 모듈 분할 · 의미매칭/guard

**브랜치:** `claude/kind-volta-IWxix` (순차 PR #108~#111).

**맥락:** "잔여 항목들 진행해. 결정이 필요한건 질문해." → 결정 2건 확정 후, 남은 백로그를 위험도순으로. AskUserQuestion 으로 "모듈 분할(안전)+render 스모크" 선택받음(고위험 매칭캐시는 제외).

**한 일 (PR별):**
- **#108** SOLA UX — 채팅 단일 진입점 통합 + handoff LLM 자동 실행(위 결정).
- **#109** 의미매칭 엣지 테스트(+6: `_build_idf`/`_tfidf_vec`/`_cosine`/대칭성) + board_v2 guard 6곳.
- **#110** 화면 render() 스모크(+13) — 6화면 빈데이터 통과 + chat_context + SOLA 인계. **conftest sola_threads 격리 버그**를 스모크가 노출(CI fresh clone `FileNotFoundError`) → conftest 에 `sola_threads.SOLA_DIR` tmp 동기화 추가.
- **#111** 오버사이즈 모듈 분할 — `data_management_v2`(1623→1406) 순수 빌더를 `ui/data_management_render.py`(259) 추출, re-import 하위호환(동작 불변).

**검증:** pytest 742→**769 passed** · 금지패턴 0 · py_compile OK · CI 전부 green.

**함정:** ① 스모크는 Streamlit ScriptRunContext 없이도 위젯 기본값 반환이라 실제 render() 호출로 조립깨짐을 잡음(brittle 아님). ② `from config import X` 한 모듈은 conftest 가 개별 동기화해야 tmp 격리됨(sola_threads 누락이 스모크로 드러남). ③ 모듈 분할은 re-import(`# noqa: F401`)로 기존 참조 보존 — 순수(st·I/O 없는) 빌더만 이동.

**남음:** board_v2 분할(데이터-결합 빌더라 신중), 고위험 매칭 공유 캐시(#2, 캐시키 staleness), 차단(임베딩 RAG·네이버 실HTML·라이브 수집).

---

## 2026-06-04 · SOLA UX — 채팅 단일 진입점 통합 + 인계 자동 실행

**브랜치:** `claude/kind-volta-IWxix` (origin/main `e26b2dd` 기준).

**맥락:** "잔여 항목들 진행해. 결정이 필요한건 질문해." → 백로그 중 결정 필요 2건을 `AskUserQuestion` 으로 확정(SOLA 2-채팅=**채팅으로 통합**, handoff 배너=**LLM 자동 실행**) 후 구현.

**한 일:**
- **SOLA 채팅 통합** — 중앙 작업대 액션 3개(제안서 생성·뉴스 요약·새 대화)를 우측 채팅 상단 **빠른 작업** 칩으로 흡수. `chat_panel._quick_actions_html`(SOLA area 한정, `?sola_action=` 링크, dept/lv3/from 보존) + `sola_workshop_v2._consume_sola_action_from_query_if_any`(→ 기존 pending flag 매핑). 작업대 중복 버튼(`wb_gen_proposal`/`wb_summarize`/`wb_new_thread`) 제거 → 안내로 대체.
- **handoff 자동 실행** — 휴면이던 `_do_ask_prefill` 를 `_auto_run_handoff_if_any` 로 배선: `?from=` 인계 도착 시 prefill 있으면 1회 자동 새 thread + LLM 전송(`_handoff_signature` 중복차단, 빈prefill 무시). 배너에 "✓ 자동 검토 시작" confirm 줄.
- CSS — `.side-chat-actions`/`.side-chat-action`(primary 칩) + `.ws-brief-autorun`.
- 테스트 +8(chat_panel 2 · sola_composer 6).

**검증:** pytest **742→750 passed** · 금지패턴 0 · py_compile OK.

**함정:** `?sola_action` 만 소비하고 dept/lv3/from 은 보존해야 제안서 생성이 인계 컨텍스트를 그대로 씀. `_handoff_autorun_done` 시그니처는 brief 의 경우 session `_board_brief_items` 제목까지 포함해야 같은 from 다른 컨텍스트를 구분.

---

## 2026-06-03 · 저위험 잔여 마무리 — match vectorize · run_log trim · insights guard

**브랜치:** `claude/kind-volta-IWxix` (PR #106 머지 후 origin/main `72488da` reset → 재사용).

**한 일:**
- **2.3** `match.score_matches`: iterrows 4곳 → `to_dict("records")` 1회(결과 불변).
- **2.4** `run_log._trim`: 사이즈 게이트(size < max_keep*80B → 읽기 스킵).
- **#3 guard 확대**: `insights_v2` 데이터-로드 3곳 → `ui._safe.guard`. (insights/board 의 `except: return empty` graceful 빈-상태 except 는 의도적 유지 — guard 부적합.)
- tests: run_log trim +2.

**검증:** pytest 740→**742 passed** · 금지 0 · compile OK. REFACTOR_PLAN ⚪ 2.3/2.4 ✅.

**남은 백로그(전부 결정/차단/대규모):** #2 매칭 결과 공유 캐시(캐시키 위험) · oversized 모듈 분할 · render 스모크(brittle) · 작업실 2채팅(UX 결정) · handoff LLM(결정) · 네이버 실HTML fixture·RAG(네트워크 차단) · PR #49(디자인 결정). → **저위험 actionable 백로그 소진.**

---

## 2026-06-03 · 개선 백로그 잔여 — LLM 회복력·템플릿 검증·guard 확대

**브랜치:** `claude/kind-volta-IWxix` (PR #105 머지 후 origin/main `5c370a1` reset → 재사용).

**한 일:**
- **4.4** `sola.client`: OpenAI 클라이언트 `timeout=45s`+`max_retries=2` 명시(행 걸린 백엔드가 rerun 멈추는 것 방지).
- **4.3** `tests/test_template_placeholders.py`: 4화면 `{{TOKEN}}` 전수 소비 정적 교차검증(드리프트→silent 빈 렌더 차단).
- **#3 guard 확대**: `board_v2` 데일리 브리핑 뉴스/작업 로드 2곳 → `ui._safe.guard`.

**검증:** pytest 735→**740 passed**(+5: client 1·placeholder 4) · 금지 0 · compile OK. REFACTOR_PLAN 백로그 4.3/4.4 ✅.

**다음(남은 백로그):** #2 매칭 결과 공유 캐시 · #3 board/insights ~38 site guard 롤아웃 · render 스모크·네이버 실HTML fixture·작업실 2채팅·handoff LLM·oversized 분할 · 외부(RAG·#49).

---

## 2026-06-03 · 개선 백로그 최우선 3건 착수 (관측성·성능)

**브랜치:** `claude/kind-volta-IWxix` (PR #104 머지 후 origin/main `fc98fb2` reset → 재사용).

**한 일 (3 커밋):**
- **#1 수집 degraded 가시화** — `data_management._collect_alert_html`(최근 런 실패=빨강/24h+ 정체=주황 상단 배너, run_log 기반) + `daily_scrape --fail-on-empty`(0건 exit 1, `scrape-daily.yml` ON). 조용한 starvation 을 화면·CI 양쪽에 표면화.
- **#2 `load_news_for_days` 디스크 재읽기 memo** — 디렉토리별 키 + 일별 mtime/parquet수 시그니처(새 수집 시 자동 무효화) + `.copy()` 반환. 호출부 34곳 무변경. (매칭 결과 캐시 2.1 은 보류.)
- **#3 `ui/_safe.guard(label)`** — silent except 를 WARN+스택트레이스 로깅으로 표면화하는 컨텍스트매니저. `data_management` 데이터-경로 5곳 적용(패턴 확립, ~40 site 롤아웃은 후속).

**검증:** pytest 719→**735 passed**(+11: 배너4·fail-on-empty2·memo1·guard4) · 금지 0 · compile OK. REFACTOR_PLAN 백로그에 ✅/부분완료 반영.

**다음:** #2 매칭 결과 캐시 · #3 board/insights 롤아웃 · RAG/PR #49(외부).

---

## 2026-06-03 · docs 최신화·정리 + 개선 백로그 발굴

**브랜치:** `claude/kind-volta-IWxix` (PR #103 머지 후 origin/main `e87f6e7` reset → 재사용).

**한 일 (docs only):**
- README 셸 설명 최신화(구 `app-side`/`app-sola` 고정패널 → 현행 네이티브 사이드바 + `[2.3,1]` 중앙/우측 채팅) · 테스트 수 720+.
- SESSIONS '다음 세션 시작점' 블록을 현재(`main e87f6e7`·#97~#103 누적·완성도 결론)로 갱신.
- REFACTOR_PLAN 에 `post-M3 완성도 하드닝(완료)` + **개선 백로그 16건**(우선순위) 캡처.
- (CHANGELOG `## [Unreleased]` "중복"은 ```md 코드펜스 안 템플릿이라 실제 중복 아님 — 무수정.)

**개선 백로그 최우선 3 (forward-looking 리뷰 발굴):**
1. **수집 degraded 가시화** — cron 0건/실패가 화면·CI 무신호 → `daily_scrape`/workflow `exit 1` + `data_management` 상단 경고 배너(`run_log.daily_status` 활용). [high·S]
2. **매칭/뉴스 캐시 통합** — `score_matches`(O(news×tasks)) 4곳 독립 재계산 + `load_news_for_days` 렌더당 다수 재읽기 → 공유 캐시. [high·M]
3. **silent except 로깅 가드** — ~45개 `except: pass` 무신호 → `ui/_safe.guard()` WARN 로깅. [high·M]

**검증:** 코드 무변경 → pytest **724 passed** 유지 · 금지 0.

**다음:** 위 백로그 1~3 착수(지시 시) · RAG/PR #49 는 외부 의존/결정.

---

## 2026-06-02 · 완성도 점검 잔여 — A3 문서/코드 드리프트 + 다크 sparkline

**브랜치:** `claude/kind-volta-IWxix` (PR #102 머지 후 origin/main `b318881` reset → 재사용).

**한 일:**
- **A3** 문서를 코드에 맞춤 — ARCHITECTURE/INVARIANTS 가 "SOLA 작업실=풀스크린·우측 채팅 미렌더"라 했으나 app.py 는 모든 화면 통일로 작업실도 `render_side` 렌더. 코드가 현재 의도라 문서 정정(작업실 예외 제거 + `[2.7,1]`→`[2.3,1]`). *작업실 채팅 억제를 원하면 코드 변경 필요 — 명시함.*
- **다크 sparkline** — `_hist_html(dark)` 파라미터로 14일 수집량 SVG 색을 테마별 분기(data-URI 라 CSS var 불가). 호출부가 ui_prefs 테마 전달.

**검증:** pytest **724 passed** · 금지 0 · compile OK · SVG 색 분기 스모크.

**남은(블록/결정):** 임베딩 RAG(백엔드 부재) · PR #49 디자인 판단 — 둘 다 사용자 결정/외부 의존.

---

## 2026-06-02 · 시스템 완성도 점검 + 잠재 결함 4건 순차 수정

**브랜치:** `claude/kind-volta-IWxix` (PR #101 머지 후 origin/main `1e83b2a` reset → 재사용).

**점검(정량 + 서브에이전트 심층):** 70 모듈·69 테스트·13.6k LOC. 금지패턴 0·TODO/bare-except/print 0·html.escape 195·compile OK. 3대 축 end-to-end 완전 배선, graceful degradation(무데이터/LLM미설정/네트워크실패) 우수. → **성숙한 production-leaning**. 결함은 *broad except 에 가려진 잠재 데이터-계약 버그* 위주.

**수정(4건 순차, 4커밋):**
- **C1/C2/D4** `news_db`: `collected_at` 을 `_ARTICLE_COLS` 에 추가(저장 시 enriched_at→published_at 폴백) — board 데일리 브리핑이 없는 컬럼을 select→KeyError→broad except 로 삼켜 매칭경로가 **조용히 죽어** '최근3건'만 돌던 것 부활. `fillna("")` 로 null→`""`(`"nan"` `<img>` 차단).
- **B4** 데이터-계층 silent 실패 3곳 로깅(board 매칭조인·news_db 깨진 parquet·enrich 파싱). UI 렌더 except 122개는 best-effort 라 제외.
- **D1/D2** archive 정적 목업을 `archive_main.html` 에서 직접 삭제(23KB→3.6KB) + 런타임 `_strip_oa_mockups` 제거 — 마커 드리프트 시 목업 재등장 위험 해소.
- **C3/C4** SQLite: ingest 동기화 실패를 `IngestResult.sqlite_error`+로깅으로 표면화(stale 분기 위험) · `task_defs_db._migrate`(user_version + 누락 컬럼 ALTER) forward-마이그레이션.

**검증:** pytest 719→**724 passed**(+5) · 금지 0 · compile OK.

**잔여(점검 발견·미수정):** A3 문서/코드 드리프트(ARCHITECTURE 는 SOLA 작업실 채팅패널 억제라는데 app.py 는 둘 다 렌더) · sparkline SVG 테마색 · 임베딩 RAG(백엔드 부재) · PR #49 디자인 판단.

---

## 2026-06-02 · 다크 모드 정교화 (2차) — 작업정의 뷰 · 콜아웃 배너

**브랜치:** `claude/kind-volta-IWxix` (PR #100 머지 후 origin/main `fefdb66` reset → 재사용).

**진단(playwright 다크 — 인사이트/작업실/보관함 추가 확인):** 메인 5화면은 1차로 다크 정상. 남은 건 **light-island 컴포넌트** — ① `task_def_manage` 상세/카드 뷰 전부 고정 라이트(자체로는 읽히나 다크 페이지에 밝은 섬) ② LLM 미설정/브리프 콜아웃 배너(amber/blue 고정).

**한 일:** `task_def_manage.py` 스타일 상수 전체 토큰화(라이트값 동일→라이트 무변경) · `_DARK_CSS` 에 `.app-llm-banner`/`.ws-brief-handoff` 다크 틴트 변형.

**검증:** pytest **719 passed**(test_task_def_manage 포함) · 금지 0 · compile OK.

**다음:** sparkline SVG 테마색(data-URI, 현재도 가독은 됨) · 임베딩 RAG(백엔드 시) · PR #49.

---

## 2026-06-02 · 다크 모드 정교화 (1차) — 입력창·카드 배경

**브랜치:** `claude/kind-volta-IWxix` (PR #99 머지 후 origin/main `715445d` reset → 재사용). 메뉴 "풀 다크" 1차.

**진단(playwright 다크 캡처):** 대부분 다크 OK 였으나 ① **입력창(검색·채팅)이 흰색** — textarea 자체는 다크인데 baseweb 래퍼 `base-input` 가 `rgb(255,255,255)` ② **보드 인사+KPI 카드(.db-greet) 등 흰 카드** — 화면 CSS 고정 `#FFFFFF` 그라데이션.

**한 일:**
- `styles._DARK_CSS`: baseweb 입력 래퍼(`base-input`/`input`/`textarea`) 다크화 추가.
- 화면 CSS 8곳(board·card·archive·sola) 흰 카드 배경 → `var(--surface-card)`/`var(--surface-soft)`/`var(--surface-inset-bg)` 토큰화. 라이트값 동일이라 라이트 무변경.

**검증:** 다크 캡처(입력창·카드 다크 확인) + 라이트 캡처(회귀 없음) + textarea 래퍼 `255→15,23,42` 측정. pytest **719 passed** · 금지 0. ⚠ `_DARK_CSS`(Python 상수) 변경은 서버 재시작 필요(모듈 캐시), CSS 파일은 리로드로 즉시 반영.

**다음:** 잔여 인라인 hex(상태 배지·텍스트색)·sparkline SVG 테마색 · PR #49.

---

## 2026-06-02 · 의미유사도 매칭(TF-IDF) + 수집 헬스 sparkline 런 오버레이

**브랜치:** `claude/kind-volta-IWxix` (PR #98 머지 후 origin/main `23ceb7f` reset → 재사용). 메뉴 3·4번.

**한 일 (2 enhancement, 1 PR):**
- **#4 sparkline 런 오버레이** — `run_log.daily_status(days)`(일별 ok/fail/None, 실패 우선) + `data_management_v2._runstatus_strip_html`(14일 볼륨 바 아래 14칸, 토큰 색). 볼륨=news_db '몇 건' vs 스트립=run_log '그날 런 성공?' → cron 조용한 실패 구분. 런 없으면 빈 문자열.
- **#3 의미유사도 하이브리드** — `match.score_matches(semantic_weight=)` 추가(기본 0=하위호환). >0 이면 TF-IDF 코사인을 `weight*cos` 가산(흔한어 낮게·희소어 높게+길이정규화 → 주제 가까운 매칭↑). 보드·인사이트·작업실·opportunity 가 `DEFAULT_SEMANTIC_WEIGHT`(4.0)로 켬. **신경망 임베딩(RAG)은 백엔드(groq 미지원·네트워크 차단) 부재로 보류** → `_tfidf_vec`/`_cosine` 만 교체하면 임베딩 확장 가능(인터페이스 유지).

**검증:** pytest 711→**719 passed**(test_match_semantic +4, test_run_log/collect_health +4) · 금지 패턴 0 · py_compile OK. 호출처 테스트 무파손(board mock·default-arg 직접호출·tolerant).

**다음:** 풀 다크 정교화(매트릭스/히트맵 색·sparkline SVG 토큰화) · 임베딩 백엔드 생기면 RAG 로 교체 · PR #49.

---

## 2026-06-02 · UI 수정 — 사이드바 펼치기 버튼 복구 + 채팅 패널 (안내·추천·입력)

**브랜치:** `claude/kind-volta-IWxix` (PR #97 머지 후 origin/main `8f88e32` 으로 reset → 재사용). harness 지정 단일 브랜치.

**맥락:** 사용자 보고 2건 — ① 사이드바가 메인과 겹치고 한번 접으면 펼치기 버튼을 못 찾음 ② 채팅 패널 표시 영역이 좁고, 안내+추천이 채팅 한번에 사라지며, 추천 프롬프트를 눌러도 입력창에 안 들어감.

**진단(playwright 실측, 사전설치 chromium):** ≥768px 겹침 0 / <768px 만 Streamlit 오버레이. 접으면 `stExpandSidebarButton`(헤더 toolbar 안)·`stHeader` 가 우리 `display:none` 으로 사라져 펼치기 불가. 추천 질문은 정적 `<span>` 이라 클릭 무반응.

**한 일:**
- `streamlit-overrides.css`: `stHeader` 통째 `display:none` → absolute·height:0·투명·pointer-events 통과 + toolbar 노이즈만 숨김 + `stExpandSidebarButton` 좌상단 고정. 접힘 시 `.db-topbar` 46px 시프트(버튼이 첫 글자 안 가림). 채팅 `.side-chat-scroll/-intro/-chip` 토큰 CSS.
- `chat_panel.py`: 안내+추천을 항상 스크롤 최상단(`render_side` 가 intro+메시지를 한 컨테이너로), 추천 chip → `?sola_prefill=` 링크 + `_consume_prefill`(위젯 생성 전 입력창 값 주입, query_params 패턴), 버블 폭 92%·토큰 색.
- `app.py`: 채팅 컬럼 `[2.7,1]→[2.3,1]`.
- `tests/test_chat_panel.py`(+3: chip 링크·prefill 주입·no-op).

**검증:** playwright 라이브 — 펼치기 버튼 보임·클릭·재펼침 PASS · 추천칩→입력창 PASS · 대화 후 안내 최상단 유지 PASS. pytest 708→**711 passed** · 금지패턴 0 · py_compile OK.

**다음:** PR 리뷰/머지 · 풀 다크 정교화(이번에 채팅 토큰화 일부 완료) · RAG · PR #49.

---

## 2026-06-02 · 수집 헬스 고도화 — 최근 N회 런 미니 타임라인 (PR #97)

**브랜치:** `claude/kind-volta-IWxix` (harness 지정 단일 브랜치 — PR #97 에 누적). 중복 PR #95·#96(verify CLI) close.

**맥락:** '수집 헬스' 1행이 마지막 런만 보여줘 연속 실패·런 누락 패턴이 안 보이던 한계 보완.

**한 일:**
- `data_management_v2._run_timeline_html()` 신규 — 최근 12회 런을 미니 막대 타임라인으로(높이=기사량, 색=ok 초록/오류 주황, hover=트리거·시각·건수·상태). `run_log.load_runs()` 기반 → "cron 돌았지만 0건"(최소 높이 셀) vs "런 없음"(셀 부재) 구분. div/span + 시맨틱 토큰(다크 추종), SVG 아님.
- `_hist_html()` dict 에 `"runs"` 키 합류(기존 60초 캐시 + 새로고침 무효화 재사용) · 템플릿 `{{HIST_RUNS}}` · CSS `.dm-runs/.dm-run-*`.
- **볼륨 14일 sparkline 은 news_db 유지** — run_log 14일 히스토리 부재로 즉시 전환 시 빈 차트 회귀. 볼륨=news_db, 런 헬스=새 타임라인으로 역할 분리.
- `tests/test_collect_health.py`(+4) · `test_dm_tabs.py` mock 에 `"runs"` 반영.

**검증:** pytest 704→**708 passed** · 금지 패턴 0 · py_compile OK · 스모크(prepare_screen_html 통과·셀 보존) 확인.

**다음:** run_log 14일 축적되면 sparkline 에 일별 런 성공/실패 오버레이 · 풀 다크/RAG · PR #49 디자인 판단.

---

## 2026-06-02 · 라이브 수집 재검증 시도 + 네이버 파서 회귀 테스트

**브랜치:** `claude/kind-volta-IWxix` (origin/main `6d6f5dc` 기준, behind/ahead 0)

**맥락:** "개발 준비" 후, 사용자가 "전체 도메인 허용 + 새 세션"을 했다며 네이버/구글 키워드검색·AI Times·오토메이션월드의 제목/본문전체/사진 라이브 수집 검증을 요청.

**한 일:**
- **네트워크 상태 진단** — `build_session().get()` 으로 5개 타깃 호스트 + 대조군 점검: pypi.org만 **200**, 나머지(`search.naver.com`/`news.google.com`/`www.aitimes.com`/`automation-world.co.kr`/`www.google.com`/`example.com`) 전부 **403 `Host not in allowlist`**. WebFetch 우회도 동일 403. → 이 컨테이너는 정책 변경 전 환경(네트워크 정책은 환경 생성 시 고정). **라이브 수집 불가**로 확정.
- **오프라인 파서 검증** — 라이브 대체로 코드가 제목/본문전체/사진을 추출하는지 확인: `fetch_article` 합성 HTML 시연(본문 문단 결합·`dataLayer`/`무단전재` 노이즈 제거·og:image 추출 OK), 구글 RSS 파서 제목/언론사/썸네일 분리 OK. 관련 회귀 39건 green.
- **`tests/test_naver.py` 신규(+6)** — 4소스 중 유일하게 단위테스트 없던 네이버 리스트 파서를 고정(제목·언론사·날짜·요약 / `n.news.naver.com` 링크 우선 / `data-src` 썸네일 / max_results / 빈 키워드 / HTTP 오류 전파). SESSIONS 가 지적한 '라이브 1순위 점검 대상' 갭 해소.

**검증:** pytest 698→**704 passed** · 금지 패턴 0 · py_compile OK.

**다음:** 정책=전체 허용 환경의 **새 세션**에서 라이브 수집 재검증(네이버 리스트 파서 실HTML 대조 1순위) · 중복 PR #95/#96(verify CLI) 하나로 정리 · 14일 sparkline run_log 기반 · 풀 다크/RAG.

---

## 2026-06-02 · Phase F — 수집 관측성 (런 로그 + 수집 헬스)

**브랜치:** `claude/laughing-pascal-pCbik` (PR #92 머지 후 origin/main `e184f50` 으로 reset → 깨끗한 베이스)

**맥락:** Phase 3(데드 청산) 머지 후 다음 단계. 매일 cron 수집이 **조용히 실패해도 알 길이 없던** 문제 해결.

**한 일:**
- `store/run_log.py` 신규 — `collect_batch` 의 `CollectionReport` 를 run_id·시각·트리거·소스별 건수·성공/실패·duration 으로 구조화해 `data/logs/runs.jsonl` 에 append. `load_runs`/`latest_run`/`entry_from_report`(순수). `config.DATA_ROOT` 호출 시점 참조로 conftest 격리 호환.
- 수집 3경로에 `record_run` 연결 — cron(`scripts/daily_scrape.py`, duration 측정)·데이터관리 새로고침(manual)·보드 수집(board). 모두 try/except 로 격리(로깅이 수집을 못 깨게).
- 데이터 관리 수집잡 최상단에 '수집 헬스' 1행(`_collect_health_li`) — 최근 런 성공/건수/시각/트리거/오류 소스. 런 없으면 빈 문자열(기존 무변경).
- `tests/test_run_log.py`(+7)·`tests/test_collect_health.py`(+3).

**검증:** pytest 686→**696 passed** · 금지 패턴 0 · py_compile OK.

**다음:** 14일 sparkline 을 run_log 기반으로 · 풀 다크/RAG · PR #49 디자인 판단.

---

## 2026-06-02 · Phase 3 — 데드 코드 삭제 (전체 완료) + PR 정리 (PR #91 머지 후)

**브랜치:** `claude/laughing-pascal-pCbik` (origin/main `7debc32` 기준)

**맥락:** 개발 환경 세팅·진행점검 후, 추천 순서대로 ① PR #91(Phase E) 머지 ② 중복 PR #88 close ③ REFACTOR_PLAN Phase 3(데드 코드) 착수.

**한 일:**
- **PR 정리**: PR #91(enrich→매칭 가중) Ready 전환 후 squash 머지(`7debc32`) — 결정-2 완결. 중복 PR #88(리팩토링 계획서, REFACTOR_PLAN.md 로 대체) close. PR #49(TS 글래스모피즘 프로토타입)는 디자인 채택 판단 필요로 보류.
- **Phase 3 데드 코드 삭제**: production import 0 인 `ui/layout.py`·`ui/task_tree.py`·`sola/insight.py`·`sola/chat_ctx.py` 4종 삭제 + 테스트 동반 정리(`test_sola_insight` 삭제, `test_sola`/`test_preview`/`test_chat_log`/`test_task_def_upload` 수술적 편집). `sola/{propose,summarize}` 는 결정-1 A 부활분이라 보존, `sola/side_context` 는 orphan 이나 연결 대상으로 보존(docstring 갱신).
- **Phase 3 잔여**: `app_shell.render_app_side`/`render_app_sola`(no-op ~300줄 + 5화면 호출부 + 패널 토글 클러스터) · `chat_panel.render`(구 bottom) · `_SOLA_TEMPLATE`+`sola_main.html`(11KB) · `task_defs_db.upsert_many`(재판정→데드) · `persona_page._archive_stats` 삭제. 부수 import(ASSETS_DIR·Iterable·bookmarks·llm_model) 정리. 좌=네이티브 사이드바, 우=`render_side` 단일 경로.
- **문서 동기화**: ARCHITECTURE(트리·데드 목록)·INVARIANTS·CLAUDE 라우팅·REFACTOR_PLAN(진행표·데드 대장·Phase 3)·CHANGELOG·SESSIONS 갱신.

**검증:** pytest 702→**686 passed**(삭제 테스트 16건) · 잔여 import 0(`grep -rn`) · 금지 패턴 0 · py_compile OK.

**다음:** Phase F(수집 관측성/로깅) · 풀 다크 폴리시/RAG 매칭 · PR #49(글래스모피즘) 디자인 판단.

---

## 2026-06-02 · Phase E — enrich LLM 키워드 매칭 가중 (PR #90 머지 후 신규)

**브랜치:** `claude/charming-sagan-REsgM` (PR #90 스쿼시 머지 후 origin/main `115b176` 으로 reset → 깨끗한 베이스에서 Phase E)

**맥락:** PR #90(UI 전면 재정비 A~D) 스쿼시 머지 완료 → 프로덕션 배포. 후속으로 결정-2(A) Phase E.

**한 일:**
- `store/match.score_matches` — enrich `keywords_llm` 가중 보너스(고유 매칭 1건당 `_LLM_KW_WEIGHT`=2.0). base 매칭 보존, enrich 안 된 기사 무영향(후방호환), LLM 키워드-only 매칭도 발견.
- `tests/test_match_enrich_weight.py` (+5).

**검증:** pytest 702/702 · 금지 패턴 0 · py_compile OK.

**다음:** Phase F(수집 관측성/로깅) · 풀 다크 폴리시 · 또는 의미기반 매칭(임베딩, 블루프린트 Phase B).

---

## 2026-06-01 · Phase D — 설정 메뉴(테마·글자 크기) · 6대 요구 완결

**브랜치:** `claude/charming-sagan-REsgM` (PR #90 누적)

**한 일:**
- `store/ui_prefs.py`(theme·font 영구화) + `styles.inject_user_prefs()`(테마/글자 zoom 주입, app.py 호출) + `persona_page._render_display_settings`(🎨 표시 설정 라디오, 변경 즉시 적용).
- 테마: 라이트/다크/오션/선셋. 글자: 작게/보통/크게(zoom).
- **다크 활성화**: Streamlit 네이티브 위젯이 config(정적 라이트) 종속이라 런타임 다크가 어려운 점을, 토큰 일괄화(화면 CSS `#fff`×89·`#E5E7EB`×6 → 토큰) + 네이티브 위젯/사이드바/채팅 다크 오버라이드 + 내 인라인 색 토큰화로 해결.
- `tests/test_ui_prefs.py` (+7).

**주의:** 풀 다크는 화면 CSS 가 카드 배경을 고정 `#fff` 로 쓰던 게 원인이라, `#fff→var(--surface-card)` 일괄 치환(라이트 무변경)으로 토큰화해야 했다. zoom 은 stMain·사이드바에 적용(채팅 100vh 와 공존 — overflow 스크롤).

**검증:** pytest 697/697 · 금지 패턴 0 · playwright 라이트/다크/오션/큰글자 4종 육안 — 다크 일관·라이트 무변경.

**사용자 6대 요구 완결:** ①연계(C) ②좌사이드바+우채팅(A) ③3영역(A) ④죽은버튼(C+SVG) ⑤컨텐츠정리(C) ⑥설정(D).

**다음:** PR #90 정리/머지 검토(매우 큼) · 또는 Phase B 후속(제안서 고도화)/E(매칭 가중치)/F(관측성). 잔여: 풀 다크의 일부 차트색·SVG 인터랙션(img 변환분).

---

## 2026-06-01 · Phase C-4 — 보관함 정리 (Phase C 완료)

**브랜치:** `claude/charming-sagan-REsgM` (PR #90 누적)

**한 일:**
- `archive_v2._strip_oa_mockups` — 죽은 컨트롤 스트립 + 하단 "전체 산출물 45건" 표/미리보기 패널(PRO-2026·₩1.4억·결정/내보내기 — 목업) 마커 슬라이스 제거.
- 템플릿: 칸반 "+ 새로 만들기"·"+6 전월 대비" 가짜 요소 제거.
- 보존: 헤더 통계·칸반 3열(대기/채택/기각) 실데이터 + 액션. 빈 칸반 → SOLA 작업실 안내.
- `tests/test_archive_cleanup.py` (+3).

**검증:** pytest 690/690 · 금지 패턴 0 · playwright 보관함 컨트롤스트립/하단표/가짜ID 0·칸반 유지·깨진img 0.

**Phase C 완료:** 인사이트(C-1)·보드(C-2)·데이터관리(C-3)·보관함(C-4) + SOLA 작업실(재설계). 전 화면 가짜 목업 제거·죽은 링크 실네비화·심플 세로 스크롤 + 전역 SVG 함정 수정.

**다음:** Phase D(설정: 테마·폰트 — 사용자 6대 요구 ⑥) → E(매칭 가중치) → F(위생/관측성). 또는 PR #90 정리/머지.

---

## 2026-06-01 · UI 전역 버그 일괄 수정 — SVG 아이콘 깨짐 + 차트 누락

**브랜치:** `claude/charming-sagan-REsgM` (PR #90 누적)

**맥락:** "모든 화면 UI 버그들부터 싹 다 잡아." 데이터관리 4건 수정에서 얻은 교훈(`st.html` 이 인라인 svg 제거 + `;utf8,` data-URI 의 `#` 깨짐)을 전 화면 전수 진단으로 확장.

**전수 진단(playwright):** 화면별 깨진 img — board 5·data 3·insights 5·sola 3·archive 14, 그리고 `inlineSVG=0`(차트 stripped).

**한 일:**
- `ui/components.prepare_screen_html()` — ① `data:image/svg+xml;utf8,<svg…>` → URL 인코딩 data-URI(`#`→%23) ② 인라인 `<svg>` → class/style 보존 `<img>`(인코딩 data-URI). `render_screen_html()` 동반.
- `app_shell.render_topbar`(전 화면 topbar) + board/insights/data/archive 메인 렌더에 적용. 각 화면 `from ui import components as _components`.
- `tests/test_ui_components.py` (+3).

**검증:** pytest 687/687 · 금지 패턴 0 · playwright 재진단 — 5화면 모두 **broken img = 0**.

**주의:** 인라인 svg→img 변환으로 매트릭스/히트맵의 in-svg `<a>` 클릭은 사라지나, st.html 이 이미 svg 를 strip 해 **원래도 비작동**(회귀 아님)이고 시각은 복구됨. 셀 선택은 매트릭스 rank 리스트 등 외부 링크로 대체됨.

**다음:** Phase C-4 보관함(하단 목업) → D(설정 테마·폰트). 인라인 차트 인터랙션 복원이 필요하면 별도 검토.

---

## 2026-06-01 · Phase C-3 — 데이터 관리 정리 + 심플 세로 스크롤

**브랜치:** `claude/charming-sagan-REsgM` (PR #90 누적)

**한 일:**
- `_strip_dm_mockups` — 죽은 필터바·페이저 + 가짜 서브카드 3종(키워드/작업정의/출처 — 실제 탭이 대체) 마커 슬라이스 제거.
- 템플릿: 가짜 "5개 작업"→"매일 새벽 자동 실행", disabled 스케줄 버튼·가짜 news-meta(1,247 등) 제거.
- `dm-split` 세로 스택(scale.css D1). 헤더 stats·탭·수집잡·뉴스카드·CRUD 등 기능 전부 보존.
- `tests/test_dm_cleanup.py` (+3).

**주의:** `_strip_dm_mockups` 의 sub-grid 제거는 비-jobs 탭에서도 안전 — 탭 본문은 sub-grid 앞에 삽입돼 `rfind('</div>')`(dm-shell 닫힘) 슬라이스가 본문을 보존.

**검증:** pytest 681/681 · 금지 패턴 0 · playwright 데이터관리 죽은요소 0·우측 채팅 노출.

**다음:** Phase C-4 보관함(하단 45건 표·페이저·미리보기 패널·일괄/내보내기 목업 정리) → D(설정 테마·폰트).

---

## 2026-06-01 · Phase C-2 — 보드 정리 + 심플 세로 스크롤

**브랜치:** `claude/charming-sagan-REsgM` (PR #90 누적)

**맥락:** "다음 진행해. 모든 기능 살려놓고, 정리 후 화면별로 심플하게·부담 없이 세로 스크롤." → 보드(홈)에 적용.

**한 일:**
- 죽은/가짜 제거: hero CTA 2개(우측 채팅과 중복), soon 탭(강한매칭/출처별/월별), 가짜 brief-meta, "검토 대기 4건"→"자동화 기회".
- 죽은 `*.html` 링크 4개 → 실제 `?app_area=` 네비 재배선(`_clean_board_html`, 기능 보존). keyword-manager.html 링크 제거.
- 뉴스 카드 클릭→원문(`_lead_story_html`/`_side_story_html` 앵커 래핑).
- 심플 세로 스크롤: `db-greet`/`db-stories`/`db-trend` 내부 2단 그리드 → 단일 컬럼 스택(scale.css §11).
- `tests/test_board_cleanup.py` (+6).

**검증:** pytest 678/678 · 금지 패턴 0 · playwright 보드 죽은요소 0·우측 채팅 노출.

**다음:** Phase C-3 데이터관리(뉴스 검색/필터/페이저·3 서브카드 목업 정리, 기능 보존) → C-4 보관함(하단 45건 표·미리보기 목업) → D(설정 테마·폰트).

---

## 2026-06-01 · Phase C-1 — 인사이트 화면 정리 (가짜 패널·죽은 필터 제거)

**브랜치:** `claude/charming-sagan-REsgM` (PR #90 누적)

**맥락:** "다음 진행해" → Phase C(화면별 정리). Phase A 로 모든 화면에 우측 채팅(render_side)이 생기면서, 템플릿에 가짜 우측 패널이 박힌 **인사이트**가 가장 깨짐(중복). 여기부터.

**한 일:**
- `insights_v2._strip_mockup_blocks` — 렌더 시 `insights_main.html` 의 ① 가짜 `ia-sola` 우측 패널(가짜 인용·"도장 부스 #3 PoC"·액션/컴포저) ② 죽은 `ia-filters` 스트립(7/30/90일·저장한 뷰)을 마커 슬라이스로 제거. div 균형 카운트 비의존(템플릿이 원래 div 균형 느슨).
- `_ia_stats` PoC 후보 중복집계 수정(기회 셀 + pending → 기회 셀만).
- `tests/test_insights_cleanup.py` (+4: 합성 strip·noop·실템플릿 strip·PoC 제외).

**검증:** pytest 672/672 · 금지 패턴 0 · playwright 인사이트 — `.ia-sola`/`.ia-filters`/"도장 부스 #3" 0, `.side-chat-marker`(우측 채팅) 노출.

**다음:** Phase C-2 보드(hero 죽은 CTA·섹션 `→`.html 404 링크·brief-meta 목업·뉴스카드 클릭) → C-3 데이터관리(필터/페이저/3 서브카드 목업) → C-4 보관함(하단 45건 표·미리보기 목업).

---

## 2026-06-01 · SOLA 작업실 3영역 통일 — 산출물 캔버스 (사용자 지적 수정)

**브랜치:** `claude/charming-sagan-REsgM` (PR #90 누적)

**맥락:** 사용자 — "SOLA 작업실 UI가 정상이냐? 채팅/결과 구분 없고, 버튼 줄바꿈·쏠림, 어디가 채팅이고 결과인지 모르겠다. 모든 화면 좌=사이드바·우=채팅으로 통일했는데 중앙엔 콘텐츠를 보여줘야지. 다시 기획해." → 정확한 지적. Phase A에서 SOLA만 통일 셸에 편입 안 하고 자체 ws-shell(스레드│채팅│ctx) 방치한 게 원인. AskUserQuestion으로 중앙 구성 확정: **산출물 캔버스**.

**한 일:**
- `app.py` SOLA 풀폭 예외 제거 → `main_col + chat_col`(다른 화면과 동일). 우측 = `chat_panel.render_side`, 중앙 = `sola_workshop_v2.render()`.
- `render()`/`_render_main` → `_render_workbench`(중앙 캔버스): 액션바(제안서 생성/요약/새 대화) + 현재 산출물 문서 카드(`st.container(border)`+`st.markdown`) + 세션 목록 + 저장한 산출물. 자체 ws-shell 템플릿·중앙 chat_input 제거.
- `_consume_summarize_if_any`·`chat_context_block` 신규. 헬퍼(`_ctx_archive_summary`/`_render_thread_list_html`/`_composer_prefill`/`_msg_html` 등) 보존 → 테스트 무변경.

**검증:** pytest 668/668 · 금지 패턴 0 · py_compile OK · playwright SOLA 빈/인계 캡처 — [좌 사이드바│중앙 작업대│우 채팅] 분리·버튼 정렬·우측 채팅(`.side-chat-marker`) 노출 확인.

**다음:** Phase C(보드/인사이트 '제안서 생성' CTA를 이 엔진에 연결 + 가짜 목업 제거 + 죽은 버튼) → D(설정 테마·폰트).

---

## 2026-06-01 · UI Phase B — 제안서 엔진 복원 (생성 → 보관함 저장 루프)

**브랜치:** `claude/charming-sagan-REsgM` (PR #90 누적)

**맥락:** Phase A(셸)·V1 제거·프로필 카드·CI flaky 수정 후, 사용자 "다음 진행해". 계획상 Phase B(제품 핵심 루프) 차례. 전수 분석에서 P0 로 지목됐던 끊긴 제안서 사슬(보드 '채택'=빈 `content=""` 북마크 / `sola/propose`·`update_content` 데드 / 생성·저장 경로 없음)을 닫는 작업.

**한 일:**
- `ui/sola_workshop_v2`에 3함수 추가: `_consume_generate_proposal_if_any`(인계 dept/lv3 + 관련 뉴스 → `sola.propose.propose_for_task` → assistant 메시지), `_consume_save_proposal_if_any`(마지막 제안서 → proposal 북마크 실 content, thread당 안정 id=재저장 갱신, 보드 캐시 무효화), `_render_sola_action_toasts`. 헬퍼 `_related_news_df`(매칭 상위 N + 폴백).
- `_render_main` 버튼: "📝 제안서 생성"/"💬 물어보기"(핸드오프 시) + "📦 보관함에 저장"(assistant 메시지 시). render() 상단에 consumer 2개 + 토스트 연결. `from sola import propose` import.
- `tests/test_sola_propose_loop.py` (+12).

**주의/함정:** 이 샌드박스는 LLM 키는 있으나 네트워크 차단(`PermissionDeniedError: Host not in allowlist`) → `propose_for_task`가 `LLMNotConfigured`가 아닌 일반 예외를 던짐. 생성 consumer의 `except Exception`이 이를 안내 메시지+에러 토스트로 처리(무중단). (이 키+무네트워크 조합이 앞선 CI flaky의 원인과 동일.)

**검증:** pytest 668/668(신규 12) · 금지 패턴 0 · py_compile OK · playwright 핸드오프에서 '📝 제안서 생성' 노출 확인.

**다음:** Phase C(화면별 가짜 패널·죽은 버튼 정리 — 보드/인사이트 '제안서 생성' CTA를 이 엔진에 연결, archive 하단 목업 제거) → D(설정: 테마·폰트) → E(매칭 가중치) → F(위생/관측성).

---

## 2026-06-01 · UI Phase A — 셸 v3 3영역 네이티브 재건

**브랜치:** `claude/charming-sagan-REsgM`

**맥락:** 사용자 UI/UX 전면 재검토 지시(6개 항목: 화면 역할·연계, 모든 화면 좌측 사이드바+우측 채팅, 3영역 겹침, 죽은 버튼, 컨텐츠 정리, 폰트·테마 설정). 전수 분석 결과 — UI 가 "디자인 시안을 반쯤만 배선한 프로토타입"(우측 `.app-sola` 패널 전체 disabled 목업, 좌측 패널 이중화, 매직 패딩, 제안서 루프 단절, 정적 가짜 데이터 다수). 재수립 계획 Phase A~G 합의 후 **Phase A(셸 재건, 네이티브 방식)부터** 착수.

**한 일:**
- `app.py` 가 레이아웃 소유 — `with st.sidebar: sidebar.render()`(네이티브 좌측 nav 단일 소스) + `st.columns([2.7,1])` main/chat. 우측 `chat_panel.render_side()` = 실제 작동 채팅(form). SOLA 작업실만 풀폭(자체 셸).
- `app_shell.render_app_side`/`render_app_sola` → no-op(Phase C 삭제 예정). `render_topbar` fixed→static.
- `sidebar.py` 통계 3칸 추가(구 app-side 정보 보존). CSS 3종(overrides/shell/scale) 매직패딩·고정패널 제거 + 우측 컬럼 sticky.
- INVARIANTS I-13 · ARCHITECTURE 셸 도식 갱신.
- **후속(V1 잔재 제거, 사용자 지적)**: 레거시 `assets/styles.css`(1463줄, V1 디자인) 삭제 + 로드 중단 → 새로고침 FOUC 제거. 유일 라이브 소비처였던 사이드바 스타일을 `assets/v2/sidebar.css`(v2 토큰)로 이전. `persona_page` V1 `page_header`(.app-header)·`section_label` 호출 제거 → 페르소나 화면 V1 헤더 해소. (`page_header` 정의는 layout.py+test 의존이라 유지.)

**주의/함정:** `st.chat_input` 은 뷰포트 하단 전폭 고정이라 컬럼에 못 담음 → `render_side` 는 `st.form`(text_area+submit)으로 우회. 컬럼 sticky 는 `.side-chat-marker` + `[data-testid="stColumn"]:has()` 훅. 화면 템플릿에 내장된 가짜 우측 패널(insights ia-sola, archive 하단)은 Phase C 정리 대상(이번엔 셸만).

**검증:** pytest 656/656 · 금지 패턴 0 · py_compile OK · playwright 5화면 캡처로 3영역 분리·겹침 없음·SOLA 일관 육안 확인.

**다음:** Phase B(제안서 엔진 복원) → Phase C(화면별 컨텐츠 정리·죽은 버튼 와이어/삭제) → Phase D(설정: 테마·폰트) → E(매칭 가중치) → F(위생/관측성) → G(고도화).

---

## 2026-06-01 · PR #89 머지 직전 docs 정리

**브랜치:** `claude/nice-bell-eEZLj` (PR #89 — Phase 0+1a+2)

**한 일:**
- `docs/REFACTOR_PLAN.md` 끝에 **"다음 세션 시작점"** 섹션 추가 — Phase 1b(`feat-sola-propose-summarize`) / 1c(`feat-enrich-match-weight`) 의 진입 파일·UX 안 3개·완료 기준·시작 명령. 다음 세션이 이 섹션만 읽고 즉시 착수 가능.
- `docs/{DEVELOPMENT_PHASES,MILESTONE_1,TASK_DEF_PLAN,UX_QA_CHECKLIST,UX_REDESIGN_PLAN,VIBE_CODING_BLUEPRINT,WORKFLOW}.md` 7개에 redirect 헤더 1줄 추가 — 다음 세션이 stale 문서를 권위 문서로 오인하지 않도록.

**다음:** PR #89 머지 → 사용자가 새 세션 시작 시 REFACTOR_PLAN 끝 섹션만 보면 됨.

---

## 2026-06-01 · Phase 2 UI dedup (`get_persona` 승격 + `app_side_stats` 단일화)

**브랜치:** `claude/nice-bell-eEZLj` (PR #89 누적)

**맥락:** 사용자 결정 — Phase 1b/1c 는 결정-1/2 (확정: 둘 다 A) 반영을 위한 더 큰 작업이라 게이트가 없는 Phase 2(순수 dedup)부터.

**한 일:**
- `ui/app_shell.get_persona()` 신설 → 5개 v2 화면의 `_load_persona` 일괄 교체·정의 제거.
- `archive_v2._archive_stats_oa`/`insights_v2._archive_stats_ia`/`data_management_v2._archive_stats_dm` 세 사본 본문을 `board_v2._archive_stats()` 위임으로 교체(lazy import). board 의 60초 캐시(`_board_kpis`)가 단일 소스가 되어 좌측 nav 카운트와 보드 KPI 가 항상 일관.
- 위 위임으로 unused 가 된 `_score_matches`/`_score_cells`/`_news_db`/`_load_tasks` import 제거(archive/data_management).
- `ui/toast.py`/`ui/url_state.py` 는 사용처 1~2건이라 dedup 가치 적어 보류(REFACTOR_PLAN 기록).

**주의/함정:** 내가 짠 `sed` 가 호출(`_load_persona()`)뿐 아니라 정의문(`def _load_persona()`)까지 치환해 4개 파일에서 `def app_shell.get_persona() -> Persona:` 가 만들어져 SyntaxError. 깨진 def 블록을 통째 제거하는 추가 패스로 복구.

**검증:** pytest 656/656 · 금지 패턴 0 · py_compile OK · diff -114줄.

**다음:** Phase 1b(결정-1: SOLA 작업실에 propose/summarize 액션 연결) → Phase 1c(결정-2: enrich keywords → 매칭 가중치) → Phase 3(데드 코드 삭제).

---

## 2026-06-01 · Phase 1a 무논쟁 correctness (F5·F7·F11·F12)

**브랜치:** `claude/nice-bell-eEZLj` (Phase 0 와 동일 PR #89 — harness 단일 브랜치 제약)

**맥락:** 사용자 "페이즈 순차적으로 진행해". Phase 0(문서) 직후 Phase 1a(코드 correctness) 착수. 단, `docs/REFACTOR_PLAN.md` 가 실재하지 않아(이전 세션 요약에만 존재) Phase 0 문서들이 dangling 참조 상태였음 → 본 작업에서 실제 코드 재확인 후 파일로 생성(참조 복구 + source of truth).

**한 일:**
- Explore 로 F3·F5·F7·F8·F9·F11·F12 전수 재확인 → **실재 4건(F5/F7/F11/F12)**, **기각 3건(F3/F8/F9, 과진단)**.
- F5: `archive_v2` 액션 후 `st.toast`. F7: `chat_log` ts 영속+복원. F11: `upsert_many` docstring 정직화. F12: `sola_workshop._archive_stats` → `board_v2._archive_stats()` 위임(실데이터).
- `tests/test_chat_log.py` ts round-trip 2건 추가.
- `docs/REFACTOR_PLAN.md` 신규(결함 대장·데드 대장·Phase 로드맵·결정 대기).

**주의/함정:** F12 위임은 `board_v2` 를 함수 내 lazy import(모듈 로드 순환 회피). F1·F2·F4·F6·F10 은 코드에서 재현 안 돼 대장 제외.

**검증:** pytest 656/656 · 금지 패턴 0 · py_compile OK.

**다음:** Phase 2(UI dedup — `app_side_stats`/`ui/toast.py`/`ui/url_state.py`/`get_persona` 승격) 또는 결정-1·2 사용자 확정 후 Phase 1b/1c.

---

## 2026-06-01 · Phase 0 문서 정합성 (REFACTOR_PLAN D1~D4)

**브랜치:** `claude/nice-bell-eEZLj` (main `afa9e33` 기준 · 변수명 통일 #87 머지 후)

**맥락:** `docs/REFACTOR_PLAN.md` (PR #88) 의 Phase 0 — 문서가 옛 5탭 라디오·`ui/*_tab.py`·Parquet-만 시대를 가리키고 있어 Claude Code 작업 효율 저하. 결정 1·2 (A·A) 확정 후 무논쟁 항목부터 착수.

**한 일:**
- `docs/ARCHITECTURE.md` 전면 재작성 (5영역 if/elif 디스패치, v2 셸 3축, SQLite task_defs, query.py SQLite 우선 fallback, 데드 코드 명시).
- `CLAUDE.md` 라우팅 표 → 실제 `ui/*_v2.py` 경로. 절대 규칙 §2 의 `ui/*_tab.py` 문구 갱신.
- `DEV_GUIDELINES.md §2·§3` CLAUDE 와 동기화.
- `docs/INVARIANTS.md I-13` → `ui/chat_panel` 단일 진입점 (이전: 데드 `ui/layout.main_and_chat`).
- Phase 0 는 문서만, 코드 변경 0.

**주의/함정:** 지정 브랜치 `claude/nice-bell-eEZLj` 가 5/29에 갈라진 stale 상태(main 보다 38커밋 뒤, 고유 46커밋이 main 에서 이미 추월·포함). 사용자 결정에 따라 `git reset --hard origin/main` 후 작업 → force push.

**검증:** 문서만 변경. `python -m py_compile` 대상 0. pytest 영향 없음.

**다음:** Phase 1a (무논쟁 correctness: F5/F7/F8/F9/F11/F12) → Phase 2 (UI dedup) → 결정-1·결정-2 반영 Phase 1b/1c.

---

## 2026-06-01 · 변수명 통일 (roadmap_df → tasks_df) — 1차 완성 정리

**브랜치:** `refactor-tasks-df-naming` (main `f121f29` 기준 · screen-CSS #86 머지 후)

**맥락:** 사용자 "변수명 통일 → 1차 완성 정리 → 안정화". `docs/TASK_DEF_PLAN.md` 리팩토링 시점 (PR-4 직후 예약분).

**한 일:**
- import alias `load_roadmap`/`_load_roadmap` → `load_tasks`/`_load_tasks`.
- 지역 변수 `roadmap_df` → `tasks_df`, DataFrame `roadmap` → `tasks` (attr 접근 포함).
- **모듈 경로 보존**: `from roadmap.query`, `roadmap.task_def_json`, `ROADMAP_DIR`, `roadmap/` 디렉토리.
- 테스트 patch 타깃 lockstep 업데이트.

**주의/함정:** 1차 sed 가 `roadmap.empty`(DataFrame attr)를 모듈 참조로 오인해 건너뜀 → insights/board/data_health 18건 실패. 2차 패스로 import 라인 제외 `roadmap.`/`roadmap[` 변수 접근만 추가 rename 해 해결. conftest 의 `roadmap` 디렉토리 path 변수는 scope 밖이라 revert.

**검증:** pytest 654/654 · 금지 패턴 0 · compile OK · 23파일 (170/170).

**다음:** export(PR-7, WIP 브랜치 `feat-task-def-export` 보존) 또는 추가 안정화. `roadmap/`→`tasks/` 패키지 rename 은 import 광범위 영향이라 보류.

**참고:** PR-7 export 모듈 (`roadmap/task_def_export.py`) 은 `feat-task-def-export` 브랜치에 WIP 커밋으로 보존됨 (JSON/엑셀 export, 재업로드 호환 9컬럼).

---

## 2026-06-01 · screen-CSS 근본 수정 — v2 셸 전 화면 복구 (제대로된 1차 완성)

**브랜치:** `fix-screen-css-injection` (main `8abcaad` 기준 · 트랙 A #85 머지 후)

**맥락:** 사용자 "css 문제 먼저 해결. 제대로된 1차 완성 목표". 트랙 A 가 우회였다면 이건 근본.

**발견 (playwright probe):**
- `st.html("<style>...")` 가 큰 `<style>` 블록을 sanitize/collapse → DOM 에 전혀 mount 되지 않음.
- 전역 `inject_global_styles` 50KB+ + screen `inject_screen_css` 28KB **둘 다** 누락.
- 데이터 관리 페이지 전체에 `--accent-primary` 토큰 0회, `.dm-tab` 0회.

**해결:**
- `ui/styles.py` 의 두 inject 함수 → `st.markdown(unsafe_allow_html=True)` (다른 코드 경로, sanitize 없음).
- `tests/test_html_rendering.py` — `styles.py` 명시 예외 (CSS 자산이라 안전).

**검증 (5 area):** total_css `2KB → 100~146KB`, v2 토큰 `0 → 50~99회`, `.dm-tab` radius `0px → 8px`.

**부수효과:** PR #85 의 inline style 안전망은 그대로 유지. 향후 회귀 시 fallback.

**검증:** pytest 654/654 · 금지 패턴 0 · 5 area 실구동 mount 확인.

**다음 (선택):** 변수명 통일 / PR-7 export / PR-8 권한 / 또는 1차 완성 정리.

---

## 2026-06-01 · 트랙 A: manage UI 검증 + 스타일 수정 + 1차 완성 보고서

**브랜치:** `fix-manage-ui-inline-styles` (main `66ad760` 기준 · PR-6 #84 머지 후)

**맥락:** 사용자 "검증 철저히" + 트랙 A 선택. 1차 완성 굳히기.

**한 일:**
- **실제 앱 구동 검증** (playwright headless): 데이터 관리 → manage 탭 목록·검색·상세·추가폼 4화면. traceback 0, CRUD 렌더 OK.
- **버그 발견·수정**: `inject_screen_css` 의 `st.html("<style>")` 가 mid-render DOM 에 주입 안 됨 (전역 CSS 는 정상). `.td-*`/`.dm-*` screen CSS 미적용 = 기존 이슈. manage UI 동적 st.html 을 inline style 로 보강 (PR-5 diff·토스트 관행). 재검증 시 카드·버튼 정상 스타일 확인.
- `docs/MILESTONE_1.md` 신규 — 1차 완성 보고서.

**검증:** pytest 654/654 · 금지 패턴 0 · 실구동 4화면 OK.

**다음 (선택):** screen-CSS 근본 수정 (board/insights/data 일괄 복구) · 변수명 통일 (cosmetic) · PR-7 export · PR-8 권한.

---

## 2026-06-01 · PR-6: 작업 정의 관리 UI — M3 **1차 완성** 🎉

**브랜치:** `feat-task-def-manage-ui` (main `faf5a99` 기준 · PR-5 #83 머지 후)

**맥락:** `docs/TASK_DEF_PLAN.md` M3 — **1차 완성 마일스톤**. 외부 도구 없이 작업 정의 CRUD + history. 시나리오 2 (1건 추가), 시나리오 3 (1건 수정), 부분적으로 시나리오 5 (일반 사용자 — 권한은 PR-8).

**구현:**
- `ui/task_def_manage.py` 신규 (~390 LOC) — 검색·리스트·상세·폼·history. stateless URL pattern. 단일 진입점 `render(query_params)`.
- `roadmap/task_def_form.py` 신규 (~145 LOC) — `TaskDefForm` 데이터클래스. `from_db_row(row)` ↔ `to_json()` round-trip. add/remove helpers.
- `ui/data_management_v2.py` — `manage` 탭 추가, tasks 그룹 기본 탭이 `task`→`manage` 로 변경. consume action/save 위젯 인스턴스화 전 호출.
- CSS `.td-*` 약 60줄.

**검증 (사용자 요구 "철저히"):**
- pytest 654/654 (PR-6 +41 + 기존 5건 업데이트)
- 금지 패턴 0 (`on_click=` 0, raw requests 0)
- `py_compile` 통과 (3개 신규 + 1개 수정 모듈)
- end-to-end smoke (모듈 import + 폼 round-trip + URL 빌더 동작 확인)
- XSS escape 테스트 (`<script>` injection → `&lt;script&gt;`)
- 한국어/이모지 유니코드 보존 검증
- legacy URL 호환 (`?dm_tab=task` → tasks 그룹 자동 추론)
- history 누적 검증 (create + update 2건)

**다음:** **🎉 1차 완성 달성.** M4 (PR-7 export) 또는 M5 (PR-8 권한) 는 선택. 사용자 요구 시 진행.

---

## 2026-06-01 · PR-5: 엑셀 업로드 diff 미리보기 + 사용자 확인

**브랜치:** `feat-excel-diff-preview` (main `625d384` 기준 · PR-A #82 머지 후)

**맥락:** `docs/TASK_DEF_PLAN.md` M2 / PR-5. 결정사항 §4 — UPSERT + 미리보기 + 사용자 확인.

**구현:**
- `roadmap/sqlite_sync.py::DiffPreview` + `compute_diff(df)` — read-only. added/updated/unchanged/kept/skipped.
- `ui/data_management_v2.py::_render_task_def_diff_preview(pending)` — 카운트 요약 + expand (200건 + "외 N건") + 취소/적용. apply=0 이면 적용 버튼 disabled.
- `_render_task_def_upload` — 직접 ingest 대신 `_task_def_pending` 페이로드 → 다음 rerun 미리보기. 적용 시 기존 `_do_task_def_ingest` 재사용.

**검증:** pytest 613/613 · 금지 패턴 0 · 신규 17건.

**다음:** **M2 완료.** M3 시작 — PR-6 (작업 정의 관리 UI · 1차 완성).

---

## 2026-06-01 · PR-A: 데이터 관리 area 2 그룹 segmented 재편

**브랜치:** `feat-dm-area-2groups` (main `c1a2221` 기준 · M1 완료 후)

**맥락:** `docs/TASK_DEF_PLAN.md` M2 / PR-A. PR-6 (작업 정의 관리 UI) 가 자리잡을 컨테이너를 먼저 만든다. 결정사항 §1 — 📰 뉴스 데이터 / 📋 작업 데이터 2 그룹 × 내부 sub-탭.

**구현:**
- `_DM_GROUPS`/`_DM_GROUP_TABS`/`_DM_GROUP_LABEL`/`_DM_GROUP_DEFAULT_TAB` 상수.
- `_dm_resolve_group_and_tab(grp, tab)` — URL 정규화 + 기존 `?dm_tab=` 단독 북마크 호환 (자동 그룹 추론).
- `_dm_tab_href` — `dm_grp` 자동 포함, news/jobs 는 깨끗한 URL 유지.
- `_dm_group_href` / `_dm_groups_html` — segmented control (a role=tab × 2).
- `_dm_tabs_html` — 현재 그룹의 sub-탭만 렌더 (news 3개 / tasks 1개).
- CSS `.dm-groups/.dm-group/.dm-group-active` 추가.

**검증:** pytest 596/596 · 금지 패턴 0 · 신규 14건 + 기존 1건 수정 (4 탭→3 탭).

**다음:** PR-5 (엑셀 업로드 diff 미리보기 + 사용자 확인) 또는 PR-6 (작업 정의 관리 UI · 1차 완성). PR-6 가 사용자 가치가 가장 크지만 부피가 큼.

---

## 2026-06-01 · PR-4: query.load_latest SQLite 우선 + Parquet fallback

**브랜치:** `feat-query-sqlite-adapter` (main `bc2bcc0` 기준 · PR-3 #80 머지 후)

**맥락:** `docs/TASK_DEF_PLAN.md` M1 / PR-4. **M1 마지막**. reader 를 SQLite 로 전환해 보드/인사이트/데이터관리/매칭이 자연스럽게 SQLite 데이터를 보게 한다. DataFrame 시그니처/컬럼 셋 무변경.

**구현:**
- `roadmap/query.py::load_latest(*, prefer="sqlite")` — SQLite 비어있지 않으면 `task_defs` → DataFrame, 비면 Parquet fallback. `prefer="parquet"` 옵션 (마이그/회귀).
- 빌드 시 `org_meta` 우선, scalar 미러 보강, lv1/2/3 가 없으면 division/process/task fallback.
- 마이그 CLI 는 `prefer="parquet"` 명시 (자기 자신을 채우는 도구).

**검증:** pytest 580/580 · 금지 패턴 0 · 신규 7건. 호출처 8곳 (board_v2/insights_v2/data_management_v2/persona_page/data_health/sidebar/onboarding/archive_v2) 무변경.

**다음:** **M1 완료.** M2 시작 — PR-A (데이터관리 area 2 그룹 재편) 또는 PR-5 (엑셀 업로드 diff 미리보기). PR-A 가 비교적 가벼우니 먼저 권장.

---

## 2026-06-01 · PR-3: 로드맵 Parquet → SQLite 동기화 + 마이그 CLI

**브랜치:** `feat-ingest-sqlite` (main `832b099` 기준 · PR-1 #78 + PR-2 #79 머지 후)

**맥락:** `docs/TASK_DEF_PLAN.md` M1 / PR-3. 엑셀 ingest 와 1회성 마이그에서 작업 정의를 SQLite 로 적재. Parquet 흐름은 유지 (PR-4 가 reader 전환).

**구현:**
- `roadmap/sqlite_sync.py` — `row_to_task_def` + `sync_dataframe` (`SyncResult`).
- `roadmap/ingest.py` — `to_sqlite=True` best-effort UPSERT, `IngestResult.sqlite_*`.
- `roadmap/schema.py` — `공정ID` → `process_id` 매핑 + 컬럼.
- `scripts/migrate_roadmap_to_sqlite.py` — 마이그 CLI (`--file/--dry-run`).
- process_id: 컬럼 우선 → JSON 내부 fallback. team/dept 없으면 skip.

**검증:** pytest 573/573 · 금지 패턴 0 · 신규 16건. 샘플 엑셀 32행 중 31건 적재(1건 JSON 빈 행 skip — 정상).

**다음:** PR-4 (`roadmap/query.py::load_latest` → SQLite SELECT, DataFrame 반환 유지) — 호출처(보드/인사이트/매칭/데이터관리) 무변경 보장.

---

## 2026-06-01 · PR-1: 작업 정의 SQLite 저장소 + CRUD

**브랜치:** `feat-task-defs-db` (main `3b2455b` 기준 · #77 머지 직후)

**맥락:** `docs/TASK_DEF_PLAN.md` PR-1 — Parquet→SQLite 마이그의 첫 단계. 의존성 없음, 가장 안전.

**구현:**
- `store/task_defs_db.py` 신규 (약 280 LOC, sqlite3 stdlib).
- 2 테이블: `task_defs` (process_id PK + JSON SOT + scalar 미러) + `task_def_history` (json_before/after + action + source).
- 매 호출 새 연결 + `CREATE TABLE IF NOT EXISTS` → conftest `ROADMAP_DIR` 격리 자동 호환.
- CRUD: `get / upsert / delete / list_all(필터) / search / history / count / upsert_many`.
- 검증: invalid/non-object JSON · missing `org_meta` · missing `team`/`dept` · `process_id` mismatch → `ValueError`.
- history 는 무한 누적 (계획 §결정 7).

**검증:** pytest 538/538 · 금지 패턴 0 · `task_defs_db` 23/23.

**다음:** PR-2 (`task_def_json` `org_meta` 확장 helper) — 독립적이라 PR-1 와 병행 가능했지만, 순차 진행하면 ingest 리팩토링 (PR-3) 의 입력이 자연스럽게 정리됨.
## 2026-06-01 · PR-2: 작업 정의 JSON `org_meta` 확장

**브랜치:** `feat-task-def-json` (main `3b2455b` 기준 · PR-1 #78 와 병행)

**맥락:** `docs/TASK_DEF_PLAN.md` PR-2 — `task_def_json` v1.0 스키마 도입. PR-3(ingest 리팩토링) 의 입력 형식 정리. PR-1 와 독립적.

**구현 (append-only · 기존 API 무변경):**
- `roadmap/task_def_json.py` 에 `SCHEMA_VERSION/ORG_META_KEYS/ORG_META_REQUIRED` 상수.
- `ingest_org_meta(json_text, org_meta, *, process_id=None, version="1.0")` — JSON 에 `org_meta` 주입 + `version` setdefault + `process_id` 동기화.
- `org_meta_of(json_text)` — 안전 추출.
- `validate_task_def_json(json_text)` — `task_defs_db.upsert` 입력 사전 검증.
- 새 예외 `TaskDefJsonError(ValueError)`.

**검증:** pytest 532/532 · 금지 패턴 0 · 신규 18건.

**다음:** PR-3 (`scripts/migrate_roadmap_to_sqlite.py` + `roadmap/ingest.py` UPSERT 리팩토링) — PR-1 머지 후 시작.

---

## 2026-06-01 · 중간 점검 + 작업 정의 데이터 마이그 계획 확정 ✅ merged (#77)

**브랜치:** `feat-task-def-plan` (main `fc0a577` 기준 · #75/76 머지 직후)

**맥락:** 사용자의 "전체 시스템 중간점검" 요청. 핵심 결정사항 확정 후 별도 plan 문서로 분리.

**결정 (`docs/TASK_DEF_PLAN.md` 참조)**:
1. 데이터 관리 화면: 2 그룹 × sub-탭 (뉴스 / 작업)
2. 엑셀 폼: 9 컬럼 (`process_id` 추가)
3. 입력: 엑셀(대량) + UI 폼(1건). JSON 업로드 ❌
4. 재업로드: UPSERT + 미리보기 + 사용자 확인 (같은 id 대체, 새 id 추가, 없는 id 보존)
5. 저장: SQLite + JSON 컬럼 + history 테이블 (무한 누적)
6. process_id: UNIQUE PK
7. 권한: 관리자(all) / 사용자(자기 팀만) — 미래

**작업 분할 (8 PR · 약 2700 LOC · 2~3주)**:
- PR-1: SQLite store + 스키마
- PR-2: task_def_json `org_meta` 확장
- PR-3: 마이그 도구 + ingest 리팩토링
- PR-4: query.load_latest 어댑터
- PR-5: 엑셀 업로드 diff 미리보기 + 확인
- PR-A: 데이터관리 area 2 그룹 재편 (병행)
- PR-6: 작업 정의 관리 UI (← 1차 완성)
- PR-7: export (선택)
- PR-8: 권한 (미래)

**1차 완성 시점:** PR-6 (M3) 완료 — 외부 도구 없이 작업 정의 관리 가능.

**리팩토링 시점:** PR-4 직후 (변수명 통일) · PR-6 후 (선택적 패키지 rename) · PR-7 후 (Parquet 폐기 청소).

**다음 작업:** PR-1 (SQLite store + 스키마) — 가장 위험 낮고 의존성 없음.

---

## 2026-05-31 · SOLA workshop thread 제목 LLM 생성 ✅ merged (#76)

**브랜치:** `feat-thread-title-llm` (main `afa73400` 기준 · #74 머지 직후)

**변경:**
- `sola/thread_title.py` 신규 — LLM 5~12자 압축 + 디스크 캐시 + 룰 fallback
- `SYSTEM_THREAD_TITLE` 프롬프트
- `_clean_title` 안전 정제 (이모지/따옴표/마침표 제거, 길이 제한)
- `ui/sola_workshop_v2.py::_append_message`: 첫 user 메시지에 generate 호출 (실패 시 기존 truncation)
- `test_sola_composer.py::clean_chat_log` fixture: store.cache 격리 + sola.client._client 캐시 클리어 추가(다른 테스트의 fake OpenAI 잔여 차단)
- +16 신규 tests

**검증:**
- pytest **506/506** (490 + 16 신규)
- 금지 패턴: on_click 0 · requests 직접 0
- LLM 미설정·예외·짧은 응답 → truncation fallback (서버 다운/키 없음에도 동작)

**다음 추천 작업:**
- 보드 KPI 카드 yesterday 비교 (현재는 빈 델타)
- SOLA workshop 좌측 thread 목록 검색/필터
- 산출물 보관함 카드 검색

---

## 2026-05-31 · 인사이트 SECTION C 히트맵 cell 클릭 wire ✅ merged (#74)

**브랜치:** `feat-heatmap-click` (main `29830c55` 기준 · #73 머지 직후)

**변경:**
- 정적 mockup 95줄 → `{{IA_HEATMAP}}` placeholder + 동적 Python 빌드
- `_hm_select_href` / `_hm_selected_key` / `_hm_count_in_news` / `_hm_cell_class` / `_hm_top_news` / `_ia_heatmap_html(selected_key)` / `_ia_heatmap_empty` 신규
- 각 셀 `<a href>` + 선택 시 outline + 하단 detail strip(top 3 뉴스 + SOLA 인계)
- 행 = unique lv3 7개, 열 = 고정 7 자동화 기술
- CSS: `a.ia-hm-c` I-19 + `.ia-hm-c-on` + `.ia-hm-detail*` 신규
- +15 tests

**검증:**
- pytest **490/490** (475 + 15 신규)
- 금지 패턴: on_click 0 · requests 직접 0

**남은 추천 작업 (이번 묶음):**
- (2) 매일 06:00 cron 트리거 / GH Actions workflow 확인 → 진행 예정
- (3) SOLA 작업실 thread 제목 LLM 생성 → 진행 예정

---

## 2026-05-31 · cron daily scrape 커스텀 RSS 통합

**브랜치:** `feat-cron-rss` (main `29830c55` 기준, #74 머지 대기 중 병행 시작)

**변경:**
- `scripts/daily_scrape.py` — `_load_extra_feeds` 신규 + `--skip-custom-rss` 플래그 + collect_batch 에 extra_feeds 전달
- `.github/workflows/scrape-daily.yml` — `skip_custom_rss` workflow_dispatch 입력 추가 + CLI 전달
- `tests/test_run_daily.py` 기존 fake signature 갱신
- +9 신규 tests

**검증:**
- pytest **499/499** (490 + 9 신규)
- 금지 패턴: on_click 0 · requests 직접 0
- workflow yml 의 `on:` 키가 PyYAML 의 boolean alias 로 True 로 파싱되는 케이스 가드

**점검 결과:**
- cron `0 0 * * *` (UTC) = KST 09:00 — 출근 후 09:00 브리핑 시점. 사용자 요청한 06:00 으로 변경하려면 `21 0 * * *` 로 수정 (별도 PR).
- 주의: GH Actions 환경에는 `data/sources/config.json` 이 없음(`.gitignore`). cron 의 커스텀 RSS 는 실질적으로 0건 — 사용자가 등록한 RSS 가 cron 에 반영되려면 `repo-level config` 로의 마이그레이션이 추가로 필요 (후속 PR 후보).

**남은 추천 작업 (이번 묶음):**
- (3) SOLA 작업실 thread 제목 LLM 생성 → 다음 진행

---


## 2026-05-31 · SOLA 오늘의 브리핑 LLM 강화 ✅ merged (#73)

**브랜치:** `feat-brief-llm` (main `4742eca7` 기준 · #72 머지 직후)

**변경:**
- `sola/board_brief.py` 신규 — LLM 1~2문장 압축 + 디스크 캐시 + 룰 fallback
- `SYSTEM_BOARD_BRIEF` 프롬프트 신규 (sola/prompts.py)
- `_brief_html(persona_label)` 가 LLM 결과를 summary 에 노출
- `_md_bold_to_html` 안전 변환기 (LLM 의 `**키워드**` 만 `<b>` 처리)
- render(): persona.label() 을 캐시 키로 전달
- +15 tests

**검증:**
- pytest **475/475** (460 + 15 신규)
- 금지 패턴: on_click 0 · requests 직접 0
- LLM 미설정·실패·빈 응답 → 룰 fallback (서버 다운/키 없음에도 화면 정상)

**남은 추천 작업:**
- 인사이트 SECTION C 공정×자동화 기술 히트맵 cell 클릭 wire
- 매일 06:00 cron 트리거 확인
- SOLA 작업실 좌측 thread 목록에 LLM 생성 제목 적용

---

## 2026-05-31 · 인사이트 매트릭스 셀 클릭 wire ✅ merged (#72)

**브랜치:** `feat-insight-matrix-click` (main `e726bd71` 기준 · #71 머지 직후)

**변경:**
- 매트릭스 SVG 버블 8개를 `<a xlink:href="?ia_mx_select=dept|lv3">` 로 wrap
- 우측 ★ PoC 후보 정적 mockup 5건(도장 비전 검사 / 9.2 / 14명/일 등) → cells 기반 동적 5건
- `_ia_mx_select_href` / `_ia_mx_selected_key` / `_ia_matrix_svg(selected_key)` / `_ia_mtx_rank_html(selected_key)` 신규·확장
- 활성 셀(matching/1위) 에 halo + bubble-on + 토글 해제 href
- 옛 mock 데이터 완전 제거 (실 score 10점 환산)
- CSS: `.ia-poc-link` 그리드 + `.ia-mtx-bubble` cursor
- +11 tests

**검증:**
- pytest **460/460** (449 + 11 신규)
- 금지 패턴: on_click 0 · requests 직접 0
- I-16 / I-19 / XSS escape 준수

**남은 추천 작업:**
- LLM 기반 SOLA 브리핑 본문 강화 (현재 score_matches 상위 3건 나열)
- 매일 06:00 cron 트리거 확인
- 인사이트 SECTION C 공정 × 자동화 기술 히트맵 cell 클릭 wire

---

## 2026-05-31 · 커스텀 RSS 실 수집 wire (store.sources → scraping) ✅ merged (#71)

**브랜치:** `feat-custom-rss-scrape` (main `acec45cc` 기준 · #70 머지 직후)

**변경:**
- `scraping/rss.py` 신규 — 범용 RSS 2.0 / Atom 파서 (`build_session` 단일 진입점)
- `collect_batch(extra_feeds=)` 인자 추가 — 키워드 무관 피드 fetch + 저장
- `_collect_extra_feeds()` 헬퍼 (board_v2) — sources.custom_sources → (name, url) 튜플
- 보드 ⑦ 즉시 수집 / 데이터관리 `?refresh=now` 모두 extra_feeds 전달
- ok 토스트에 "RSS N건" 카운트
- +14 tests

**검증:**
- pytest **449/449** (435 + 14 신규)
- 금지 패턴: on_click 0 · requests 직접 0 (scraping.http 유지)
- HTTP 단일 진입점 — `scraping/rss.py` 가 `build_session()` 만 사용

**남은 추천 작업:**
- 인사이트 매트릭스 셀 클릭 wire (보드 매트릭스와 동일 패턴)
- 매일 06:00 cron 트리거 확인
- LLM 기반 SOLA 브리핑 본문 강화 (요약/요점)

---

## 2026-05-31 · 보드 음성으로 듣기 (TTS) — Web Speech API ✅ merged (#70)

**브랜치:** `feat-board-tts` (main `a33a0dd` 기준 · #69 머지 직후)

**변경:**
- `_tts_button_html` / `_tts_disabled_html` 신규 — `data-tts` + inline `onclick`, `SpeechSynthesisUtterance(ko-KR)`
- 브리핑 패널 disabled 버튼 → 실재생 버튼 (요약+제목 N개)
- 매트릭스 detail 패널에 작은 "듣기" 버튼 (dept · lv3 · 점수 · 매칭 · 이유)
- 템플릿 `{{BRIEF_TTS_BTN}}` placeholder
- CSS: `.db-act-tts`, `.db-mx-detail-actions`, `.db-mx-tts`
- +9 신규 tests, 2개 갱신

**검증:**
- pytest **435/435** (426 + 9 신규)
- 금지 패턴: Streamlit `on_click=` 0 (HTML `onclick` 은 별개) · `requests.*` 0
- XSS: `json.dumps` + `html.escape(..., quote=True)` 로 data-tts 안전 인코딩

**남은 추천 작업:**
- 커스텀 RSS 실 수집 wire (scraping 모듈 통합)
- 매일 06:00 cron 트리거 확인
- 인사이트 SECTION B (매트릭스 클릭/상세) 도 매트릭스 셀 클릭 wire 후 TTS

---

## 2026-05-31 · 수집 트리거 실 실행 (`?refresh=now` → collect_batch 호출) ✅ merged (#69)

**브랜치:** `feat-collect-trigger` (main `54ec5bc` 기준 · #68 머지 직후)

**변경:**
- `_consume_refresh_if_any`: 페르소나 관심사 키워드로 `collect_batch` 동기 호출
- 분기 토스트 — ok / warn(키워드 없음) / error(전부 실패 또는 예외)
- `_render_refresh_toast_if_needed`: 튜플 분기 + warn 색 + True 호환
- `_refresh_cta_html`: 툴팁이 실 수집을 안내
- +9 신규 tests, 기존 1개 갱신·2개 추가

**검증:**
- pytest **426/426** (415 + 9 신규 + 2 추가)
- 금지 패턴: on_click 0 · requests 직접 0 (`scraping.http` 단일 진입점 유지)
- collect 실패해도 캐시 invalidate 는 항상 수행

**남은 추천 작업:**
- 보드 음성으로 듣기 (TTS)
- 커스텀 RSS 실 수집 wire (scraping 모듈 통합)
- 매일 06:00 cron 트리거(외부) 확인

---

## 2026-05-31 · 출처 설정 CRUD (B.5 src 탭 read-only → CRUD) ✅ merged (#68)

**브랜치:** `feat-src-crud` (main `42932521` 기준 · #67 머지 직후)

**변경:**
- `store/sources.py` 신규 — `data/sources/config.json` 영구화 (`disabled`, `custom`)
- 기본 4 출처 toggle (URL `?src_action=toggle&src_name=`)
- 커스텀 RSS 추가/제거 (URL `?src_action=remove&src_name=` + Streamlit 폼)
- `_dm_src_body_html`: 기본+커스텀+기타(news ID) 3구분, 비활성 흐림, 토글/제거 링크
- CSS: `.dm-src-row-off`, `.dm-src-st-off`, `.dm-src-act(-rm)`, `.dm-src-url-mini`
- +18 tests

**검증:**
- pytest **415/415** (397 + 18 신규)
- 금지 패턴: on_click 0 · requests 직접 0
- URL stateless — toggle 후 1회 소비 → 쿼리 정리

**남은 추천 작업:**
- 보드 음성으로 듣기 (TTS)
- 수집 트리거 실 실행 (`?refresh=now` 가 캐시만 무효화 → `collect_batch` 호출)
- 커스텀 RSS 실 수집 wire (scraping 모듈 통합)

---

## 2026-05-31 · 산출물 칸반 "+N건 더 보기" wire ✅ merged (#67)

**브랜치:** `feat-archive-more` (main `2fabd7d` 기준 · #66 머지 직후)

**변경:**
- 칸반 "+N건 더 보기" `<button disabled>` → `<a>` 전환 + "− 접기" 토글
- `?expand=pending,adopted` stateless 다중 컬럼 토글 (다른 컬럼 보존)
- `_expanded_cols_from_query` / `_archive_expand_href` / `_build_cards_html` 확장 / `_oa_stats_and_cards(expanded_csv)`
- CSS: `a.oa-col-more` I-19 + `.oa-col-more-collapse` 접기 강조
- +14 tests

**검증:**
- pytest **397/397** (383 + 14 신규)
- 금지 패턴: on_click 0 · requests 직접 0
- URL stateless — 다른 area 이동 시 expand 자동 클리어

**남은 추천 작업:**
- 출처 설정 추가/제거 폼 (B.5 src 탭 CRUD)
- 보드 음성으로 듣기 (TTS)
- 수집 트리거 실 실행

---

## 2026-05-31 · 보드 ⑥ 매트릭스 버블 클릭 wire ✅ merged (#66)

**브랜치:** `feat-matrix-click` (main `3e9d1ff` 기준 · #65 머지 직후)

**변경:**
- 매트릭스 버블 `<button disabled>` → `<a href="?mx_select=dept|lv3">` 전환
- `_mx_select_href` / `_mx_selected_key` / `_board_matrix_html(selected_key)` 신규·확장
- 선택된 셀에 `db-mx-on` 활성 + 상세 패널 동적 갱신(`rank` 위)
- 미지 선택값 fallback → 1위
- CSS: `a.db-mx-bubble` I-19 + `.db-mx-on` 활성 스타일
- +9 tests

**검증:**
- pytest **383/383** (374 + 9 신규)
- 금지 패턴: on_click 0 · requests 직접 0

**남은 추천 작업:**
- 산출물 칸반 "+N건 더 보기"
- 출처 설정 추가/제거 폼
- 보드 음성으로 듣기 (TTS)

---

## 2026-05-31 · 인사이트 트렌드 키워드 클릭 wire ✅ merged (#64)

**브랜치:** `feat-insight-kw-click` (main `cd23856` 기준 · #63 머지 직후)

**변경:**
- `_tkw_list_html` 의 `<button disabled>` → `<a class="ia-tkw-item" href="?tkw=K">`
- 활성 키워드 href 는 빈 tkw (토글 해제), 비활성은 새 선택
- `_ia_process_map_html(selected_kw)` — 30일 뉴스를 키워드 substring 필터 → score_cells
- `_news_filter_by_keyword` 신규 helper
- `_ia_pmap_empty(selected_kw)` — 필터 0건 안내 + "전체 보기" 링크
- `assets/v2/screens/insights.css` — `a.ia-tkw-item` I-19
- +11 tests

**검증:**
- pytest **360/360** (349 + 11 신규)
- 금지 패턴: on_click 0 · requests 직접 0
- URL stateless — area 이동 시 query 전체 재작성으로 자동 클리어

**남은 추천 작업:**
- 데이터관리 키워드/내부 출처 설정 본문(B.5)
- 매트릭스 버블 클릭
- 산출물 칸반 +N건 더 보기
## 2026-05-31 · B.5 데이터관리 4 탭 본문 (키워드 / 작업 정의 / 출처 설정)

**브랜치:** `feat-data-mgmt-b5` (main `cd23856` 기준 · #63 머지 직후)
**병행 작업:** `feat-insight-kw-click` (#64) 와 독립 — 충돌 영역 없음

**변경:**
- `data_management_main.html` — `<button disabled>` 4탭 → `{{DM_TABS}}` 동적 + `{{DM_MAIN_BODY_OPEN/CLOSE}}` 래퍼
- `_dm_tabs_html` / `_dm_tab_href` / `_dm_tab_body_html` / `_dm_kw_body_html` / `_dm_task_body_html` / `_dm_src_body_html` 신규
- `_render_main(selected_tab, persona)` — jobs 외 탭에서 dm-split 을 `display:none` 으로 숨기고 본문 inline
- `render()`: `?dm_tab=` 읽기, task 탭에서만 `_render_task_def_upload()` 위젯 노출
- CSS: `a.dm-tab` I-19 + dm-tab-body/chip/src-table 신규
- 기존 task_def_upload 테스트는 `?dm_tab=task` 진입으로 업데이트
- +14 tests

**검증:**
- pytest **363/363** (349 + 14 신규)
- 금지 패턴: on_click 0 · requests 직접 0
- URL stateless — jobs 기본은 dm_tab 생략 깨끗

**남은 추천 작업:**
- 매트릭스 버블 클릭 wire
- 산출물 칸반 +N건 더 보기
- 출처 설정에 추가/제거 폼 (현재는 read-only)

---

## 2026-05-31 · 인사이트 트렌드 키워드 클릭 wire

**브랜치:** `feat-insight-kw-click` (#64)

**변경:**
- 트렌드 키워드 `<button disabled>` → `<a>` 전환 + `?tkw=` 필터
- `_ia_process_map_html(selected_kw)` 30일 뉴스 필터 후 score_cells
- `_news_filter_by_keyword` 신규 helper
- +11 tests

**검증:** pytest **360/360**

---

## 2026-05-31 · topbar 알림/설정 버튼 정직화 ✅ merged (#63)

**브랜치:** `feat-topbar-actions` (main `e92aa20` 기준 · #62 머지 직후)

**변경:**
- `ui/app_shell.py::render_topbar` — 알림/설정 `<button disabled>` → `<a class="db-hdr-btn">`
  - 알림 → `?app_area=📦 산출물 보관함`, 채택 대기(pending)>0 일 때만 점+배지(99+ 캡)
  - 설정 → `?persona_editor=1`
- `_notif_count()` 신규 (bookmarks pending, 실패 0)
- `assets/v2/shell.css` + `board.css`: `a.db-hdr-btn` I-19 + `.db-hdr-badge`
- +8 tests

**검증:**
- pytest **349/349** (341 + 8 신규)
- 금지 패턴: on_click 0 · requests 직접 0
- 가짜 알림 점 제거 — pending 0 이면 점/배지 미노출

**남은 추천 작업:**
- 데이터관리 키워드·출처 설정 본문 (B.5)
- 인사이트 트렌드 키워드 클릭 wire
- 매트릭스 버블 클릭

---

## 2026-05-31 · 보드 ⑦ 키워드 관리 wire (× 삭제 + 즉시 수집) ✅ merged (#62)

**브랜치:** `feat-keyword-mgmt-wire` (main `cee1bde` 기준 · #61 머지 직후)

**변경:**
- `persona/schema.py` — `muted_keywords` 필드 신규(자동 추출 숨김 목록).
- 보드 ⑦ × 버튼 두 곳 모두 `<a href="?kw_action=del_user|mute&keyword=">`
- 즉시 수집 CTA → `<a href="?kw_action=collect">` → `scraping.run_daily.collect_batch`
- `_kw_action_href` / `consume_kw_action_if_any` / `render_kw_action_toast_if_needed`
- `_board_kw_mgr_html`: muted 필터 + `<a>` 전환 (disabled 자취 제거)
- 공용 `_render_inline_toast` 추출(opp/kw 공유)
- CSS I-19 (.db-kchip-x, .db-kw-sum-cta)
- +16 tests

**검증:**
- pytest **341/341** (325 + 16 신규)
- 금지 패턴: on_click 0건 · requests 직접 호출 0건
- e2e: persona 관심사 × → save → 카드 갱신 / mute → 자동 추출 필터 /
  collect → collect_batch 호출 (mocked) → 토스트

**남은 추천 작업:**
- topbar 알림/설정 버튼 정직화
- 데이터관리 키워드·출처 설정 본문 (B.5)
- 인사이트 트렌드 키워드 클릭 wire

---

## 2026-05-31 · 자동화 기회 카드 보류/채택 wire (보관함 연동) ✅ merged (#61)

**브랜치:** `feat-opp-actions` (main `4eb6dc7` 기준)

**변경:**
- 보드 ④ 카드의 보류/채택 `<button disabled>` → `<a href="?opp_action=...">`
- consume_opp_action_if_any: 1회 소비 → Bookmark 추가 + query strip
- render_opp_action_toast: ok/error 토스트
- _archive_stats 캐시 invalidate
- CSS I-19 (a.db-prop-hold/accept)
- +10 tests

**검증:**
- pytest **325/325** (315 + 10 신규)
- e2e: ?opp_action=accept&dept=도장1팀&lv3=비전 검사 → adopted bookmark
  추가, toast 노출, query 정리 확인

**남은 추천 작업:**
- 키워드 관리 wire (보드 ⑦)
- topbar 알림/설정 버튼

---

## 2026-05-30 · 작업 정의 엑셀 Phase 3 — 업로드 UI + 용어 통일

**브랜치:** `feat-task-def-upload` (main `2466962` 기준)

**사용자 요청:**
- "로드맵" 용어 → "작업 정의 데이터" 로
- Phase 3 진행 (업로드 UI wire)

**변경:**
- 데이터관리 본문 끝에 "📂 작업 정의 데이터 업로드" 섹션
  - 컬럼 안내 + 현 저장 건수 + file_uploader + 시트 선택 + 5행 미리보기
  - "✅ 이 파일로 업로드 + 저장" → pending → ingest → toast
  - 성공 시 모든 dm 캐시 invalidate (보드/인사이트 즉시 갱신)
- 용어 일괄 치환 (8 파일, 사용자 노출 텍스트만)
- +7 신규 tests + test_data_health wording 갱신

**검증:**
- pytest **315/315** (308 + 7 신규)
- 금지패턴 0
- e2e: pending → 32건 ingest 성공 toast 확인
- 브라우저: 업로드 섹션 + 글로벌 채팅 정상 배치

**남은 작업** (별도 PR):
- 자동화 기회 카드 채택/보류 wire
- 키워드 관리 wire (보드 ⑦ 삭제 + 즉시 수집)
- topbar 알림/설정 버튼

---

## 2026-05-30 · 작업 정의 엑셀 Phase 2 — 매칭 정확도↑ + 카드 objective + SOLA 컨텍스트

**브랜치:** `feat-roadmap-phase2` (main `ea98108` 기준 — 3개 PR 머지 후)

**변경:**
- `flatten_for_match` / `first_objective` helper 추가
- `store.match.score_matches`: task_def_json 평탄 텍스트도 매칭 토큰화 (정확도↑)
- `sola.opportunity.score_cells`: `sample_objectives` 컬럼 신규
- `board_v2._opp_card_html`: 🎯 목표 한 줄 노출
- `board_v2.chat_context_block`: 자동화 기회 + 1위 cell 작업 정의 상세

**검증:**
- pytest **308/308** (297 + 11 신규)
- e2e: 합성 뉴스 "RFID OCR 부재번호" → "판넬 선별" 매칭 (점수 21.0) +
  sample_objectives "BOM 기준 주판 수입 검수" 노출
- 기존 사용처 호환 (task_def_json 없는 엑셀에도 정상 동작)

**Phase 3 (별도 PR):**
- 데이터관리 "내부 로드맵" 탭 wire (현재 disabled)
- 작업 정의 검색 UI + JSON 정의서 카드 뷰

---

## 2026-05-30 · 작업 정의 엑셀 Phase 1 — 신엑셀 컬럼 + JSON 파서

**브랜치:** `feat-roadmap-task-def` (main `bfc3fd4` 기준)

**배경:** 사용자가 신규 작업 정의 엑셀(가공팀 32행 샘플) 공유. 형식:
  - 컬럼: 팀/부서/**분과**/**공정**/작업/세부작업/공정정의서(줄글)/**공정정의서(JSON)**
  - JSON: process_id/name/description/objectives/quality_risks/automation_areas 등
  - 추후 데이터 확장 예정 (형식 동일)

**변경:**
- `roadmap/schema.py` — division/process/task_def_json 신규 OPTIONAL 컬럼 + COLUMN_MAP 한글 매핑
- `roadmap/ingest.py` — lv1/2/3 비어있으면 division/process/task 로 자동 fallback (기존 사용처 호환)
- `roadmap/task_def_json.py` 신규 — TaskDef + parse + automation_keywords + to_chat_context_lines. dict 리스트 자동 평탄화 (area · technology · effect 등)
- `tests/fixtures/sample_task_def.xlsx` + `tests/test_roadmap_task_def.py` (+17)

**검증:**
- pytest **277/277** (260 + 17 신규)
- 32행 round-trip 성공 (8 컬럼 → 13 컬럼 Parquet)
- `load_latest` + `score_cells` 호환 확인

**Phase 2 (별도 PR):**
- 자동화 매칭에 `automation_keywords` 활용 (정확도↑)
- 보드 ④ 자동화 기회 카드에 `objectives` 노출
- SOLA 컨텍스트에 `to_chat_context_lines` 첨부

**Phase 3 (별도 PR):**
- 데이터관리 "내부 로드맵" 탭 wire (현재 disabled)
- 작업 정의 검색 + JSON 정의서 카드 뷰
## 2026-05-30 · SOLA workshop 우측 ws-ctx 패널 실데이터 wire

**브랜치:** `feat-sola-ctx-panel` (main `bfc3fd4` 기준)

**변경:**
- ws-ctx 4 카드: 페르소나 스냅샷 wire (편집 링크 + 실 team/keyword count)
  / 고정 출처 정직 빈 안내 / 산출물 보관함 카드 (pending 카운트 + 최근 1건 +
  보관함 area 링크) / 이 스레드 산출물 정직 빈 안내
- `_ctx_archive_summary` + `_ctx_age_label` 헬퍼
- ws-ctx-edit/link <a> CSS 회복 (I-19)

**검증:**
- pytest **267/267** (260 + 7 신규)
- 금지패턴 0
- 브라우저: 모든 ws-ctx 카드 실데이터/정직 빈 상태 렌더 확인

**SOLA workshop 양 사이드(좌측 thread list + 우측 ws-ctx) 완전 마감.**
남은 시안 mock 영역: 본문 ws-typing 효과(LLM 응답 streaming 미구현 흔적)
정도. 다음 작업은 보드 일부 disabled 영역 또는 사용자 작업 정의 엑셀.
## 2026-05-30 · 글로벌 SOLA 채팅 + 화면별 안내 + SOLA workshop 좌측 fix

**브랜치:** `feat-global-chat` (main `bfc3fd4` 기준)

**사용자 요구:**
1. 페르소나 설정 때도 LLM 채팅창 + 페르소나 설정 관련 질문 답변
2. SOLA 작업실 좌측 영역 문제 (app-side + ws-threads 중복)
3. 모든 화면 진입 시 그 화면 컨텍스트 LLM 에 주입
4. 모든 화면 진입 시 채팅창에 안내 메시지/추천 질문

**변경:**
- 신규 `ui/chat_panel.py` — area별 본문 하단 채팅 패널 (메시지 + chat_input + 안내 카드)
- `ui/persona_page.py::chat_context_block` 추가 (4번 + 1번 요구)
- `app.py` — chat_panel.render(area_key) 모든 area 에 wire, persona 분기에도 ctx set, consume_send_if_any 최상단 호출
- `ui/sola_workshop_v2.py` — render_app_side() 호출 제거 (2번 요구)
- `assets/v2/streamlit-overrides.css` — body:has(.ws-shell) padding-left 16px
- 6 area `_AREA_INTROS` 정의 (headline + 추천 질문 3~5건)

**검증:**
- pytest **273/273** (267 + 6 신규)
- 금지 패턴 0
- 브라우저: 보드/SOLA workshop/페르소나 3 화면 캡처 — 좌측 겹침 해결,
  본문 하단 채팅 패널 + 추천 질문 노출 확인
- st.html 사용 (test_html_rendering 통과)

**SOLA workshop 만 예외** (자체 풀스크린 채팅이 본문에 있음). 나머지 5 화면(보드/데이터관리/인사이트/산출물/프로필)은 모두 동일 글로벌 패널.

---

## 2026-05-30 · B.4 후속 2 — SOLA thread 검색 wire

**브랜치:** `feat-sola-thread-search` (main `864b85c` 기준)

**변경:**
- `_filter_threads_by_query`(제목 substring·대소문자 무시·빈 query 패스스루)
- `_render_thread_list_html(search_query="")` — 검색 모드면 단일 "검색 결과 N건"
  평탄 그룹, 빈 결과는 친화 카드 (XSS escape)
- `_render_main` 에 `st.text_input(key="_sola_search_q")` — 시안 input 은
  HTML 내부라 wire 불가, Streamlit native 로 본문 위에 노출

**검증:**
- pytest **260/260** (250 + 10 신규)
- 금지패턴 0
- 브라우저: '도' 검색 시 "검색 결과 2건" + 도장/도료만 노출, VOC 빠짐
- XSS — 검색어 `<script>` 입력 시 escape 확인

**SOLA workshop 좌측 영역 완전 마감.** thread 영구화 + 새 대화 + 전환 +
pin 토글 + 삭제 + 검색 모두 wire 완료. 남은 mock 요소 0.

---

## 2026-05-30 · B.4 후속 — 인계 새 thread + pin 토글 + 삭제

**브랜치:** `feat-sola-thread-polish` (main `47b7851` 기준)

**변경:**
- 인계(CTA) → 전용 새 thread 생성 후 prefill (기존 대화 안 섞임), 종류별 시드 제목
- 활성 thread 액션 3종: 새 대화 / 고정 토글 / 삭제(2-click 확인)
- `_do_toggle_pin` 핸들러 (touch=False)

**검증:**
- pytest **250/250** (248 + 3 신규)
- 금지패턴 0
- e2e: 인계 → 새 thread "자동화 기회 검토", 기존 thread 안 오염(msg 2 유지),
  pin 토글 True/False, 메시지 있는 thread 삭제 → active 재선정

**남은 후속 (별도 PR):** thread 검색 wire (input 아직 disabled)

---

## 2026-05-30 · B.4 — SOLA thread 영구화 + 좌측 list 실데이터

**브랜치:** `feat-sola-thread-store` (main `e5c8aa0` 기준)
**상태:** 구현 완료, PR 생성 예정

**배경:** PR #52 까지는 모든 SOLA 대화가 `chat_key="sola_main"` 단일 파일에
누적. 사용자가 여러 주제 대화하면 한 thread 에 섞임. thread 별 분리 + 좌측
시안 24 thread 실데이터화.

**변경:**
- `store/sola_threads.py` 신규 — Thread CRUD + ensure_active + 자동 제목 + 마이그
- `ui/sola_workshop_v2.py` — active thread 기반 메시지 load/save + 좌측 list 동적
- 새 대화 / 전환 / 삭제 pending 핸들러 + URL `?switch_thread=` 1회 소비
- A.3 잔재 (`sola_main`) 자동 마이그 (첫 user 메시지로 thread 제목 + msg_count)

**검증:**
- pytest **248/248** (233 + 15 신규)
- 금지패턴 0
- e2e: 첫 진입 → thread 자동 1개, [➕ 새 대화] → 추가, 메시지 전송 →
  title 자동 ("도장 PoC 일정이 4개월이면 무리일까?") + msg_count=2
- 브라우저: SOLA 좌측 thread list 실데이터로 렌더 확인

**남은 작업 (별도 PR):**
- thread 검색 wire (현재는 disabled)
- thread pin 토글 (API 는 있지만 UI 미배선)
- 보드/인사이트 카드 CTA → 새 thread 로 진입하도록 수정 (현재는 active thread 에 prefill)

---

## 2026-05-29 · A.3 후속 — 화면 콘텐츠 자동 LLM 컨텍스트 주입 (Option 1)

**브랜치:** `feat-sola-composer-llm` (PR #52 에 추가 커밋)

**요청:** "사용자가 보고있는 화면에서 보이는 어떤것이든 질문하면 다 대답할 수 있어야해"

**변경:**
- 각 v2 area 모듈에 `chat_context_block(persona)` 함수 신규 — 그 화면이 보여주는 모든 데이터를 LLM-친화 텍스트로 packaging (board 7섹션·data_mgmt 4섹션·insights 4섹션·archive 칸반)
- `app.py` — 각 area render() 직후 컨텍스트 생성 → `_chat_context_for_sola` 에 저장
- `sola_workshop_v2._build_llm_messages` — system 블록에 화면 컨텍스트 첨부

**검증:**
- pytest **233/233** (220 + 13 신규)
- 합성 데이터 e2e: 보드 진입 → 컨텍스트 311자 생성 → SOLA system 메시지에 "오늘 KPI: 수집 125건…⑥ 매트릭스 1위: 도장·비전 검사 점수 95" 포함 확인
- 토큰 비용: 빈 상태 80~150자, 데이터 채워졌을 때 500~1500자 (Groq 무료 티어 충분)

---

## 2026-05-29 · A.3 — SOLA composer 실 LLM 호출 wire

**브랜치:** `feat-sola-composer-llm` (main `383e8ca` 기준 rebase)
**상태:** 구현 완료, PR 생성 예정

**배경:** PR #50/#51 머지 후 main 동기화. composer prefill까지만 동작하던
SOLA 채팅을 실제 LLM 호출까지 wire. 사용자 환경에서 Groq API 키 사용 예정.

**Option α (미니멀, 채택):**
- 단일 `chat_key="sola_main"` thread (B.4의 thread store는 별도 PR)
- 시안 footer textarea+send는 readonly/disabled로 시각만 유지
- 실 입력은 `st.chat_input` (화면 하단 자동 고정, 전송 버튼 내장)
- prefill 인계 시 "이 컨텍스트로 물어보기" 버튼

**변경:**
- `assets/v2/screens/sola_main.html` — 시안 메시지 15블록 → `{{WS_MESSAGES}}`
- `ui/sola_workshop_v2.py`:
  - `_load_messages` / `_append_message` (chat_log roundtrip)
  - `_build_llm_messages` (system + persona block + history)
  - `_msg_html` (XSS escape + newline)
  - `_render_messages_html` (empty 친화 카드 / 순서대로 렌더)
  - `_consume_send_if_any` (pending → LLM → append → rerun, 폴백/예외 처리)
  - `_consume_prefill_ask_if_any` (인계 버튼 → 즉시 송신)
  - `_render_main` 에 chat_input + prefill 버튼 추가
- `tests/test_sola_composer.py` (+16)

**검증:**
- pytest **220/220** (204 + 16 신규)
- 금지패턴 0
- 브라우저 캡처: 빈 상태 + opp 인계 상태 둘 다 정상 렌더
- 실 Groq 호출은 컨테이너 정책상 차단됨 (사용자 환경에선 정상 동작)

**남은 작업 (별도 PR):**
- B.4 — SOLA thread store (좌측 24 thread + 검색)
- 보드/인사이트 카드의 정적 시안 추가 데이터 바인딩

---

## 2026-05-29 · 페르소나 온보딩 마법사 (신규 브랜치 feat-persona-onboarding)

**브랜치:** `feat-persona-onboarding` (main = #50 머지 후 `8e8cd15`)
**상태:** 구현 완료, PR 생성 예정

**배경:** PR #50(v2) 머지 완료 → main 동기화. 빈 데이터 환경 첫 진입점인
페르소나 설정을 마법사로. + 브라우저 검증 환경 구축 (`/opt/pw-browsers` 사전설치
chromium 발견 — apt/snap/google/playwright-CDN 전부 차단됐으나 이게 동작).

**변경:**
- `ui/onboarding.py` 신규 — 환영 + 4단계(이름/부서·팀/직무/관심공정) 마법사
- `persona/store.py` — dismiss 마커 3함수 (`.onboarding_dismissed`)
- `app.py` — 온보딩 게이트 (`should_show` → render + st.stop)
- 위젯 GC 함정 회피: `_onb_data` 스냅샷 (단계 전환 시 unmount 위젯 값 보존)
- `scripts/verify_browser.py` — 6화면 자동 캡처 헬퍼 (cherry-pick)
- `tests/test_onboarding.py` (+9)

**검증:** pytest **204/204** · 금지패턴 0 · AppTest 전 흐름(완료 저장/dismiss
영구화/뒤로가기 보존/편집중 억제) + 브라우저 welcome 스크린샷

**다음:** A.3 (SOLA composer 실 LLM 호출) — `feat-sola-composer-llm` 브랜치 대기

---

## 2026-05-29 · v2 메인 머지 준비 — persona 셸 통일 + 미배선 탭 정직화

**브랜치:** `claude/nice-bell-eEZLj` · **PR #50** · 누적 41 커밋

**머지 블로커 3건 처리:**
1. persona_page v2 셸 마이그 — topbar + app-side + setup banner. 폼 위젯은 유지(편집 필요), active_area="" 로 nav 강조 없음
2. 데이터관리 탭 3개(키워드/로드맵/출처) disabled + "B.5 PR" 정직화
3. 보드 트렌드 "월별" + 탑스토리 필터 → db-tab-soon (line-through + not-allowed)

**SHOULD 처리:**
- README UI 설명 v1 → v2 셸 구조로 갱신

**검증:** pytest **195/195** · 금지패턴 0 · py_compile OK · active_area="" nav 안전 확인

**머지 가능 상태 도달.** 남은 건 모두 별도 PR:
- A.3 (composer 실 LLM) · B.4 (thread 영구화) · B.5 (데이터관리 탭 본문 + 트렌드 월별 + 키워드 관리)

---

## 2026-05-28 · archive "수정"→SOLA 인계 + SOLA 미배선 요소 정직화

**브랜치:** `claude/nice-bell-eEZLj` · **PR #50** · 누적 40 커밋

**변경:**
- archive 카드 "수정" → `_edit_handoff_href` (`from=edit&bm_id=&title=`) → SOLA 작업실
- sola_workshop_v2 : `edit` from kind (banner + composer prefill "기존 제안서 수정")
- sola_main.html 정직화: 새 스레드/검색 disabled + thread list 미리보기 노트
- INVARIANTS I-16 : edit kind + 1회-소비 액션 패턴 문서화
- +2 tests (edit href / edit prefill)

**검증:** pytest **195/195** · 금지패턴 0 · py_compile OK
**자체 검토:** archive cards e2e (adopt/edit/reject/restore 링크 모두 렌더), data refresh CTA placeholder 1:1, consume 순서(캐시 읽기 전) 확인

**B.4 PR 로 미룸:** SOLA thread list 실데이터 (thread store 설계 필요), 데이터관리 탭 4개 본문, 트렌드 월별 버킷.

---

## 2026-05-28 · 중간 작업 — archive 카드 액션 + 데이터관리 refresh + 회귀 테스트

**브랜치:** `claude/nice-bell-eEZLj` · **PR #50** · 누적 39 커밋

**변경:**
- archive_v2: 채택/기각/되돌리기 wire — `_archive_action_href` + `_consume_action_if_any`. 1순위 카드만 action 노출, 채택/기각 컬럼 1순위에 "↶ 되돌리기" 추가
- data_management_v2: "지금 실행" 정적 → "지금 새로고침" 동적 — 캐시 invalidate + 녹색 toast
- archive.css / data_management.css — `<a>` CTA CSS 회복 (I-19)
- +6 tests : archive action URL/소비/noop, dm refresh caches+toast, 라벨 ellipsis, MATRIX_DEPT_COLORS 공유

**검증:** pytest **193/193 passed** · 금지패턴 0 · py_compile OK

**남은 큰 작업 (별도 PR 추천):**
- A.3 SOLA composer 실 LLM 호출 wire
- B.4 SOLA thread 영구화 (chat_log 확장)
- persona_page v2 마이그
- 데이터관리 실 수집 트리거 (현재는 캐시 갱신만)

---

## 2026-05-28 · 마무리 — 차트 clamp · dept 색 공유 · v1 -1366줄 · INVARIANTS 4건

**브랜치:** `claude/nice-bell-eEZLj` · **PR #50** · 누적 38 커밋

**변경:**
- **Polish:**
  - 인사이트 차트 callout box 좌표 viewBox 안으로 clamp (우측 끝 잘림 해결)
  - 두 매트릭스 라벨 cap 14→12자 + ellipsis
  - 매트릭스 dept 색상 단일 진실 → `board_v2.MATRIX_DEPT_COLORS` 공유
  - 보드 ② "음성으로 듣기 · 3:42" → "준비 중" disabled (정적 가짜 라벨 제거)
- **INVARIANTS +4**: I-16 handoff URL 패턴 · I-17 sticky banner stacking · I-18 MATRIX_DEPT_COLORS · I-19 `<a>` CTA CSS 회복 규칙
- **v1 데드코드 -1366줄** : board_tab/home_tab/sola_tab/bookmarks_tab 4 모듈 + 3 v1 테스트 제거 (data_health 만 보존). app.py noqa 도 4개 제거.

**검증:**
- pytest **187/187 passed** (217 - 30 v1 tests 제거 = 187)
- 금지 패턴 0, py_compile OK
- 외부 참조 grep 결과 0

**현 PR 상태:** 마무리 완료. 추가 작업은 별도 PR (A.3 LLM 호출 wire / B.4 thread 영구화 / persona_page v2 / archive 카드 액션).

---

## 2026-05-28 · A.7 후속 (composer prefill) + A.4 ⌘K wire + CTA 스타일 회복

**브랜치:** `claude/nice-bell-eEZLj` · **PR #50** · 누적 36 커밋

**변경:**
- `sola_workshop_v2._composer_prefill()` — `?from` 4종에 따라 textarea 자동 채움
- composer 템플릿에 `{{COMPOSER_PINS/PLACEHOLDER/PREFILL}}` 3 placeholder, rows=3
- handoff banner sticky 위치 stacking — LLM banner 동시 노출 시 132px 로 자동 하강
- app.py 에 `app_shell.render_command_palette()` wire (5-nav + 페르소나 row 모달)
- shell.css : a/label 형태의 db-hdr-search + ph/kbd 자식 스타일
- board.css / insights.css : `<a>` 로 전환된 CTA 4종 (db-prop-discuss / db-mx-cta / db-act / db-act-primary / ia-pc-detail) 의 text-decoration · :visited 회복
- +7 tests: composer prefill 6 케이스 + 팔레트 렌더

**검증:**
- py_compile OK (5개 파일)
- 금지 패턴 (on_click=, 사외 requests.*) — 0 hits
- 테스트는 다음 일괄 실행에서 검증

**남은 작업 (deferred):**
- 남은 v1 5 모듈 (board_tab/bookmarks_tab/data_health/home_tab/sola_tab) 의 테스트 v2 마이그 → 추후 코드 정리 가능 (현 PR 범위 밖)

---

## 2026-05-28 · A.7 확장 — 4 CTA 모두 SOLA 작업실로 라우팅 통일

**브랜치:** `claude/nice-bell-eEZLj` · **PR #50** · 누적 35 커밋

**변경:**
- `_sola_handoff_href(from_kind, **payload)` 신규 헬퍼 (board_v2)
- 자동화 기회 4 카드 "SOLA와 검토" → `?from=opp&dept&lv3`
- 매트릭스 detail "제안서 작업장에서 보기" → `?from=matrix&dept&lv3`
- 인사이트 공정 매핑 3 카드 "상세 →" → `?from=ia_map&dept&lv3`
- SOLA 작업실 handoff banner 일반화 (`_HANDOFF_LABELS` 테이블 + 4 from kind)
- +4 tests: handoff URL 빌더, opp/matrix/ia_map CTA 패턴 검증

**검증:**
- pytest **210/210 passed** (206 + 4 신규)
- 금지 패턴 0, py_compile OK
- 4 CTA 패턴 동일 — 차후 다른 카드 추가도 `_sola_handoff_href` 한 줄로 wire 가능

**다음:**
1. **A.7 후속 — SOLA 채팅 composer 에 brief/opp/matrix/ia_map 컨텍스트 자동 prefill** (LLM 입력 wire)
2. **A.4 — Ctrl+K 검색 모달** (전역 검색)
3. **남은 v1 5 모듈 테스트 v2 마이그**

---

## 2026-05-28 · A.7 — 보드 ② SOLA 브리핑 CTA → SOLA 작업실 라우팅

**브랜치:** `claude/nice-bell-eEZLj` · **PR #50** · 누적 34 커밋
**상태:** 첫 인터랙션 wire — 보드 → SOLA 컨텍스트 인계

**변경:**
- `_brief_html()` — 빈/유효 두 분기에서 `st.session_state["_board_brief_items"]` 갱신/삭제. CTA 는 `<a href="?app_area=🤖+SOLA+작업실&from=brief">`.
- 보드 템플릿 `<button>` → `{{BRIEF_CTA}}` placeholder.
- `sola_workshop_v2._render_brief_handoff_banner_if_needed` — `?from=brief` 일 때만 sticky 파란 banner + 3건 제목 ol.
- `sola_workshop_v2.render` 에 setup banner + brief banner 호출 wire.
- 신규 테스트 `test_board_brief_cta_routes_to_sola_with_from_brief`: cta href / session_state 인계 검증.

**검증:**
- pytest **206/206 passed** (205 + 1 신규)
- 금지 패턴 0
- py_compile OK
- A.7 라우팅 단위 테스트로 회귀 방어

**다음:**
1. **A.7 후속** — SOLA 작업실 templates 의 채팅 composer 와 brief items 를 실제 wire (LLM 호출은 별도 PR)
2. **A.4 — Ctrl+K 검색 모달** (전역 검색)
3. **레거시 테스트 v2 마이그** — 남은 v1 5 모듈 정리

---

## 2026-05-28 · 회귀 베이크 + v1 데드코드 925줄 제거 (I + H)

**브랜치:** `claude/nice-bell-eEZLj` · **PR #50** · 누적 33 커밋

**변경:**
- `tests/test_v2_screens.py` (+8 tests) — 보드/인사이트 helper 회귀 베이크 (빈 상태 + 합성 데이터 클래스 검증)
- v1 데드코드 925줄 제거:
  * `ui/ingest_tab.py` (-284)
  * `ui/news_tab.py` (-121)
  * `ui/proposal_workbench.py` (-364)
  * `ui/roadmap_tab.py` (-156)
- `app.py` — 4개 noqa 임포트 제거, 남은 v1 모듈은 "테스트 의존" 사유로 라벨링
- `sola/refine.py` — stale docstring 정리

**검증:**
- pytest **205/205 passed** (197 + 8 신규)
- 4 v1 모듈 외부 참조 grep 결과 0
- 금지 패턴 (on_click=, 사외 requests.*) — 0 hits
- py_compile OK
- push 성공 PR #50

**남은 v1 모듈 (테스트 의존):** board_tab / bookmarks_tab / data_health / home_tab / sola_tab. 다음 정리는 해당 테스트들의 v2 마이그레이션 후.

**다음:**
1. **A.7 — 보드 ② CTA → SOLA workshop 라우팅** (인터랙션 첫 진입)
2. **A.4 — Ctrl+K 검색 모달**
3. **레거시 테스트 v2 마이그레이션** (board_tab → board_v2 helpers)

---

## 2026-05-28 · v2 인사이트 공정 매핑 + LLM 미설정 banner (B.3 + C)

**브랜치:** `claude/nice-bell-eEZLj` · **PR #50** · 누적 32 커밋

**변경:**
- `ui/insights_v2.py::_ia_process_map_html` (cached) — top trending kw → score_cells head(3) → 카드 3개. fit% = 60+score/max×36, 1위 ia-pcard-top + ★ 최적 매칭. sample_tasks/sample_news fallback.
- `assets/v2/screens/insights_main.html` — .ia-map ~115줄 → `{{IA_PROCESS_MAP}}`
- `ui/app_shell.py::render_setup_banner_if_needed` 신규 — LLM 미설정 시 본문 상단 sticky 노란 banner. body:has(.db-topbar) scoped.
- `board_v2.py` / `insights_v2.py::render()` 에서 호출

**검증:**
- pytest 197/197, py_compile OK, 금지 패턴 0
- 합성 cells 3 → 3 카드 + 1 top + fit '96/87/79' 평균 87%, top kw '비전 검사'
- push 성공 PR #50

**보드 + 인사이트 메인 영역 시각 바인딩 완료. 남은 큰 항목:**
- 산출물 보관함 v2 (kanban + carousel)
- 데이터 관리 v2 (job 행 + sparkline 외 추가 항목)
- 인터랙션 (A 시리즈)

**다음:**
1. **H — v1 레거시 정리** (home_tab, insights_v1 등) — 안정화된 v2 가 v1 대체 가능한지 확인 후 제거
2. **A.4 — Ctrl+K 모달** (검색 search bar)
3. **A.3 — SOLA composer** (입력→pending→LLM)

---

## 2026-05-28 · v2 인사이트 트렌드 차트 + 기회 매트릭스 실데이터 (B.3)

**브랜치:** `claude/nice-bell-eEZLj` · **PR #50** · 누적 31 커밋

**변경:**
- `ui/insights_v2.py`
  - `_ia_chart_parts` (cached) — 보드 `_weekly_keyword_series(5)` 재사용 → 5주 × top-5 series 라인 차트 (1순위 강조 gradient fill + callout, 2-3 컬러 강조, 4-5 mute). Legend / pill 동시 생성.
  - `_ia_matrix_svg` (cached) — `score_cells.head(8)` → 600×420 SVG. 좌상단 = PoC 후보 (쉽움 + 효과 大). dept 5색 팔레트, 1위 cell halo.
- `assets/v2/screens/insights_main.html` — 트렌드 차트 ~75줄 + 매트릭스 ~115줄 placeholder 화
- 빈 상태: 두 차트 모두 min-height 유지 안내 카드

**검증:**
- pytest 197/197, py_compile OK
- 합성 데이터: chart svg 2920자 / legend 3 strong+2 mute / pill '+162%', matrix svg 3878자 / 4 버블 (9 circles + halo dasharray)
- 금지 패턴 0
- push 성공 PR #50

**다음:**
1. **인사이트 공정 매핑 카드** (`.ia-map` / `.ia-pc-list`) — 키워드 → 매칭 공정
2. **인사이트 SECTION C 부서 인사이트** (있다면)
3. **C — LLM 미설정 전역 banner**
4. **A.3 — SOLA composer 인터랙션** (입력→pending→LLM)

---

## 2026-05-28 · v2 보드 ⑦ 내 키워드 관리 실데이터

**브랜치:** `claude/nice-bell-eEZLj` · **PR #50** · 누적 30 커밋
**상태:** 보드 7섹션 (① ~ ⑦) 실데이터 바인딩 완료 — **보드 화면 정복 완료**

**변경:**
- `_board_kw_mgr_html(persona)` — 2 그룹 + summary, 빈 상태 fallback
- 템플릿 ~85줄 → `{{BOARD_KW_MGR}}` placeholder
- pytest 197/197, 합성 데이터 170행 → 4 SOLA + 3 user chips, 30일 평균 6건/일 확인

**보드 정복 완료 — 7섹션:**
① 인사 + KPI 4 (페르소나 빈상태 분기) · ② SOLA 브리핑 top 3 · ③ 탑 스토리 1 lead + 4 side · ④ 자동화 기회 4 · ⑤ 트렌드 차트 + 키워드 6 · ⑥ 매트릭스 6 버블 + detail · ⑦ 키워드 관리 + summary

**다음:**
1. **인사이트 트렌드 차트** (보드 ⑤ 패턴 재사용 가능)
2. **인사이트 매트릭스** (보드 ⑥ 패턴 재사용)
3. **인사이트 공정 매핑 카드** (키워드 → 매칭 공정)
4. 또는 A 시리즈 (SOLA composer / ⌘K 모달 / 카드 액션 라우팅) 인터랙션

---

## 2026-05-28 · v2 보드 ⑥ 기회 매트릭스 ROI×난이도 산점도 실데이터

**브랜치:** `claude/nice-bell-eEZLj` · **PR #50** · 누적 29 커밋
**상태:** 보드 섹션 ① ② ③ ④ ⑤ ⑥ 실데이터 완료 (남은: ⑦ 키워드 관리)

**변경:**
- `ui/board_v2.py::_board_matrix_html` (cached) — score_cells head(6) → 버블 6개 동적 좌표/크기/quadrant 토글, detail aside = 1위 cell
- `assets/v2/screens/board_main.html` — 매트릭스 ~65줄 → `{{BOARD_MATRIX}}` 단일 placeholder
- 빈 상태: '뉴스 + 로드맵 매칭 후' 안내

**검증:** pytest 197/197, py_compile OK, 합성 cells 6 → 6 버블/strong-1/soft-1/detail '도장1팀 · 비전 검사' 확인

**다음:** ⑦ 키워드 관리 (페르소나 keywords + 직접 추가 그룹)

---

## 2026-05-28 · v2 보드 트렌드 차트 + 키워드 리스트 실데이터 (B.1)

**브랜치:** `claude/nice-bell-eEZLj` · **PR #50** (Draft) · 누적 28 커밋
**상태:** 보드 섹션 ① ② ③ ④ ⑤ 실데이터 완료 (남은: ⑥ 매트릭스 · ⑦ 키워드 관리)

**변경:**
- `ui/board_v2.py` — `_weekly_keyword_series(weeks=8)` (top-6 키워드 × 주별 버킷), `_path_d` / `_sparkline_d` (SVG path 생성), `_delta_pct` (head 1/3 vs tail 1/3 변화율), `_board_trend()` (cached, 어노테이션·Y라벨·6 li rows 빌드), `_board_trend_block_html()` (전체 트렌드 섹션 HTML)
- `assets/v2/screens/board_main.html` — 트렌드 섹션 ⑤ 의 하드코딩 ~108줄을 `{{BOARD_TREND}}` 한 줄로 교체
- 빈 상태: 데이터 부족 시 안내 카드

**검증:**
- `python -m py_compile` OK
- `python -m pytest -q` **197/197 passed**
- 금지 패턴 (`on_click=`, 사외 `requests.*`) — 0 hits
- 합성 데이터 스모크: 56일 458행 → 8 라벨 (W15..금주), 6 시리즈, +149% delta 어노테이션 확인

**다음 단계:**
1. ⑥ 기회 매트릭스 (ROI×난이도 산점도) — `_score_cells` 결과 → 버블 좌표 매핑
2. ⑦ 키워드 관리 (SOLA 자동 추출 + 직접 추가 그룹) — 페르소나 기반
3. 인사이트 트렌드 차트도 동일 패턴으로 (board 함수 공유 가능성)

---

## 2026-05-28 · v2 디자인 시스템 Phase 0+1 (오늘의 보드)

**브랜치:** `claude/nice-bell-eEZLj`
**PR:** [#50](https://github.com/jhr0966/News_TEST/pull/50) (Draft)
**카테고리:** `feat`
**상태:** in-progress

**배경:**
Claude Design 핸드오프 번들 `InsightBoard Design System v2 (2026-05-28)` 도착. Azure 라이트 테마 + 풀폭 고정 헤더(.db-topbar) + 좌·우 fixed 패널(.app-side / .app-sola) 의 통합 셸을 5개 메인 화면에 적용. 보존 후 점진 교체 전략 — 첫 화면은 오늘의 보드.

**완료:**
1. **디자인 토큰 + 폰트 인프라** — `assets/v2/tokens.css`, `assets/v2/card.css`, `assets/v2/shell.css` (핸드오프 `_card.css` / `_v2.css` 그대로 이식). Pretendard / JetBrains Mono variable woff2 를 `static/fonts/` 에 커밋, `enableStaticServing=true` 로 `app/static/fonts/` 경로 서빙.
2. **셸 무력화 분기** — `assets/v2/streamlit-overrides.css` 의 모든 룰을 `body:has(.db-topbar)` 로 묶음. v2 셸을 그리는 화면에서만 Streamlit 기본 헤더/사이드바를 숨기고, 본문 컨테이너에 280/384px 패딩을 적용. v1 화면은 영향 없음.
3. **글로벌 크롬 헬퍼** — `ui/app_shell.py` 에 `render_topbar/render_app_side/render_app_sola` 3개 함수. 페르소나 통계, LLM 상태, 5-nav (query-param `?app_area=...` 호환) 까지 와이어. 인터랙티브 버튼은 모두 `disabled` (Phase 2~ 에서 와이어업).
4. **오늘의 보드 v2** — `ui/board_v2.py` + `assets/v2/screens/board_main.html` (핸드오프 main 컬럼 그대로) + `assets/v2/screens/board.css` (시안 자체 스타일 ~2200줄). 페르소나 이름·갱신 시각만 동적 치환, 나머지 7섹션 콘텐츠는 시안의 한국어 그대로.
5. **app.py 분기 교체** — `📊 오늘의 보드` 만 `board_v2.render()` 호출. 나머지 4 분기는 그대로 (v1 화면 유지).

**검증:**
- `python -m py_compile` — OK (변경 파일 전체)
- `on_click=` / `requests.get/Session()` 금지 패턴 — 0 hits
- `pytest -q` — **197/197 passed**
- `ui/home_tab.py` 보존 (`# noqa: F401`) — 롤백 시 한 줄 교체로 복귀 가능

**다음 단계 (Phase 2~):**
1. 데이터 관리 화면 v2 (`data-management v2.html` → `ui/data_management_v2.py`)
2. 인사이트 분석 화면 v2
3. SOLA 작업실 + 제안서 작업장 v2
4. 산출물 보관함 (칸반 드래그 포함)
5. 설정 화면
6. 인터랙션 와이어업 — ⌘K 검색 모달, SOLA composer, 패널 접기/펴기 (query-param + pending flag 패턴)

---

## 2026-05-19 · LLM 미설정 시 입력 컨텍스트 미리보기

**브랜치:** `claude/review-insight-board-Ej5EO`
**카테고리:** `feat`
**상태:** in-progress

**배경:**
LLM 키가 비어 있을 때 "⚠️ LLM 미설정: ..." 한 줄만 표시되어 사용자가 실제로 어떤
컨텍스트가 LLM 에 전달될지 확인할 길이 없었음. 운영자가 키를 발급/세팅하기 전에
"이 화면에서 무엇이 LLM 에 들어가는지" 미리 검증 가능하도록 미리보기 모드 추가.

**한 일:**
1. `sola/preview.py` — `format_messages_preview(messages, *, header, footer_hint)` 추가.
   - 역할(system/user/assistant) 라벨 + `text` 코드블록 본문 + `.env` 안내 footer.
2. LLM 호출 지점에서 `LLMNotConfigured` 캐치 → 미리보기 반환으로 일관 처리:
   - `sola/summarize.py`, `sola/propose.py`, `sola/insight.py` (캐시에는 저장 X)
   - `ui/layout.py::render_chat_panel` (사이드 채팅)
   - `ui/proposal_workbench.py::_do_discuss` (작업장 대화)
3. `_do_refine` 예외 케이스 — refine 은 좌측 본문을 덮어쓰므로 미리보기로 대체하면 안 됨.
   `sola/refine.py::build_refine_messages` 분리 + `_do_refine` 이 LLMNotConfigured 캐치
   시 동일 messages 로 채팅에만 미리보기 노출, 좌측 본문은 유지.
4. 회귀 가드 8건 — `tests/test_preview.py`.

**검증:**
- `pytest -q` 197 passed
- 금지 패턴 (on_click, requests.*) 0건
- py_compile OK

**다음 세션 TODO:**
- 사용자 수동 QA: 키 없는 상태 / 키 있는 상태 모두 정상.
- 입력 컨텍스트가 길어질 경우 미리보기 줄임 처리 검토 (현재는 그대로 출력).

---

## 2026-05-19 · 뉴스 수집 AttributeError 회귀 수정

**브랜치:** `claude/review-insight-board-Ej5EO`
**카테고리:** `fix`
**상태:** in-progress

**배경:**
Streamlit Cloud(`share.streamlit.io`, Python 3.14 + bs4 4.14+) 에서 "데이터 관리 → 뉴스 수집" 실행 시
`scraping/enrich.py:107 _strip_noise` 의 `tag.get("style", "")` 호출이 `AttributeError`
(`self.attrs.get(key, default)` 단계) 로 떨어져 전체 수집 batch 가 중단됨.

**한 일:**
1. `_strip_noise` 를 `getattr(tag, "attrs", None)` + `isinstance(dict)` 가드로 방어 — bs4 환경 편차에 안전.
2. `fetch_article` HTML 파싱 블록을 `try/except` 로 감싸 단일 페이지 실패 → 빈 dict 반환. batch 보호.
3. 회귀 가드 3건 — `tests/test_enrich.py`:
   - `test_strip_noise_survives_tag_without_attrs_dict`
   - `test_fetch_article_returns_empty_on_parse_exception`
   - `test_enrich_articles_skips_failing_article`

**검증:**
- `pytest -q tests/test_enrich.py` 통과
- `pytest -q` 전체 통과
- `grep on_click=` / `requests.get` 가드 0

---

## 2026-05-19 · 종합 마무리 — docs 업데이트 + invariants 보강

**브랜치:** `chore-docs-and-final-tidyup`
**카테고리:** `chore`
**상태:** in-progress

**배경:**
이 세션에서 진행된 10개 PR(#36~#45) 의 결과를 `docs/UX_REDESIGN_PLAN.md` 와 `docs/INVARIANTS.md` 에 반영해 후속 작업자가 단일 문서에서 현재 상태를 파악 가능하게.

**한 일:**
1. `docs/UX_REDESIGN_PLAN.md` 에 §13 "2026-05-19 — UX 2차 개편 (Next-Best-Action / 채팅 통합 / 배포 지원)" 섹션 추가 — PR 표, 7단계 사용자 여정 마무리 상태, LLM 백엔드 우선순위, 누적 회귀 가드 수.
2. `docs/INVARIANTS.md` 에 새 invariant 3건 추가:
   - **I-13** — 사이드 채팅 패널은 `main_and_chat` 단일 진입점 (메인에 별도 chat_input 금지)
   - **I-14** — LLM 설정은 `config._env_or_secret()` 경유 (env > st.secrets > 디폴트)
   - **I-15** — `chat_log` 는 `chat_key` 별 파일, `_safe_key()` 로 traversal 차단
3. 코드 미사용 import 감사 — `sola_tab.py` 등 정리 잔재 없음 확인.

**검증:**
- `pytest -q` 186 passed (회귀 없음, 코드 변경 없는 docs 위주)

**다음 세션 TODO:**
- 사용자 브라우저 수동 QA 7-시나리오
- Streamlit Cloud 배포 후 실제 LLM 호출 확인

---

## 2026-05-19 · 배포 지원 — Streamlit Cloud Secrets fallback ✅ merged (#45)

`config.py::_env_or_secret()` 헬퍼로 env 우선, `st.secrets` fallback. README "☁️ Streamlit Community Cloud 배포" 섹션. `.env` 추적 제거. 회귀 가드 6건.

---

## 2026-05-19 · UX — 사이드 채팅 패널 기본 펼침 (옵션 A) ✅ merged (#44)

**브랜치:** `feat-chat-panel-default-open`
**카테고리:** `feat`
**상태:** in-progress

**배경:**
사용자가 "어느 화면을 가도 우측 LLM 채팅창이 항상 떠있어야 한다" 고 요청. 5-Phase 종료 후 정리:
- ✅ 7개 탭(home/board/news/ingest/roadmap/bookmarks/sola) 모두 사이드 채팅 패널 지원
- ✅ 화면 데이터 자동 컨텍스트 주입 (`page_context_fn`)
- ✅ chat_key 별 영구화 (PR #43)
- ❌ "항상 떠있음" — 토글 디폴트가 닫힘이라 첫 진입 시 사용자가 클릭해야 활성화됨

→ 옵션 A 선택. 디폴트를 펼침으로 전환.

**한 일:**
1. `ui/layout.py::main_and_chat` 에 `default_open: bool = True` 인자 추가. `is_open = st.session_state.get(open_key, default_open)` 로 변경.
2. `ui/styles.py::page_header` 의 토글 디폴트도 `True` 로 정렬해 라벨이 첫 진입부터 "💬 채팅 닫기" 로 표시.
3. 사용자가 닫으면 `session_state[_chat_open_{key}] = False` 가 저장되어 다음 진입에서도 그 선호 보존 (페이지마다 독립).
4. 회귀 가드: `tests/test_chat_log.py::test_main_and_chat_defaults_to_open` — `inspect.signature` 로 `default_open=True` 잠금.

**검증:**
- `python -m py_compile ui/layout.py ui/styles.py` OK
- `pytest -q` 180 passed (179 → 180, +1 가드)

**다음 세션 TODO:**
- 종합 수동 QA — 신규 사용자 진입 시 우측 패널이 즉시 펼쳐지고 헤더 토글로 접기/펼치기 가능한지.
- (옵션 B/C 검토 보류) 전역 단일 히스토리 통합, `proposal_workbench` 사이드 패널 흡수는 추후 사용자 피드백에 따라.

---

## 2026-05-19 · UX Phase 5 (+ 선택) — 제안서 워크벤치 강화 + 사이드 채팅 영구화

**브랜치:** `feat-ux-phase5-workbench-and-chat-persist`
**카테고리:** `feat`
**상태:** in-progress

**배경:**
UX 5-Phase 개편 마지막 단계 + Phase 4 의 trade-off("chat_log 영구화 사라짐") 해소를 한 PR 로.

**한 일 (Phase 5):**
1. `ui/proposal_workbench.py` 의 "💬 대화" / "✏️ 수정" 라디오 아래에 모드 시각 배너 추가. 대화 = 파란 톤(읽기 전용 컨텍스트), 수정 = 앰버 톤(좌측 본문 LLM 교체). 즉시 인식 가능.
2. 버튼 카피 명확화 — "★ 북마크 저장" → "📌 새 버전으로 저장" (새 북마크 추가), "💾 원본 업데이트" → "💾 원본 덮어쓰기" (in-place 교체). 모든 버튼에 의도와 가역성을 알리는 `help` 추가.
3. `assets/styles.css` 에 `.wb-mode-banner` + `.wb-mode-talk` / `.wb-mode-edit` 추가.

**한 일 (선택 — chat_log 영구화):**
1. `store/chat_log.py` 를 `chat_key` 별 파일 분리로 확장. 기존 인자 없는 호출은 `chat_key="default"` 매핑 → `data/sola/chat_history.jsonl` 단일 파일 유지 (후방 호환). 그 외 키는 `data/sola/chat/{slug}.jsonl`, `_safe_key()` 정규식으로 파일명 슬러그 (디렉토리 traversal 차단).
2. `ui/layout.py::render_chat_panel` 에 `persist=True` 옵션 (디폴트) 추가:
   - 첫 진입 시 `chat_log.load_history(chat_key)` 로 디스크 복원.
   - 사용자 입력·LLM 응답 시 `chat_log.save_history(history, chat_key)` 덮어쓰기.
   - "초기화" 클릭 시 `chat_log.reset(chat_key)` 함께 제거.
3. Phase 4 trade-off 해소 — SOLA 사이드 채팅이 새로고침 후에도 복원됨. 다른 6개 탭(home/board/news/ingest/roadmap/bookmarks) 사이드 채팅도 모두 영구화 혜택.
4. 회귀 가드 4건 — `tests/test_chat_log.py` 신규: 기본 키 후방 호환, chat_key 격리, reset 범위, 슬러그 검증.

**검증:**
- `python -m py_compile store/chat_log.py ui/layout.py ui/proposal_workbench.py` OK
- 금지 패턴 0건
- `pytest -q` 179 passed (이전 175 → 179, +4 가드)

**다음 세션 TODO:**
- 5-Phase 머지 후 종합 수동 QA — 페르소나 미설정 / 로드맵 미업로드 / 뉴스 0건 시나리오 3가지에서 흐름 검증.
- `docs/UX_REDESIGN_PLAN.md` 에 5-Phase 완료 기록 추가 (별도 PR 또는 후속).

---

## 2026-05-19 · UX Phase 4 — SOLA 채팅 UI 단일화

**브랜치:** `feat-ux-phase4-chat-unification`
## 2026-05-19 · LLM 빠른 시작 — Groq 키 발급 CTA + README 가이드

**브랜치:** `feat-groq-setup-and-llm-cta`
**카테고리:** `feat`
**상태:** in-progress

**배경:**
UX 점검에서 H 우선순위 마찰 #4 — "SOLA 작업실 채팅 ≠ 사이드 패널 → 같은 기능 2가지 인터페이스". `sola_tab.py::_render_chat` 가 메인 영역에 큰 채팅 UI 를 제공하고 `render_chat_panel` 이 우측 사이드 패널에 또 다른 채팅 UI 를 제공. 히스토리/컨텍스트가 분리되어 사용자가 두 곳에서 다른 결과를 받음.

**한 일:**
1. `ui/sola_tab.py` 의 `_render_chat()`, `_build_proposal_context()` 제거.
2. `render()` 에 `main_and_chat("sola", page_context_fn=..., persona=...)` 추가 — 우측 사이드 채팅 패널이 다른 5개 탭과 동일 패턴으로 표시.
3. `sola_mode` 라디오에서 "채팅" 옵션 제거 → [뉴스 요약, 자동화 과제 제안서] 2개로 좁힘. 작업실은 산출물 생성 전용.
4. `_build_page_context(news, roadmap, persona)` 신규 — 현재 모드/필터/세션 산출물/카운트를 사이드 패널 컨텍스트로 압축.
5. `render_chat_panel` 이 이미 `include_session_proposal=True`, `include_adopted=True` 라 직전 작성 제안서 + 채택 제안서 자동 첨부됨 (`_build_proposal_context` 의 기능을 자연스럽게 흡수).
6. 미사용 import 정리 — `chat_ctx`, `chat_log`, `persona_ctx`, `SYSTEM_CHAT`, `chat`.
7. 회귀 가드 2건 — `test_build_page_context_summarizes_mode_and_counts`, `test_sola_tab_no_longer_exposes_main_chat_helpers`.

**Trade-off / 알려진 변경:**
- `chat_log.jsonl` 영구화는 사이드 패널이 지원하지 않아 SOLA 채팅 영구화가 일시적으로 사라짐. 새로고침 시 히스토리 리셋. 차후 `render_chat_panel` 에 chat_log 통합으로 보강 후보.
- 메인 영역의 큰 채팅 UI 가 사라지고 사이드 패널 (`main_chat_ratio=(3, 2)`) 로 이동. 약 40% 가로폭이라 충분히 사용 가능.

**검증:**
- `python -m py_compile ui/sola_tab.py` OK
- 금지 패턴 0건
- `pytest -q` 173 passed (이전 171 → 173, +2 가드)

**다음 세션 TODO (Phase 5 후보):**
- 제안서 워크벤치 UX 강화 — `ui/proposal_workbench.py` 의 좌측 MD / 우측 채팅 2-열 레이아웃에서 "💬 대화" / "✏️ 수정" 모드 시각 배너, 버튼 카피 통일.
- (선택) `render_chat_panel` 에 chat_log 영구화 옵션 추가 → SOLA 사이드 채팅 새로고침 후에도 복원.
사용자가 "Groq API 적용해서 실제 사용 가능하게" 라고 요청. 코드는 이미 OpenAI 호환 클라이언트로 Groq 를 지원하고 있었지만, **키 발급 → .env 설정 → 동작 확인** 흐름이 README/UI 에서 1번에 보이지 않아 첫 사용자가 "어디서 키를 받지?", "정상 동작하는지?" 를 추론해야 했음. UX 관점에서 이 dead-end 를 제거.

**한 일:**
1. `README.md` 상단에 "🚀 빠른 시작 (Groq 무료 API)" 섹션 추가. 3-step (의존성 설치 → 키 발급 → 실행) 으로 압축. 🟢/🟠 상태 점 의미 안내, 다른 백엔드 전환은 `.env.example` 참고로 위임.
2. `ui/sidebar.py::_llm_footer_html()` 헬퍼 신규 — 기존 인라인 푸터 빌더를 분리. LLM 설정 완료 시는 기존 형태 그대로, 미설정 시는 안내 카드로 확장 (Groq 외부 링크 + `.env` 변수 안내).
3. `assets/styles.css` 에 `.sidebar-footer-empty` (앰버 테두리 + 배경) + `.sidebar-llm-empty-hint` (인라인 anchor/code 스타일) 추가.
4. 회귀 가드 2건 — `tests/test_sidebar_profile.py::test_llm_footer_ready_shows_model_only`, `::test_llm_footer_empty_shows_groq_cta_with_key_setup_hint`.

**검증:**
- `python -m py_compile ui/sidebar.py` OK
- `pytest -q` 173 passed (이전 171 → 173, +2 가드)

**다음 세션 TODO (Phase 4 — 위험도 🔴):**
- `ui/sola_tab.py` 의 별도 채팅 모드를 사이드 패널(`main_and_chat`)로 통합해 SOLA 작업실은 산출물 생성 전용으로 좁힘.
- 채팅 히스토리 store 키 정합성 검토 (`store/chat_log.py`).

---

## 2026-05-19 · UX Phase 3 — IA 정리 + 인사이트 분석 탭화 + 부서 인사이트 자동 표시

**브랜치:** `feat-ux-phase3-ia-tabs`
**카테고리:** `feat`
**상태:** in-progress

**배경:**
UX 점검 마찰 TOP 10 중 다음 3건 해소:
- "뉴스 콘텐츠" 가 데이터 관리/산출물 보관함 두 곳에서 진입 가능해 위치 불명확 (#8)
- 인사이트 분석 페이지가 단일 스크롤 6섹션이라 피로 (#6)
- 부서별 AI 인사이트가 자동이 아니라 "생성" 버튼 필요 (#7)

**한 일:**
1. **IA 단일화 (`app.py`)** — `news_tab` 을 산출물 보관함에서 떼어내 데이터 관리 3-탭(`1. 뉴스 수집 / 2. 뉴스 둘러보기 / 3. 로드맵 업로드`)으로 이동. 산출물 보관함은 단일 페이지(북마크 채택 관리 전용)로 정리. `ui/sidebar.py::_AREA_DESCRIPTIONS` 동기화.
2. **인사이트 분석 탭화 (`ui/board_tab.py::render`)** — 4섹션을 `st.tabs(["📈 트렌드", "⚙️ 자동화 기회", "🤖 부서 인사이트", "🔗 계층 매칭"])` 으로 분할. 메트릭 그리드 + 분석 흐름 가이드는 탭 위에 그대로 유지해 페이지 컨텍스트 보존.
3. **부서 인사이트 자동 표시 (`_render_dept_insights`)** — 캐시 키가 (dept, titles head(8), llm_model) 라 두 번째부터 LLM 비용 0 이라는 점을 활용해 자동 표시. 수동 "AI 인사이트 생성·갱신" 버튼 제거. LLM 미설정 시는 `status_card` 안내, "🔄 다시 생성" 버튼은 캐시 무시 강제 갱신용. 부서별 `st.spinner` 로 진행 표시.

**검증:**
- `python -m py_compile` OK
- 금지 패턴 (`on_click`, `st.markdown(..., unsafe_allow_html=True)`) 0건
- `pytest -q` 171 passed (이전 171 유지, 동작 회귀 없음)

**다음 세션 TODO (Phase 4 후보 — 위험도 🔴):**
- 채팅 UI 단일화 — `ui/sola_tab.py` 의 별도 채팅 모드를 사이드 패널(`main_and_chat`) 로 흡수해 같은 기능 2가지 인터페이스를 한 곳으로. 채팅 히스토리 store 동기화 검토.
- SOLA 작업실 탭은 "산출물 생성"(요약 · 제안서) 전용으로 역할 좁힘.

---

## 2026-05-19 · UX Phase 2 — 온보딩 가이드 + 페르소나 로드맵 의존성 해결

**브랜치:** `feat-ux-phase2-onboarding-persona`
**카테고리:** `feat`
**상태:** in-progress

**배경:**
Phase 1 후속. UI/UX 점검에서 H 우선순위 마찰 2건을 해소:
1. **온보딩 부재** — 페르소나 미설정 상태의 홈 페이지가 "⬅️ 사이드바에서 페르소나 설정하세요" 카피만 표시. 첫 사용자가 "다음 무엇을?" 추론해야 함.
2. **페르소나 selectbox 가 로드맵 의존** — 로드맵 미업로드 시 부서/팀 selectbox 옵션이 빈 리스트 → 사용자가 어떤 값도 선택할 수 없는 dead-end.

**한 일:**
1. `ui/home_tab.py::_onboarding_steps_html()` 신규 — 페르소나·로드맵·뉴스 상태에 따라 3단계(프로필 → 로드맵 → 뉴스)를 step_guide 로 표시. 하나라도 미완료면 홈 상단에 자동 노출, 각 step 의 active(녹색) 토글로 진행률 시각화.
2. `_persona_welcome` 의 미설정 카피를 "처음 시작하시나요? / 아래 3단계를 차례대로 마치면..." 환영 카드로 교체.
3. `ui/persona_page.py` 가드 — 로드맵 비어있을 때:
   - `_has_roadmap_options()` 헬퍼로 옵션 존재 여부 판단
   - 부서·팀 → selectbox 대신 `text_input` fallback (placeholder + help 안내)
   - 관심 공정 → caption + 기존 값 유지 (`st.session_state["px_lv3"]` 보존)
   - 페이지 상단에 "🗂 로드맵이 아직 업로드되지 않아 추천 목록이 비어있습니다" 안내.
4. `ui/sidebar.py` 의 `_persona_card_html()` — 페르소나 미설정 시 `persona-profile-card-empty` 클래스 + hint "👋 클릭해서 프로필 설정 시작" 로 시각·카피 강화.
5. `assets/styles.css` 에 `.persona-profile-card-empty` 점선 테두리 + edit-hint 펄스 애니메이션 추가.
6. 회귀 가드 1건 — `_onboarding_steps_html` 의 active 카운트 토글 검증.

**검증:**
- `python -m py_compile` OK
- 금지 패턴 (`on_click`, `requests.*`, `st.markdown(..., unsafe_allow_html=True)`) 0건
- `pytest -q` 171 passed (이전 170 → 171, +1 가드)

**다음 세션 TODO (Phase 3 후보):**
- 뉴스 콘텐츠 위치 단일화 (현재 `데이터 관리` 와 `산출물 보관함` 두 곳에서 진입 가능 → 한 곳으로).
- `ui/board_tab.py` 인사이트 분석 페이지의 6섹션을 `st.tabs(["트렌드", "자동화 기회", "부서 인사이트", "매칭"])` 로 분할해 스크롤 피로 해소.
- 인사이트 분석의 부서별 AI 인사이트 "생성·갱신" 버튼을 제거하고 자동 표시 (이미 캐싱되어 비용 부담 적음).

---

## 2026-05-19 · UX Phase 1 — Next-Best-Action 카피 통일 + 라벨 단순화

**브랜치:** `feat-ux-phase1-next-best-action`
**카테고리:** `feat`
**상태:** in-progress

**배경:**
UI/UX 전체 점검(Explore agent 리포트) 결과 초반 4단계(페르소나 → 수집 → 둘러보기 → 채팅)와 6단계(제안서 작업장)에 마찰이 집중되어 있었음. Phase 1 은 동작 변경 없이 **카피·툴팁·빈 상태 안내** 만 사용자 시각으로 다듬어 "설명서 없이 직관적" 경험을 강화하는 작은 단위.

**개편 계획 (Phase 1~5)**
1. Phase 1: Next-Best-Action 카피 통일 (이 세션)
2. Phase 2: 온보딩 + 페르소나 의존성 해결
3. Phase 3: 정보 구조(IA) 정리 (뉴스 콘텐츠 위치 단일화, 인사이트 페이지 섹션 탭화)
4. Phase 4: 채팅 UI 단일화 (SOLA 탭 별도 채팅 → 사이드 패널 통합)
5. Phase 5: 제안서 워크벤치 UX 강화

**한 일 (Phase 1):**
1. 모든 `status_card` 빈 상태 안내를 "다음 → [메뉴] → [액션]" 패턴으로 통일. 9곳 (`home_tab` 2, `board_tab` 4, `news_tab` 1, `bookmarks_tab` 1, `sola_tab` 1, `ingest_tab` 1).
2. `ui/ingest_tab.py` 카피 정리 — 페이지 제목 "뉴스 수집 + 본문 Enrich" → "뉴스 수집", 버튼 라벨 "본문 Enrich" → "LLM 키워드·요약 추가" (PR #37 로 본문/이미지 자동 fetch 가 수집에 통합되었으므로 의미 재정의). step_guide / page_context 도 동일.
3. `ui/persona_page.py` 의 "관심 공정(Lv3)" → "관심 공정" (기술 용어 제거, help 에 Lv3 안내 위치 변경).
4. `ui/board_tab.py` 의 score 의미 caption 추가 — "각 카드의 score = 부서·공정 셀에 누적된 뉴스↔작업 매칭 점수 합. 클수록 자동화 도입 여지 ↑". 슬라이더/체크박스에 `help` 추가.
5. 동작·시그니처 변경 없음. 모든 위젯 key 보존.

**검증:**
- `python -m py_compile` 7개 파일 OK
- 금지 패턴 0건
- `pytest -q` 170 passed (회귀 없음)

**다음 세션 TODO (Phase 2 후보):**
- 페르소나 미설정 홈 페이지 강화 — "3단계 시작 가이드 (페르소나 → 로드맵 → 뉴스)" 카드 도입.
- `ui/persona_page.py` 의 selectbox 가 로드맵 없으면 빈 옵션 → 자유 입력 fallback 또는 "로드맵 먼저 업로드하세요" 가드.
- 사이드바 프로필 카드의 "관심 공정 미설정" 상태에 클릭 유도 (CTA) 보강.

---

## 2026-05-19 · fix — 뉴스 수집 본문 `&nbsp;` 잔재 / 이미지 No Image 다발

**브랜치:** `fix-news-cleanup-and-image`
**카테고리:** `fix`
**상태:** in-progress

**배경:**
뉴스 수집 직후 카드를 보면 (1) 본문 사이에 `&nbsp;` 등 HTML 엔티티가 그대로 노출되고 (2) 거의 모든 카드가 "No Image" 플레이스홀더로 표시됨. 원인 분석:

1. `_clean_article_text` 가 `\xa0` (실제 non-breaking space character) 만 공백으로 치환할 뿐 `&nbsp;` 같은 entity literal 은 decode 하지 않음. RSS description 처럼 escape 된 HTML 이 들어오면 BeautifulSoup `get_text` 한 번으로는 `&nbsp;` 가 살아남음.
2. `_run_collect` 가 RSS/검색 결과를 그대로 저장만 하고 본문 fetch (= `fetch_article`) 를 호출하지 않음. og:image / lazy-loading img 는 fetch 후에야 잡히므로 수집 직후 `image_url` 은 RSS description 안의 명시적 `<img>` 가 있을 때만 채워짐 → 대부분의 카드에서 누락.
3. 추가로 `_extract_image_url` 이 `data-src`, `data-original`, `src` 3가지만 검사해 `data-lazy-src`, `srcset`, `<picture><source srcset>` 등 최신 lazy-load 패턴을 놓침.

**한 일:**
1. `scraping/enrich.py::_clean_article_text` 에 `html.unescape()` 2회 호출 추가 — `&amp;nbsp;` 같이 이중 escape 된 케이스까지 안전하게 풀림. nbsp/zero-width 처리는 그대로.
2. `_IMAGE_SELECTORS` 에 `og:image:secure_url`, `twitter:image:src`, `link[rel=image_src]`, `meta[itemprop=image]` 추가. `_img_src_from_attrs()` 헬퍼 도입 — `data-src` → `data-original` → `data-lazy-src` → `data-lazy` → `data-image` → `data-thumb` → `data-url` → `src` 순으로 lazy 속성 탐색, `srcset` / `data-srcset` 의 첫 후보도 처리.
3. `_extract_image_url` selector 에 `picture source` 추가, 광고/스페이서 필터에 `1x1`, `transparent` 추가.
4. `ui/ingest_tab.py::_run_collect` 가 각 source 검색 직후 `_hydrate_articles()` 헬퍼로 `enrich_articles(with_llm=False)` 호출 → 본문·이미지를 같이 fetch 후 `save_articles`. 진행 바 텍스트가 소스별 `[done/total]` 로 갱신, 결과 메시지에 "본문 N건 확보" 노출. LLM 키워드/요약은 기존 "Enrich" 버튼에 그대로 분리.
5. `tests/test_enrich.py` 에 회귀 가드 3건 추가 — `_clean_article_text` 의 entity decode, `picture source srcset` 인식, `data-src` lazy-load 인식.

**검증:**
- `python -m py_compile scraping/enrich.py ui/ingest_tab.py` OK
- 금지 패턴 (`on_click`, `requests.{get,post,Session}`) 검사 0건
- `pytest -q` 170 passed (이전 167 → 170, 회귀 가드 3건 추가)

**다음 세션 TODO:**
- (선택) `scripts/daily_scrape.py` / `scraping/run_daily.py` 의 cron 흐름에도 본문 fetch 자동 포함 여부 검토. 현재는 UI 수집만 보강됨.
- 수집 시간이 늘었으니 max_results 디폴트(10) 조정 필요한지 사용 후 판단.
- naver/google 스크래퍼 자체의 image_url 추출도 lazy 속성 패턴으로 일반화하면 fetch 실패 시 대안 확보 가능.

---

## 2026-05-19 · refactor — components 빌더 출력 정리 + 카드 헬퍼 승격 판단

**브랜치:** `claude/review-insight-board-Ej5EO`
**카테고리:** `refactor`
**상태:** in-progress

**배경:**
직전 회귀(`ui/home_tab.py:540~542` 의 `st.markdown(..., unsafe_allow_html=True)` 잔재 → raw HTML 노출)의 근본 원인은 `ui/components.py` 의 빌더들이 4-space 들여쓰기로 시작하는 multi-line f-string을 반환했기 때문. 향후 같은 회귀를 막기 위해 빌더 출력 자체를 column 0 부터 시작하도록 정리.

**한 일:**
1. `ui/components.py` 의 `metric_card`, `status_card`, `action_card`, `step_item` 4개 빌더를 single-line concatenated f-string 방식으로 재작성. 조건부 fragment (`icon_html`, `caption_html`) 는 변수로 빼서 가독성 유지.
2. CSS class / 속성 / 시그니처 / 동작은 모두 보존. `tests/test_ui_components.py` 회귀 없음.
3. 카드 헬퍼 승격(`_dept_insight_card_html` 등 board_tab의 3종 → components) 은 검토 결과 **보류**. `news-card` class는 board/news/ingest/bookmarks 4곳에서 사용되지만 각 탭의 콘텐츠 구조(이미지+본문 / 메타+title+body / 단순 body)가 모두 달라 generic helper로 묶기엔 인자만 늘어남(YAGNI). 다른 탭에서 같은 디자인이 필요해질 때 일반화 검토.

**검증:**
- `python -m py_compile ui/components.py` OK
- `pytest -q` 167 passed
- 직접 영향 테스트 (`test_ui_components`, `test_html_rendering`, `test_home_trend_widget`, `test_board_flow`) 28/28 통과

**다음 세션 TODO:**
- 사이드 채팅 열림/닫힘 두 모드에서 홈 화면 카드 표시 수동 회귀 확인 (자동 가드는 `test_html_rendering` 이 차단 중).
- (선택) 다른 탭에서 `news-card` 인라인 HTML을 패턴화해 board 카드 헬퍼와 함께 일반화할 만한 공통 슬롯 도출.

---

## 2026-05-19 · fix — 홈 "자동화 기회 Top 5" raw HTML 노출 제거

**브랜치:** `claude/review-insight-board-Ej5EO`
**카테고리:** `fix`
**상태:** in-progress

**배경:**
홈 화면 스크린샷에서 메트릭 카드 옆에 `<div class="metric-card teal">…` 같은 HTML 소스가 그대로 텍스트로 노출됨. `ui/home_tab.py:537~538` 에서 `render_html(...)` (= `st.html`) 로 정상 렌더한 같은 섹션을 540~542 에서 `st.markdown(..., unsafe_allow_html=True)` 로 다시 그리고 있었는데, `metric_card()` / `_top_opportunities_html()` 가 4-space 들여쓰기로 시작하는 multi-line f-string을 반환하기 때문에 markdown이 이를 **code block** 으로 해석해 raw HTML 텍스트가 그대로 보이는 회귀가 있었음.

**한 일:**
1. `ui/home_tab.py` 의 중복 540~542 블록 제거 (`st.markdown(…, unsafe_allow_html=True)` 사용 부분).
2. `tests/test_html_rendering.py` 가 `ui/*.py` 의 `st.markdown(..., unsafe_allow_html=True)` 호출을 모두 금지하는데 (`ui/components.py` 만 예외), 이로써 통과 복구.

**검증:**
- `python -m py_compile ui/home_tab.py` OK
- `grep -nE 'st\.markdown\([^)]*unsafe_allow_html' ui/` — 0건 (docstring 외)
- `pytest -q` 167 passed (이전 1 failed → 0 failed)

**다음 세션 TODO:**
- 사이드 채팅 패널이 열렸을 때 / 일반 모드 모두 회귀 없는지 수동 확인.
- `ui/components.py` 의 카드 빌더들이 multi-line f-string으로 4-space 들여쓰기를 반환하는데, 향후 markdown 경로 실수를 막기 위해 빌더 출력을 single-line 으로 정리하거나, `render_html()` 사용을 강제하는 lint 강화 검토.

---

## 2026-05-19 · refactor — 인사이트보드 평탄화 및 page_context 재계산 제거

**브랜치:** `claude/review-insight-board-Ej5EO`
**카테고리:** `refactor`
**상태:** in-progress

**배경:**
`ui/board_tab.py` 가 521줄 단일 파일에 트렌드/기회/부서/매칭 4개 섹션 + page_context 빌더가 들어가 있었음. 카드 HTML이 인라인 멀티라인 f-string으로 산재해 가독성이 낮았고, `_compute_trends_payload()` / `opportunity.score_cells()` 가 메인 렌더와 채팅 page_context 양쪽에서 별도 호출되어 채팅 토글 시 매 frame 재계산되는 비효율이 있었음.

**한 일:**
1. `_TrendsPayload` dataclass 도입 — 5-튜플 반환을 명시 필드로 교체. `_empty_emergence()` 헬퍼로 빈 dict 중복 제거.
2. 카드 HTML을 `_dept_insight_card_html`, `_opportunity_card_html`, `_match_card_html` 로 분리. 페르소나 강조 로직은 `_persona_emphasis(persona, dept)` 헬퍼로 통합 (3곳 중복 제거).
3. 트렌드 렌더 분리: `_render_trend_brief`, `_render_trend_charts`, `_render_emergence`. 부서 정렬은 `_ordered_depts()`, 오포튜니티 카드 그리드는 `_render_opportunity_cards()` 로 분리.
4. `render()` 시작점에서 `payload`, `cells` 를 한 번만 계산하여 `_render_trends`, `_render_opportunity`, `_build_page_context` 에 인자로 전달 — 채팅 page_context 평가 시 중복 계산 제거.
5. `_render_overview()` 분리 — 메트릭 그리드 + 흐름 가이드 + 데이터 부족 안내를 한 함수로 묶고 `render()` 본문 단순화.
6. 테스트로 시그니처가 잠긴 `_insight_flow_html`, `_opportunity_to_sola_state`, `_opportunity_flow_context` 는 그대로 유지.

**검증:**
- `python -m py_compile ui/board_tab.py` OK
- 금지 패턴 (`on_click`, `requests.{get,post,Session}`) 검사 0건
- `pytest -q` 166 passed, 1 failed (`tests/test_html_rendering.py` — `ui/home_tab.py:540,542`의 pre-existing 위반, 이번 변경과 무관)
- board 직접 관련 6개 파일 (`test_board_flow`, `test_opportunity`, `test_sola_insight`, `test_trend_brief`, `test_trends_multi_day`, `test_html_rendering` 의 board scope 부분) 31/31 통과

**다음 세션 TODO:**
- (선택) `ui/home_tab.py:540,542` 의 `st.markdown(..., unsafe_allow_html=True)` 를 `render_html()` 로 마이그레이션해 `test_html_rendering` 회복.
- 카드 HTML 헬퍼들을 `ui/components.py` 로 승격해 다른 탭(news_tab, home_tab)도 재사용할지 검토.

---

## 2026-05-18 · UX — 사이드바 프로필/페르소나 편집 페이지

**브랜치:** `work`
**카테고리:** `style`
**상태:** in-progress

**배경:**
사이드바에 페르소나 입력 필드가 줄줄 표시되어 네비게이션이 길어지고 프로필처럼 보이지 않는 문제가 있었음. 사용자는 최상단에 큰 아바타와 설정 요약을 보고, 아바타를 눌러 별도 편집 화면으로 이동하길 원함.

**한 일:**
1. `ui/sidebar.py` 에 큰 상반신 아바타 기반 프로필 카드 추가. 이름/부서/직무/팀/관심 공정을 요약 표시.
2. 사이드바 inline 페르소나 입력 폼 제거. 상단 아바타 카드 클릭 시 `show_persona_editor` 플래그로 메인 편집 페이지 이동.
3. `ui/persona_page.py` 신설 — 페르소나 편집을 메인 콘텐츠 페이지에서 처리하고 저장/초기화/돌아가기 제공.
4. `assets/styles.css` 에 sidebar profile v2 스타일 추가.
5. `tests/test_sidebar_profile.py` 추가 — HTML escape, 미설정 기본값, 옵션 헬퍼 테스트.
6. `CHANGELOG.md`, `docs/SESSIONS.md` 갱신.

**다음 세션 TODO:**
- 브라우저 렌더링에서 아바타 카드 높이와 사이드바 스크롤 여부를 스크린샷으로 확인.
- 필요 시 실제 이미지 업로드/선택형 아바타 기능 추가 검토.

**블로커:** 없음.

## 2026-05-18 · PR merge conflict 반복 원인/방지 설정

**브랜치:** `work`
**카테고리:** `chore`
**상태:** in-progress

**배경:**
PR 생성 때마다 merge conflict가 반복되는 이유는 모든 작업이 `CHANGELOG.md` 와 `docs/SESSIONS.md` 상단을 동시에 수정하고, 경우에 따라 같은 작업 브랜치를 재사용해 target branch와 변경 범위가 계속 겹치기 때문. 특히 두 문서는 append/prepend-only 로그인데 Git 기본 병합은 같은 위치 삽입을 충돌로 처리한다.

**한 일:**
1. `.gitattributes` 추가 — `CHANGELOG.md`, `docs/SESSIONS.md` 에 `merge=union` 적용.
2. `DEV_GUIDELINES.md` 브랜치 전략에 최신 main 기반 새 브랜치, PR 전 rebase/merge 확인, 고충돌 파일 union merge 정책 추가.
3. `CLAUDE.md` 에 PR 충돌 방지 섹션 추가.
4. `git check-attr merge -- CHANGELOG.md docs/SESSIONS.md` 로 attribute 적용 확인.

**다음 세션 TODO:**
- 이 PR이 main에 머지된 뒤부터 같은 로그 파일의 동시 상단 수정 충돌이 줄어드는지 확인.
- 그래도 충돌이 나면 `docs/SESSIONS.md` 를 날짜별 fragment 방식으로 쪼개는 추가 구조 변경 검토.

**블로커:** 없음.

## 2026-05-18 · UX 마무리 QA — 완료 상태/품질 점검

**브랜치:** `work`
**카테고리:** `docs/test`
**상태:** in-progress

**배경:**
Phase 0~6 기능 구현과 후속 작업장/보관함 루프가 끝났으므로, 전체 시스템 개발 완료 상태를 문서화하고 테스터 관점에서 자동화 검증·앱 기동 smoke·수동 QA 체크리스트를 정리.

**한 일:**
1. `docs/UX_REDESIGN_PLAN.md` 에 Phase 0~6 구현 완료 상태, 대표 파일, 최종 QA 상태 추가.
2. `docs/UX_QA_CHECKLIST.md` 신설 — 전체 완료 상태, 자동화 테스트 결과, 메뉴별 수동 QA 시나리오, 남은 리스크 정리.
3. 품질 점검으로 `make check`, `pytest -q`, Streamlit health smoke 실행.
4. `CHANGELOG.md`, `docs/SESSIONS.md` 갱신.

**다음 세션 TODO:**
- 운영/브라우저 환경에서 실제 스크린샷 QA 수행.
- 실데이터 수집과 LLM 실호출 기반 결과 품질 검수.

**블로커:** 없음.

## 2026-05-18 · UX Phase 6 후속 — 제안서 작업장/보관함 연결

**브랜치:** `work`
**카테고리:** `refactor`
**상태:** in-progress

**배경:**
Phase 6 에서 SOLA 작업실과 산출물 보관함의 큰 흐름을 정리했지만, 보관된 제안서를 다시 작업장으로 열어 수정하고 원본 북마크에 반영하는 폐쇄 루프가 약했음. 제안서 생성 → 보관 → 수정 → 상태 결정 → 다운로드 흐름을 더 명확히 연결.

**한 일:**
1. `ui/bookmarks_tab.py` 제안서 카드에 `작업장` 버튼 추가 — 선택한 북마크를 SOLA 작업실 제안서 작업장 수정 모드로 라우팅.
2. `ui/proposal_workbench.py` 북마크 출처 제안서에 상태/결정 메모 저장 UI 를 명시 버튼 방식으로 정리.
3. 작업장에서 수정된 현재 본문을 원본 북마크에 바로 덮어쓰는 `원본 업데이트` 버튼 추가.
4. `store.bookmarks.update_content` 추가 — 제목/본문/태그를 in-place 업데이트.
5. `tests/test_bookmarks.py`, `tests/test_sola_workspace.py` 에 북마크 업데이트와 작업장 라우팅 테스트 추가.
6. `CHANGELOG.md`, `docs/SESSIONS.md` 갱신.

**다음 세션 TODO:**
- 전체 UX 개편 마무리 점검: `docs/UX_REDESIGN_PLAN.md` Phase 0~6 완료 상태 반영.
- 스크린샷 기반 QA 또는 수동 점검 체크리스트 작성.

**블로커:** 없음.

---

## 2026-05-18 · UX Phase 6 — SOLA 작업실/산출물 보관함 정리

**브랜치:** `work`
**카테고리:** `refactor`
**상태:** in-progress

**배경:**
Phase 5 에서 인사이트 분석의 자동화 기회가 SOLA 제안서 생성으로 연결되었으므로, 마지막 단계는 SOLA 작업실을 산출물 생성 엔진으로 정리하고 보관함을 결과 관리 장소로 강화하는 것.

**한 일:**
1. `ui/sola_tab.py` 에 뉴스 요약, 자동화 과제 제안서, 컨텍스트 채팅, 산출물 보관함 작업 유형 카드를 추가.
2. SOLA 실행 전 뉴스/로드맵/LLM 준비 상태를 `status_card` 로 표시.
3. 뉴스 요약 결과를 마크다운 다운로드하거나 산출물 보관함에 저장하는 버튼 추가.
4. `store.bookmarks.summary_counts` 추가 — 타입별 산출물 수와 제안서 의사결정 상태를 집계.
5. `ui/bookmarks_tab.py` 상단에 전체 산출물/제안서/채택 과제/검토 중 KPI 추가.
6. `tests/test_sola_workspace.py`, `tests/test_bookmarks.py` 에 Phase 6 회귀 테스트 추가.
7. `CHANGELOG.md`, `docs/SESSIONS.md` 갱신.

**다음 세션 TODO:**
- Phase 6 후속: 제안서 작업장(`proposal_workbench`)과 보관함 사이의 채택/다운로드/수정 이력을 더 명확히 연결.
- 전체 UX 개편 마무리 점검: 문서의 Phase 0~6 완료 여부 표시와 스크린샷 기반 QA.

**블로커:** 없음.

## 2026-05-18 · UX Phase 5 — 인사이트 분석 실행 흐름

**브랜치:** `work`
**카테고리:** `refactor`
**상태:** in-progress

**배경:**
Phase 4 에서 데이터 관리 준비 상태를 상단 대시보드로 통합했으므로, 다음 단계는 인사이트 분석 화면을 `트렌드 → 로드맵 연결 → 자동화 기회 → SOLA 제안서` 실행 흐름으로 재배치하는 것. 사용자가 매트릭스 결과를 보고 바로 산출물 생성으로 넘어갈 수 있어야 함.

**한 일:**
1. `ui/board_tab.py` 에 Phase 5 분석 실행 흐름 StepGuide 추가.
2. 자동화 기회 매트릭스 섹션명을 `로드맵 연결 · 자동화 기회` 로 조정하고, 같은 score 계산 결과를 흐름/카드/context 에 재사용.
3. 자동화 기회 카드에 `SOLA 제안` 버튼 추가 — 선택한 부서·공정 값을 `SOLA 작업실 > 자동화 과제 제안서` 필터로 전달하고 해당 메뉴로 이동.
4. 사이드 SOLA 컨텍스트에 실행 전환 대상 자동화 기회 후보를 포함.
5. `tests/test_board_flow.py` 추가 — StepGuide active 상태, SOLA 라우팅 상태, 기회 context 회귀 테스트.
6. `CHANGELOG.md`, `docs/SESSIONS.md` 갱신.

**다음 세션 TODO:**
- Phase 6: SOLA 작업실을 작업 유형 카드 중심으로 재구성하고 산출물 보관함과 저장/채택 흐름을 연결.
- Phase 6 후속: 북마크/제안서/채택 과제 통합 보기에서 제안서 상태 전환과 다운로드 동선을 정리.

**블로커:** 없음.

---

## 2026-05-14 · UX Phase 4 — 데이터 관리 준비 상태 대시보드

**브랜치:** `work`
**카테고리:** `refactor`
**상태:** in-progress

**배경:**
Phase 3 에서 오늘의 보드가 다음 행동을 추천하도록 개선했으므로, 다음 단계는 `데이터 관리` 화면을 단순 수집/업로드 탭 묶음이 아니라 분석 준비 상태판으로 통합하는 것. 사용자가 뉴스·본문·로드맵·LLM 중 무엇이 부족한지 탭 진입 전에 알아야 함.

**한 일:**
1. `ui/data_health.py` 신설 — 뉴스 DB, 본문 Enrich, 로드맵 DB, LLM 설정 상태를 계산하는 순수 헬퍼와 HTML 렌더러 추가.
2. `app.py` 의 `데이터 관리` 메뉴 상단에 데이터 준비 상태 KPI와 품질 점검 카드 표시.
3. `assets/styles.css` 에 데이터 품질 카드 그리드 스타일 추가.
4. `tests/test_data_health.py` 추가 — Enrich 비율, 준비 상태 메시지, HTML escape, context 요약 테스트.
5. `CHANGELOG.md`, `docs/SESSIONS.md` 갱신.

**다음 세션 TODO:**
- Phase 5: 인사이트 분석을 `트렌드 → 로드맵 연결 → 자동화 기회 → SOLA 제안서` 흐름으로 재배치.
- Phase 6: SOLA 작업실을 작업 유형 카드 중심으로 재구성하고 산출물 보관함과 저장/채택 흐름을 연결.

**블로커:** 없음.

---

## 2026-05-14 · UX Phase 3 — 오늘의 보드 추천 행동/기회 Top 5

**브랜치:** `work`
**카테고리:** `refactor`
**상태:** in-progress

**배경:**
Phase 2 에서 앱 쉘과 공통 카드 문법을 정리했으므로, 다음 단계인 Phase 3 의 핵심 목표(첫 화면에서 다음 행동 결정)를 구현. 오늘의 보드는 단순 현황판이 아니라 데이터 준비 → 분석 → SOLA 산출물 생성으로 이어지는 첫 의사결정 화면이어야 함.

**한 일:**
1. `ui/home_tab.py` 에 뉴스/로드맵/본문 확보/페르소나/자동화 기회 상태를 보고 우선순위를 정하는 `추천 다음 행동` 섹션 추가.
2. `sola.opportunity.score_cells()` 결과를 재사용해 오늘의 보드 하단에 `자동화 기회 Top 5` 카드 추가. 페르소나 부서와 일치하는 기회는 `내 부서`로 강조.
3. 사이드 SOLA 컨텍스트에 추천 다음 행동과 자동화 기회 Top 목록을 포함해 홈 화면 기반 대화가 다음 액션을 설명할 수 있게 개선.
4. `assets/styles.css` 에 추천 행동/기회 펄스 카드 스타일 추가.
5. `tests/test_home_trend_widget.py` 에 추천 행동 우선순위, escape, 내 부서 강조, context 포함 회귀 테스트 추가.
6. `CHANGELOG.md`, `docs/SESSIONS.md` 갱신.

**다음 세션 TODO:**
- Phase 4: 데이터 관리 화면을 뉴스 DB/로드맵 DB/Enrich/LLM 상태가 한눈에 보이는 데이터 품질 대시보드로 통합.
- Phase 5: 인사이트 분석을 `트렌드 → 로드맵 연결 → 자동화 기회 → SOLA 제안서` 흐름으로 재배치.
- Phase 6: SOLA 작업실을 작업 유형 카드 중심으로 재구성하고 산출물 보관함과 저장/채택 흐름을 연결.

**블로커:** 없음.

---

## 2026-05-14 · UX Phase 2 후속 — 로드맵 업로드 단계 안내

**브랜치:** `work`
**카테고리:** `refactor`
**상태:** in-progress

**배경:**
뉴스 수집 화면에 StepGuide 를 적용한 뒤, 같은 `데이터 관리` 영역의 로드맵 업로드 탭도 동일한 단계 안내 문법으로 맞춰야 함. 로드맵 업로드는 인사이트 분석의 전제 조건이므로 업로드 후 무엇이 가능해지는지 명확히 보여줄 필요가 있음.

**한 일:**
1. `ui/roadmap_tab.py` 상단에 `엑셀 선택 → 시트 확인 → 검증·저장 → 매칭 준비` 4단계 안내 추가.
2. 로드맵 작업/부서 수/Lv3 공정 수를 공통 `metric_card` 로 표시.
3. 기존 로드맵 없음 `status_card` 는 유지하되, 상태 카드 위에 0건 KPI 를 함께 보여 데이터 준비 상태를 더 명확히 표시.
4. `CHANGELOG.md`, `docs/SESSIONS.md` 갱신.

**다음 세션 TODO:**
- Phase 3: 오늘의 보드에 추천 행동/자동화 기회 Top 카드 추가.
- SOLA 작업실을 작업 유형 카드 중심으로 재구성.

**블로커:** 없음.

---

## 2026-05-14 · UX Phase 2 후속 — 데이터 관리 단계 안내

**브랜치:** `work`
**카테고리:** `refactor`
**상태:** in-progress

**배경:**
사용자가 기능 실행 순서를 알기 어렵다는 문제를 해결하기 위해, 데이터 관리의 뉴스 수집 화면부터 단계 안내형 UI 를 적용. 수집 화면은 키워드/소스 선택, 수집·저장, 본문 Enrich, 인사이트 분석 이동 순서가 명확해야 함.

**한 일:**
1. `ui.components.step_item`, `step_guide` 추가 — escape 처리된 단계 안내 HTML 빌더.
2. `assets/styles.css` 에 Step Guide 스타일 추가.
3. `ui/ingest_tab.py` 상단에 4단계 안내를 추가하고, 오늘 저장/본문 확보/소스 수 현황을 `metric_card` 로 표시.
4. 뉴스가 없는 상태를 `status_card` 로 표시해 바로 다음 행동(키워드와 소스 선택 후 수집·저장)을 안내.
5. `tests/test_ui_components.py` 에 StepGuide escape/active 테스트 추가.
6. `docs/ARCHITECTURE.md`, `CHANGELOG.md` 갱신.

**다음 세션 TODO:**
- Phase 3: 오늘의 보드에 추천 행동/자동화 기회 Top 카드 추가.
- 데이터 관리 화면에서 로드맵 업로드 탭도 StepGuide 패턴으로 맞추기.

**블로커:** 없음.

---

## 2026-05-14 · UX Phase 2 후속 — 빈 상태/상태 카드 통일

**브랜치:** `work`
**카테고리:** `refactor`
**상태:** in-progress

**배경:**
Phase 2 에서 공통 `MetricCard`/`StatusCard`/`ActionCard` 컴포넌트를 만들었지만, 여러 화면의 빈 상태는 여전히 `card-flat`, `st.info`, `st.warning` 등으로 들쭉날쭉하게 남아 있었음. 다음 개편 전 사용자 안내 문법을 우선 통일.

**한 일:**
1. `ui/roadmap_tab.py` — 로드맵 미업로드 상태를 `status_card` 로 교체.
2. `ui/board_tab.py` — 상단 KPI 를 `metric_card` 로 교체하고, 분석 데이터 부족/매칭 없음/필터 결과 없음 상태를 `status_card` 로 교체.
3. `ui/news_tab.py`, `ui/bookmarks_tab.py`, `ui/task_tree.py` — 뉴스 없음, 산출물 없음, 로드맵 없음 안내를 `status_card` 로 교체.
4. `CHANGELOG.md`, `docs/SESSIONS.md` 갱신.

**다음 세션 TODO:**
- Phase 2 계속: `ingest_tab` 수집 상태/폼을 상태 카드 + 단계 안내로 재배치.
- Phase 3: 오늘의 보드 추천 행동/자동화 기회 Top 카드 추가.

**블로커:** 없음.

---

## 2026-05-14 · UX Phase 2 — 공통 UI 컴포넌트 기반 정리

**브랜치:** `work`
**카테고리:** `refactor`
**상태:** in-progress

**배경:**
UX Phase 1 로 5개 업무 메뉴 앱 쉘을 만들었고, 다음 단계로 화면마다 반복되는 KPI/상태/빠른 행동 카드의 디자인 문법을 통일할 필요가 있음. `docs/UX_REDESIGN_PLAN.md` Phase 2 의 `MetricCard`/`StatusCard`/`ActionCard` 후보를 우선 구현.

**한 일:**
1. `ui/components.py` 신설 — `metric_card`, `metric_grid`, `status_card`, `action_card`, `action_grid` HTML 빌더 추가. 외부/사용자 문자열은 모두 `html.escape()` 처리하고 tone 은 allowlist 로 제한.
2. `assets/styles.css` 에 Navy/Teal 제품 토큰과 metric/status/action 공통 카드 스타일 추가.
3. `ui/home_tab.py` 의 기본 `st.metric` 3개, 데이터 준비 안내 card-flat, 빠른 행동 inline HTML 을 공통 컴포넌트로 교체.
4. `tests/test_ui_components.py` 추가 — escape, tone sanitizing, grid wrapper 검증.
5. `docs/ARCHITECTURE.md`, `CHANGELOG.md` 갱신.

**다음 세션 TODO:**
- Phase 2 계속: `ingest_tab`, `roadmap_tab`, `board_tab` 의 빈 상태/상태 카드를 `status_card` 로 점진 교체.
- Phase 3: 오늘의 보드에 추천 행동/자동화 기회 Top 카드 추가.

**블로커:** 없음.

---

## 2026-05-14 · UX Phase 1 — 앱 쉘/네비게이션 개편

**브랜치:** `work`
**카테고리:** `refactor`
**상태:** in-progress

**배경:**
`docs/UX_REDESIGN_PLAN.md` 의 Phase 1 시작. 기존 `홈 · 탐색 · 작업실` 3영역은 기능 묶음에 가까워 사용자가 업무 순서를 이해하기 어려웠음. 첨부 구조도의 흐름을 따라 데이터 준비, 분석, SOLA 산출물 생성, 보관함으로 메뉴를 분리.

**한 일:**
1. `app.py` 라우팅을 `오늘의 보드 · 데이터 관리 · 인사이트 분석 · SOLA 작업실 · 산출물 보관함` 5개 업무 메뉴로 변경.
2. `ui/sidebar.py` 메뉴와 브랜드 문구를 업무 흐름형으로 변경하고, 기존 세션의 `app_area` 값이 새 메뉴에 없으면 오늘의 보드로 안전하게 보정.
3. `ui/home_tab.py`, `ui/news_tab.py` 안내 문구와 빠른 행동 카드를 새 메뉴명에 맞게 갱신.
4. `assets/styles.css` 에 사이드바 업무 흐름 힌트 스타일 추가.
5. `README.md`, `docs/ARCHITECTURE.md`, `CHANGELOG.md` 갱신.

**다음 세션 TODO:**
- Phase 2: 공통 `MetricCard`/`StatusCard`/`ActionCard`/`EmptyState` 컴포넌트와 디자인 토큰 정리.
- Phase 3: 오늘의 보드를 추천 행동 중심 대시보드로 재설계.

**블로커:** 없음.

---

## 2026-05-14 · UX 전면 개편 계획 문서화

**브랜치:** `work`
**카테고리:** `docs`
**상태:** in-progress

**배경:**
사용자가 첨부한 제조기술 로드맵 인사이트보드 구조도를 기준으로, 현재 GitHub 레포 UI/UX가 복잡하고 흐름이 불명확하다는 피드백을 제공. Codex가 이후 개편 작업을 진행할 때 참고할 수 있도록 분석과 개편 계획을 레포 문서로 고정할 필요가 있음.

**한 일:**
1. `docs/UX_REDESIGN_PLAN.md` 신설 — 문제 진단, 목표 제품 이미지, 새 IA, 화면별 개편안, 디자인 방향, 사용자 시나리오, 단계별 구현 로드맵 정리.
2. `README.md` 개발 문서 표에 UX 개편 계획 링크 추가.
3. `CHANGELOG.md` [Unreleased] 에 문서 추가 내역 기록.

**다음 세션 TODO:**
- Phase 1: `app.py`/`ui/sidebar.py` 앱 쉘을 `오늘의 보드 · 데이터 관리 · 인사이트 분석 · SOLA 작업실 · 산출물 보관함` 구조로 개편.
- Phase 2: `assets/styles.css` 와 공통 UI 컴포넌트 정리.

**블로커:** 없음.

---

## 2026-05-14 · 검증/보안 정리 — env 예시와 Makefile 정렬

**브랜치:** `work`
**카테고리:** `fix`
**상태:** in-progress

**배경:**
전체 상태 점검 중 `.env.example` 에 실제 API 키 형태의 값이 남아 있고, `Makefile` 이 삭제된 과거 파일명을 참조해 `make check` 가 즉시 실패하는 문제를 확인.

**한 일:**
1. `.env.example` 의 `LLM_API_KEY` 를 placeholder 로 교체하고, 실제 키는 `.env` 에만 입력하라는 주석 추가.
2. `Makefile` 을 현재 레포 구조에 맞춰 `git ls-files '*.py'` 기반 compile, `rg` 금지 패턴 검사, 전체 `pytest -q` 실행으로 정렬.
3. `make check` 에 `.env.example` API 키 패턴 검사를 추가해 예시 파일에 실제 키가 다시 들어오는 것을 차단.

**다음 세션 TODO:**
- 노출됐던 API 키는 공급자 콘솔에서 폐기/재발급.
- 필요하면 secret scanning/pre-commit 도입.

**블로커:** 없음.

---

## 2026-05-13 · Phase 6-A 후속 — 트렌드 위젯 roadmap 의존성 제거

**브랜치:** `fix-home-trend-roadmap-gate`
**카테고리:** `fix`
**상태:** in-progress

**배경:**
PR #21 머지 직후 Codex P2 review #2 — `render()` 의 `if roadmap.empty or news.empty:` 분기 안에 위젯이 갇혀 있어 로드맵 미업로드(뉴스만 수집된 onboarding) 상태에서 위젯이 안 보임. 트렌드 위젯 자체는 roadmap 의존성이 없으므로 분기 분리 필요.

**한 일:**
- `ui/home_tab.render` 의 위젯 블록을 roadmap-gate 바깥으로 이동. 새 분기:
  1. `if not news.empty:` → 트렌드 위젯 (roadmap 무관) 렌더.
  2. `if roadmap.empty or news.empty:` → 안내 카드. 아니면 부서 뉴스 + AI 인사이트 2:1.
- 페이로드 계산은 이미 stateless (빈 news 도 안전), 신규 테스트 없이 기존 14건 통과.

**다음 세션 TODO:**
- cron 안에서 enrich 자동 호출 (Phase 6-B 후속).
- Phase 6-C 매트릭스 셀 LLM 코멘트.

**블로커:** 없음.

---

## 2026-05-13 · Phase 6-A 홈 트렌드 위젯

**브랜치:** `feat-home-trend-widget` (main 위, M5-β 머지 후)
**카테고리:** `feat`
**상태:** in-progress

**배경 (사용자 선택):**
M5-β 가 보드 트렌드 섹션에만 한 줄 카드를 띄움 → 홈 진입 시에는 트렌드를 못 봄. AskUserQuestion 결과 **홈 카드에 SOLA 한 줄 + emergence 칩** 선택.

**한 일:**
1. `_compute_home_trend_payload(news_today, *, days=7, now=None)` — 보드의 헬퍼와 동일 패턴이지만 `now` 주입으로 테스트 결정성 확보. 보드의 헬퍼와는 의도적으로 분리(보드는 `st.session_state` 의존, 홈은 stateless).
2. `_chip_row(label, df, color)` — count / delta 자동 분기. XSS escape.
3. `_trend_widget_html(brief, emergence)` — 🧠 SOLA 한 줄 + 3행 칩 카드. brief 비면 안내 문구.
4. `_build_trend_context(brief, payload)` + `_build_page_context(..., trend_ctx=)` — 사이드 채팅이 홈 트렌드를 자연스럽게 인지.
5. `render()` 메인 영역에 위젯 + [🔄 갱신] 버튼 (pending flag 패턴). brief 는 `_home_brief_text` 세션 키.
6. `tests/test_home_trend_widget.py` 13건. 전체 126/126 통과.

**효과:**
- 홈 진입 → 메트릭 아래 즉시 🧠 SOLA 한 줄 + 🆕 / 📈 / 📉 칩.
- [갱신] → trend_brief.brief("최근 7일", ...) → 캐시 hit 빠름.
- 사이드 채팅이 홈에서 "이 키워드 왜 떴어?" 같은 질문에 즉답 가능.

**다음 세션 TODO:**
- Phase 6-C 매트릭스 셀 LLM 코멘트 배치 미리 채우기.
- 위젯 칩 클릭 → 보드 emergence 표 점프 (현재는 정적 표시만).
- cron 안에서 enrich 자동 호출 (Phase 6-B 후속).

**블로커:** 없음.

---

## 2026-05-13 · Phase 6-B cron 일일 자동 수집 ✅ merged

**브랜치:** `feat-daily-scrape-cron` (main 위에서 분기)
**카테고리:** `feat`
**상태:** merged (PR #19)

**배경 (사용자 선택):**
emergence 정확도는 누적 데이터에 비례. 그러나 현재 수집은 UI 버튼 클릭 의존. AskUserQuestion 결과 **자동 PR 생성** 선택 — cron 이 매일 수집하되 main 직접 push 는 금지 (CLAUDE.md §7 준수), Draft PR 로 사람이 머지 결정.

**구현:**
1. `config.DEFAULT_DAILY_KEYWORDS` — 조선소 도메인 8개 기본 키워드 상수.
2. `scraping/run_daily.py` — UI 와 독립된 배치 진입점.
   - `collect_batch(keywords, sources, max_results, on_step)` — 키워드×소스 매트릭스 수집.
   - **핵심 결정:** 같은 소스의 키워드별 결과를 메모리 누적 후 소스당 1번만 `save_articles` (file stamp 가 초 단위라 같은 초 내 다중 저장 시 덮어쓰기 버그).
   - `CollectionReport` dataclass — saved/errors 분리, `summary_lines()` 로그용.
3. `scripts/daily_scrape.py` — `python -m scripts.daily_scrape` CLI (argparse, 항상 exit 0).
4. `.github/workflows/scrape-daily.yml` — cron `0 0 * * *` (KST 09:00) + `workflow_dispatch` (keywords/max_results override). peter-evans/create-pull-request@v6 로 Draft PR 자동 생성.
5. `tests/test_run_daily.py` 7건 — search 함수를 monkeypatch 해서 디스패치/저장/에러 격리/CLI 기본값 검증.

**검증:**
- pytest 120/120 통과.
- 금지 패턴 (on_click, requests 직접 호출) 모두 0건.
- workflow YAML 문법은 GH Actions 실제 실행 시 검증 (로컬 dry-run 안 함).

**다음 단계 후보:**
1. Repo settings 에서 GH secrets `LLM_API_KEY`/`LLM_BACKEND`/`LLM_MODEL` 설정 (선택 — enrich 활성화 시).
2. 첫 cron 실행 후 자동 PR 동작 확인 → 머지 시 main 의 `data/news/` 누적.
3. 후속: cron 안에서 enrich 자동 호출(현재는 raw 수집만), 또는 누적 일수 늘어나면 emergence 자체에 기간 가중치 도입.

---

## 2026-05-13 · M5-β 트렌드 LLM 한 줄 해석 카드

**브랜치:** `feat-trend-brief` (M5-α 머지 후 main 위에서 재구성)
**카테고리:** `feat`
**상태:** in-progress

**배경 (사용자 선택):**
M5-α 로 다중 일자 트렌드 (일자별 카운트 + emergence 3분류) 가 들어갔지만 사용자가 표를 직접 읽어야 했음. AskUserQuestion 결과 **emergence LLM 해석 카드** 선택 — 표 위에 SOLA 가 1~2문장으로 "이번 기간 핵심 트렌드"를 자연어로 보여주는 카드.

**한 일:**
1. `sola/prompts.SYSTEM_TREND_BRIEF` — 1~2문장 평문 / 굵은 키워드 1~3개 / 입력에 없는 사실 금지.
2. `sola/trend_brief.brief(period_label, vol_df, emergence, force)` — LLM 호출 + 디스크 캐시 + 룰 기반 fallback.
3. `ui/board_tab` 트렌드 섹션 상단 **🧠 SOLA 한 줄** 카드 + [갱신] 버튼 (pending flag 패턴). 결과는 `_brief_text_<period>` 세션 키.
4. `_compute_trends_payload(news_today)` 헬퍼로 (period, days, period_df, vol_df, emergence) 일괄 계산 — `_render_trends` 와 `_build_page_context` 가 같은 로직 재사용.
5. brief 텍스트도 page_context 에 자동 포함 → 사이드 채팅이 SOLA 해석을 인지.
6. `tests/test_trend_brief.py` 8건. 전체 113/113 통과.

**효과:**
- 보드 진입 → 기간 "최근 7일" → [갱신] → "최근 일주일 **용접 자동화** 와 **디지털트윈** 이 두드러집니다" 같은 한 줄.
- 같은 입력은 캐시 → 무료 재로딩. 다른 기간/키워드면 자동 재호출.
- LLM 미설정 환경에서도 룰 기반 1줄로 graceful.

**다음 세션 TODO:**
- 일일 자동 수집 (cron/GH Actions).
- 매트릭스 셀별 LLM 코멘트 일괄 생성 (배치 미리 채우기).
- 트렌드 한 줄을 홈 카드에도 노출 (홈 위젯).

**블로커:** 없음.

---

## 2026-05-13 · M5-α 다중 일자 트렌드 (Phase 5)

**브랜치:** `feat-multi-day-trends` (main 위에서 분기, Phase 2~4 통합 머지 후)
**카테고리:** `feat`
**상태:** in-progress

**배경 (사용자 선택):**
Phase 4 통합 머지 직후 AskUserQuestion 결과 **다중 일자 트렌드** 선택. 지금까지 인사이트보드 트렌드는 '오늘' 만 보여서 사이클 관점이 빠져있던 것을 7일/30일 대조로 확장.

**한 일:**
1. `store/news_db.load_news_for_days(days, now)` — 오늘 포함 최근 N 일 디렉토리 합본 + link dedupe + 누락 일자 스킵 + 깨진 parquet 스킵.
2. `store/trends.daily_volume(df, days, now)` — 일자별 카운트, 데이터 없는 일자도 0 으로 채움 (라인 차트 끊김 방지).
3. `store/trends.keyword_emergence(today, base, top_n, min_count)` — new/gone/rising 3분류. `keywords_llm` 우선.
4. `store/trends.compare_distribution(today, base, key, top_n)` — 분포 비교 (delta 내림차순).
5. `ui/board_tab` 트렌드 섹션 — 기간 라디오(오늘/7일/30일), 라인 ↔ 바 자동 전환, days>1 일 때 🆕/📈/📉 emergence 3열.
6. `ui/board_tab._build_page_context` — 선택 기간 + 일자별 카운트 + emergence 를 사이드 채팅 컨텍스트에 자동 포함.
7. `tests/test_trends_multi_day.py` 11건 + conftest 에 `news_db.NEWS_DIR` 동기화. 전체 105/105 통과.

**효과:**
- "오늘 새로 떠오른 키워드는?" "어제까지 많이 나오던 게 오늘 사라졌나?" 같은 사이클 단위 질의 가능.
- 사이드 채팅이 자동으로 기간 컨텍스트 + emergence 를 인지 → LLM 응답이 더 정확.

**다음 세션 TODO:**
- 일일 자동 수집 (cron / GH Actions).
- 매트릭스 셀별 LLM 코멘트 일괄 생성 (배치 미리 채우기).
- emergence 결과를 LLM 으로 해석한 "오늘의 트렌드 한 줄" 카드.

**블로커:** 없음. 과거 데이터가 없으면 emergence 가 조용히 빈 결과 반환 (graceful).

---

## 2026-05-13 · UI-4 사이드바 컴팩트 개편 (Phase 4)

**브랜치:** `style-sidebar-polish` (Phase 3 위에서 분기)
**카테고리:** `style`
**상태:** in-progress

**배경 (사용자 지시):**
"아까 사이드바 개편하는 건?" — Phase 1 에서 브랜드/섹션만 가다듬었는데 페르소나 큰 폼이 항상 노출돼 사이드바가 너무 길었던 문제. 컴팩트화 진행.

**한 일:**
1. `.persona-card` — 아바타(이름/부서 첫글자, 파랑 그라데이션) + 이름 + 부서·직무·팀 meta(ellipsis). 페르소나 설정됨 상태에서만 노출.
2. `.persona-cta` — 미설정 상태일 때 dashed 파란 CTA + 폼 즉시 노출.
3. 편집 토글 — `✏️ 편집` 버튼으로 폼 expander 열고 닫기 (pending flag 패턴). 저장 시 자동 닫힘.
4. 시스템 상태 → 사이드바 푸터(`.sidebar-footer` + `.sidebar-dot` ok/warn) 로 이동.
5. 영역 네비 라디오 — 큰 네비 버튼 스타일(전폭, 좌측 정렬, padding 9/13).
6. `ui/sidebar.py` 내부 헬퍼 분리(`_avatar_text` / `_persona_card_html` / `_persona_form_body` / `_handle_persona_pending` / `_render_persona_block`).
7. 전체 94/94 통과, on_click·외부 requests 0건.

**다음 세션 TODO:**
- 다중 일자 트렌드 (기능).
- 일일 자동 수집 (cron/GH Actions).
- 매트릭스 셀별 LLM 코멘트 일괄 생성.
- 사이드바 영역 네비 → 아이콘 + 텍스트의 더 큰 버튼 (선택).

**블로커:** 없음. 기능 변경 0, UI만 재배치.

---

## 2026-05-13 · UI-3 사이드 채팅 컨텍스트 강화 (Phase 3)

**브랜치:** `style-ui-redesign-phase3` (Phase 2 위에서 분기)
**카테고리:** `style`
**상태:** in-progress

**배경 (사용자 선택):**
Phase 2 가 머지된 직후 "다음 단계 진행" 지시. AskUserQuestion 결과 **사이드 채팅 컨텍스트 강화** 선택.
지금까지 사이드 채팅은 페이지 컨텍스트(현재 화면)만 받았는데, 사용자의 이전 결정(채택 제안서)·작업 중인 제안서·페르소나가 자동 첨부되면 LLM 이 일관된 답을 줄 수 있음.

**한 일:**
1. `sola/side_context.py` 신설 — `build_side_system()` 순수 함수.
   - 배치: base → 페르소나 → 현재 화면 → 직전 작성 제안서 → 채택 제안서.
   - 채택 제안서는 (제목·결정일·메모)만 / 직전 제안서는 앞 3000자 / 전체 8000자 cap.
   - 반환값 `(sys_msg, labels)` — 라벨은 패널 헤더에 첨부 칩으로 노출.
2. `ui/layout.render_chat_panel` 강화 — `include_adopted` / `include_session_proposal` / `adopted_limit` 옵션 추가. 패널 헤더 아래에 `📎 ...` 첨부 칩 자동 노출. LLM 호출은 같은 헬퍼로 시스템 조립.
3. `tests/test_side_context.py` 10건 — 모든 경계(빈 / 미설정 / 절단 / 정렬) 검증. 전체 94/94 통과.

**효과:**
- 어제 회의에서 "용접 PoC 채택" → 오늘 어느 탭이든 💬 토글 → "이 화면이랑 관련된 게 뭐가 있을까?" 물으면 자동으로 어제 채택안을 인지.
- 제안서 작성 직후 보드/뉴스 탭에서 채팅 → 직전 제안서가 자동 컨텍스트 → 일관된 후속 질의 가능.

**다음 세션 TODO:**
- 사이드바 페르소나 패널 컴팩트화.
- 다중 일자 트렌드.
- 일일 자동 수집 (cron/GH Actions).

**블로커:** 없음.

---

## 2026-05-13 · UI-2 사이드 채팅 + 새 디자인 전체 탭 적용 (Phase 2)

**브랜치:** `style-ui-redesign-phase2` (Phase 1 위에서 분기)
**카테고리:** `style`
**상태:** in-progress

**배경:**
Phase 1 에서 디자인 시스템 + 사이드 채팅 인프라(`ui/layout.py`) 를 만들고 `home_tab` 에 데모 적용. Phase 2 는 같은 패턴을 나머지 7개 탭에 일관 적용해 시스템 전체를 새 디자인 + 사이드 채팅 인지로 통일.

**한 일:**
1. **board_tab** — `main_and_chat("board")` + page_context(트렌드·매트릭스·기회 상위 8셀). 4개 섹션을 `section_label` 로 정리.
2. **ingest_tab** — `main_and_chat("ingest")` + page_context(통계·소스 분포·최근 헤드라인).
3. **news_tab** — `main_and_chat("news")` + page_context(언론사·키워드 분포).
4. **bookmarks_tab** — `main_and_chat("bookmarks")` + page_context(현재 필터 목록). 상태 배지 인라인 style → `.status-badge` 클래스로 통일. 카드 루프를 `_render_items()` 헬퍼로 분리.
5. **roadmap_tab** — `main_and_chat("roadmap")` + page_context(부서·Lv3 집계).
6. **sola_tab** — 상태 패널 `.card-flat`, 라디오 label_visibility 정리. (자체 채팅 본체라 사이드 토글 제외)
7. **proposal_workbench** — `st.subheader` → `page_header` 로 통일.
8. 모든 탭의 페이지 컨텍스트는 lazy → 토글 OFF 일 때 평가 안 됨 → 추가 비용 0.

**조치:**
- pytest 84/84 ✅, py_compile OK, on_click·외부 requests 0건.
- 기능 변경 0 (HTML 카드 구조/세션키/계산 로직 그대로).

**다음 세션 TODO:**
- 사이드 채팅 패널의 컨텍스트 자동 첨부 — 활성 북마크/제안서, 검색 결과 등 보다 풍부한 컨텍스트.
- 사이드바 페르소나 패널 → 컴팩트 카드.
- 다중 일자 트렌드 (기능 작업).
- 일일 자동 수집 (cron/GH Actions).

**블로커:** 없음.

---

## 2026-05-13 · UI-1 디자인 시스템 v2 + 사이드 채팅 인프라 (Phase 1)

**브랜치:** `style-ui-redesign-phase1`
**카테고리:** `style`
**상태:** in-progress

**배경 (사용자 요청):**
"시스템 UI가 처음 깃허브에 들어있던 코드 때문에 틀에 갇혔는데, 트렌디하고 깔끔하게 새롭게 디자인. 좌측 사이드바, 중간 메인, 필요시 우측 LLM 채팅창. ChatGPT/Claude 같이 라운드 카드 프레임. AI 친화적 UI/UX."
+ "깔끔한 흰색에 파란색이 포인트인 시스템."

**선택 (AskUserQuestion 3건 Recommended):**
- 진행 방식: Phase 1 (디자인 시스템 + 인프라) 먼저
- 사이드 채팅: 상단 토글 버튼 on/off, 컨텍스트 자동 인지
- 폰트: Pretendard 단일

**한 일:**
1. `assets/styles.css` 전면 리뉴얼 — 디자인 토큰, Pretendard, 흰색 + 파랑 액센트(`#2563EB`), 라운드 12~16px, subtle shadow, 일관된 모던 위젯(버튼·라디오·탭·입력·expander), 카드 컴포넌트, 빠른 액션 그리드.
2. `ui/styles.py` 강화 — `page_header(chat_toggle_key=...)` 헤더 + 💬 채팅 토글, `section_label()` 헬퍼.
3. `ui/layout.py` 신설 — `main_and_chat()` 컨텍스트 매니저로 메인 + 우측 사이드 채팅. `render_chat_panel()` 헬퍼. 페이지 컨텍스트 lazy 평가.
4. `ui/sidebar.py` modern — 브랜드 마크 + 섹션 레이블 + 깔끔한 상태 칩.
5. `ui/home_tab.py` Phase 1 demo 적용 — 페르소나 welcome, 메트릭 3개, 부서 뉴스/AI 인사이트(채팅 토글에 따라 반응형), 빠른 액션 그리드.
6. 전체 84/84 통과 (UI 변경, 로직 변경 없음).

**Phase 2 TODO (다음 세션):**
- `ui/board_tab` / `ui/ingest_tab` / `ui/news_tab` / `ui/bookmarks_tab` / `ui/sola_tab` / `ui/proposal_workbench` / `ui/roadmap_tab` 에 새 디자인 + 사이드 채팅 적용.
- 각 페이지의 `page_context_fn` (현재 화면 내용 → LLM 컨텍스트) 정의.
- 기능 작업(다중 일자 트렌드, 일일 자동 수집 등)은 별도.

**블로커:** 없음. 기능 변경 0, CSS·레이아웃 헬퍼만 추가.

---

## 2026-05-13 · docs 작업 완료 보고 규칙

**브랜치:** `docs-completion-report-rule`
**카테고리:** `docs`
**상태:** in-progress

**배경 (사용자 요청):**
"개발 지시할 때마다 끝나고 나면 무엇이 어떻게 개발됐는지, 어떻게 조치됐는지, 다음 단계는 무엇인지 안내하도록 지침에 추가."

**한 일:**
1. `CLAUDE.md` 절대 규칙에 **8번** 추가 — 작업 완료 보고 의무.
   - (1) 무엇이 개발됐는지: 파일·함수·핵심 동작
   - (2) 조치: 테스트·금지패턴·커밋·푸시·PR 번호/링크/상태·CI
   - (3) 다음 단계: 후속 작업 1~3건 권장
   - 한 메시지로 보고, 단순 정보 질문 응답은 제외.
   - 형식 예시 포함 (✅ 제목 · 변경 · 조치 · 다음).

**다음 세션 TODO:**
- 다중 일자 트렌드 (오늘 vs 어제 vs 7일).
- 일일 자동 수집 (cron/GH Actions).
- 매트릭스 셀별 LLM 코멘트 일괄 생성.
- 작업 트리 검색창.

**블로커:** 없음.

---

## 2026-05-13 · M4-η 채택된 제안서를 채팅 컨텍스트에 자동 노출

**브랜치:** `feat-chat-adopted-context`
**카테고리:** `feat`
**상태:** in-progress

**배경:**
M4-ζ 로 의사결정 상태(adopted)는 영구 보존되지만, 이번 사이클의 LLM 호출에 영향을 안 주면 사이클이 완전히 닫히지 않음. 채택된 제안서를 채팅 컨텍스트로 자동 노출해 **새 결정이 과거 결정과 일관되도록** 마무리.

**한 일:**
1. `store/bookmarks.list_adopted_proposals(*, limit=5)` — adopted 제안서를 `decided_at` 내림차순 N건.
2. `sola/chat_ctx.build_context_block(..., adopted_proposals=...)` — "이전 사이클에서 채택된 제안서" 섹션. 제목 + 메모만 (본문 X). 배치: 첨부 제안서 → 채택 제안서 → 오늘 뉴스.
3. `ui/sola_tab._render_chat` — `list_adopted_proposals(limit=5)` 자동 주입.
4. `ui/proposal_workbench._do_discuss` — 대화 모드 동일. `_active_bm_id()` 로 활성 제안서 자신은 중복 제거.
5. `tests/test_bookmarks.py` 2건 + `tests/test_sola.py` 3건. 전체 84/84 통과.

**사이클 효과:**
- 어제 회의에서 "용접 자동화 PoC 채택" → adopted + 메모 "3분기 PoC 승인".
- 오늘 새 뉴스 수집 → 채팅에서 "이거 우리 어떻게 적용?" 물으면 LLM 이 어제 채택한 PoC 를 자동 인지하고 일관된 답변.

**다음 세션 TODO:**
- 다중 일자 트렌드 (오늘 vs 어제 vs 7일).
- 일일 자동 수집 (cron/GH Actions).
- 매트릭스 셀별 LLM 코멘트 일괄 생성.
- 작업 트리 검색창.

**블로커:** 없음. 채택 제안서가 0건이면 컨텍스트 섹션 미노출 (graceful).

---

## 2026-05-13 · M4-ζ 북마크 의사결정 상태 + 자동 만료

**브랜치:** `feat-bookmark-status-expiry`
**카테고리:** `feat`
**상태:** in-progress

**배경 (사용자 요청):**
"생성한 제안서는 30일 후에 삭제되고, 채택한 제안서는 삭제되지 않게 하자."
한 사이클 닫는 다음 단계 — 의사결정 폐쇄 루프 + 자동 hygiene.

**한 일:**
1. `store/bookmarks.Bookmark` 에 `status`/`decision_note`/`decided_at` 필드 추가. 옛 record `from_dict` 호환.
2. `store/bookmarks.set_status(bm_id, status, note)` — 상태 갱신 헬퍼.
3. `store/bookmarks.expire_old(days=30, types=("proposal",), now=None)` — `created_at` 기준 N일 지나고 `status != "adopted"` 인 항목만 삭제. adopted 영구 보존, 다른 타입 미적용.
4. `app.py` — 세션당 1회 진입 시 `expire_old()` 자동 호출.
5. `ui/bookmarks_tab.py` — 카드마다 상태 셀렉터(pending/adopted/rejected) + 결정 메모 + 💾 저장. 상태 배지(⏳/✅/✖) + 정책 안내 캡션.
6. `ui/proposal_workbench.py` — 북마크 출처 활성 제안서에 좌측 상단 상태 셀렉터 (즉시 저장).
7. `tests/test_bookmarks.py` 9건 추가. 전체 79/79 통과.

**사이클 효과:**
- 작업장에서 ★ 저장 → 기본 `pending` → bookmarks 탭/작업장에서 회의 후 `adopted` 또는 `rejected` 로 변경 → adopted 는 영원히 보존, 다른 것은 30일 후 자동 정리.
- 30일 만료는 hygiene → 작업장 입력 selectbox 가 옛 폐기된 제안서로 어지러워지지 않음.

**다음 세션 TODO:**
- 채팅 컨텍스트에 "최근 채택된 제안 N건" 자동 노출 (사이클 간 연결).
- 다중 일자 트렌드.
- 일일 자동 수집 (cron/GH Actions).
- 매트릭스 셀별 LLM 코멘트 일괄 생성.

**블로커:** 없음. 만료는 idempotent + decided_at 가 없는 옛 record 도 안전.

---

## 2026-05-12 · M4-ε 제안서 작업장 (살아있는 제안서)

**브랜치:** `feat-proposal-workbench`
**카테고리:** `feat`
**상태:** in-progress

**배경:**
"한 사이클이 완성되려면?" 질문에 대해 사용자가 PDF export 대신 **제안서를 살아있는 문서로 다루는 워크플로**를 선택. 즉 제안서를 PC에서 .md 연 것처럼 카드 뷰로 보여주고, LLM 채팅으로 (1) 내용 수정 (2) 요약·개선 (3) 제안서 기반 대화를 이어가는 작업장.

**한 일:**
1. `sola/refine.py` 신설 — `refine_proposal(current_md, instruction, persona)` (현 MD + 지시 → 새 MD).
2. `sola/prompts.SYSTEM_PROPOSAL_REFINE` 추가 — "완성된 전체 MD 만 출력, 기존 섹션 구조 유지" 가정.
3. `ui/proposal_workbench.py` 신설 — 2열(좌: 카드 뷰 / 우: SOLA 패널), 입력 소스 selectbox(세션 직전 + 북마크), 모드 라디오(💬 대화 / ✏️ 수정), 액션(↶ undo · ★ 북마크 저장 · ⬇️ MD).
4. `app.py` — 작업실 sub-tab 에 "📝 제안서 작업장" 추가 (총 4개: SOLA / 작업장 / 뉴스 / 북마크).
5. `tests/test_refine.py` 4건 추가 (MD·지시 전달 / 페르소나 주입 / 페르소나 None / 낮은 temperature). 전체 70/70 통과.

**다음 세션 TODO:**
- 북마크에 status 필드 (`pending`/`adopted`/`rejected`) → 사이클 추적.
- 다중 일자 트렌드.
- 매트릭스 셀별 LLM 코멘트 일괄 생성.
- 작업 트리 검색창.
- 일일 자동 수집 (cron/GH Actions).

**블로커:** 없음. workbench 는 LLM 미설정 상태에서도 대화 모드의 LLM 호출만 실패하고 좌측 뷰·수정 모드는 graceful degrade.

---

## 2026-05-12 · M4-δ 제안서 채팅 컨텍스트 첨부

**브랜치:** `feat-chat-proposal-context`
**카테고리:** `feat`
**상태:** in-progress

**배경:**
사용자가 "제안서까지 채팅으로 이어가나?" 검증 요청. 코드 확인 결과 `chat_ctx.build_context_block`이 뉴스+로드맵만 받고 있어 생성된 제안서를 채팅 컨텍스트로 못 잇는 갭 발견. 갭 메움.

**한 일:**
1. `sola/chat_ctx.build_context_block` 시그니처에 `proposal: str | None = None` 추가. 제안서가 있으면 최상단(뉴스보다 먼저)에 배치.
2. `ui/sola_tab._build_proposal_context` 신설 — 세션의 `sola_prop_result` + 북마크 selectbox 두 경로 통합.
3. `ui/sola_tab._render_chat` "📎 제안서 컨텍스트 첨부" expander 추가. 직전 제안서 없으면 토글 disable, 북마크 없으면 selectbox 빈 옵션만.
4. `tests/test_sola.py` proposal 케이스 3건 추가 (앞쪽 배치 / proposal-only / None·빈문자열 무시).
5. 전체 66/66 통과, on_click·외부 requests 0건.

**다음 세션 TODO:**
- 다중 일자 트렌드 (현재 오늘만).
- 매트릭스 셀별 LLM 코멘트 일괄 생성 (배치 미리 채우기).
- 제안서 PDF export.
- 작업 트리 검색창.

**블로커:** 없음.

---

## 2026-05-12 · chore Quick Wins (CI + 라우팅 정정 + env sanitize) ✅ merged

**브랜치:** `chore-quick-wins`
**카테고리:** `chore`
**상태:** ✅ merged (PR #5 → main `b5a3ba6`)

**배경:**
M1~M4-γ 진행 동안 `CLAUDE.md`/`DEV_GUIDELINES.md`/`README.md` 가 폐기된 옛 파일명(`scraper.py`/`insights.py`/`cardnews.py`)을 가리키고 있어 다음 세션이 잘못된 파일을 찾을 위험. PR 자동 검증도 부재. `.env.example` 에 실제 API 키가 박혀 커밋된 상태.

**한 일:**
1. `.github/workflows/ci.yml` 신설 — py_compile · on_click 금지 · requests 직접호출 금지(scraping/http.py 제외) · pytest 4단계 검증.
2. `CLAUDE.md` — 도메인 설명 + 라우팅 표 + 검증 명령 갱신 (실제 패키지 구조 `scraping/ roadmap/ store/ sola/ persona/ ui/` 반영).
3. `DEV_GUIDELINES.md` §2/§3/§4/§6/§8 — 파일별 역할표, 라우팅 표, invariant, 검증 명령, 스택 모두 갱신.
4. `README.md` — 옛 파일명 제거, 페이지 스모크 안내 → 일반 pytest 안내.
5. `.env.example` — Groq 실키를 `your-api-key-here` placeholder 로 교체.

**블로커:** 없음. 단, 이전에 커밋된 실키는 별도 rotate 필요.

---

## 2026-05-12 · M4-γ 자동화 기회 매트릭스 + 북마크

**브랜치:** `claude/plan-insight-board-system-5MfMe`
**카테고리:** `feat`
**상태:** in-progress (PR #3 에 누적)

**한 일:**
1. `sola/opportunity.py` — 부서×공정 셀별 점수(`score_cells`) + 셀당 한 줄 LLM 코멘트(`llm_commentary`, 캐시).
2. `sola/prompts.py` — `SYSTEM_OPPORTUNITY` 추가.
3. `store/bookmarks.py` — JSONL 영구화 (`data/bookmarks/items.jsonl`). 4가지 타입(opportunity/proposal/news/task).
4. `ui/board_tab.py` — 자동화 기회 매트릭스 섹션(표 + 2열 카드 + ☆ 북마크 + 페르소나 부서 강조).
5. `ui/bookmarks_tab.py` 신설 — 타입 필터 + 카드 리스트 + 🗑️ 삭제.
6. `app.py` — 작업실에 "📌 북마크" sub-tab 추가.
7. `ui/sola_tab.py` — 제안서 결과에 ☆ 북마크 버튼.
8. 테스트 11건 추가 (opportunity 5 + bookmarks 6). 전체 63/63 통과.

**다음 세션 TODO (M4-δ 또는 M5 후보):**
- 작업 트리에 검색창 (수천 작업 대비).
- 제안서 PDF export (한글 폰트 임베딩).
- GitHub Actions CI (pytest + py_compile + 금지 패턴).
- 다중 일자 트렌드 (현재 오늘만).
- 부서별 매트릭스 셀별 LLM 코멘트 일괄 생성 (배치 미리 채우기).

**블로커:** 없음. 페르소나 미설정 상태에서도 매트릭스/북마크 모두 정상 동작.

---

## 2026-05-12 · M4-β 페르소나 + 3영역 UI 재편

**브랜치:** `claude/plan-insight-board-system-5MfMe`
**카테고리:** `feat`
**상태:** in-progress (PR #3 에 누적)

**한 일:**
1. `persona/` 패키지 신설 — schema(dataclass) / store(JSON) / context(LLM 프롬프트 블록).
2. `ui/sidebar.py` — 페르소나 설정 패널(부서 select + 직무 자유 입력 + 관심 Lv3 멀티) + 영역 선택 + LLM 상태.
3. `ui/task_tree.py` — 부서→Lv1→Lv2→Lv3 단계적 드릴다운 위젯, board·propose에서 재사용.
4. `ui/home_tab.py` 신설 — 페르소나 카드, 우리 부서 관련 뉴스, 부서 AI 인사이트, 빠른 행동.
5. `app.py` 3영역 재편 — 홈 / 탐색(수집·로드맵·보드 sub-tabs) / 작업실(SOLA·뉴스 sub-tabs).
6. `sola.propose.propose_for_task` 가 `persona=` 인자 받고 시스템 프롬프트에 페르소나 자동 주입.
7. `ui/sola_tab.py` 채팅·제안서가 페르소나 컨텍스트 사용, 작업 선택이 task_tree 드릴다운으로.
8. `ui/board_tab.py` — 사용자 부서 인사이트 카드를 맨 앞으로 정렬, 강조 테두리 + 🎯 뱃지.
9. 테스트 7건 추가, 전체 52/52 통과.
10. `tests/conftest.py` — `persona.store`, `store.cache`, `store.chat_log` 의 from-import 바인딩도 동기 패치.

**다음 세션 TODO (M4-γ 후보):**
- `sola/opportunity.py` — 부서×공정 매트릭스 셀별 자동화 점수 (배치 LLM).
- `store/bookmarks.py` — 관심 뉴스/제안서 즐겨찾기 영구화.
- 작업 트리에 검색창 추가 (수천 작업 대비).

**블로커:** 없음. 페르소나 미설정 상태에서도 모든 화면이 정상 동작 (안내 메시지만 표시).

---

## 2026-05-12 · M4-α 본문 Enrich + 도메인 사이트 (AI Times, 오토메이션월드)

**브랜치:** `claude/plan-insight-board-system-5MfMe`
**카테고리:** `feat`
**상태:** in-progress (PR #3 에 누적)

**시스템 재기획 (사용자 확정):**
- 목적 재정리: "조선소 작업 정의를 알고 있는 AI 어시스턴트가 외부 기술 동향을 우리 작업에 어떻게 적용할지 번역해주는 시스템".
- 페르소나 = 부서(엑셀 자동) + 자유 입력 직무 — M4-β.
- UI 3영역(홈/탐색/작업실) 재편 — M4-β.
- M4-α 부터 순차 진행.

**M4-α 한 일:**
1. `scraping/enrich.py` — 본문 fetch + LLM 키워드/요약, 본문 해시 캐시(`store.cache`).
2. `scraping/tech_sites.py` — AI Times, 오토메이션월드 휴리스틱 수집, `search_all()` 합본.
3. `sola/prompts.py` — `SYSTEM_KEYWORD_EXTRACT`, `SYSTEM_SUMMARY_SHORT` 추가.
4. `store/news_db.py` 컬럼 확장(`content`, `keywords_llm`, `summary_llm`, `enriched_at`), 과거 Parquet 안전 로드, last-wins 중복 제거.
5. `ui/ingest_tab.py` — 멀티 소스 선택 + "본문 Enrich" 버튼 + 진행률 + LLM 결과 뱃지/카드.
6. 테스트 10건 추가 (HTTP·LLM 모킹), 전체 45/45 통과.

**다음 세션 TODO (M4-β):**
- `persona.py` + `store/persona_db.py` — 부서·직무·관심 작업 영구화.
- `ui/` 3영역 재편 — `home_tab.py` 신설, 5탭 → 홈/탐색/작업실로 합쳐서 그룹화.
- 작업 트리 뷰 (부서 → Lv1 → Lv2 → Lv3 드릴다운).
- 페르소나 컨텍스트가 SOLA 채팅·인사이트 카드에 자동 주입.

**블로커:** 없음. 본문 enrich 결과는 LLM 키 있어야 풀 동작.

---

## 2026-05-12 · M3 트렌드·부서별 AI 인사이트·채팅 영구화

**브랜치:** `claude/plan-insight-board-system-5MfMe`
**카테고리:** `feat`
**상태:** in-progress (PR #3 에 누적)

**한 일:**
1. `store/cache.py` — 파일 기반 LLM 응답 캐시 (SHA1 16자 키).
2. `store/trends.py` — `by_date(published_at 우선)` / `by_source` / `top_keywords` 집계.
3. `store/chat_log.py` — 채팅 히스토리 JSONL 영구 저장/복원.
4. `sola/insight.py` + `SYSTEM_INSIGHT` — 부서 한 문단 인사이트, (부서·뉴스 제목셋·모델) 키 캐싱.
5. `ui/board_tab.py` — 일자별·소스별 트렌드 차트, 버튼 트리거 부서별 인사이트 카드(2열).
6. `ui/sola_tab.py` — 채팅 자동 로드/저장, 초기화 시 파일도 제거.
7. 테스트 11건 추가 (캐시·트렌드·채팅·인사이트 캐싱). 전체 35/35 통과.

**다음 세션 TODO (M4 후보):**
- 제안서 PDF export (한글 폰트 임베딩).
- GitHub Actions CI (pytest + py_compile + 금지 패턴 검사).
- 부서별 인사이트 카드에 "원문 보기" 링크 / 근거 뉴스 토글.

**블로커:** 없음.

---

## 2026-05-12 · M2 구글 뉴스 + SOLA LLM 채팅

**브랜치:** `claude/plan-insight-board-system-5MfMe`
**카테고리:** `feat`
**상태:** in-progress (PR #3 에 누적)

**한 일:**
1. `scraping/google.py` — Google News RSS 검색 (ElementTree 파서, 추가 의존성 없음).
2. `ui/ingest_tab.py` — 소스 셀렉터(네이버/구글/둘 다) 및 소스별 저장 통계 표시.
3. `sola/client.py` — OpenAI SDK 단일 진입점, `LLM_BACKEND` 라우팅, `LLMNotConfigured` 예외.
4. `sola/prompts.py` — 한국어 출력 가정 시스템 프롬프트 3종.
5. `sola/summarize.py`, `sola/propose.py`, `sola/chat_ctx.py` — 요약/제안서/채팅 컨텍스트.
6. `ui/sola_tab.py` 재작성 — 3 sub-mode + `st.chat_message`/`st.chat_input` 기반 채팅.
7. `config.py` 에 `python-dotenv` 로 `.env` 자동 로드, `requirements.txt` 갱신.
8. 테스트 12건 추가 (구글 RSS / SOLA 호출·컨텍스트 모킹). 전체 24/24 통과.

**다음 세션 TODO (M3):**
- 제안서 PDF export (Markdown → PDF).
- 부서별 자동 인사이트 카드 (배치 LLM 호출 + 캐싱).
- 채팅 히스토리 영구 저장(JSONL).

**블로커:** 없음. 사용자가 `.env` 에 `LLM_API_KEY` 를 채우면 즉시 동작.

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
