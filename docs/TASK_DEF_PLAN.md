# 작업 정의 데이터 시스템 — Plan & Decisions

> **목적**: 작업 정의 데이터(엑셀 → 시스템 내부) 의 저장·관리·CRUD 를 위한 마이그레이션 계획.
> 컨텍스트 압축 후 단일 source 로 복원 가능하도록 별도 문서로 분리.

---

## 결정사항 (사용자 확정 · 2026-05-31)

| # | 항목 | 결정 |
|---|---|---|
| 1 | 데이터 관리 화면 구조 | **2 그룹 × 내부 sub-탭** — 📰 뉴스 데이터 / 📋 작업 데이터 |
| 2 | 엑셀 폼 | **9 컬럼** — `팀 / 부서 / 분과 / 공정 / 작업 / 세부작업 / 공정ID / 공정정의서(줄글) / 공정정의서(JSON)` |
| 3 | 입력 경로 | 엑셀(대량 신규/업데이트) + UI 폼(1건 추가/수정). **JSON 업로드 ❌** |
| 4 | 엑셀 재업로드 동작 | **UPSERT + 미리보기 + 사용자 확인** (같은 process_id 대체 / 새 id 추가 / 없는 id 보존) |
| 5 | 저장 형식 | **SQLite + JSON 컬럼** + 별도 history 테이블 |
| 6 | process_id | UNIQUE PRIMARY KEY |
| 7 | History 보존 | 무한 누적 (정리는 나중에) |
| 8 | 권한 | 관리자(모두) / 사용자(자기 팀만) — 미래 작업 (multi-user 시점에) |
| 9 | export | 보류 (PR-7 시점에 재논의) |

---

## 데이터 모델

### 엑셀 입력 (9 컬럼)

```
팀      | 부서        | 분과     | 공정 | 작업 | 세부작업 | 공정ID       | 공정정의서(줄글)         | 공정정의서(JSON)
가공팀  | 판넬조립부  | 구조내업 | 판넬 | 선별 | 선별     | PNL-SEL-001  | ##공정 개요##...        | { "process_id": "PNL-SEL-001", ... }
```

- `공정ID` 가 unique key. JSON 안의 `process_id` 와 동기화 (mismatch 시 ingest 에러)
- 외곽 7 컬럼(팀~세부작업)은 부서·계층 분류
- 줄글 정의서: 검토용 free-form text
- JSON 정의서: LLM/시스템용 구조화 정의

### task_def_json 확장 스키마 (org_meta 주입)

```json
{
  "version": "1.0",
  "org_meta": {
    "team": "가공팀",
    "dept": "판넬조립부",
    "division": "구조내업",
    "process": "판넬",
    "task": "선별",
    "sub_task": "선별",
    "lv1": "...",
    "lv2": "...",
    "lv3": "..."
  },
  "process_id": "PNL-SEL-001",
  "process_domain": "조선소 생산관리",
  "process_category": "판넬",
  "process_name": "판넬 선별 (Panel Main Plate Inspection & Loading)",
  "process_description": "...",
  "objectives": [...],
  "overall_quality_risks": [{"risk": ..., "consequence": ...}, ...],
  "automation_potential_areas": [{"area": ..., "technology": ..., "expected_effect": ...}, ...],
  "related_processes": [...],
  "crane_safety_standards": [...],
  "sub_processes": [...],
  "task_def_text": "##공정 개요## ..."
}
```

- ingest 가 엑셀 외곽 컬럼 → `org_meta` 자동 주입
- JSON 1건 = 1 작업 + 부서 메타 + 정의서 모두 self-contained
- 외부 LLM 시스템과 그대로 호환

### SQLite 스키마

