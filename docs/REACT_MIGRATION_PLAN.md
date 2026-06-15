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

> 결정 갱신(2026-06-15): **산출물 보관함 화면 삭제**, **SOLA 작업실 → 자동화 제안 개명**.
> 보관(북마크) 기능은 별도 화면 대신 **콘텐츠가 생기는 화면의 탭으로 분산**한다
> (뉴스 보관 → 뉴스 수집 탭, 제안서 보관 → 자동화 제안 탭).
>
> **메뉴 순서·구조**(2026-06-15): nav를 **2단으로 분리** — 매일 쓰는 메인 3개와 가끔 쓰는 관리 2개.
> 성격이 다른 화면(소비 vs 데이터 운영)을 한 줄에 평면 나열하지 않아 첫인상 부담을 줄인다.
>
> ```
> 메인        ① 📊 오늘의 보드   ② 🔎 인사이트 분석   ③ 🤖 자동화 제안
> ───────────── (구분선)
> 관리        ④ 🗞 뉴스 수집     ⑤ 📋 작업 정의
> ```
> (메인 = 소비/실행, 관리 = 데이터 운영. 일반 사용자는 메인 3개만 인지하면 됨)

| 순 | 그룹 | 새 화면명 | 라우트 | 이전 | 결정 | 역할(한 문장) · 탭 구성 |
|---|---|---|---|---|---|---|
| 1 | 메인 | **홈 / 오늘의 브리핑** | `/` | 오늘의 보드 | 유지·축소 | 페르소나 맞춤 "오늘 볼 것" 다이제스트. 심층 차트는 분석으로 이관 |
| 2 | 메인 | **인사이트 분석** | `/insights` | 인사이트 분석 | 유지·강화 | 트렌드·매칭·자동화 기회 매트릭스. **기회 카드 → `이 기회로 제안 만들기` CTA** |
| 3 | 메인 | **자동화 제안** | `/proposals` | SOLA 작업실(개명) | 유지·**탭 추가** | 탭: `제안 생성`(채팅/작업대로 제안서 초안) · **`보관한 제안`**(채택·보관 제안서만) |
| 4 | 관리 | **뉴스 수집** | `/collect` | 뉴스 수집 | 유지·**탭 추가** | 탭: `수집`(카드뷰) · **`보관한 뉴스`**(북마크 뉴스만) · `수집 설정`(키워드·출처·이력) |
| 5 | 관리 | **작업 정의** | `/taskdefs` | 작업 정의 | 유지·폼 확정 | 엑셀 업로드 + JSON 폼 CRUD (→ 2단계) |

- **取**: 보드(축소) · 인사이트 · **자동화 제안** · 뉴스 수집 · 작업정의 5축.
- **捨 / 변경**:
  - ① **SOLA 작업실 → `자동화 제안`(`/proposals`) 개명**. 역할(요약·제안서 생성 + 대화)은 유지, 명칭만 사용자 언어로.
  - ② **산출물 보관함 화면 완전 삭제** (사이드바 메뉴 제거 + `ui/archive_v2.py` 폐기). 데이터(`store/bookmarks.py`)는 그대로 두되 **type별로 표시 위치를 분산**:
    - `type=news`(보관한 뉴스) → **뉴스 수집 `보관한 뉴스` 탭**.
    - `type=proposal`(보관/채택한 제안서) → **자동화 제안 `보관한 제안` 탭**(기존 칸반 대신 보관 목록).
  - ③ **보드 내부 중복 트렌드/매트릭스/키워드 블록 제거** → 인사이트 분석으로 단일화. 보드에는 "더 보기 → 인사이트" 링크만.
  - ④ 데드코드(`sola/side_context.py` orphan 등)는 전환 대상에서 제외.
- **이름**: 보드는 React 첫 진입(`/`)이므로 **홈/브리핑** 성격을 반영.

### 보관(북마크) 데이터 흐름 (화면 삭제 후)
```
store/bookmarks.py  (단일 저장소, 화면만 사라짐)
        ├─ type=news     →  뉴스 수집 · [보관한 뉴스] 탭
        └─ type=proposal →  자동화 제안 · [보관한 제안] 탭
```
- 보드 사이드바 통계 "채택 대기"는 `type=proposal` 미채택 수로 그대로 산출(저장소 유지라 영향 없음).

### 심플·직관 원칙 (UX 검토 반영, 2026-06-15)

"직관적·심플·부담 없음"을 위해 화면 구성에 다음 원칙을 적용한다.

