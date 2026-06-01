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
| **1b** | 결정-1 반영 (제안서 흐름) | ⏸ 결정 대기 |
| **1c** | 결정-2 반영 (enrich→매칭 연결) | ⏸ 결정 대기 |
| **3** | 데드 코드 삭제 (layout/task_tree/sola 4종) | ⏳ 예정 |

> ⚠ 작업 브랜치 제약: 현재 세션은 `claude/nice-bell-eEZLj` 단일 브랜치에서 진행(harness 지정). 통상 규칙(Phase 당 새 브랜치)과 달리 Phase 0·1a 가 같은 PR(#89)에 누적됨.

---

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
| `ui/layout.py` | `main_and_chat` 정의 but 호출 0 (테스트만) | Phase 3 삭제, I-13 은 chat_panel 로 이미 정정(#89) |
| `ui/task_tree.py` | 드릴다운 위젯, 호출 0 | Phase 3 삭제 |
| `sola/propose.py` | production import 0 | 결정-1 후 부활 or 삭제 |
| `sola/summarize.py` | production import 0 | 결정-1 후 부활 or 삭제 |
| `sola/insight.py` | production import 0 | Phase 3 삭제 후보 |
| `sola/chat_ctx.py` | production import 0 | Phase 3 삭제 후보 |
| `store/task_defs_db.upsert_many` | 호출 0 (테스트만) | Phase 3 데드 재판정 |

> 삭제는 테스트 의존을 함께 정리해야 하므로 한 Phase 로 묶는다. sola 4종 중 `propose`/`summarize` 는 결정-1(제안서·요약 흐름 부활) 결과에 따라 운명이 갈리므로 **결정 전 삭제 보류**.

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

## Phase 3 — 데드 코드 삭제 (예정)

결정-1·1b 완료 후. `ui/layout.py`·`ui/task_tree.py` + 결정-1 에서 부활 안 된 sola 모듈 + 테스트 정리. 삭제마다 `grep -rn` 으로 잔여 import 0 재확인.
