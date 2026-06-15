# REACT_PREP_INVENTORY — React 전환 준비물 실측 카탈로그

> 계획문서 [`REACT_MIGRATION_PLAN.md §0.5`](./REACT_MIGRATION_PLAN.md)의 **상세 부속서**.
> 전환 직전 코드 실측(2026-06-15)으로 "무엇을 어디로 옮겨야 React가 기계적으로 되는가"를 박제.
> 숫자는 `app.py` + `ui/` 기준(`__pycache__` 제외).

## 실측 요약

| 지표 | 값 | 전환 함의 |
|---|---|---|
| `st.session_state` 접근 | 310곳 / 유효 키 ~60개 | React 상태(서버 vs UI vs 이벤트)로 3분류 필요 |
| `st.rerun()` | 95곳 | pending→rerun 패턴 → React 이벤트/뮤테이션으로 치환 |
| `query_params` 키 | 24종 | 라우트 1종 + 이벤트 트리거 23종 분리 |
| `st.html(...)` | 85곳 | React 컴포넌트화 대상 |
| `unsafe_allow_html` | 13곳 | XSS 경로 → React는 기본 이스케이프 |
| `@st.dialog` | 0 (모달=query_params+html) | 모달도 라우트/상태로 재설계 |
| CSS | `assets/v2/*.css` 6 + `screens/*.css` 5 | 토큰 그대로 승계 |

---

## 1. 세션 상태키 카탈로그 (310곳 / ~60키)

React 이식 규칙: **(S)서버데이터→React Query, (U)UI로컬상태→useState/URL, (E)이벤트트리거→핸들러/뮤테이션(상태 아님)**.
`on_click 금지` 규칙 때문에 imperative 동작이 전부 "pending flag + rerun"으로 우회되어 있음 → 이들은 **상태가 아니라 이벤트**이므로 React에선 키 자체가 사라진다.

### (E) 이벤트 트리거 — React에서 소멸 (핸들러로 직결)
> `_do_*` (버튼 의도), `_*_pending` (처리 대기), `_*_toast`/`_msg` (1회성 알림), `_*_confirm`.

| 그룹 | 키 | React 대체 |
|---|---|---|
| 온보딩 | `_do_onb_start/next/prev/finish/close/dismiss/collect_now` | 핸들러 onClick |
| 페르소나 | `_do_persona_page_save/derive/reset/back`, `persona_page_msg` | mutation + toast |
| 작업정의 | `_do_task_def_ingest`, `_do_td_save`, `_task_def_pending`, `_td_nav_pending`, `_td_del_confirm`, `_task_def_toast`, `_td_toast` | mutation + 확인 다이얼로그 |
| 수집/키워드 | `_do_kw_settings_save`, `_kw_action_pending`, `_kw_action_toast`, `_sc_collect_modal_pending`, `_sc_diag_pending` | mutation |
| 출처 | `_do_src_add`, `_do_src_action`, `_src_action_toast` | mutation |
| 제안/SOLA | `_do_generate_proposal`, `_do_save_proposal`, `_do_sola_send`, `_do_ask_prefill`, `_do_delete_thread`, `_do_toggle_pin`, `_switch_thread_pending`, `_sola_action_pending`, `_sola_action_toast` | mutation/SSE |
| 기회/보관 | `_do_archive_action`, `_opp_action_pending`, `_opp_action_toast` | mutation |

### (U) UI 로컬 상태 — useState / URL 쿼리
| 키 | 의미 | React |
|---|---|---|
| `app_area` | 현재 화면 | **React Router 경로** (URL) |
| `_dm_active_tab`, `sc_collect_view`, `sc_browse_mode`, `sc_news_cat` | 데이터관리 탭/뷰/카테고리 | URL 탭 파라미터 |
| `_topbar_q`, `_topbar_q_seen`, `_news_search_q` | 검색어 | useState (debounce) |
| `_oa_expanded`, `_kw_settings_open`, `show_persona_editor` | 펼침/모달 토글 | useState / 라우트 |
| `_sc_table_sel`, `_sc_open_news` | 선택/열린 기사 | useState / URL `?news=` |
| `_onb_step`, `_onb_dismissed_session`, `onb_keywords` | 온보딩 진행 | useState (+localStorage) |
| `px_lv3` | 밀도/스케일 | UI 설정 |