1. **nav 2단 분리** (위 도식) — 메인 3(소비/실행) · 관리 2(데이터 운영). 일반 사용자는 메인만 인지.
2. **기회 → 제안 한 흐름** — 인사이트 분석의 자동화 *기회* 매트릭스 카드에 `이 기회로 제안 만들기` CTA를 달아 자동화 제안 화면으로 이어준다. 두 화면이 "비슷한 두 개의 문"이 아니라 *탐색 → 실행* 흐름이 되게 한다.
3. **보드 슬림화** — 첫 화면은 운영 KPI 나열 대신 "맞춤 뉴스 + 오늘의 추천 액션 1개" 중심. 운영 카운트(매칭/제안/채택 대기)는 사이드바 통계로만.
4. **페르소나 선택적화** — 기본값으로 바로 쓰기 시작, 설정은 사용 중 자연스럽게 유도(첫 실행에 "설정부터" 벽 제거).
5. **보관 발견성** — 보관함을 두 탭으로 분산하므로 탭에 개수 배지(`보관한 뉴스 (3)`)로 "저장한 게 여기 있다"를 드러낸다.
6. **채팅 단일화** — 전 화면 우측 채팅 + 작업실 자체 채팅 → 전역 어시스턴트 드로어 1개(4단계).

### 1단계 산출물
- 화면 매핑 확정표(위) + 사이드바 nav 6→5: `ui/sidebar.py::AREAS`를 `[📊 오늘의 보드, 🔎 인사이트 분석, 🤖 자동화 제안, 🗞 뉴스 수집, 📋 작업 정의]` 순서로 재정렬(`📦 산출물 보관함` 제거, `🤖 SOLA 작업실`→`🤖 자동화 제안`).
- `ui/archive_v2.py` 폐기 + 북마크 렌더를 `보관한 뉴스`/`보관한 제안` 탭으로 이식.
- 보드에서 인사이트로 이관/삭제할 블록 목록.

---

## 1.5단계 — 자동화 제안 파이프라인 (핵심 가치 흐름)

> 컨셉(2026-06-15): 뉴스 수집 + 작업정의(업로드 완료)를 전제로, **적절한 작업↔뉴스를 자동
> 매칭해 자동화 제안서를 만들고 오늘의 보드에 띄운다.** 단, "전부 자동 생성"의 비용·노이즈·신뢰
> 문제를 피하기 위해 **2단 Lazy 생성**으로 구현한다.
>
> 생성 적극성 결정: **매일 상위 1~3건은 풀 제안서 선생성**(보드에서 바로 읽기), 나머지는 클릭 시 생성.

### 재사용 빌딩블록 (대부분 이미 존재)
| 단계 | 모듈 | 비고 |
|---|---|---|
| 매칭 | `store/match.py::score_matches` | 토큰 + LLM 키워드 + TF-IDF 의미유사도. **LLM 없이도 동작** |
| 기회 랭킹 | `sola/opportunity.py::score_cells` | 부서×공정(Lv3) 기회 점수 |
| 제안서 작성 | `sola/propose.py::propose_for_task(task, news_df, persona)` | 작업 1건 + 관련 뉴스 → 마크다운 |
| 보드 노출 | `sola/board_brief.py` | 캐시 + LLM 실패 시 룰 fallback |
| 저장 | `store/bookmarks.py` | `type=proposal` 저장·만료 |

### 파이프라인 (2단 Lazy)
```
[일일 cron · 싼 단계 — LLM 거의 안 씀]   scraping/run_daily.py 확장
  뉴스 수집 → score_matches → score_cells 로 '오늘의 기회' Top-N 랭킹
    → 후보 리스트 저장(작업명 × 뉴스 N건 × 점수 × 한줄 이유)
    → 상위 1~3건만 propose_for_task() 로 풀 제안서 '선생성'(초안=대기 저장)

[오늘의 보드 — 슬림]
  "오늘의 자동화 제안 N건" 티저 카드. 선생성된 1~3건은 [바로 읽기],
   나머지 후보는 [제안서 보기](클릭 시 생성)

[자동화 제안 화면 · 비싼 단계 — 클릭 시 1회 LLM]
  미생성 후보 클릭 → propose_for_task() 1회 생성 → 초안(대기)
   → 사용자 [채택/보관] → [보관한 제안] 탭
```

### 두 진입점 → 한 화면 수렴
- **보드 티저 카드** (자동 추천) ─┐
- **인사이트 매트릭스 `이 기회로 제안 만들기` CTA** (탐색) ─┴→ **자동화 제안 화면**(생성·편집·보관)

### 신뢰·비용 통제 장치
- **Top-N 한정**(일 3~5건 노출, 선생성은 1~3건) — 전량 생성 금지.
- **dedup** — 이미 제안/기각한 작업↔뉴스 클러스터는 N일 재노출 안 함.
- **근거 노출** — 제안서에 매칭 뉴스·점수("왜 매칭됐나") 항상 동반.
- **피드백(후속)** — 티저 👍/🙈 → 다음 랭킹 가중치 조정.

