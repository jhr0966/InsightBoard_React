# SESSIONS — 작업 세션 로그

> **최신 세션이 상단.** 다음 세션은 상단 1개만 읽고 복원한다.
> 완료된 세션은 "✅ merged"로 닫는다.

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
