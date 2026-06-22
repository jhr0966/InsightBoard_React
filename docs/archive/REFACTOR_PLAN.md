> 📜 **아카이브 (완료·히스토리)** — React 전환 과정의 계획/기록 문서. 현재 코드와 다를 수 있다. 현행 기준은 `CLAUDE.md` · `docs/ARCHITECTURE.md` 를 보라.

# REFACTOR_PLAN — 정리·정합 로드맵

> 1차 완성(M1~M3) 후 누적된 드리프트·결함·중복을 단계적으로 정리하는 작업 계획.
> 각 Phase 는 독립 커밋. 결함은 `F<n>`, 결정 필요 항목은 `결정-<n>`, 데드 코드는 본문 표기.
> **이 문서가 정리 작업의 source of truth.** 문서 라우팅(`CLAUDE.md`/`DEV_GUIDELINES.md`)이 여기를 가리킨다.

---

## 진행 현황

| Phase | 범위 | 상태 |
|---|---|---|
| **0** | 문서 정합 (ARCHITECTURE/CLAUDE/DEV_GUIDELINES/INVARIANTS + 본 문서) | ✅ 완료 (PR #89) |
| **1a** | 무논쟁 correctness — F5·F7·F11·F12 | ✅ 완료 (PR #89) |
| **2** | UI 중복 제거 — `get_persona` 승격 + `app_side_stats` 단일화 | ✅ 완료 (PR #89) |
| **1b** | 결정-1 반영 (제안서·요약 흐름) | ✅ 완료 (PR #90 Phase B — SOLA 작업실 연결) |
| **1c / E** | 결정-2 반영 (enrich→매칭 가중) | ✅ 완료 (PR #91) |
| **3** | 데드 코드 삭제 (모듈 4종 + no-op 패널·레거시 채팅·batch helper) | ✅ 완료 |

> ⚠ 작업 브랜치 제약: 현재 세션은 `claude/nice-bell-eEZLj` 단일 브랜치에서 진행(harness 지정). 통상 규칙(Phase 당 새 브랜치)과 달리 Phase 0·1a 가 같은 PR(#89)에 누적됨.

---

## Phase 4 — 부분 갱신(UX)·성능 (🔄 1차 완료, 잔여 로드맵)

> 목표: 클릭/상태 변경 시 **문서 전체 reload(흰 깜빡임) 제거** + rerun 비용 절감.
> 1차(PR: refactor-partial-updates): 일자별 parquet 메모 · 자산/헬퍼 캐시 · 뉴스 수집
> 브라우저 `@st.fragment` 부분 rerun (dialog-in-fragment 브라우저 실측 OK).

**잔여 — 앵커(`href="?…"`) → 위젯 전환 우선순위** (모두 same-screen·전체 reload 유발):

| 우선 | 대상 | 위치 | 패턴 |
|---|---|---|---|
| ~~P1~~ ✅ | 보드 기회 액션 → 버튼+pending 전환 완료(2026-06-10) | `board_v2.py` | 완료 |
| ~~P1~~ ✅ | 보드 키워드 관리 → 버튼+pending 전환 완료(2026-06-10) | `board_v2.py` | 완료 |
| ~~P1~~ ✅ | ~~작업 정의 `?td_view/td_edit/td_hist/td_action` 스위트~~ → 목록=오버레이 버튼, 액션=버튼+`_td_nav_pending`(query 번역 — 딥링크 호환) 전환 완료 | `task_def_manage.py` | 완료(2026-06-10) |
| ~~P2~~ ✅ | ~~채팅 빠른 작업 칩 `?sola_action=`~~ → 버튼+pending 전환 완료 | `chat_panel.py` `_render_quick_action_chips` | 완료(2026-06-10) |
| P2 | SOLA 스레드 전환 `?switch_thread=` | `sola_workshop_v2.py` (~847) | 항목별 컨테이너+오버레이 |
| P3 | 인사이트 히트맵/매트릭스 SVG 클릭 `?ia_*` | `insights_v2.py` | SVG 내 앵커라 위젯 전환 불가 — fragment 로 reload 비용만 절감 검토 |
| P3 | persona_editor 앵커(topbar/사이드바) | `app_shell.py`·`sidebar.py` | HTML topbar 구조상 유지(빈도 높지만 reload 후 모달이라 체감 낮음) |

**fragment**: ✅ 우측 채팅 패널 완료(2026-06-10 — SOLA 작업실 외 화면 부분 rerun). 잔여 후보: 보관함 칸반(액션은 `st.rerun(scope="app")` 로 상단 소비자 유지).

## 결함 대장 (F-번호)

코드 전수 확인 결과. **[실재]** 만 수정 대상, **[기각]** 은 과진단으로 확인돼 작업 없음.

| ID | 판정 | 위치 | 내용 |
|---|---|---|---|
| F3 | **[기각]** | `store/match.py:41` | news_cols 가 동적으로 존재 컬럼만 필터 → 불일치 없음 |
| F5 | **[실재]** ✅1a | `ui/archive_v2.py` | 북마크 채택/보류/복구 후 토스트 없음 → 액션 피드백 부재 |
| F7 | **[실재]** ✅1a | `store/chat_log.py:35,45` | `ts` 저장·로드 누락 → workshop 이 추가한 timestamp 영속 안 됨 |
| F8 | **[기각]** | `store/match.py:13` | 토큰(`[가-힣A-Za-z0-9]{2,}`) 단위 교집합 → "RAIN" 내 "AI" 오탐 없음 |
| F9 | **[기각]** | data_management_v2 외 | 모든 `sort_values` 결과가 사용/재할당됨 → 데드 정렬 없음 |
| F11 | **[실재]** ✅1a | `store/task_defs_db.py:324` | docstring 이 "전체 rollback" 주장하나 행마다 commit(원자성 거짓) + production 호출 0 |
| F12 | **[실재]** ✅1a | `ui/sola_workshop_v2.py:56` | `match_today=32, opportunities=4` 하드코딩 → 실데이터 무관 |

> F1·F2·F4·F6·F10 은 이전 세션 요약에만 있던 가설로, 코드 재확인에서 재현되지 않아 대장에서 제외(필요 시 재발견하면 재등재).

### Phase 1a 적용 내역 (PR #89)

- **F5**: `_STATUS_TOAST` 맵 + `render()` 에서 `_consume_action_if_any()` 결과가 있으면 `st.toast`.
- **F7**: `save_history`/`load_history` 가 `ts` 가 있으면 함께 영속·복원(없으면 생략 — 후방 호환).
- **F11**: docstring 을 실제 동작(행별 즉시 commit·부분 적용 가능·비원자)으로 정정. 진짜 트랜잭션은 호출부 책임으로 명시. (함수 자체는 테스트 의존이라 보존 → Phase 3 에서 데드 여부 재판정)
- **F12**: `sola_workshop_v2._archive_stats` 를 `board_v2._archive_stats()`(60초 캐시 `_board_kpis` 실데이터) 위임으로 교체. 실패 시 0 폴백.

---

## 데드 코드 대장

production(app.py·ui/·scripts/) import 0 확인. Phase 3 에서 삭제 후보.

| 대상 | 근거 | 처리 |
|---|---|---|
| `ui/layout.py` | `main_and_chat`/`render_chat_panel`/`split_with_chat` 호출 0 | ✅ Phase 3 삭제 |
| `ui/task_tree.py` | 드릴다운 위젯, 호출 0 | ✅ Phase 3 삭제 |
| `sola/propose.py` | (구 데드) | ✅ 부활 — SOLA 작업실 `propose_for_task` |
| `sola/summarize.py` | (구 데드) | ✅ 부활 — SOLA 작업실 뉴스 요약 |
| `sola/insight.py` | production import 0 | ✅ Phase 3 삭제 |
| `sola/chat_ctx.py` | production import 0 | ✅ Phase 3 삭제 |
| `sola/side_context.py` | `ui/layout` 삭제로 호출 0 (orphan) | 보존 — 사이드 채팅 컨텍스트 연결 대상 |
| `app_shell.render_app_side/sola` (+패널 토글) | no-op, 5화면이 호출 | ✅ Phase 3 삭제 (호출부+함수) |
| `chat_panel.render` (구 bottom expander) | render_side 가 대체, app.py 미사용 | ✅ Phase 3 삭제 |
| `sola_workshop_v2._SOLA_TEMPLATE` + `sola_main.html` | 정의만, read 0 | ✅ Phase 3 삭제 |
| `store/task_defs_db.upsert_many` | production 은 단건 upsert 만 사용 | ✅ Phase 3 삭제 (재판정→데드) |

> ✅ 결정-1 A 로 `propose`/`summarize` 는 부활(SOLA 작업실 연결). 나머지 4종(`layout`·`task_tree`·`insight`·`chat_ctx`)은 Phase 3 에서 테스트 동반 삭제 완료. `side_context` 는 layout 삭제로 orphan 이나 보존.

---

## Phase 2 — UI 중복 제거 (완료)

correctness 영향 없는 순수 dedup. PR #89 에 누적.

1. ✅ **`get_persona` 승격** (`ui/app_shell.get_persona`): 5개 v2 화면(`board`/`insights`/`archive`/`sola_workshop`/`data_management`)에 동일 구현되어 있던 `_load_persona` 를 단일 진입점으로 통합. 호출처 일괄 교체.
2. ✅ **app_side_stats 단일화**: `archive_v2._archive_stats_oa` / `insights_v2._archive_stats_ia` / `data_management_v2._archive_stats_dm` 가 `board_v2._archive_stats` 와 정확히 동일한 계산을 별도 사본+개별 캐시로 반복 → 세 사본을 board 60초 캐시(`_board_kpis`) 위임으로 교체. 4중 캐시 → 1중 캐시. unused import 동반 정리.
3. ⏸ **`ui/toast.py`**: 현재 `st.toast` 사용처 1곳뿐 → dedup 가치 부족, 보류. F1b/F1c 에서 사용처 증가 시 재검토.
4. ⏸ **`ui/url_state.py`**: `del st.query_params[k]` 가 10여 곳에 흩어져 있으나 각 함수가 다른 키·다른 후속 로직 → 단순 헬퍼로 추출 가치 적음. 패턴이 늘어나면 재검토.

**효과**: -114줄(161 삭제/47 추가) · 캐시 일관성(보드와 좌측 nav 카운트가 항상 동일) · `Persona` import 경로 단순화.

---

## 결정 대기 항목

### 결정-1 — 제안서/요약 흐름 (sola/propose·summarize)
- 현재: SOLA 작업실은 자유 채팅만. `sola/propose.py`(자동화 제안서)·`summarize.py`(뉴스 요약)는 구현돼 있으나 UI 미연결(데드).
- 선택지: **(A)** 작업실에 "제안서 생성"·"요약" 액션으로 부활 / (B) 완전 삭제하고 채팅 프롬프트로만.
- **확정: A** (2026-06-01 사용자). → Phase 1b 에서 UI 연결.

### 결정-2 — enrich → 매칭 연결
- 현재: `scraping/enrich.py`(본문 fetch + LLM 키워드/요약)는 수집 탭에서 옵션이나, 매칭(`store/match.py`)이 enrich 된 keywords 를 충분히 활용하는지 점검 필요.
- 선택지: **(A)** enrich keywords 를 매칭 가중치에 반영 / (B) 현행 유지.
- **확정: A** (2026-06-01 사용자). → Phase 1c.

---

## Phase 3 — 데드 코드 삭제 (✅ 완료)

- ✅ **모듈 4종**: `ui/layout.py`·`ui/task_tree.py`·`sola/insight.py`·`sola/chat_ctx.py` + 테스트 동반 정리(`test_sola_insight` 삭제, `test_sola`/`test_preview`/`test_chat_log`/`test_task_def_upload` 수술적 편집).
- ✅ **no-op 패널·레거시·미사용**: `app_shell.render_app_side`/`render_app_sola`(no-op 본문 ~300줄 + 5화면 호출부 + 패널 토글 클러스터) · `chat_panel.render`(구 bottom expander) · `sola_workshop_v2._SOLA_TEMPLATE`+`sola_main.html` · `task_defs_db.upsert_many`(재판정→데드) · `persona_page._archive_stats`. 부수 import(ASSETS_DIR·Iterable·bookmarks·llm_model) 정리.
- **보존**: `sola/{propose,summarize}`(결정-1 A 부활) · `sola/side_context`(orphan 이나 사이드 채팅 컨텍스트 연결 대상).
- 검증: pytest 702→**686 passed** · 잔여 import 0(`grep -rn`) · 금지 패턴 0 · py_compile OK.

---

## 다음 세션 시작점

> PR #89 (Phase 0+1a+2) 머지 직후 새 세션을 시작할 때 이 섹션만 보면 됨. 두 단계는 서로 독립 → 병렬 가능.

### Phase 1b — SOLA 작업실에 `propose`·`summarize` 액션 연결 (결정-1 A)

**브랜치명:** `feat-sola-propose-summarize`

**진입 파일 (읽을 것만):**
- `ui/sola_workshop_v2.py` — `_render_main` / ws-ctx 패널 영역 (액션 버튼 추가 위치)
- `sola/propose.py` — 자동화 제안서 생성기 (현재 데드). 시그니처·LLM 호출 형태 파악.
- `sola/summarize.py` — 뉴스 요약기 (현재 데드).
- `store/sola_threads.py` — 결과 메시지 저장 방식 (assistant 메시지로 thread 에 append).

**UX 안 (첫 메시지로 사용자에게 2~3개 제시 후 합의):**
1. **ws-ctx 우측 패널 카드** — "📝 제안서 생성"·"📰 요약" 버튼이 우측 컨텍스트 패널 상단에 카드로 노출. 클릭 시 현재 thread context(`?from=` payload 또는 최근 메시지) 로 LLM 실행, 결과를 assistant 메시지로 채팅에 append. **추천(기존 인계 흐름과 자연스러움).**
2. **채팅 입력창 toolbar** — 입력창 위에 `[ 제안서 ] [ 요약 ]` 빠른 액션 칩. 빈 thread 에서도 즉시 사용 가능.
3. **topbar 액션 메뉴** — `app_shell.render_topbar` 우측에 드롭다운으로. 화면 어디서나 호출 가능하나 UI 변경 폭이 큼.

**완료 기준:** propose/summarize 가 ws-ctx 카드(또는 합의된 위치)에서 실행되어 결과가 thread 의 assistant 메시지로 append · `?from=opp|matrix` 인계 페이로드와도 호환 · 회귀 테스트 1~2건.

### Phase 1c — `scraping/enrich` keywords → `store/match.score_matches` 가중치 (결정-2 A)

**브랜치명:** `feat-enrich-match-weight`

**진입 파일:**
- `scraping/enrich.py` — `enrich_article(...)` 의 출력 스키마 (`keywords` 필드 확인).
- `store/match.py` — `score_matches(...)` 의 가중치 계산 로직 (현재 기사 title/desc 토큰만 사용?).
- `store/news_db.py` — 저장 시 `keywords` 컬럼이 보존되는지 (Parquet schema).

**작업 요지:** `score_matches` 가 기사의 enrich 된 `keywords` (LLM 추출) 를 매칭 점수에 가중치로 추가. enrich 안 된 기사는 현행 fallback.

**완료 기준:** enrich keywords 가 있는 기사가 그렇지 않은 기사보다 동일 작업 정의에 대해 더 높은 score → 테스트로 검증.

### 공통 — 시작 직전 체크

```bash
git fetch origin main && git checkout main && git pull
git checkout -b feat-sola-propose-summarize   # 또는 feat-enrich-match-weight
python -m pytest -q                            # 656/656 baseline 확인
```

---

## ✅ post-M3 완성도 하드닝 (2026-06, 완료)

M1~M3 + Phase 0~3·E·F 이후 **시스템 완성도 점검**에서 발견한 잠재 결함 4건 + 문서 드리프트를 수정(PR #102·#103). `pytest 724 passed` · 금지패턴 0 · 70 모듈·69 테스트.
- **C1/C2/D4** `news_db`: `collected_at` 컬럼이 없어 board 데일리 브리핑 매칭경로가 KeyError→broad except 로 **silent death** 하던 것 → `_ARTICLE_COLS` 추가 + `enriched_at→published_at` 폴백. `fillna("")` 로 null→`""`(깨진 `<img src=nan>` 차단).
- **B4** 데이터-경로 silent 실패 로깅(board 매칭조인·news_db 깨진 parquet·enrich 파싱).
- **D1/D2** archive 정적 목업을 `archive_main.html` 에서 직접 제거 + 런타임 `_strip_oa_mockups` 삭제.
- **C3/C4** SQLite 동기화 실패 `IngestResult.sqlite_error` 표면화 + `task_defs_db._migrate`(user_version + 누락 컬럼 ALTER).
- **A3** ARCHITECTURE/INVARIANTS 를 코드(모든 화면 통일·작업실도 `render_side`·`[2.3,1]`)에 맞춤.

---

## 개선 백로그 (forward-looking, 2026-06) — 우선순위

점검 후 forward-looking 리뷰로 도출. 효과(high/med/low) × 노력(S/M/L).

### 🔴 우선 (high)
- ✅ **수집 degraded 가시화** (완료) — `data_management._collect_alert_html` 상단 경고 배너(실패/24h+ 정체) + `daily_scrape --fail-on-empty`(0건 시 exit 1, `scrape-daily.yml` ON).
- 🟡 **매칭/뉴스 캐시 통합** (부분 완료) — ✅ `load_news_for_days` 디스크 재읽기 memo(`_news_window_memo`, mtime 무효화). **남음**: `score_matches`(O(news×tasks)) 4곳 독립 재계산을 공유 캐시(news-window+tasks-hash 키)로 — 캐시키 위험 커 별도 PR. [M]
- 🟡 **silent except → 로깅 가드** (대부분 완료) — ✅ `ui/_safe.guard(label)` 도구 + `data_management` 5 · `insights_v2` 3 · `board_v2` 8(브리핑 2 + 매트릭스/KPI/키워드/채팅컨텍스트 6) 적용. **남음**: 잔여 `except: pass`(cache-clear·optional-step)는 대부분 의도적 — 신규 silent 로드 생길 때만 가드. [S]

### 🟡 다음 (med)
- ✅ **screen `render()` 스모크 테스트** (완료) — `tests/test_screen_smoke.py`(+13): 6화면 render() 가 빈 데이터에서 예외 없이 통과 + chat_context_block + SOLA 인계 경로. Streamlit 이 ScriptRunContext 없이 위젯 기본값 반환이라 실제 호출로 조립 깨짐을 잡음(mock 최소 — brittle 아님).
- **네이버 파서 실HTML fixture** — 합성 HTML만 검증, 10-셀렉터 fallback·`≥2` 휴리스틱이 실파손 지점 → 실 SERP fixture 1~2건. [M]
- ✅ **SOLA 작업실 2-채팅 정리** (완료, 결정: 채팅으로 통합) — 작업대 액션(제안서 생성·뉴스 요약·새 대화)을 우측 채팅 **빠른 작업** 칩(`chat_panel._quick_actions_html`, `?sola_action=`)으로 흡수, `_consume_sola_action_from_query_if_any` 가 pending flag 로 매핑. 작업대 중복 버튼 3개 제거.
- ✅ **handoff 배너 LLM 배선** (완료, 결정: 자동 실행) — `_auto_run_handoff_if_any` 가 `?from=` 인계 도착 시 prefill 을 1회 자동 전송(`_handoff_signature` 중복차단). 배너에 자동검토 confirm 줄.
- ✅ **HTML placeholder 소비 검증** (완료) — `tests/test_template_placeholders.py` 가 4화면 `{{TOKEN}}` 전수 소비 정적 교차검증.
- ✅ **`sola.client` 타임아웃/재시도** (완료) — 클라이언트에 `timeout=45s`+`max_retries=2` 명시.
- 🟡 **oversized 모듈 분할** (부분 완료) — ✅ `data_management_v2`(1623→1406) 의 순수 프레젠테이션/라우팅 빌더를 `ui/data_management_render.py`(259)로 추출(re-import 하위호환, 동작 불변). **남음**: `board_v2`(~1.7k) — 빌더가 데이터-결합도 높아(load·score 내장) pure 추출 폭이 작고 신중 필요, 별도 PR. [S~L]

### ⚪ 여력 시 (low)
✅ 매칭 `iterrows()`→`to_dict("records")` · ✅ `run_log._trim` 사이즈 게이트 · ✅ 의미매칭 엣지케이스 테스트(+6: `_build_idf`/`_tfidf_vec`/`_cosine`/대칭성). **남음**: 라이브 수집 백그라운드+폴링(네트워크 차단).

### 🚧 외부 의존/결정 (단독 처리 불가)
임베딩 RAG(임베딩 백엔드 부재 — 현재 TF-IDF 대체, `_tfidf_vec`/`_cosine` 스왑으로 확장) · PR #49(글래스모피즘 디자인 채택/close 결정).