### API 영향 (3단계와 연결)
- `POST /api/proposals/generate` — 후보(작업+뉴스) → 풀 제안서 1회 생성 (클릭/선생성 공용).
- `GET /api/proposals/today` — 오늘의 후보·선생성 제안 리스트(보드 티저용).
- `GET /api/proposals?status=saved` — 보관한 제안 탭.

### 보드 티저 카드 사양 ("오늘의 자동화 제안")
보드 상단 슬림 섹션. 운영 KPI 대신 이 카드가 보드의 핵심 콘텐츠.

| 요소 | 내용 | 비고 |
|---|---|---|
| 제목 | 대상 작업명 (`process_name` + Lv3 공정) | 무엇에 대한 제안인지 |
| 매칭 신호 | "관련 뉴스 N건" + 대표 뉴스 1건 제목 | 근거 노출(신뢰) |
| 점수 배지 | 상/중/하 (cell_score 구간화) | 숫자 대신 직관 라벨 |
| 한 줄 이유 | "왜 이 작업에 지금?" 1문장 | cron 단계 룰/캐시 문장 |
| 상태·CTA | 선생성 → **[바로 읽기]** / 미생성 → **[제안서 만들기]** | 후자만 클릭 시 LLM |

- 정렬: 점수 desc, **최대 3~5건**. 선생성 1~3건을 상단에 시각적으로 구분(✦ 표시).
- 빈 상태: "오늘은 새 자동화 기회가 없어요 — 인사이트 분석에서 직접 찾아보기" 링크.
- 클릭 → 모두 자동화 제안 화면으로(딥링크에 후보 키 전달).

### dedup (중복 제안 억제) 설계
같은 작업↔뉴스 조합이 매일 다시 후보로 뜨는 것을 막는다.

- **클러스터 키** `cluster_key = hash(process_id + 정렬된 상위 매칭 뉴스 id 집합)`.
  뉴스 구성이 의미 있게 바뀌면 키가 달라져 **다시 후보 가능**(새 근거 = 새 제안).
- **억제 상태 저장**: 신규 경량 테이블(`store/proposal_log.py` 신설 또는 `bookmarks` 확장)
  — `cluster_key, process_id, status(proposed|dismissed|adopted), updated_at`.
- **재노출 금지 기간**:
  - `proposed`(노출만 됨) → **14일** 후보 제외.
  - `dismissed`(🙈) → **30일** 제외.
  - `adopted`(채택/보관) → **영구** 후보 제외(보관한 제안 탭에 존재).
- cron 후보 랭킹 단계에서 위 로그를 조회해 억제 대상은 후보에서 드롭한다.

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
| 자동화 제안 | `/api/proposals/generate`, `/api/proposals/today`, `/api/proposals?status=saved`, `/api/threads`, `/api/assistant/chat` | `sola/propose`, `sola/opportunity`, `store/sola_threads`, `store/bookmarks` |
| 보관(북마크) | `/api/bookmarks?type=news\|proposal` — 단일 저장소, 화면 없이 탭에서 조회 | `store/bookmarks` |
| 페르소나 | `/api/persona` | `persona/` |
| 어시스턴트 컨텍스트 | `/api/assistant/context?screen=` | 화면별 `chat_context_block` 일반화 |

- 각 화면의 `chat_context_block(...)`은 SOLA 컨텍스트 패키징 → `/api/assistant/context`로 일반화.

---

## 4단계 — React 전환

- **라우팅** = 5 화면(메뉴 순): `/`, `/insights`, `/proposals`, `/collect`, `/taskdefs`. 보관함 라우트 없음 — 보관은 `/collect`·`/proposals`의 탭.
- **전역 어시스턴트 드로어 1개** — 채팅 2중화 해소. 현재 화면을 context로 전달.
- **디자인 토큰 승계** — `assets/v2/*.css`(tokens·card·shell·sidebar) 토큰을 그대로 가져와 시각 일관성 유지.
- 상태관리/데이터 패칭은 API 계약(3단계) 기준.

---

## 진행 순서 & 권장 착수점

1. **1단계(화면 확정)** — nav 6→5(보관함 삭제 + SOLA 작업실→자동화 제안), 보관 탭(뉴스/제안) 이식, 보드 중복 블록 정리.
2. **2단계(작업정의 폼/API)** — 데이터 계약의 기준점. **여기를 먼저 단단히.**
3. **3단계(API 계약)** — 나머지 도메인 OpenAPI 고정.
4. **4단계(React)** — 라우트·컴포넌트·드로어.

> 작업정의 폼이 전체 데이터 계약의 기준이므로 2단계를 최우선으로 확정한 뒤 나머지
> API를 같은 패턴으로 확장한다.
