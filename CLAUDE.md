# CLAUDE.md — News 프로젝트 작업 규칙

> 이 파일은 Claude가 News 레포에서 작업할 때 가장 먼저 읽는 **유일한** 상시 문서다.
> 나머지 docs/는 필요할 때만 선택적으로 읽는다. (→ [`DEV_GUIDELINES.md`](./DEV_GUIDELINES.md))

## 도메인

조선소 작업 정의를 이해하는 LLM 어시스턴트가 외부 기술 동향을 우리 작업에 어떻게 적용할지 번역해주는 시스템. 3대 축:

1. **수집·enrich** (`scraping/`) — 네이버 / 구글 RSS / AI Times / 오토메이션월드, 본문 fetch + LLM 키워드·요약.
2. **로드맵·매칭** (`roadmap/`, `store/`) — 조선소 작업 정의 엑셀 → Parquet, 룰 기반 뉴스↔작업 매칭, 자동화 기회 매트릭스.
3. **SOLA LLM** (`sola/`, `persona/`) — 요약·제안서·채팅·부서 인사이트·매트릭스 코멘트, 페르소나 자동 주입.

UI는 `ui/` 패키지의 탭 모듈로 분리, `app.py`는 평탄 디스패처.

## 절대 규칙 (반드시 지킬 것)

1. **토큰 절약**: 수정 대상 파일만 읽어라. UI 작업에 `sola/` 전체를 읽지 마라. (`DEV_GUIDELINES.md` §1)
2. **평탄 스크립트**: `app.py`는 위→아래 실행 흐름. 마크업/state 헬퍼는 도메인 모듈(`ui/*_v2.py`, `ui/app_shell.py`, `ui/chat_panel.py` 등)로 빼라.
3. **on_click 금지**: `if st.button():` → `_do_*` pending flag → `st.rerun()` 패턴만.
4. **HTTP 단일 진입점**: `scraping.http.build_session()` 외의 `requests.get/Session()` 금지.
5. **XSS 방어**: 세션에 들어가거나 `st.markdown(unsafe_allow_html=True)`로 나가는 모든 사용자/외부 문자열은 `html.escape()`.
6. **네임스페이스 분리**: `sc_*` (수집), `rm_*` (로드맵), `ins_*` (보드), `sola_*` (LLM), pending은 `_` prefix.
7. **main 직push 금지**: 모든 변경은 작업 브랜치 → PR → 머지.
8. **작업 완료 보고 의무 (패치노트 형식)**: 모든 개발 지시가 끝나면 사용자에게 아래를 **반드시** 한 메시지로 정리한다 (생략 금지, 단순 정보 질문 응답은 제외).
   1. **무엇을 어떻게 수정했는지 — 패치노트처럼 항목별로 명확히 쭉 나열**. 각 항목은 `무엇을(파일·함수·기능) → 어떻게 바꿨고 왜(동작·효과)` 가 한눈에 보이게 쓴다. 기호·약어만 뭉쳐 나열하지 말고, 읽어서 이해되는 문장으로.
   2. **어떻게 조치됐는지** — 테스트 결과(N/N passed), 금지 패턴 검사, 커밋·푸시·PR 번호/링크/상태, CI 상태(queued/in_progress/success/failure), 충돌 시 해소 방법.
   3. **다음 단계 — 내용까지 설명**. 후속 작업 1~3건을 제목만 던지지 말고, "무엇을 왜 하는지 · 어디 파일을 건드리는지" 를 한두 줄로 풀어 사용자가 이해하고 바로 지시할 수 있게.

   형식 예시:

   ```
   ✅ <제목> — PR #N (Draft/Ready/Merged) · CI <상태>

   ■ 무엇을 어떻게 수정했나 (패치노트)
   - <파일/모듈>: <무엇을 어떻게 바꿨는지> → <효과/이유>
   - …

   ■ 조치: pytest N/N · 금지패턴 0 · push <성공/실패> · CI <상태>

   ■ 다음 단계
   1. <작업명> — <무엇을 왜, 어디를 건드리는지 1~2줄>
   ```

## 읽기 라우팅 (작업별 최소 파일)

> v2 셸 기준. 화면 모듈은 모두 `ui/*_v2.py`. `ui/<name>_tab.py` 는 더 이상 존재하지 않는다.