```sql
CREATE TABLE task_defs (
  process_id    TEXT PRIMARY KEY,
  team          TEXT NOT NULL,     -- JSON.org_meta.team 미러
  dept          TEXT NOT NULL,
  division      TEXT,
  process       TEXT,
  task          TEXT,
  json          TEXT NOT NULL,     -- 완전 JSON (source of truth)
  task_def_text TEXT,              -- 줄글 정의서 (검토용)
  created_at    TEXT NOT NULL,
  updated_at    TEXT NOT NULL,
  created_by    TEXT,              -- 미래 권한용
  updated_by    TEXT
);
CREATE INDEX idx_task_defs_dept ON task_defs(dept);
CREATE INDEX idx_task_defs_team ON task_defs(team);
CREATE INDEX idx_task_defs_process ON task_defs(process);

CREATE TABLE task_def_history (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  process_id    TEXT NOT NULL,
  json_before   TEXT,              -- NULL 이면 신규
  json_after    TEXT NOT NULL,
  action        TEXT NOT NULL,     -- 'create' / 'update' / 'delete'
  changed_at    TEXT NOT NULL,
  changed_by    TEXT,              -- 미래 권한용
  source        TEXT               -- 'excel_upload' / 'ui_edit' / 'migration'
);
CREATE INDEX idx_history_process ON task_def_history(process_id, changed_at DESC);
```

- 외곽 scalar 컬럼은 JSON.org_meta 의 **미러** (index/검색용). SOT는 JSON
- mismatch 가드: insert/update 시 JSON.org_meta 와 scalar 컬럼 동기화 검증
- history 는 무제한 누적 (정리는 future work)

---

## PR 의존성 그래프

```
PR-1: SQLite store 신규 + 스키마        ← 독립
        │
        ├──→ PR-2: task_def_json org_meta 스키마 확장   ← 독립
        │       │
        │       └──→ PR-3: Parquet → SQLite 마이그 도구 + ingest 리팩토링
        │               │
        │               └──→ PR-4: query.load_latest 어댑터 (DataFrame 유지)
        │                       │
        │                       └──→ PR-5: 엑셀 업로드 흐름 개편 (diff 미리보기 + 확인)
        │                               │
PR-A: 데이터 관리 area 2 그룹 재편       │
        │                               │
        └───── 둘 다 머지 후 ──→ PR-6: 작업 정의 관리 UI (검색·1건 보기·편집·추가·삭제·history)
                                        │
                                        └──→ PR-7: export (JSON/엑셀) — 결정 시
                                                │
                                                └──→ PR-8: 권한 시스템 (multi-user 시점에)
```

### PR 규모 추정

| PR | 제목 | 코드 추정 | 테스트 추정 | 난이도 |
|---|---|---|---|---|
| PR-1 | SQLite store + 스키마 | ~300 LOC | +20 | 낮 |
| PR-2 | task_def_json `org_meta` 확장 | ~150 LOC | +10 | 낮 |
| PR-3 | 마이그 도구 + ingest 리팩토링 | ~400 LOC | +15 | 중 |
| PR-4 | query 어댑터 (호출처 무변경) | ~150 LOC | +8 | 낮 |
| PR-5 | 엑셀 업로드 diff 미리보기 + 확인 | ~500 LOC | +20 | 중-상 |
| PR-A | 데이터관리 area 2 그룹 재편 | ~300 LOC | +10 | 중 |
| PR-6 | 작업 정의 관리 UI (검색·편집·CRUD) | ~700 LOC | +30 | 상 |
| PR-7 | export (JSON/엑셀) | ~200 LOC | +10 | 낮 |
| PR-8 | 권한 시스템 (미래) | ~600 LOC | +25 | 상 |

**합계** (PR-1 ~ PR-7): 약 **2700 LOC + 123 tests**, 2~3주 작업

---

## 화면 시뮬레이션

### 시나리오 1: 초기 등록 (관리자)

```
1. 🧱 데이터 관리 → 📋 작업 데이터 그룹 → [📊 엑셀 업로드] sub-탭
2. 9 컬럼 엑셀 파일 선택 → 시트 선택 → 5행 미리보기
3. [✅ 이 파일로 업로드 + 저장] 클릭
4. 다음 화면: 업로드 미리보기
     ✅ 추가: 32건  [전체 보기]
     ⚠️ 수정: 0건
     ℹ️ 기존 작업 (이번 엑셀 외): 0건
   [취소] [✅ 32건 적용]
5. 적용 → SQLite 에 INSERT 32건 + history 32건 + 토스트 "32건 등록됨"
6. 자동으로 [✏️ 작업 정의 관리] sub-탭으로 이동
```

### 시나리오 2: 1건 추가 (관리자)

