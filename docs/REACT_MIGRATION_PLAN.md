# REACT_MIGRATION_PLAN — React 전환 전 정리 계획

> 목적: Streamlit → React 전환에 앞서 **화면 역할을 재정의**하고, 불필요한 중복을
> 제거하며, 화면명을 정리하고, **작업정의 업로드 / JSON 저장 폼을 데이터 계약으로
> 고정**한 뒤 전환에 들어간다. 전환 자체보다 **계약(스키마·API) 고정**이 핵심.
>
> 결정 사항(2026-06-15): **보관함 흡수 + 보드/인사이트 중복 제거** → 6화면 → 5화면.

---

## 0. 현재 구조 진단

좌측 사이드바 nav + `st.columns([2.3, 1])`(중앙 콘텐츠 + **전 화면 공통 우측 채팅**).

| 현재 화면 | 모듈 | 규모 | 핵심 역할 |
|---|---|---|---|
| 📊 오늘의 보드 | `ui/board_v2.py` | 2070줄 | KPI 4 + 탑스토리 + 트렌드/매트릭스/키워드 |
| 🗞 뉴스 수집 | `ui/data_management_v2.py::render_collect` | 2540줄(공유) | 수집잡·키워드·출처 카드뷰 + 수집설정 |
| 📋 작업 정의 | `…::render_taskdef` + `ui/task_def_manage.py` | 755줄 | 엑셀 업로드 + CRUD + history |
| 🔎 인사이트 분석 | `ui/insights_v2.py` | 1174줄 | 트렌드·매칭·자동화 기회 매트릭스 |
| 🤖 SOLA 작업실 | `ui/sola_workshop_v2.py` | 1135줄 | 3열(쓰레드/채팅/컨텍스트) 요약·제안서 |
| 📦 산출물 보관함 | `ui/archive_v2.py` | 481줄 | 북마크·채택 칸반 |

### 전환 전 반드시 정리할 문제

1. **채팅 surface 2중화** — 전 화면 우측 `chat_panel.render_side` + SOLA 작업실 자체
   풀스크린 채팅. React에서는 **전역 어시스턴트 드로어 1개**로 통일한다.
2. **보드 ↔ 인사이트 분석 기능 중복** — 트렌드/매트릭스/키워드 시각화가 양쪽 중복.
   보드 = "오늘 볼 것" 다이제스트, 인사이트 = 심층 분석으로 경계를 가른다.
3. **데이터 관리 2화면이 한 모듈(2540줄)에 공존** — 성격상 "운영/입력" 묶음.
4. **Streamlit 강결합** — UI가 `store/`·`roadmap/`·`sola/`를 Python 직호출.
   React는 **HTTP API 계약**이 선행 필요. 이게 전환의 진짜 핵심 작업.

---

## 1단계 — 화면 역할 재정의 · 이름 변경 · 取捨 (6→5)

| 새 화면명 | 라우트 | 이전 | 결정 | 역할(한 문장) |
|---|---|---|---|---|
| **홈 / 오늘의 브리핑** | `/` | 오늘의 보드 | 유지·축소 | 페르소나 맞춤 "오늘 볼 것" 다이제스트. 심층 차트는 분석으로 이관 |
| **뉴스 수집** | `/collect` | 뉴스 수집 | 유지 | 수집잡·키워드·출처 운영 + 수집설정 |
| **작업 정의** | `/taskdefs` | 작업 정의 | 유지·폼 확정 | 엑셀 업로드 + JSON 폼 CRUD (→ 2단계) |
| **인사이트 분석** | `/insights` | 인사이트 분석 | 유지·강화 | 트렌드·매칭·자동화 기회 매트릭스 집중 |
| **SOLA 작업실** | `/workshop` | SOLA 작업실 + 산출물 보관함 | 유지·**흡수** | 요약·제안서 생성 + 대화 + **산출물 보관(탭)** |

- **取**: 보드(축소) · 수집 · 작업정의 · 인사이트 · SOLA 5축.
- **捨**:
  - ① **산출물 보관함 → SOLA 작업실 하위 탭으로 흡수** (별도 메뉴 제거). 칸반(대기/채택/기각)을 작업실의 `산출물` 탭으로 이동.
  - ② **보드 내부 중복 트렌드/매트릭스/키워드 블록 제거** → 인사이트 분석으로 단일화. 보드에는 "더 보기 → 인사이트" 링크만 남긴다.
  - ③ 데드코드(`sola/side_context.py` orphan 등)는 전환 대상에서 제외.
- **이름**: 보드는 React 첫 진입(`/`)이므로 **홈/브리핑** 성격을 이름에 반영.

### 1단계 산출물
- 화면 매핑 확정표(위) + 사이드바 nav를 6→5로 축소.
- 보드에서 인사이트로 이관/삭제할 블록 목록.

