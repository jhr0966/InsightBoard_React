# 1차 완성 보고서 (Milestone 1 — 작업 정의 데이터 시스템)

> 작성: 2026-06-01 · 범위: `docs/TASK_DEF_PLAN.md` M1~M3 (PR-1 ~ PR-6 + PR-A).
> 목적: "사용자가 외부 도구 없이 작업 정의를 관리"하는 minimum viable 달성 보고.

---

## 1. 무엇이 완성됐나

작업 정의 데이터의 **저장 → 적재 → 조회 → 관리** 전 구간을 Parquet 단방향에서
**SQLite + JSON 양방향 CRUD** 로 전환했다.

```
엑셀 업로드 ──(diff 미리보기+확인)──▶ SQLite(task_defs)  ◀──(UI 폼 CRUD)── 사용자
                                          │
                  ┌───────────────────────┼───────────────────────┐
              보드 카드               인사이트 매트릭스          SOLA 컨텍스트
              (load_latest → DataFrame, 호출처 무변경)
```

### 데이터 계층 (M1)
| PR | 결과물 |
|---|---|
| PR-1 #78 | `store/task_defs_db.py` — SQLite `task_defs` + `task_def_history`. CRUD 8 API. |
| PR-2 #79 | `roadmap/task_def_json.py` v1.0 — `org_meta` 주입/추출/검증. |
| PR-3 #80 | `roadmap/sqlite_sync.py` + `scripts/migrate_roadmap_to_sqlite.py` — 엑셀/Parquet → SQLite. |
| PR-4 #81 | `roadmap/query.py::load_latest(prefer="sqlite")` — SQLite 우선, Parquet fallback. 호출처 8곳 무변경. |

### 사용자 가시 (M2)
| PR | 결과물 |
|---|---|
| PR-A #82 | 데이터 관리 area 2 그룹 (📰 뉴스 / 📋 작업) segmented control. |
| PR-5 #83 | 엑셀 업로드 diff 미리보기 + 사용자 확인 (추가/수정/유지/제외). |

### 작업 정의 관리 UI (M3 — 1차 완성)
| PR | 결과물 |
|---|---|
| PR-6 #84 | `ui/task_def_manage.py` + `roadmap/task_def_form.py` — 검색·상세·추가·수정·삭제·history. |
| (이 PR) | manage UI inline style 보강 (screen-CSS 미적용 이슈 우회). |

---

## 2. 각 화면의 역할 & 사용 흐름

### 📋 작업 데이터 그룹 → ✏️ 작업 정의 관리 (신규, 핵심)
1. **목록/검색**: 작업명·공정ID·JSON 본문 substring 검색. 카드 클릭 → 상세.
2. **상세**: org_meta(팀/부서/분과/공정/작업) · 목표 · 품질 리스크 · 자동화 영역 · 액션 4종.
3. **추가** (`+ 새 작업 추가`): 구조화 폼. 공정ID + team/dept 필수. 저장 → SQLite + history.
4. **수정**: 현재 값 prefill 폼 (공정ID readonly). 저장 → UPDATE + history(before/after).
5. **삭제**: 브라우저 confirm → URL 액션 → DELETE + history.
6. **history**: 변경 이력(create/update/delete + source + 시각) 최신순.

### 📋 작업 데이터 그룹 → 📊 엑셀 업로드
- 9 컬럼 엑셀 업로드 → 시트 미리보기 → **변경 사항 미리보기** (추가 N / 수정 M / 유지 K / 제외 S) → 확인 → UPSERT.

### 📰 뉴스 데이터 그룹 (jobs / kw / src)
- 기존 수집잡·키워드·출처 관리. PR-A 에서 그룹 분리만, 기능 동일.

### 다른 화면 (보드/인사이트/SOLA)
- `load_latest()` 가 SQLite 를 읽도록 바뀌었을 뿐 **코드·동작 변화 없음**. 작업 정의 매칭/매트릭스/컨텍스트 모두 동일.

---

## 3. 검증

- **단위/통합 테스트**: 654 passed (M1~M3 누적 신규 약 150건).
- **금지 패턴**: `on_click=` 0, raw `requests.*` 0.
- **실제 구동 검증** (playwright headless): 목록·검색·상세·추가폼 4화면 모두 Python traceback 0. CRUD 액션 버튼 렌더 확인.
- **XSS**: 사용자 입력 전부 `html.escape`. injection 테스트 통과.

### 검증 중 발견·수정한 이슈
- **screen CSS 미적용** (✅ 후속 PR 에서 근본 해결): `inject_screen_css()` 뿐 아니라 `inject_global_styles()` 의 `st.html("<style>")` 도 DOM 에 mount 되지 않았음. 전체 v2 CSS (`--accent-primary` 토큰 포함) 전부 누락 = board/data/insights/sola/archive 모든 v2 셸이 unstyled 였음.
  - **근본 원인**: Streamlit `st.html()` 이 수만 자 `<style>` 블록을 sanitize/collapse. `st.markdown(unsafe_allow_html=True)` 는 다른 코드 경로로 보존.
  - **해결**: `ui/styles.py` 의 두 inject 함수를 `st.markdown(unsafe_allow_html=True)` 로 전환. `tests/test_html_rendering.py` 에 `styles.py` 명시적 예외 (CSS 자산은 사용자 입력 아님).
  - **검증**: 5 area 모두 `total_css ≥ 100KB`, v2 토큰 50~99회, screen 마커 8~25회 mount.
  - **manage UI inline style 은 안전망으로 유지** — Streamlit 버전 회귀 시 fallback.

---

## 4. 남은 작업 (1차 완성 이후, 선택)

| 항목 | 내용 | 우선도 |
|---|---|---|
| ~~screen-CSS 근본 수정~~ | ✅ 후속 PR 에서 해결 (`st.markdown(unsafe_allow_html=True)`) | 완료 |
| 변수명 통일 | 호출처 `roadmap_df` → `tasks_df` (cosmetic, 8파일) | 낮 |
| PR-7 export | 작업 정의 JSON/엑셀 내보내기 (범위·포맷 결정 필요) | 선택 |
| PR-8 권한 | multi-user + team 권한 + 로그인 | 미래 |
| `roadmap/` → `tasks/` | 패키지 rename (import 다수 영향) | 낮 |

---

## 5. 데이터 모델 요약 (참조)

```sql
task_defs(process_id PK, team, dept, division, process, task,
          json, task_def_text, created_at, updated_at, created_by, updated_by)
task_def_history(id PK, process_id, json_before, json_after,
                 action, changed_at, changed_by, source)
```

JSON(SOT) 안에 `org_meta`(team/dept/division/process/task/sub_task/lv1~3) 주입.
scalar 컬럼은 검색·필터 인덱스용 미러. `load_latest` 가 이 JSON 을 ALL_COLUMNS
DataFrame 으로 복원해 기존 호출처와 호환.