### (S) 서버 데이터 캐시 — React Query (서버 소유)
| 키 | 출처 | React Query 키 |
|---|---|---|
| `persona` | `persona/store` | `['persona']` |
| `_board_brief_items` | `sola/board_brief` | `['board','brief']` |
| `_chat_context_for_sola` | 화면별 `chat_context_block` | `/api/assistant/context` |
| `sc_diag_result`, `_sc_collect_modal_result` | 수집 실행 결과 | collect mutation 응답 |
| `_onb_collect_result` | 온보딩 수집 | mutation 응답 |
| `_did_expire_check` | 캐시 만료 점검 | 서버 책임으로 이전 |

> **착수점**: (E) 그룹은 React에서 키가 사라지므로 가장 안전. (U)는 URL 설계가 핵심(아래 §2). (S)는 §3-API 계약에 종속.

---

## 2. 라우팅·이벤트 카탈로그 (query_params 24종)

Streamlit엔 라우터가 없어 **모든 화면전환·imperative 동작이 URL 쿼리**로 표현됨. React Router로 옮길 때 **진짜 라우트 vs 일회성 액션**을 분리한다.

| query_params 키 | 현재 용도 | React 매핑 |
|---|---|---|
| `app_area` | 메인 화면 선택 | **라우트** `/`,`/insights`,`/proposals`,`/collect`,`/taskdefs` |
| `from` | 뒤로가기 출발지 | 라우터 history / state |
| `lv`, `dept` | 인사이트 레벨·부서 필터 | URL 쿼리 `?lv=&dept=` |
| `news`, `bm_id`, `title` | 기사/북마크 상세 | URL `?news=` (모달 라우트) |
| `td_pid`, `td_q`, `td_action`, `tkw` | 작업정의 선택·검색·액션 | `/taskdefs/:id` + mutation |
| `keyword`, `kw_action`, `dm_clear_q` | 키워드 관리 액션 | mutation |
| `src_name`, `src_action` | 출처 액션 | mutation |
| `sola_action`, `sola_prefill`, `switch_thread` | SOLA 액션·스레드 전환 | mutation / `?thread=` |
| `opp_action`, `mx_select`, `ia_mx_select`, `hm_select` | 기회·매트릭스 선택 | useState / mutation |
| `persona_editor` | 페르소나 모달 | 라우트/상태 |
| `action`, `refresh` | 범용 액션·강제갱신 | mutation / invalidate |

> **함의**: `app_area`·`from`·`lv`·`dept`·`news` ≈ 진짜 URL 상태(공유·북마크 가능해야). 나머지 `*_action` 류는 React에서 URL이 아닌 **이벤트**로 — URL 오염 제거.

---

## 3. 컴포넌트 인벤토리 (st.html 85곳)

`ui/components.py` 빌더가 이미 컴포넌트 경계를 그어둠 → React 컴포넌트로 1:1 이식 가능. 화면 markup은 `assets/v2/screens/*.html` 셸을 채우는 구조.

### 공통 컴포넌트 (`ui/components.py` → `<Components/>`)
| 빌더 | React 컴포넌트 | CSS |
|---|---|---|
| `metric_card` / `metric_grid` | `<MetricCard>` / `<MetricGrid>` | `card.css` |
| `status_card` | `<StatusCard tone>` | `card.css` |
| `action_card` / `action_grid` | `<ActionCard>` / `<ActionGrid>` | `card.css` |
| `step_item` / `step_guide` | `<StepGuide>` | `card.css` |
| `render_screen_html` / `prepare_screen_html` | 셸 렌더러 → React 레이아웃 | `shell.css` |
| `inject_focus_nav` | topbar/nav | `sidebar.css`,`shell.css` |

