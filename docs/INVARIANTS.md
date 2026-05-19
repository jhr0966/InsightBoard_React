# INVARIANTS — 깨뜨리면 버그가 나는 규칙

> Streamlit 재실행 모델과 스크래핑 계층에서 반복 발견된 함정들.
> 새로운 버그/해결책이 나오면 여기에 I-N으로 추가한다.

## 기본 원칙

Streamlit은 위→아래로 스크립트를 매번 재실행한다. 위젯을 생성한 **후**에 해당 위젯의 state key를 쓰면 `StreamlitAPIException` 또는 silent desync가 난다. 따라서 **모든 state 쓰기는 run 최상단**, 위젯 인스턴스화 이전에 끝내야 한다.

---

## I-1 — 스크래핑 결과는 pending flag 경유

검색 버튼 핸들러에서 직접 `st.session_state.sc_articles = [...]` 하지 마라. 이미 한 번 렌더된 위젯의 state가 덮어써지면서 값이 튕긴다.

**✅ 올바른 패턴**
```python
# 최상단
if st.session_state.get("_search_pending"):
    kw = st.session_state["_search_pending"]
    st.session_state.sc_articles = scraper.search_naver_news(kw)
    del st.session_state["_search_pending"]

# 나중에 (버튼)
if st.button("검색"):
    st.session_state["_search_pending"] = st.session_state.sc_keyword
    st.rerun()
```

## I-2 — 위젯 state 쓰기는 최상단 pending-flag 핸들러에서만

`text_input`, `selectbox` 등의 `key=`로 묶인 state는 위젯이 렌더된 뒤에는 쓸 수 없다. 쓰고 싶다면 pending flag로 다음 run의 최상단에 처리.

## I-3 — `on_click=` 금지

콜백은 Streamlit 내부적으로 state 쓰기 타이밍이 불투명하다. 반드시:
```python
if st.button("액션", key="sc_btn_search"):
    st.session_state["_do_search"] = True
    st.rerun()
```

## I-4 — `app.py`는 평탄 스크립트

카드/배지/템플릿 등 **마크업 생성** 헬퍼는 `cardnews.py`나 `components/`로. `app.py` 내부에 `render_*` 이름 헬퍼를 두면 숨은 state 변이와 조건 분기가 섞여 추적 불가.

유일한 예외: `_show_debug()`처럼 **state를 읽기만** 하고 출력하는 순수 함수.

## I-5 — 도메인 필터 통과 후에만 state에 저장

`fetch_latest_tech_news`의 결과에 다른 도메인(예: 구글 광고 리다이렉트) URL이 섞이면 enrich 단계에서 외부 사이트로 대량 요청이 나간다. `_same_root_domain` + `_is_plausible_article_link`를 통과한 결과만 `sc_articles`에 저장한다.

## I-6 — 외부 HTTP는 `_build_session()` 경유

- 재시도·백오프 정책이 한 곳에 모여 있어야 변경이 쉽다.
- UA 로테이션과 타임아웃도 마찬가지.
- 새 코드에서 `requests.get(...)` 직접 호출은 리뷰에서 거부.

## I-7 — 본문 enrich는 `enrich_articles_parallel`만

개별 기사 본문을 fetch하는 로직이 여러 곳에 퍼지면 병렬도·캐시·예외 처리가 엇갈린다. 단일 진입점만 사용.

## I-8 — HTML 출력 전 `html.escape()`

세션에 넣는 title/press/summary는 이미 scraper에서 escape된다는 가정이지만, **새 필드를 추가할 때**는 항상 escape를 확인. `st.markdown(..., unsafe_allow_html=True)`로 나가는 조각에 raw 문자열 삽입 금지.

## I-9 — 네임스페이스 prefix

| prefix | 의미 |
|---|---|
| `sc_*` | 스크래핑 state (e.g. `sc_articles`, `sc_keyword`, `sc_debug`) |
| `ins_*` | 인사이트 state (e.g. `ins_selected_press`, `ins_date_range`) |
| `cn_*` | 카드뉴스 state (e.g. `cn_selected_article`, `cn_template`) |
| `_*_pending` | 다음 run 최상단에서 처리할 이벤트 |
| `_do_*` | 버튼 클릭 플래그 |

다른 도메인의 state를 직접 읽/쓰지 마라 (예: insights가 `sc_articles`를 복사해 `ins_df`로 파생시키는 것은 OK, 원본을 수정하는 것은 금지).

## I-10 — 카드뉴스 이미지 합성은 `cardnews.render_png()` 단일 진입점

