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
2. **평탄 스크립트**: `app.py`는 위→아래 실행 흐름. 마크업/state 헬퍼는 도메인 모듈(`ui/*_tab.py`)로 빼라.
3. **on_click 금지**: `if st.button():` → `_do_*` pending flag → `st.rerun()` 패턴만.
4. **HTTP 단일 진입점**: `scraping.http.build_session()` 외의 `requests.get/Session()` 금지.
5. **XSS 방어**: 세션에 들어가거나 `st.markdown(unsafe_allow_html=True)`로 나가는 모든 사용자/외부 문자열은 `html.escape()`.
6. **네임스페이스 분리**: `sc_*` (수집), `rm_*` (로드맵), `ins_*` (보드), `sola_*` (LLM), pending은 `_` prefix.
7. **main 직push 금지**: 모든 변경은 작업 브랜치 → PR → 머지.

## 읽기 라우팅 (작업별 최소 파일)

| 작업 | 읽을 파일 |
|---|---|
| 스크래퍼 셀렉터·HTTP | `scraping/<source>.py` (+ `scraping/http.py`) |
| 본문 enrich / 키워드·요약 | `scraping/enrich.py` |
| 로드맵 엑셀 적재·스키마 | `roadmap/ingest.py`, `roadmap/schema.py` |
| 뉴스↔작업 매칭 / 자동화 기회 | `store/match.py`, `sola/opportunity.py` |
| 트렌드·캐시·북마크·채팅 영구화 | `store/{trends,cache,bookmarks,chat_log}.py` |
| LLM 호출·프롬프트 | `sola/client.py`, `sola/prompts.py` |
| 요약·제안서·채팅 컨텍스트 | `sola/{summarize,propose,chat_ctx,insight}.py` |
| 페르소나 | `persona/{schema,store,context}.py` |
| UI 탭 (수집·로드맵·뉴스·보드·SOLA·홈·북마크) | `ui/<name>_tab.py` |
| 사이드바·작업 트리 | `ui/sidebar.py`, `ui/task_tree.py` |
| CSS·스타일 | `ui/styles.py` (+ `assets/styles.css`) |
| 진입점·디스패치·세션 키 | `app.py` (+ `docs/INVARIANTS.md`) |
| 아키텍처 파악 | `docs/ARCHITECTURE.md` |

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
