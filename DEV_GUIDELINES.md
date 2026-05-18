# News 개발 지침

> CLAUDE.md의 규칙을 정리한 개발자용 요약 문서.
> 3대 축: **수집·enrich · 로드맵·매칭 · SOLA LLM**

## 1. 토큰 절약 규칙 (최우선)

1. **코드 파일은 수정 대상만 읽는다.** "전체 파악"을 위해 모든 파일을 읽지 마라.
2. **docs/는 라우팅 표에 해당하는 문서만 1개 읽는다.** 2개 이상 동시에 읽지 마라.
3. **SESSIONS.md는 상단 1개 세션만.** 전체를 읽지 마라.
4. **단순 수정은 해당 파일만 읽고 바로 수정.** 관련 없는 파일 탐색 금지.
5. **읽기 전에 자문**: "이 파일을 안 읽으면 작업이 불가능한가?" — 아니면 읽지 마라.

## 2. 파일별 역할 및 읽는 시점

| 파일/패키지 | 역할 | 언제 읽나 |
|---|---|---|
| `app.py` | Streamlit 엔트리 (평탄 스크립트, 3영역 디스패치) | 영역/탭/네비게이션/세션 상태 작업 시 |
| `scraping/` | 네이버·구글RSS·AI Times·오토메이션월드 + HTTP 단일 진입점 + 본문 enrich | 크롤링·파서·셀렉터·본문 enrich 작업 시 |
| `roadmap/` | 조선소 작업 정의 엑셀 → snake_case 정규화 → Parquet | 로드맵 스키마/적재/쿼리 작업 시 |
| `store/` | 뉴스 Parquet · 매칭 · 트렌드 · 캐시 · 채팅·북마크 영구화 | 데이터 저장·조회·집계 작업 시 |
| `sola/` | LLM 호출 · 프롬프트 · 요약·제안서·채팅·인사이트·자동화 기회 | LLM 호출·프롬프트·결과 포맷 작업 시 |
| `persona/` | 사용자 부서·직무·관심 공정 (JSON 영구화) | 페르소나 UI/컨텍스트 주입 작업 시 |
| `ui/` | 탭 모듈(수집/로드맵/뉴스/보드/SOLA/홈/북마크) · 사이드바 · 작업트리 | UI 변경 시 (해당 `<name>_tab.py` 만 읽기) |
| `config.py` | `.env` 로딩 · LLM 백엔드 라우팅 · 데이터 경로 상수 | 환경/백엔드/경로 작업 시 |
| `assets/styles.css` | 전역 CSS 토큰·컴포넌트 스타일 | CSS 수정 시에만 |
| `docs/INVARIANTS.md` | state/위젯 불변식 | state·widget·세션키 작업 시에만 |
| `docs/ARCHITECTURE.md` | 모듈 경계·데이터 플로우 | 아키텍처 이해 필요 시에만 |
| `docs/WORKFLOW.md` | 멀티에이전트 워크플로 | 에이전트 협업 시에만 |
| `docs/SESSIONS.md` | 세션 로그 | 이전 세션 복원 시 (상단 1개만) |
| `CHANGELOG.md` | 릴리스 이력 | 릴리스/버전 작업 시에만 |

## 3. 라우팅 표

| 작업 | 읽을 파일 (이것만) |
|---|---|
| 스크래퍼 셀렉터·HTTP 버그 | `scraping/<source>.py` (+ `scraping/http.py`) |
| 새 사이트 추가 (도메인 휴리스틱) | `scraping/tech_sites.py` |
| 본문 enrich / 키워드·요약 | `scraping/enrich.py` |
| 로드맵 엑셀 스키마/적재 | `roadmap/{schema,ingest,query}.py` |
| 뉴스↔작업 매칭 | `store/match.py` |
| 자동화 기회 매트릭스 | `sola/opportunity.py` |
| 트렌드·캐시·북마크·채팅 영구화 | `store/{trends,cache,bookmarks,chat_log}.py` |
| LLM 호출·프롬프트 | `sola/client.py` + `sola/prompts.py` |
| 요약·제안서·채팅 컨텍스트·인사이트 | `sola/{summarize,propose,chat_ctx,insight}.py` |
| 페르소나 | `persona/{schema,store,context}.py` |
| UI 탭 변경 | `ui/<name>_tab.py` |
| 사이드바·작업 트리 | `ui/sidebar.py`, `ui/task_tree.py` |
| 영역/탭/세션 상태 | `app.py` + `docs/INVARIANTS.md` |
| CSS만 수정 | `ui/styles.py`, `assets/styles.css` |
| 아키텍처 파악 | `docs/ARCHITECTURE.md` |
| 이전 세션 복원 | `docs/SESSIONS.md` (상단 1개) |
| 릴리스/버전 | `CHANGELOG.md` |
| 단순 문답 | **CLAUDE.md 만으로 충분** |

