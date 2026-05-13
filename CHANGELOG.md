# Changelog

모든 주요 변경은 여기에 기록한다. 포맷: [Keep a Changelog](https://keepachangelog.com/) + SemVer.
릴리스 = `main` 머지 시점.

## [Unreleased]

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