---

## 2단계 — 작업정의 업로드 & JSON 저장 폼 확정 (전환 선행 필수)

현 폼은 이미 잘 정의됨: `roadmap/task_def_form.py::TaskDefForm` + `roadmap/task_def_json.py`(스키마 v1.0). 이를 **React/백엔드 공용 계약**으로 고정한다.

### 2.1 스키마 고정 (task_def JSON v1.0)

```
process_id            (필수)
process_name
process_description
process_domain
process_category
work_flow
previous_process
next_process
objectives            : string[]
overall_quality_risks : { risk, consequence }[]
automation_potential_areas : { area, technology, expected_effect }[]
key_check_points      : string[]
safety_notes          : string[]
main_equipment        : string[]
org_meta              : { team*, dept*, division, process, task, sub_task, lv1, lv2, lv3 }
```
- 저장 시 `ingest_org_meta`가 `org_meta`를 주입·검증(`team`·`dept` 필수).
- 빈 문자열/빈 리스트는 직렬화에서 제거(현 `to_json` 규칙 유지).

### 2.2 API 계약 (작업정의)

| 메서드 | 경로 | 위임 | 설명 |
|---|---|---|---|
| POST | `/api/taskdefs/upload` | `roadmap/ingest.py` | 엑셀 → 행별 JSON 파싱·미리보기 |
| GET | `/api/taskdefs?q=` | `store/task_defs_db.py` | 검색/목록 |
| GET | `/api/taskdefs/:id` | `task_defs_db.get` | 1건 상세 |
| POST/PUT | `/api/taskdefs/:id` | `task_defs_db` + `ingest_org_meta` | 생성/수정(검증) |
| DELETE | `/api/taskdefs/:id` | `task_defs_db` | 삭제 |
| GET | `/api/taskdefs/:id/history` | `task_defs_db` | 변경 이력 |

### 2.3 폼 UX 정리 포인트
- 동적 리스트 add/remove → 현 `_do_*` pending 패턴 대신 React 로컬 state.
- JSON 미리보기 + 검증 에러 표시 일원화(`TaskDefJsonError` → 필드 에러 매핑).
- 엑셀 업로드 = 드롭존 → 파싱 미리보기 → 일괄 저장 흐름.

---

## 3단계 — 백엔드 API 계약 추출 (Streamlit 분리)

화면이 의존하는 `store/`·`roadmap/`·`sola/` 호출을 REST(or tRPC) 엔드포인트로 묶어 **OpenAPI 고정**.

| 도메인 | 대표 엔드포인트 | 위임 모듈 |
|---|---|---|
| 뉴스 | `/api/news`, `/api/collect/run`, `/api/keywords`, `/api/sources` | `store/news_db`, `scraping/`, `store/sources` |
| 작업정의 | (2단계 표) | `roadmap/`, `store/task_defs_db` |
| 트렌드/매칭 | `/api/trends`, `/api/matches`, `/api/opportunities` | `store/trends`, `store/match`, `sola/opportunity` |
| SOLA | `/api/sola/summarize`, `/api/sola/propose`, `/api/threads`, `/api/assistant/chat` | `sola/`, `store/sola_threads`, `store/chat_log` |
| 산출물 | `/api/bookmarks` | `store/bookmarks` |
| 페르소나 | `/api/persona` | `persona/` |
| 어시스턴트 컨텍스트 | `/api/assistant/context?screen=` | 화면별 `chat_context_block` 일반화 |

- 각 화면의 `chat_context_block(...)`은 SOLA 컨텍스트 패키징 → `/api/assistant/context`로 일반화.

---

## 4단계 — React 전환

- **라우팅** = 5 화면(`/`, `/collect`, `/taskdefs`, `/insights`, `/workshop`).
- **전역 어시스턴트 드로어 1개** — 채팅 2중화 해소. 현재 화면을 context로 전달.
- **디자인 토큰 승계** — `assets/v2/*.css`(tokens·card·shell·sidebar) 토큰을 그대로 가져와 시각 일관성 유지.
- 상태관리/데이터 패칭은 API 계약(3단계) 기준.

---

## 진행 순서 & 권장 착수점

1. **1단계(화면 확정)** — nav 6→5, 보관함 흡수, 보드 중복 블록 정리 목록.
2. **2단계(작업정의 폼/API)** — 데이터 계약의 기준점. **여기를 먼저 단단히.**
3. **3단계(API 계약)** — 나머지 도메인 OpenAPI 고정.
4. **4단계(React)** — 라우트·컴포넌트·드로어.

> 작업정의 폼이 전체 데이터 계약의 기준이므로 2단계를 최우선으로 확정한 뒤 나머지
> API를 같은 패턴으로 확장한다.
