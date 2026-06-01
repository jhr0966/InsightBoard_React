# 전체 시스템 리팩토링 & 최적화 계획서

> 작성: 2026-06-01 · 1차 완성(M1~M3) 직후 전수 점검 기반.
> 검증 방법: 병렬 코드 감사 2건(기능 end-to-end / 아키텍처·모듈화) + 5화면 실구동 + 핵심 주장 직접 grep 검증.
> **이 문서는 계획서다. 코드 변경은 단계별 PR 로 별도 진행.**

---

## 0. 한 줄 요약

**해피패스는 동작하고 654 테스트가 그린이지만, 테스트가 "UI 가 이미 버린 아키텍처"를 검증하고 있어 안심은 착시다.** 5대 기능 중 "제안서 작성"은 사실상 단절돼 있고(빈 북마크), enrich 파이프라인 산출물은 핵심 매칭에서 안 쓰이며, 제안·요약·인사이트 생성 모듈 4개는 production 호출이 0이다. 모듈화는 백엔드는 깨끗하나 UI 5화면이 공통 헬퍼를 우회해 동일 코드를 6벌씩 복제한다. 문서(ARCHITECTURE/CLAUDE/INVARIANTS)는 옛 구조를 가리켜 Claude Code 작업 효율을 떨어뜨린다.

---

## 1. 검증된 발견 (전부 직접 확인)

### 1-A. 기능 결함 (correctness) — 우선순위 높음

| # | 발견 | 위치 | 영향 |
|---|---|---|---|
| F1 | **`sola/propose·summarize·insight·chat_ctx` 4개 모듈 전부 데드** (production 호출 0, 테스트만 사용) | `sola/{propose,summarize,insight,chat_ctx}.py` | 제안서/요약/부서 인사이트 "생성"이 앱에서 호출 안 됨. 테스트는 통과하지만 사용자에겐 미연결 |
| F2 | **제안서 북마크가 빈 content 로 생성, 채울 경로 없음** (`update_content` 도 데드) | `ui/board_v2.py:110` (`content=""`), `store/bookmarks.py:139` | "제안서 작성" 기능이 제목+상태만 있는 껍데기. archive UI 안내문("제안서를 만들면 여기로 모입니다")이 실제 흐름과 불일치 |
| F3 | **핵심 매칭이 enrich 산출물을 무시** | `store/match.py:41` (`news_cols=("title","summary","keywords")`) | LLM 본문/요약/키워드(`content`/`summary_llm`/`keywords_llm`)가 매칭·자동화 매트릭스에 반영 안 됨 → enrich 파이프라인 가치 손실 |
| F4 | **cron 수집이 enrich 안 함** | `scripts/daily_scrape.py`, `scraping/run_daily.py` | 일일 자동 수집 뉴스는 본문/요약 비어 사용자가 수동 enrich 전엔 저가치 |
| F5 | **업로드 성공 토스트가 부정확** (`row_count` = 엑셀 전체 행, 실제 저장분 아님) | `ui/data_management_v2.py:684` | skip 된 행 포함해 "N건 저장" 으로 과대 보고. `sqlite_created+updated` 써야 |
| F6 | **SOLA 채팅에 히스토리 truncation 없음** | `ui/sola_workshop_v2.py:428` | 긴 대화가 모델 컨텍스트 한도 초과 가능 (전체 히스토리 매 턴 전송) |
| F7 | **`ts` 필드가 reload 시 손실** (`chat_log` 스키마에 없음) | `ui/sola_workshop_v2.py` ↔ `store/chat_log.py:40` | 재로드된 과거 메시지 타임스탬프 공란 |
| F8 | **히트맵 `"AI"` 부분문자열 과매칭** (`"Wait"·"domain"` 등에 매칭) | `ui/insights_v2.py:549,583` | 자동화 매트릭스 "AI" 열 수치 부풀려짐 |
| F9 | **데드 정렬 분기** (`_hm_top_news` 가 없는 컬럼 `collected_at` 로 정렬) | `ui/insights_v2.py:619` | "top news" 실제론 파일 순서 |
| F10 | **`upsert_articles` 가 중복 parquet 누적** (원본 미삭제) | `store/news_db.py:101` | enrich 마다 당일 파일 수 2배, 정확성이 파일명 사전순에 의존 |
| F11 | **`upsert_many` 데드 + 거짓 docstring** ("rollback" 주장하나 행마다 개별 commit) | `store/task_defs_db.py:324` | 미사용. 삭제 또는 트랜잭션 수정 필요 |
| F12 | **SOLA 사이드바 통계 하드코딩** (`{match_today:32, opportunities:4}` 가짜값) | `ui/sola_workshop_v2.py:56` | 다른 화면은 실시간 계산, SOLA 만 가짜 |

