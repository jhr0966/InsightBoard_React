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



## I-13 — 글로벌 채팅 패널은 `ui/chat_panel.py` 단일 진입점 (Phase A: 우측 컬럼)

v2 셸의 레이아웃은 **`app.py` 가 소유**한다: 좌측 네이티브 `st.sidebar`(nav) + `st.columns([2.3, 1])` 의 메인/채팅 2-컬럼. 우측 채팅 컬럼은 `ui/chat_panel.render_side(persona, area_key=...)` 단 한 곳에서 마운트한다. 어느 area 에서든 사용자가 채팅 form 으로 전송한 텍스트는 render 직전 `chat_panel.consume_send_if_any(persona)` 가 단일 처리한다.

- **app.py 규약**: 5개 area **전부(SOLA 작업실 포함)** 를 `with main_col:` 안에서 렌더하고, `with chat_col:` 안에서 `chat_panel.render_side(_persona, area_key=...)` 호출 — 모든 화면이 동일한 `[좌 사이드바 │ 중앙 │ 우 채팅]`. 작업실 중앙은 산출물 작업대(스레드 + composer), 우측은 글로벌 채팅(통일 설계). *(작업실에서 우측 채팅을 억제하려면 코드 변경 필요 — 현재는 의도적으로 미억제.)*
- **우측 채팅 구현**: `st.chat_input` 은 뷰포트 하단 전폭 고정이라 컬럼에 담기지 않는다 → `render_side` 는 `st.form`(text_area + form_submit_button) 으로 송신하고 `_do_sola_send` pending 을 세팅한다. 컬럼 sticky 패널화는 `.side-chat-marker` 훅 + `streamlit-overrides.css` 의 `[data-testid="stColumn"]:has(.side-chat-marker)`.
- **금지**: 화면별 고정 HTML 우측 패널(구 `app_shell.render_app_sola` 의 disabled 목업)을 부활시키지 말 것. 우측 LLM 채팅은 `render_side` 단일 경로(**모든 area 동일** — 작업실 예외 없음).
- **area_key 네임스페이스**: area 슬러그(이모지 포함)가 chat_key 로 사용된다. `store.chat_log` 가 `_safe_key()` 로 슬러그를 강제해 `data/sola/chat/{slug}.jsonl` 분리 저장 (I-15).
- **컨텍스트 핸드오프**: 각 area 의 `chat_context_block(persona)` 결과가 `session_state["_chat_context_for_sola"]` 에 저장돼 다음 send 에서 사용된다.
- **데드 정리 완료 (Phase 3)**: 좌측은 네이티브 `st.sidebar`, 우측 LLM 채팅은 `chat_panel.render_side` 단일 경로. 구 고정 HTML 패널 `app_shell.render_app_side`/`render_app_sola`(no-op)·패널 토글 클러스터·`chat_panel.render`(구 bottom expander)·`ui/layout.py`·`ui/task_tree.py`·`sola/{insight,chat_ctx}.py`·`task_defs_db.upsert_many` 모두 삭제됨.

## I-14 — LLM 설정은 `config._env_or_secret()` 경유

`LLM_BACKEND` / `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` 4개 모두 `_env_or_secret(name, default)` 를 통해 읽는다. 우선순위:

1. OS 환경변수 (`.env` 파일 포함, `python-dotenv` 자동 로드)
2. `st.secrets` (Streamlit Cloud 배포 시 App settings → Secrets)
3. 디폴트 (Groq 기준)

`os.getenv` 를 직접 새로 추가하지 말 것. 또한 `.env` 파일은 **절대 commit 금지** (`.gitignore` 에 등록되어 있음).

## I-15 — `chat_log` 는 `chat_key` 별 파일

`store.chat_log.{save_history,load_history,reset}` 가 모두 `chat_key` 인자를 받는다. 인자 생략 시 `default` 로 매핑되어 기존 `data/sola/chat_history.jsonl` 경로 유지 (후방 호환). 새 `chat_key` 는 `data/sola/chat/{slug}.jsonl` 에 저장되며 `_safe_key()` 가 파일명 슬러그를 강제 (디렉토리 traversal 차단).

## I-16 — v2 화면 인계 URL 패턴 `?app_area=...&from=<kind>&dept=&lv3=`

보드/인사이트의 카드 CTA 는 모두 `ui/board_v2._sola_handoff_href(from_kind, **payload)` 한 줄로 만든다. SOLA 작업실은 `?from` 값을 보고 composer prefill 과 handoff banner 를 동시 결정.

- **단일 진입점**: `_sola_handoff_href` (board_v2) / `_edit_handoff_href` (archive_v2) 외 직접 `?app_area=...` 문자열 조립 금지. payload 자동 quote.
- **지원 from kind**: `brief` (보드 ② SOLA 브리핑), `opp` (보드 ④ 자동화 기회), `matrix` (보드 ⑥ 매트릭스 detail), `ia_map` (인사이트 공정 매핑), `edit` (산출물 보관함 카드 "수정" → `bm_id`+`title` 전달).
- **brief 만 session_state**: 3건 뉴스 제목 리스트는 `st.session_state["_board_brief_items"]` 에 저장 (URL 길이 제한 회피). 보드 진입마다 갱신/삭제.
- **opp/matrix/ia_map/edit**: 모두 stateless — URL 만으로 prefill 재현 가능.
- **1회-소비 액션 패턴**: 산출물 보관함 `?action=adopt|reject|restore&bm_id=...` (`_consume_action_if_any` → `bookmarks_store.set_status` → 캐시 invalidate → query strip) + 데이터관리 `?refresh=now` (`_consume_refresh_if_any` → 캐시 clear → toast flag). 둘 다 render 첫 단계에서 소비 후 query 제거 → 새로고침/재방문 시 재실행 방지.

## I-17 — v2 sticky banner stacking 규칙

`.app-llm-banner` (LLM 미설정 안내) 와 `.ws-brief-handoff` (SOLA 인계) 가 동시 노출되면 둘 다 `position: sticky` 라 stacking 됨. 다음 분기 규칙으로 위치 결정:

- 단독 LLM: `top: 76px`
- 단독 handoff: `top: 76px`
- 둘 다 노출: handoff 가 `top: 132px` (LLM 56px + margin)
  - CSS 분기: `body:has(.app-llm-banner) .ws-brief-handoff { top: 132px; }`

새 sticky 안내 배너 추가 시 동일 패턴으로 `body:has(...)` 조건부 offset 누적.

## I-18 — v2 매트릭스 dept 색상은 `board_v2.MATRIX_DEPT_COLORS` 공유

보드 ⑥ + 인사이트 SECTION B 매트릭스가 같은 dept 색을 쓰도록 단일 dict (`MATRIX_DEPT_COLORS` + `MATRIX_DEPT_FALLBACK`) 공유. 새 dept 추가는 한 곳만 갱신. 두 매트릭스의 시각 일관성 보장.

## I-19 — v2 CTA `<button disabled>` → `<a href>` 전환 시 CSS 회복 필수

`<a>` 는 기본 `text-decoration: underline` + `color: blue/purple (visited)`. `.db-prop-discuss` / `.db-mx-cta` / `.db-act{-primary}` / `.ia-pc-detail` 처럼 button 전제 CSS 를 a 에도 적용할 때:

```css
.foo { text-decoration: none; }
.foo:hover { text-decoration: none; }
a.foo, a.foo:visited { color: <원래색>; }
```

세 가지 모두 빠지면 미세한 시각 회귀 (밑줄/자주색 visited) 발생.
