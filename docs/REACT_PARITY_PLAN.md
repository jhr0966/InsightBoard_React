# REACT_PARITY_PLAN — 기존 Streamlit UI/UX·기능 100% React 재현 계획

> 목표: 현행 Streamlit 앱(`app.py`·`ui/`)의 **모든 화면·인터랙션·시각화·핸드오프**를
> React(`web/`)에서 동등하게 재현한다. `docs/REACT_MIGRATION_PLAN.md`(전환 토대)의 후속 —
> 이 문서는 **기능 패리티 실행 계획**이다.
>
> 근거: 2026-06-15 코드 실측 인벤토리(board/insights/data_management/archive/shell/persona/
> onboarding/chat/sola_workshop 전 화면). 이미 완료된 토대는
> `docs/REACT_PREP_INVENTORY.md` 참조.

## 결정 (확정)
- **차트 = SVG 직접 구현** — 현행 픽셀 단위 동일 모양(4분면·충돌회피·선택 글로우·적응형 granularity)까지 재현. 라이브러리 대체 안 함.
- **진행 = 문서(이 PR) → Phase 0 착수**.
- 식별·감사 필드, 제공자 추상화, 스토리지 seam 은 토대에서 이미 완료 → 그대로 사용.

## 원칙
1. **현행 UX 1:1 (디자인 계승, 개선 허용)** — 기존 Streamlit v2 디자인 시스템(레이아웃·카드·간격·색·타이포·화면별 CSS)을 **그대로 계승**한다. 카드뉴스·기사 모달·칸반·SVG 차트·핸드오프·온보딩까지 시각·인터랙션 동등. 단 **친숙함을 깨지 않는 선에서 개선**(접근성·반응형·로딩 상태·미세 정렬)은 허용 — "더 나빠지지 않기"가 하한선.
2. **상태 모델 변환** — Streamlit `pending flag + rerun` → React 이벤트/뮤테이션, `query_param 액션` → 이벤트(`*_action`류는 URL 오염 제거), 진짜 URL 상태(`app_area`·`from`·필터·선택)만 라우트/쿼리로.
3. **백엔드 우선** — 화면이 쓰는 데이터가 API에 없으면 엔드포인트부터(§2).
4. **디자인 토큰·에셋 승계** — `assets/v2/*.css`(tokens·card·shell·sidebar·screens/*) + 폰트 그대로. 4테마(light/dark/ocean/sunset) 유지.

---

## 1. 화면별 패리티 명세 (실측 인벤토리 요약)

### 1.1 📊 오늘의 보드 (`ui/board_v2.py`) — 7 섹션 (최대 작업)
1. **인사말 + KPI 4** — 수집·매칭·자동화제안·채택대기(델타 배지). `←/↑` delta.
2. **SOLA 브리핑(아침 7분)** — LLM 한줄+불릿(룰 폴백) + **뉴스 카드 캐러셀 5**(썸네일 그라데이션 폴백·출처 배지·상대시간·2줄 클램프) + 출처 cite pills + CTA "이 5건으로 제안서 만들기→"(`from=brief`).
3. **탑 스토리** — 2열 카드 그리드(페르소나 매칭 강한 순), 썸네일 lazy/no-referrer, 호버 lift.
4. **자동화 제안 카드** — 3열, status 배지·카테고리 태그·메트릭4(score/relevance/impact/roi)·[보류/채택/자세히] → 북마크+토스트.
5. **기회 매트릭스** — 좌 **SVG 버블차트**(X=난이도·Y=ROI·4분면·반경=score·dept색·**충돌회피 오프셋**·선택 글로우) / 우 상세패널(순위·3통계·CTA `from=matrix`). 선택=`?mx_select=dept|lv3`.
6. **8주 트렌드** — 좌 **SVG 라인차트**(4계열·top 강조·마커·**적응형**: 데이터 부족 시 14일 일간모드+"신규 N건") / 우 키워드 6 리스트(점·스파크라인·델타배지).
7. **키워드 관리** — 자동추출(30일 top6, 히트 tier 색) + 사용자추가 칩(× 뮤트/삭제) + 요약바 + CTA "지금 즉시 수집→"(`collect_batch`).

### 1.2 🔎 인사이트 분석 (`ui/insights_v2.py`)
- **헤더 KPI 4**(분석뉴스30일·신규트렌드·매칭공정·PoC후보). 필터 스트립은 **목업 → 실배선**(기간/공정/카테고리).
- **A. 트렌드→공정 매핑**: 좌 5주 라인차트(top3 강조+콜아웃) / 우 키워드 6(랭크·바·NEW배지·델타, `?tkw=` 토글) / 하단 매핑 카드 3(★최적매칭·적합도%·현재/신호·`from=ia_map`).
- **B. 매트릭스**: 좌 SVG 버블(600×420·4분면 틴트·`?ia_mx_select=`) / 우 PoC 랭킹 5(난이도×효과·점수).
- **C. 히트맵**: 7공정×7기술(비전/협동로봇/예지보전/디지털트윈/AGV/AI/외골격) 색강도 5단계·셀선택(`?hm_select=`)·하단 상세 strip(뉴스 미리보기3+CTA `tech=`).
- **우측 SOLA 분석패널**: 컨텍스트 핀·Q&A 카드·액션 버튼(→ 전역 채팅으로 통합).

### 1.3 🗞 뉴스 수집 (`ui/data_management_v2.render_collect`)
- KPI 4(활성출처·오늘·30일·최종갱신) + **경보 배너**(수집 실패/stale).
- 액션바: [🔄 지금 수집](→진행 모달) · [⚙ 수집 설정](서브뷰).
- **카드/표 토글** → 카드: **대분류 탭**(키워드/포탈)·**출처칩**·**사진 카드 그리드(3열·24)**·기사 모달(이미지·본문·원본링크). 표: dataframe 행선택→모달.
- 전역 검색(제목/본문/요약/키워드).
- **⚙ 수집 설정 서브뷰**: 키워드(자동/사용자/뮤트) · **출처 토글/추가/제거**(그룹별) · **수집 이력**(최근 run·오늘 잡·14일 막대차트·런 타임라인12) · **기사 진단**(URL→HTTP·소프트블록·셀렉터).
- **수집 진행 모달**: 실시간 진행+결과 요약.

### 1.4 📋 작업 정의 (`ui/data_management_v2.render_taskdef` + `task_def_manage`)
- KPI 3(등록정의·부서·마지막갱신).
- **엑셀 업로드 + diff 미리보기**(before/after, 확인 시 저장/교체).
- 검색(`?td_q=`) + 리스트 카드(보기) + [＋새 작업].
- **상세 뷰**: org_meta 그리드·태그·설명·섹션(작업흐름·확인사항·목표·품질리스크·자동화영역·안전·장비·공정연결)·**이력**(action·시각·source·who).
- **풀 편집 폼(20+필드)**: team/dept/division/process/task/sub_task, process_name/description/domain/category, objectives[], overall_quality_risks[{risk;consequence}], automation_potential_areas[{area;tech;effect}], key_check_points[], safety_notes[], main_equipment[], previous/next_process, task_def_text. 검증 후 PUT.

### 1.5 📦 산출물 보관함 (`ui/archive_v2.py`)
- KPI(총·채택률·채택·대기·기각).
- **칸반 3열**(대기/채택/기각, 열 색): 카드(타입태그·ID·제목·설명·태그칩·나이) + 열 상단 액션([채택]/[기각]/[되돌리기]) + 더보기(+N) + SOLA 편집 핸드오프(`from=edit&bm_id=&title=`).

### 1.6 🧭 앱 셸 (`ui/app_shell.py`·`ui/sidebar.py`)
- **Topbar**: 브레드크럼(WORKFLOW/화면) · 제목 · 갱신시각 · **FRESH/LIVE/STALE 배지** · 알림벨(채택대기>0 카운트→보관함) · 설정기어(→페르소나) · 아바타 · **전역 검색**(Enter→뉴스수집 필터).
- **Sidebar**: 브랜드 · **페르소나 카드**(설정/미설정 분기·→페르소나) · 통계 3열 · **그룹 nav 6**(메인①②③ / 관리④⑤⑥·active 강조) · **LLM 상태 푸터**(키 미설정 안내+Groq 발급 링크).
- **⌘K 커맨드 팔레트** · 우측 SOLA 채팅 패널.

### 1.7 👤 페르소나 설정 (`ui/persona_page.py`)
- 기본정보(이름·팀·부서·직무 — 로드맵 있으면 select) · 관심공정(multiselect) · 관심키워드(Enter 칩) · **SOLA 분석**(derive/캐시/규칙폴백·칩+연관공정/작업·재분석) · 테마/글자크기(4테마) · 저장/초기화/돌아가기 · 키보드 내비.

### 1.8 🚀 온보딩 마법사 (`ui/onboarding.py`)
- 6단계 모달(환영→이름→팀·부서→직무→관심사→수집제안→수집실행) · 진행바·step indicator · 키보드(Enter→다음, Ctrl+Enter→제출)·자동포커스 · dismiss 마커(재노출 안 함) · 완료 시 persona 저장+derive.

### 1.9 💬 전역 채팅 패널 (`ui/chat_panel.py`)
- 화면별 컨텍스트 주입 · **추천질문 pills**(클릭=즉시전송, 화면별 문구) · 메시지 버블(user/assistant·시각) · 자동스크롤 · **SSE 스트리밍** · 스레드 영속 · (SOLA 작업실은 빠른작업 칩 3).

### 1.10 🤖 자동화 제안 / SOLA 작업실 (`ui/sola_workshop_v2.py`)
- 3열(스레드목록 | 산출물 작업대 | 채팅).
- **핸드오프 배너 + 자동검토**(`from=brief/opp/matrix/ia_map/edit` → prefill 자동전송 + "✓ 자동 검토 시작").
- 작업대: 컨텍스트 칩 · **현재 산출물 문서**(마지막 assistant 메시지·마크다운) · [📦 보관함 저장]/[🔄 다시 생성]/빈상태.
- 스레드: 검색 · 그룹핑(고정/오늘/어제/이번주/이전) · 열기 · 고정 · 2단계 삭제.
- 저장한 산출물 요약 카드.

### 1.11 🩺 데이터 준비/헬스 (`ui/data_health.py`)
- 메트릭 4(오늘 뉴스·본문 확보율·정의된 작업·LLM 상태) + 상태 카드 5(News DB·Content Enrich·Task Def DB·LLM Config·Data Quality, warn/ok). 위치: 수집 설정 하단 또는 독립 섹션.

### 1.12 🔁 전 화면 공통 (교차 요소 — 반드시 재현)
- **테마 4종 + 글자크기**: 앱 전역 적용·영속(`ui_prefs`). 페르소나 설정에서 변경 → 즉시 반영.
- **빈 상태 카피**: 각 화면 고유 문구 그대로(예 보드 매트릭스 "아직 매칭된 자동화 제안이 없어요.", 트렌드 "데이터 부족…30일 이상 수집 후").
- **1회성 토스트**: 액션(채택/기각/저장/수집/출처) 후 성공/실패 알림(1회 표시 후 소멸).
- **상대시간 라벨**: 방금/N시간 전/어제/M월 D일 — 카드·모달·칸반 공통 헬퍼.
- **출처 색 그라데이션·기사 나이 라벨** 헬퍼(`data_management_render.py`) 승계.
- **키보드 UX**: 폼/모달 자동포커스 · Enter→다음 입력 · Ctrl/⌘+Enter→제출(페르소나·온보딩·작업정의 폼·채팅).
- **로딩/스켈레톤**: 차트·리스트·KPI 로딩 상태(개선 항목 — 현행 spinner 대체).
- **반응형**: 좌 nav · 중앙 · 우 채팅 3-컬럼의 축소(태블릿/모바일)는 개선 영역.
- **경고 배너**: curl_cffi(WAF 우회) · LLM 키 미설정 안내(Groq 링크) 승계.
- **알림 정직성**: topbar 벨은 채택 대기 > 0 일 때만 카운트(거짓 알림 없음).

### 1.13 ✅ 커버리지 체크리스트 (사전 인벤토리 → 본 계획 반영 확인)
| Streamlit 모듈 | 화면/기능 | 본 계획 | 반영 |
|---|---|---|---|
| `ui/board_v2.py` | 오늘의 보드 7섹션(브리핑·탑스토리·제안·매트릭스·트렌드·키워드) | §1.1 | ✅ |
| `ui/insights_v2.py` | 인사이트(트렌드→공정·매트릭스·히트맵·필터) | §1.2 | ✅ |
| `ui/data_management_v2.py` `render_collect` | 뉴스 수집(카드/표·탭·칩·모달·검색) | §1.3 | ✅ |
| ↳ `_render_collect_settings` | 수집 설정(키워드·출처·이력·진단) | §1.3 | ✅ |
| ↳ 수집 모달 | 진행/결과 | §1.3 | ✅ |
| `ui/data_management_v2.py` `render_taskdef`·`task_def_manage` | 작업 정의(업로드 diff·상세·풀폼·이력) | §1.4 | ✅ |
| `ui/archive_v2.py` | 보관함 칸반 3열 | §1.5 | ✅ |
| `ui/app_shell.py` | topbar·우측 패널·⌘K | §1.6 | ✅ |
| `ui/sidebar.py` | 사이드바(페르소나 카드·nav·LLM) | §1.6 | ✅ |
| `ui/persona_page.py` | 페르소나 설정·derive·테마 | §1.7 | ✅ |
| `ui/onboarding.py` | 온보딩 6단계 | §1.8 | ✅ |
| `ui/chat_panel.py` | 전역 채팅(pills·SSE·컨텍스트) | §1.9 | ✅ |
| `ui/sola_workshop_v2.py` | 자동화 제안 작업실(핸드오프·작업대·스레드) | §1.10 | ✅ |
| `ui/data_health.py` | 데이터 헬스 | §1.11 | ✅ |
| `ui/components.py`·`assets/v2/*` | 컴포넌트·디자인 토큰·4테마 | §1.12·§3 | ✅ |
| `ui/data_management_render.py` | 출처색·나이 라벨 헬퍼 | §1.12 | ✅ |

> 데드/보류 모듈(`ui/layout.py`·`ui/task_tree.py` 등 — `REFACTOR_PLAN` 참조)은 재현 대상 제외.

---

## 2. 백엔드 API 공백 (현재 24경로 → 추가)

| 추가 | 용도 | 위임 |
|---|---|---|
| `GET/PUT /api/persona` · `POST /api/persona/derive` | 페르소나 CRUD·SOLA 분석 | `persona.store`·`persona.derive` |
| `GET /api/matches?days=&top=` | persona×뉴스 매칭(브리핑·탑스토리·매핑) | `store.match.score_matches` |
| `GET /api/board` | 보드 종합(브리핑+탑스토리+KPI+매칭) | `sola.board_brief`+`match` |
| `GET /api/trends/weekly?weeks=` · `/emergence` | 주간 시계열·신규 키워드 | `store.trends` |
| `GET /api/sources` · `POST /api/sources` · `POST /api/sources/{name}/toggle` · `DELETE /api/sources/{name}` | 출처 설정 | `store.sources` |
| `GET /api/collect/status` · `/runs?limit=` · `POST /api/collect/diagnose` | 수집 이력·진단 | `store.run_log`·`scraping.diagnose` |
| `POST /api/collect` **SSE** | 수집 진행 스트리밍 | `scraping.run_daily`(지연) |
| `POST /api/proposals/summarize` | 뉴스 요약 | `sola.summarize` |
| `PATCH /api/bookmarks/{id}` content · `GET /api/bookmarks?status=` | 칸반 수정·필터 | `store.bookmarks` |
| `GET/PUT /api/ui-prefs` · `GET /api/health/data` | 테마·데이터 헬스 | `store.ui_prefs`·`data_health` |
| `POST /api/taskdefs/upload` diff preview | 업로드 전 diff | `roadmap.ingest`(dry-run) |

> 모두 식별·감사 필드 규약(§ `_audit`) + Identity 의존성 적용. 수집/진단은 `scraping` 지연 import(서버리스 503).

---

## 3. 컴포넌트 · 차트 라이브러리 (Phase 0 산출물)

### 공통 컴포넌트 (`web/src/components/ui/`)
`Card` · `KPIStatGrid`(델타 배지) · `Chip`/`Badge`(tone) · `Tabs` · `Modal`/`Dialog`(dismissible 제어) · `Toast`(1회성) · `KanbanColumn` · `Pills`(추천질문) · `EmptyState` · `CardNewsGrid` · `ArticleModal`.

### 차트 (`web/src/components/charts/` — SVG 직접)
- `LineChart` — 다계열·top 강조·마커·콜아웃·적응형 granularity(주간↔일간).
- `BubbleMatrix` — 4분면·축 라벨·반경 정규화·dept 팔레트·**충돌회피 오프셋**·hover scale·**선택 글로우/halo**·클릭.
- `Heatmap` — 행공정×열기술·색강도 5단계·셀 선택 outline·하단 상세 strip.
- `Sparkline` · `BarChart`(수집량·14일·호버 title).

### 디자인 시스템
`assets/v2/*.css`(tokens·card·shell·sidebar·screens/*) 승계 + Pretendard/JetBrains 폰트(`public/fonts/`). 4테마(light/dark/ocean/sunset) CSS 변수.

---

## 4. Phase 계획

| Phase | 내용 | 산출물 |
|---|---|---|
| **P0** | 디자인시스템·셸·공통 컴포넌트·**차트 4종** | `components/ui/*`·`charts/*`·`Layout`(topbar/sidebar/⌘K) |
| **P1** | API 공백 메우기(§2 전부) + OpenAPI 타입 재생성 | `api/routers/*` 확장 |
| **P2** | 화면 재현 (보드→인사이트→수집→작업정의→보관함→페르소나/온보딩→자동화제안) | `web/src/pages/*` 정밀화 |
| **P3** | 교차: 어시스턴트 컨텍스트·핸드오프(`from=*`)·추천 pills·토스트·URL 파라미터·온보딩 게이팅 | `AssistantDrawer`·라우팅 |
| **P4** | 백엔드 호스팅 연결(`VITE_API_BASE`) + **Streamlit 은퇴**(`app.py`·`ui/` 폐기) | 배포·정리 |

**화면 순서 근거**: 보드가 차트 4종을 모두 써서 P0 컴포넌트를 검증 → 인사이트가 그걸 재사용 → 수집/작업정의/보관함은 폼·테이블·칸반 → 페르소나/온보딩/자동화제안은 상태흐름 복잡(마지막).

## 5. 최대 리스크
1. **SVG 차트 4종** — 단일 최대 작업(버블 충돌회피·히트맵 색강도·트렌드 적응형).
2. **핸드오프/컨텍스트 배선** — 화면→SOLA 작업실 자동검토 prefill, 화면별 chat_context.
3. **라이브 수집·진단** — 호스팅 백엔드 필요(서버리스 부적합) → P4 호스팅 후 완전 동작.
4. **상태 모델 변환** — pending/rerun·query_param 액션 34키를 React 이벤트로(드리프트 주의).

## 6. 완료 정의 (Definition of Done)
- §1.13 커버리지 체크리스트의 **모든 행이 React에서 동작** — 6개 화면 + 셸 + 페르소나/온보딩 + 자동화제안 + 데이터 헬스가 현행과 시각·인터랙션 동등(디자인 계승).
- **전 화면 공통(§1.12) 재현**: 4테마+글자크기·빈 상태 카피·1회성 토스트·상대시간·키보드 UX·경고 배너.
- 모든 데이터가 API 경유(직접 store 호출 없음), OpenAPI 스냅샷 동기화.
- 차트 4종 픽셀 패리티. 핸드오프 5종(brief/opp/matrix/ia_map/edit) 동작.
- 호스팅된 백엔드 연결 → Streamlit 폐기.
