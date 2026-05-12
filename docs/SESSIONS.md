# SESSIONS — 작업 세션 로그

> **최신 세션이 상단.** 다음 세션은 상단 1개만 읽고 복원한다.
> 완료된 세션은 "✅ merged"로 닫는다.

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