### 화면별 st.html 밀도 (이식 순서 가늠)
| 파일 | st.html | 화면 |
|---|---|---|
| `ui/data_management_v2.py` | 22 | 뉴스 수집 + 작업정의 (카드뷰·모달) |
| `ui/board_v2.py` | 12 | 오늘의 보드 |
| `ui/sola_workshop_v2.py` | 11 | 자동화 제안 |
| `ui/onboarding.py` | 9 | 온보딩 |
| `ui/task_def_manage.py` | 7 | 작업정의 관리 |
| `ui/chat_panel.py` | 6 | 어시스턴트 패널 |
| `ui/components.py` | 5 | 공통 빌더 |
| `ui/persona_page.py` / `archive_v2.py` / `styles.py` / `app_shell.py` / `insights_v2.py` | 4/3/3/2/1 | — |

### CSS 토큰 (그대로 승계)
`assets/v2/`: `tokens.css`(색·간격·타이포 변수) · `card.css` · `shell.css` · `sidebar.css` · `scale.css` · `streamlit-overrides.css`(→ React에선 폐기).
`assets/v2/screens/`: `board/insights/data_management/archive/sola.css` → 화면별 모듈 CSS.

> **이식 순서 권장**: 공통 컴포넌트(components.py) → 저밀도 화면(insights 1, taskdefs) → 고밀도(data_management 22)로. 셸(`app_shell`)·토큰 먼저 깔고 화면을 채운다.

---

## 4. 식별·감사 필드 표준 (Phase 1 도입, Phase 2 활성)

모든 영구화 레코드·API 요청/응답에 포함. Phase 1은 단일 사용자라 기본값 상수.

```
user_id      str   소유 사용자        Phase1 기본 "local"
workspace_id str   테넌트/작업공간    Phase1 기본 "default"
created_by   str   행위자(감사)       Phase1 기본 "local"
created_at   str   생성 UTC ISO8601
updated_at   str   갱신 UTC ISO8601
```

### 현황 (실측)
- `store/_audit.py` — **표준 헬퍼 도입** ✅ (`stamp()`/`backfill()`/`now_iso()` + `DEFAULT_USER="local"`/`DEFAULT_WORKSPACE="default"`).
- `store/bookmarks.py` — 5필드 **전체 적용** ✅ (`Bookmark` dataclass + `add`/`update_content`/`set_status` stamp, 과거 레코드 백필).
- `store/task_defs_db.py` — `user_id`/`workspace_id` 컬럼 추가(schema v2 마이그레이션) + `upsert` stamp + 읽기 백필 ✅. (`created_at`/`updated_at`/`created_by`/`updated_by` 는 기존 보유.)
- `store/sola_threads.py` — `created_at`/`updated_at` 기존 보유(부분).
- 그 외 store(`news_db`,`trends`,`sources`,`chat_log`), `persona/store`, `roadmap` — **미적용** ⬜ (헬퍼 준비됨, 동일 패턴으로 점진 적용).

### 적용 원칙
1. 신규/수정되는 모든 write 경로에 5필드 채움(헬퍼 1개로 통일 권장: `store/_audit.stamp(record, user="local")`).
2. SQLite는 `ALTER TABLE ... ADD COLUMN` 또는 신규 테이블 정의에 포함. Parquet/JSON은 직렬화 시 필드 추가(누락분은 읽을 때 기본값 채움).
3. 인증 미들웨어 Phase 1 = no-op(항상 `user_id="local"`) → Phase 2에서 실제 토큰으로 교체. API 스키마는 지금부터 5필드 노출.

---

## 부록 — 재현 커맨드

```bash
# 세션키
grep -rhoE "session_state\[(['\"])[A-Za-z0-9_]+\1\]|session_state\.[A-Za-z0-9_]+" app.py ui/ \
  | sed -E "s/session_state\[['\"]//; s/['\"]\]//; s/session_state\.//" | sort -u
# query_params 키
grep -rhoE "query_params(\.get\(['\"][a-z_]+|\[['\"][a-z_]+)" app.py ui/ | sed -E "s/.*['\"]//" | sort -u
# 밀도
grep -rcE "st\.html\(" app.py ui/*.py | grep -v ':0$' | sort -t: -k2 -rn
```
