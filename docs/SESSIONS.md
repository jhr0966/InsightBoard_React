# SESSIONS — 작업 세션 로그

> **최신 세션이 상단.** 다음 세션은 상단 1개만 읽고 복원한다.
> 완료된 세션은 "✅ merged"로 닫는다.

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