### 1-B. 모듈화 / 유지보수 — 우선순위 중

| # | 발견 | 수치 |
|---|---|---|
| M1 | **`_load_persona()` 6개 동일 복사본** | board/data_mgmt/insights/sola/archive + `app_shell._get_persona` |
| M2 | **토스트 색상 dict + 렌더 로직 중복** | dict 6곳, render 7함수 |
| M3 | **`_X_href` URL 빌더 15개** + `app_area=…&quote(…)` 31줄 + `quote()` 49회 | 전 화면 |
| M4 | **`consume_*_if_any` 13개** (대부분 allowed-set 만 다름) | 전 화면 |
| M5 | **`_archive_stats*` 6개** (3개는 동일 body) | 이름 4종 난립 |
| M6 | **`ui/components.py` 우회** — 5개 v2 화면이 공통 컴포넌트 안 쓰고 inline HTML | 중복의 근본 원인 |
| M7 | **대형 파일**: board_v2 1664 / data_mgmt 1423 / insights 1207 — 변경 단위(위젯 ~13줄)보다 라우팅 단위(파일)가 100배 | §1 토큰 규칙 위반 |
| M8 | **데드 모듈**: `ui/layout.py`(218), `ui/task_tree.py`(74), `ui/data_health.py`(테스트 전용) | runtime 미사용 |

### 1-C. 문서 드리프트 — 우선순위 높음 (Claude Code 효율 직결)

| # | 문서 | 문제 |
|---|---|---|
| D1 | `docs/ARCHITECTURE.md` | 존재하지 않는 `home_tab/ingest_tab/roadmap_tab/board_tab/sola_tab/news_tab/bookmarks_tab` 기술. "5탭 라디오", Parquet, `roadmap_df` — 전부 옛 세대 |
| D2 | `CLAUDE.md` 읽기 라우팅 | `ui/<name>_tab.py` 가리킴 → 실제 `*_v2.py`. `ui/task_tree.py` (데드) 아직 안내 |
| D3 | `docs/DEV_GUIDELINES.md §3` | 동일 `*_tab.py` 라우팅 |
| D4 | `docs/INVARIANTS.md I-13` | 데드 `ui/layout.py::main_and_chat` 를 표준으로 명시 (실제 `chat_panel.py`) |

### 1-D. 백엔드 (양호 — 손대지 말 것)

- 계층 비순환: `store`(최하) → `roadmap`/`scraping` → `sola` → `ui` → `app.py`. `store/roadmap/scraping/persona/sola` 어느 것도 `ui` import 안 함.
- `on_click=` 0, scraping/http 외 raw `requests` 0. 라이브 invariant 준수.

---

## 2. ⚠️ 핵심 결정 필요 (사용자 판단)

리팩토링 방향이 갈리는 지점. **이 결정 없이 Phase 1 진행 불가.**

### 결정-1: "빈 제안서" 흐름 (F1·F2) — 가장 중요

5대 기능 중 "과제 제안서 작성"이 현재 **단절**. 두 갈래:

- **(A) 연결한다** — 워크숍 채팅에 "이 대화를 제안서로 저장" 액션 추가 → `bookmarks.update_content(bm_id, draft)` 호출. 데드 `update_content` 부활. opp-card 액션 시 `propose_for_task` 로 실제 초안 생성. → 원래 설계 실현, 작업 큼.
- **(B) 단순화한다** — 채팅-프리필 방식을 진짜 설계로 인정. 데드 `sola/{propose,summarize,insight}` + `update_content` 삭제, 테스트도 정리. archive 안내문 수정. → 정직·간결, 기능 축소.
- **(C) 하이브리드** — 제안서 저장 경로(A의 핵심)만 연결하고, `propose_for_task` 자동생성은 보류. `summarize/insight` 는 삭제.

### 결정-2: enrich → 매칭 연결 (F3·F4)

- **(A) 연결** — `match.py news_cols` 에 `summary_llm/keywords_llm/content` 추가 + cron 에 `--enrich` 단계. enrich 가치 실현.
- **(B) 현상 유지** — enrich 는 UI 표시용으로만. 매칭은 제목/요약 기반 유지.

### 결정-3: 데드 sola 모듈 (F1)

결정-1 과 연동. 연결(A) 이면 살리고, 단순화(B) 면 `propose/summarize/insight/chat_ctx` + 테스트 삭제.

---

## 3. 단계적 계획 (Phase 0 → 4)

> 각 Phase 는 독립 PR 묶음. CLAUDE.md 브랜치 규칙(최신 main → 작업 브랜치 → PR) 준수. 매 PR pytest + 금지패턴 + 가능하면 실구동 검증.

### Phase 0 — 문서 정합성 (D1~D4) · 위험 낮음 · 즉시
가장 먼저. 이후 모든 작업의 "지도"를 바로잡아 토큰 낭비·오작업 방지.
- [ ] `docs/ARCHITECTURE.md` 전면 갱신 — v2 화면 구조 + SQLite + task_defs + 2그룹 데이터관리 + 계층 그래프.
- [ ] `CLAUDE.md` 읽기 라우팅 표 → `*_v2.py` / 신규 sub-모듈 경로.
- [ ] `docs/DEV_GUIDELINES.md §3` 동기화.
- [ ] `docs/INVARIANTS.md I-13` → `chat_panel.py` 로 정정 (또는 layout.py 삭제 후 재작성).
- **PR 1건, ~문서만.**

### Phase 1 — 기능 결함 수정 (F1~F12) · 위험 중 · 결정 후
결정-1/2/3 확정 후 착수. 권장 분할:
- [ ] **PR-1a (correctness 빠른 수정, 무논쟁)**: F5(토스트 카운트), F7(`ts` 영속), F8(`AI` 워드바운더리), F9(데드 정렬 제거), F11(`upsert_many` 삭제 or 트랜잭션), F12(SOLA 가짜 통계 → 실계산). 작음·저위험.
- [ ] **PR-1b (제안서 흐름)**: 결정-1 결과 반영. (A/C 면 저장 경로 연결, B 면 데드 삭제+안내문 수정).
- [ ] **PR-1c (enrich 매칭)**: 결정-2 결과. (A 면 match.py 컬럼 추가 + cron enrich 단계 + 테스트).
- [ ] **PR-1d (수집 위생)**: F6(채팅 truncation), F10(`upsert_articles` 덮어쓰기), `latest_parquet` mtime 정렬.

### Phase 2 — UI dedup (M1~M6) · 위험 낮음
아키텍처 감사 P1~P4. 각 화면 즉시 축소 + 버그 1개 제거. 화면 분할(Phase 3) 전에 해야 분할이 깨끗.
- [ ] **PR-2a**: `app_shell.get_persona()` 승격, `_load_persona` 6벌 삭제.
- [ ] **PR-2b**: `ui/toast.py` 신규 (`consume_toast(key)` + 팔레트) → dict 6/render 7 대체.
- [ ] **PR-2c**: `ui/url_state.py` 신규 (`area_href`, `action_href`, `consume_query_action`). I-16 핸드오프 entrypoint 는 thin wrapper 로 유지.
- [ ] **PR-2d**: `_archive_stats*` → `app_side_stats()` 단일화 (F12 와 합칠 수도).