## 4. 불변 규칙 요약

자세한 내용: [`docs/INVARIANTS.md`](./docs/INVARIANTS.md)

- **I-1** 스크래핑 결과 쓰기는 `_search_pending` 플래그로 다음 run 최상단에서만.
- **I-2** 위젯 state 쓰기는 최상단 pending-flag 핸들러에서만.
- **I-3** `on_click=` 금지. `if st.button():` + `_do_*` 플래그 + `st.rerun()`.
- **I-4** `app.py`는 평탄 스크립트. 마크업/state 헬퍼는 `ui/*_tab.py`로 이전.
- **I-5** 스크래핑 결과는 도메인 필터 통과 후에만 state에 저장.
- **I-6** 외부 HTTP는 항상 `scraping.http.build_session()` 사용.
- **I-7** 본문 enrich는 `scraping.enrich.enrich_articles` 진입점만 사용.
- **I-8** HTML을 세션에 넣거나 `unsafe_allow_html=True`로 렌더 시 `html.escape()` 필수.
- **I-9** 네임스페이스: 수집 `sc_`, 로드맵 `rm_`, 보드 `ins_`, SOLA `sola_`, pending은 `_` prefix.
- **I-10** LLM 호출은 `sola.client.chat()` 단일 진입점, 프롬프트는 `sola/prompts.py` 상수만 사용.

## 5. 브랜치 전략

- **`main`**: 안정 코드만. 직접 push 금지. 머지만 허용.
- **작업 브랜치**: 수정 요청마다 최신 `main`에서 별도 브랜치를 만든다. 이미 PR을 만든 브랜치를 다음 작업에 재사용하지 않는다.
- **PR 올리기 전**: 가능한 환경에서는 `git fetch` 후 최신 `main`에 rebase/merge해 충돌을 먼저 확인한다.
- **고충돌 파일**: `CHANGELOG.md`, `docs/SESSIONS.md`는 여러 PR이 상단을 동시에 수정하므로 `.gitattributes`에서 `merge=union`을 적용한다. 충돌은 줄어들지만 머지 후 중복/순서는 리뷰어가 확인한다.
- **네이밍**: `<카테고리>-<설명>` (슬래시 금지, 하이픈 구분)
  - `fix-scraper-selector`
  - `feat-insight-trend`
  - `feat-cardnews-export`
  - `style-unify-cards`
  - `refactor-session-keys`
  - `docs-invariants`

## 6. 검증 (커밋 전 필수)

```bash
# 스테이지된 .py 만 compile (CI 가 모든 .py 를 자동 검사)
python -m py_compile $(git diff --name-only --cached | grep '\.py$')

grep -rnE 'on_click\s*=' app.py ui/                                # 0
grep -rnE 'requests\.(get|post|Session)\(' \
     app.py ui/ sola/ store/ roadmap/ persona/ scraping/ \
     | grep -v 'scraping/http\.py:'                                # 0

pytest -q
```

> `.github/workflows/ci.yml` 이 PR 마다 동일 검증을 자동 실행한다.

## 7. 변경 시 갱신

작업 브랜치의 같은 커밋에서 다음을 함께 업데이트:

1. `CHANGELOG.md` [Unreleased] 섹션에 엔트리 추가
2. `docs/SESSIONS.md` 상단에 세션 항목 추가
3. 새로운 invariant 발생 시 → `docs/INVARIANTS.md`에 추가

## 8. 스택

- **Streamlit** ≥ 1.32 · `app.py` 단일 평탄 스크립트 + `ui/` 탭 모듈
- **BeautifulSoup4 + lxml** (fallback: `html.parser`) · `scraping/`
- **Pandas + PyArrow** · 뉴스/로드맵 Parquet (`store/`, `roadmap/`)
- **openpyxl** · 로드맵 엑셀 적재 (`roadmap/ingest.py`)
- **OpenAI SDK ≥ 1.40** · `LLM_BACKEND` 스위치 (`sola/client.py`) — Groq / 사내 / Ollama
- **python-dotenv** · `.env` 자동 로드 (`config.py`)
- **`assets/styles.css`** · Noto Serif KR · IBM Plex Sans KR
- **배포**: Streamlit Cloud → `main` 브랜치 추적