- Pillow 로드, 폰트 경로, 여백 상수는 `cardnews.py` 상단에 한 번만.
- 다른 곳에서 `PIL.ImageDraw`를 import해 직접 합성하면 폰트 경로 오차로 서버/로컬 불일치 발생.

## I-11 — DataFrame 컬럼 고정

`articles_to_dataframe`이 반환하는 컬럼 순서는 CSV/엑셀 export 스키마와 동일해야 한다. 컬럼 추가 시:

1. `scraper.articles_to_dataframe` 수정
2. `app.py`의 `_table_column_config` 동기화
3. `CHANGELOG.md`에 schema change 명시

## I-12 — 레거시 예외 (마이그레이션 전까지 유지)

아래는 현행 코드에 남아 있는 규칙 위반이지만, **개별 브랜치에서 이관하기 전에는 건드리지 않는다** (한 번에 대규모 리팩터링 금지).

### L-1. `app.py` 세션 키 prefix 미적용
현행:
```
articles_naver, articles_tech, keyword_naver, debug_log
```
I-9 요구: `sc_*` prefix. → **신규 state 키는 반드시 prefix 적용.** 기존 4개는 `refactor-session-keys` 브랜치에서 일괄 rename 예정.

### L-2. `app.py` 내 `render_cards_html`, `render_results` 함수
I-4(`app.py`는 평탄 스크립트, 마크업 헬퍼 금지) 위반. 하지만 스크래퍼 탭의 카드/테이블 렌더가 이 두 함수에 의존. → **`feat-cardnews-migrate` 브랜치에서 `cardnews.render_html`/`cardnews.render_deck` 로 이관 예정.** 이관 전에는 두 함수를 그대로 호출해도 된다. **단, 새 render_* 함수 추가는 금지.**

### L-3. CSS 인라인 vs `assets/styles.css` 이중화
현행 `app.py` 상단 `st.markdown("<style>...")` 블록이 아직 살아 있다. `assets/styles.css` 는 `.cn-*` / `.ins-*` 신규 네임스페이스만 담당. → **CSS 수정 작업은 라우팅 표의 "CSS만 수정" 항목을 참조하되, 기존 `.news-*` / `.card-*` 토큰은 app.py 상단에서 고친다.** 전체 이관은 `refactor-css-extract` 브랜치.

### 검증에서 예외 처리

커밋 전 체크의 `grep -nE '^def render_' app.py` 는 현재 2건이 정상. 새로 추가되면 안 되므로 **증가 여부**만 감시한다.



## I-13 — 사이드 채팅 패널은 `main_and_chat` 단일 진입점

`ui/layout.py::main_and_chat(chat_key, ...)` 가 우측 채팅 패널의 표준 컨텍스트 매니저. 새 탭 추가 시 동일 패턴으로 호출.

- **금지**: 메인 영역에 별도 `st.chat_input` / `st.chat_message` 로 LLM 채팅 UI 를 다시 만들기. (Phase 4 에서 `sola_tab._render_chat` 제거로 일관성 확보 — `ui/proposal_workbench` 의 모드 채팅은 좌측 MD 와 1:1 매칭되는 작업장 전용 패턴으로 예외)
- **chat_key 네임스페이스**: 페이지마다 고유 문자열. session_state 키(`_chat_open_{key}`, `_sidechat_{key}`, …)와 영구화 파일(`data/sola/chat/{key}.jsonl`)이 이 키로 분리됨.
- **default_open**: `True` 가 디폴트. 사용자 선호는 `session_state[_chat_open_{key}]` 에 저장되어 페이지마다 독립적으로 보존.

## I-14 — LLM 설정은 `config._env_or_secret()` 경유

`LLM_BACKEND` / `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` 4개 모두 `_env_or_secret(name, default)` 를 통해 읽는다. 우선순위:

1. OS 환경변수 (`.env` 파일 포함, `python-dotenv` 자동 로드)
2. `st.secrets` (Streamlit Cloud 배포 시 App settings → Secrets)
3. 디폴트 (Groq 기준)

`os.getenv` 를 직접 새로 추가하지 말 것. 또한 `.env` 파일은 **절대 commit 금지** (`.gitignore` 에 등록되어 있음).

## I-15 — `chat_log` 는 `chat_key` 별 파일

`store.chat_log.{save_history,load_history,reset}` 가 모두 `chat_key` 인자를 받는다. 인자 생략 시 `default` 로 매핑되어 기존 `data/sola/chat_history.jsonl` 경로 유지 (후방 호환). 새 `chat_key` 는 `data/sola/chat/{slug}.jsonl` 에 저장되며 `_safe_key()` 가 파일명 슬러그를 강제 (디렉토리 traversal 차단).