```
1. 🧱 데이터 관리 → 📋 작업 데이터 → [✏️ 작업 정의 관리]
2. 우상단 [+ 새 작업 추가] 클릭
3. 폼 화면:
   - 조직 메타: 팀(셀렉트) / 부서(셀렉트) / 분과 / 공정 / 작업 / 세부작업 (text)
   - 공정 ID: text (자동 중복 검증)
   - 공정명: text
   - 공정 설명: textarea
   - 목표: 리스트 [+ 추가] [- 삭제]
   - 품질 리스크: 리스트 (risk + consequence 한 쌍)
   - 자동화 영역: 리스트 (area + technology + expected_effect 세 쌍)
   - 줄글 정의서: textarea (선택)
4. [💾 저장] → INSERT + history + 토스트
```

### 시나리오 3: 1건 수정 (관리자)

```
1. 🧱 데이터 관리 → 📋 작업 데이터 → [✏️ 작업 정의 관리]
2. 검색창에 "비전" 입력 → 매칭 작업 N건 리스트
3. "판넬 선별 (PNL-SEL-001)" 카드 클릭 → 우측 panel 또는 expand 로 상세
4. [수정] 버튼 → 시나리오 2 와 같은 폼 (현재 값 prefill)
5. objectives 1개 추가 + [💾 저장]
6. UPDATE + history (json_before/json_after 모두 저장)
7. 토스트 "수정됨"
```

### 시나리오 4: 업데이트 엑셀 재업로드 (관리자)

```
1. 시나리오 1 의 1~3 동일
2. 다음 화면: 업로드 미리보기 (이번엔 기존 데이터 있음)
     ✅ 추가: 5건                              [전체 보기]
       - PNL-SEL-033 (...)
       - ...
     ⚠️ 수정: 8건                              [diff 보기]
       - PNL-SEL-001 — objectives 3→4개로 추가
       - PNL-SEL-005 — automation_potential_areas 변경
       - ...
     ℹ️ 엑셀에 없는 기존 작업: 19건            [목록 보기]
       → 그대로 유지됩니다. 삭제하려면 UI 에서 개별 삭제하세요.
   [취소] [✅ 13건 적용 (추가 5 + 수정 8)]
3. diff 보기 클릭 → 각 작업 변경 사항을 side-by-side 표시
4. [✅ 13건 적용] → UPSERT + history + 토스트
```

### 시나리오 5: 일반 사용자 (미래 — 권한 시스템 도입 후)

```
1. 🧱 데이터 관리 → 📋 작업 데이터 → [✏️ 작업 정의 관리]
2. 자기 팀 (예: 가공팀) 의 작업만 노출 (필터 자동 적용)
3. 다른 팀 작업도 검색 가능하지만 [읽기 전용] 배지 + 수정 버튼 비활성
4. [+ 새 작업 추가] 버튼은 자기 팀 컨텍스트로 prefill
5. 자기 팀 작업 수정 → UPDATE + history (changed_by 자동 기록)
```

---

## 마일스톤 (1차 완성 기준)

### Milestone M1: 마이그레이션 완료 (PR-1~4)
- SQLite 저장 시작
- 엑셀 업로드는 그대로 (UPSERT)
- 매칭/카드 로직 무변경
- **완성 시 영향**: 보드/인사이트/SOLA 모두 동일 동작. 내부 storage 만 변경.

### Milestone M2: 사용자 가시 변화 (PR-5, PR-A)
- 엑셀 업로드 diff 미리보기 + 확인
- 데이터 관리 area 가 2 그룹 (뉴스/작업) 으로 재편

### Milestone M3: 작업 정의 관리 화면 (PR-6) ← **1차 완성**
- 검색·1건 보기·추가·수정·삭제·history 보기
- 사용자가 외부 도구 없이 작업 정의 관리 완료
- **1차 완성 시점** (사용자 요구사항 기준 minimum viable)

### Milestone M4: export (PR-7) — 선택
- JSON/엑셀 다운로드
- 다른 LLM 시스템과 통합 가능

### Milestone M5: 권한 (PR-8) — 미래
- multi-user + admin/member 분리
- 자기 팀 작업만 수정 가능

---

## 리팩토링 시점