### Phase 3 — 대형 파일 분할 (M7) · 위험 중
변경 단위 = 위젯이 되도록. 라우팅 표도 sub-모듈로 갱신.
- [ ] **PR-3a**: `ui/data_management_v2.py` → `ui/data_management/{tabs,news,task_def,sources,keywords}.py` (가장 엉킴, 228줄 클러스터 2개 우선).
- [ ] **PR-3b**: `ui/board_v2.py` → `ui/board/{handoff,brief,trend,matrix,keywords}.py` (I-16/I-18 심볼 re-export 유지).
- [ ] **PR-3c**: `ui/insights_v2.py` → `ui/insights/{chart,matrix,heatmap,process_map}.py`.
- [ ] sola_workshop_v2: 분할 보류(900줄 미만), mid-file import(L697)만 정리.

### Phase 4 — 정리 (M8, P9~P10) · 위험 낮음~중
- [ ] **PR-4a**: 데드 `ui/layout.py` + `ui/task_tree.py` 삭제, I-13/라우팅 정합 (Phase 0 과 연계).
- [ ] **PR-4b**: `ui/data_health.py` 처리 (화면 연결 or import 를 테스트로 이동).
- [ ] **PR-4c** (마이그 sign-off 후): `roadmap/ingest.py` Parquet 이중기록 제거 + `query._load_parquet` fallback 제거 + 마이그 CLI 은퇴. news 는 Parquet 유지(설계).
- [ ] **PR-4d**: `_SOURCE_GRADIENTS` + age 포매터 → `ui/format.py` 또는 `components.py`. v2 화면 inline HTML 을 가능한 `components.py` 경유로.

---

## 4. 전체 시스템 사용 흐름 & 시나리오 검토

| 시나리오 | 현재 상태 | 비고 |
|---|---|---|
| **데이터 업로드** (엑셀→미리보기→적용) | ✅ 동작 | 토스트 카운트만 부정확(F5) |
| **작업 정의 CRUD** (검색·추가·수정·삭제·history) | ✅ 동작 | 1차 완성 핵심, inline style 로 안정 |
| **뉴스 수집(수동)** + enrich | ✅ 동작 | 중복 parquet 누적(F10) |
| **뉴스 수집(cron)** | ⚠️ 부분 | enrich 안 함(F4) → 저가치 행 |
| **인사이트 분석** (매트릭스·히트맵·매칭) | ⚠️ 부분 | enrich 미반영(F3), AI 과매칭(F8), 5× 중복 연산 |
| **LLM 채팅** (SOLA 작업실) | ✅ 동작 | truncation 없음(F6), ts 손실(F7), 입력창 2개처럼 보임(UI) |
| **제안서 작성** | ❌ 단절 | 빈 북마크, 생성 모듈 데드(F1·F2) — **결정-1 필요** |
| **부서 인사이트 / 뉴스 요약** | ❌ 미연결 | `insight_for_dept`/`summarize_news` 데드(F1) |

---

## 5. 권장 진행 순서

1. **Phase 0** (문서) — 즉시, 무논쟁. 지도부터 정확히.
2. **결정-1/2/3** 확정 (사용자).
3. **Phase 2** (UI dedup) — 저위험, 모든 화면 축소 + 버그 1개. Phase 3 전 토대.
4. **Phase 1** (기능 결함) — 결정 반영. PR-1a(무논쟁) 먼저.
5. **Phase 3** (분할) → **Phase 4** (정리).

> Phase 0 + Phase 2 + Phase 1a 는 결정 없이도 바로 가능 (무논쟁·저위험). 나머지는 결정-1/2/3 후.