| 작업 | 읽을 파일 |
|---|---|
| 스크래퍼 셀렉터·HTTP | `scraping/<source>.py` (+ `scraping/http.py`) |
| 본문 enrich / 키워드·요약 | `scraping/enrich.py` |
| 일일 cron 수집 | `scraping/run_daily.py`, `scripts/daily_scrape.py` |
| 로드맵 엑셀 적재·스키마 | `roadmap/ingest.py`, `roadmap/schema.py` |
| 작업 정의 CRUD (SQLite) | `store/task_defs_db.py`, `roadmap/{task_def_form,task_def_json}.py` |
| 로드맵 조회 (SQLite→Parquet) | `roadmap/query.py`, `roadmap/sqlite_sync.py` |
| 뉴스↔작업 매칭 / 자동화 기회 | `store/match.py`, `sola/opportunity.py` |
| 트렌드·캐시·북마크·채팅 영구화 | `store/{trends,cache,bookmarks,chat_log,sola_threads,sources}.py` |
| LLM 호출·프롬프트 | `sola/client.py`, `sola/prompts.py` |
| 보드/트렌드 LLM 산출 | `sola/{board_brief,trend_brief,opportunity,side_context}.py` |
| 페르소나 | `persona/{schema,store,context}.py` |
| 📊 오늘의 보드 | `ui/board_v2.py` |
| 🧱 데이터 관리 | `ui/data_management_v2.py` (+ `ui/task_def_manage.py`, `ui/data_health.py`) |
| 🔎 인사이트 분석 | `ui/insights_v2.py` |
| 🤖 SOLA 작업실 | `ui/sola_workshop_v2.py` |
| 📦 산출물 보관함 | `ui/archive_v2.py` |
| v2 셸 (topbar·좌측 nav·우측 SOLA 패널·⌘K) | `ui/app_shell.py` |
| 사이드바 / 페르소나 모달 / 온보딩 | `ui/sidebar.py`, `ui/persona_page.py`, `ui/onboarding.py` |
| 글로벌 채팅 패널 (우측 컬럼) | `ui/chat_panel.py` (`render_side`) |
| CSS·스타일 | `ui/styles.py` (+ `assets/v2/*.css`: tokens·card·shell·sidebar·streamlit-overrides·scale + `screens/*.css`) |
| HTML 컴포넌트 빌더 | `ui/components.py` |
| 진입점·디스패치·세션 키 | `app.py` (+ `docs/INVARIANTS.md`) |
| 아키텍처 파악 | `docs/ARCHITECTURE.md` |
| 리팩토링 로드맵·결정 | `docs/REFACTOR_PLAN.md` |

> ⚠ 데드 (건드리기 전 `REFACTOR_PLAN` 확인): `sola/side_context.py`(orphan·보존 — 사이드 채팅 컨텍스트 연결 대상). `propose`/`summarize` 는 부활(SOLA 작업실 연결). Phase 3 에서 `ui/layout.py`·`ui/task_tree.py`·`sola/{insight,chat_ctx}.py`·`app_shell.render_app_side/sola`(+패널 토글)·`chat_panel.render`·`task_defs_db.upsert_many`·`sola_main.html` 삭제됨.

전체 라우팅 표는 [`DEV_GUIDELINES.md §3`](./DEV_GUIDELINES.md#3-라우팅-표).

## 커밋 전 체크리스트

```bash
# 스테이지된 .py 만 compile (CI 가 모든 .py 를 자동 검사)
python -m py_compile $(git diff --name-only --cached | grep '\.py$')

grep -rnE 'on_click\s*=' app.py ui/                                # 0
grep -rnE 'requests\.(get|post|Session)\(' \
     app.py ui/ sola/ store/ roadmap/ persona/ scraping/ \
     | grep -v 'scraping/http\.py:'                                # 0

pytest -q
```

> GitHub Actions(`.github/workflows/ci.yml`)이 동일 검증을 PR 마다 자동 실행한다.

커밋에는 다음이 함께 포함되어야 한다:
- `CHANGELOG.md` [Unreleased] 항목 추가
- `docs/SESSIONS.md` 상단 세션 기록
- 새 invariant 발생 시 `docs/INVARIANTS.md` 갱신

## 브랜치 네이밍

`<카테고리>-<설명>` — 슬래시 금지, 하이픈 구분.
카테고리: `fix`, `feat`, `refactor`, `style`, `docs`, `chore`.

예: `feat-insight-trend`, `fix-scraper-selector`, `style-cardnews-typography`.

## PR 충돌 방지

- 작업마다 최신 `main`에서 새 브랜치를 만들고, 이미 PR을 올린 브랜치를 다음 작업에 재사용하지 않는다.
- PR 생성 전 가능한 경우 최신 `main`으로 rebase/merge해서 충돌을 로컬에서 먼저 확인한다.
- `CHANGELOG.md`와 `docs/SESSIONS.md`는 모든 PR이 상단을 수정하는 고충돌 파일이므로 `.gitattributes`의 `merge=union` 설정으로 자동 병합한다. 병합 후 중복/순서만 리뷰한다.