| 시점 | 항목 | 이유 |
|---|---|---|
| **PR-4 직후** | `_load_roadmap()` 호출처 (보드/인사이트/데이터관리/매칭) 의 변수 이름 통일 (`roadmap_df` → `tasks_df`) | "로드맵" 잔여 변수명 정리 (사용자 노출은 이미 "작업 정의" 로 통일됨) |
| **PR-6 완료 후** | `roadmap/` 패키지를 `tasks/` 로 rename (선택) | 코드 식별자도 "작업 정의" 로 통일. 비용 큼 — 다른 모듈 import 다 수정 |
| **PR-7 직후** | `data/` 디렉토리 구조 정리 (`data/roadmap/*.parquet` 제거 또는 `data/archive/`로 이동) | Parquet 폐기 후 잔여 청소 |
| **PR-8 (권한)** | persona 모델 확장 — 현재 single-user → multi-user. login 추가 | 권한 도입 전제 |

---

## 진행 상황 추적 체크박스

### PR-1: SQLite store + 스키마 ✅
- [x] `store/task_defs_db.py` 신규 (sqlite3 + JSON1)
- [x] schema migration: `task_defs` + `task_def_history` 테이블 자동 생성
- [x] CRUD API: `get(process_id)`, `upsert(...)`, `delete(process_id)`, `list_all(filters)`, `search(query)`, `history(process_id)`, `count()`, `upsert_many(...)`
- [x] tests: 단위 23건

### PR-2: task_def_json org_meta 확장 ✅
- [x] `roadmap/task_def_json.py` 스키마 정의 (v1.0) — `SCHEMA_VERSION`, `ORG_META_KEYS` 9개, `ORG_META_REQUIRED`
- [x] `ingest_org_meta(json_text, org_meta, *, process_id=None, version="1.0")` helper
- [x] `org_meta_of(json_text)` + `validate_task_def_json(json_text)` + `TaskDefJsonError` 추가
- [x] tests: 단위 18건

### PR-3: 마이그 도구 + ingest 리팩토링 ✅
- [x] `scripts/migrate_roadmap_to_sqlite.py` — Parquet → SQLite (`--file/--dry-run/--changed-by`)
- [x] `roadmap/ingest.py::ingest_excel` 수정 — `to_sqlite=True` best-effort UPSERT
- [x] `roadmap/sqlite_sync.py` — `row_to_task_def` + `sync_dataframe`
- [x] 엑셀 9 컬럼 폼 — `공정ID` → `process_id` 매핑 (없으면 JSON 내부 fallback)
- [~] 폴백 읽기 (SQLite 없으면 Parquet): PR-4 의 reader 전환 시점으로 이관
- [x] tests: 통합 16건

### PR-4: query 어댑터 ✅
- [x] `roadmap/query.py::load_latest(*, prefer="sqlite")` — SQLite 우선, Parquet fallback (DataFrame 반환 유지)
- [x] 호출처 검증 — 8곳 (board_v2/insights_v2/data_management_v2/persona_page/data_health/sidebar/onboarding/archive_v2) 무변경
- [x] tests: 호환성 7건

### PR-5: 엑셀 업로드 diff 미리보기
- [ ] `ui/data_management_v2.py::_render_excel_diff_preview` 신규
- [ ] pending 패턴 — preview → confirm → apply
- [ ] diff 화면: 추가/수정/유지 카운트 + 상세 expand
- [ ] tests: e2e 20건

### PR-A: 데이터 관리 2 그룹 재편
- [ ] 2 그룹 segmented control (📰 뉴스 / 📋 작업)
- [ ] URL: `?dm_grp=news|tasks&dm_tab=...`
- [ ] 기존 4 탭 → 2 그룹 안으로 재배치
- [ ] tests: 라우팅 10건

### PR-6: 작업 정의 관리 UI
- [ ] sub-탭 "✏️ 작업 정의 관리" 추가
- [ ] 검색창 + 매칭 리스트
- [ ] 1건 expand/우측 패널 — 상세 보기
- [ ] 폼 위젯: 구조화 입력 (외곽 메타 + objectives 리스트 + risks/automation 리스트)
- [ ] 액션: 추가 / 수정 / 삭제 / history 보기
- [ ] tests: 30건

### PR-7: export (선택)
- [ ] [🔽 JSON 다운로드] / [📊 엑셀 다운로드] 버튼
- [ ] 표준 JSON 스키마 export
- [ ] tests: 10건

### PR-8: 권한 (미래)
- [ ] User 모델 (`store/users.py`)
- [ ] `team_id` 기반 권한 룰
- [ ] login / 세션
- [ ] audit log
- [ ] tests: 25건
