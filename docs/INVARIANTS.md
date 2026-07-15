# INVARIANTS — 깨뜨리면 버그가 나는 규칙

> React(`web/`) + FastAPI(`api/`) 스택의 계층·계약 불변식. 새 함정이 나오면 I-N으로 추가.
> (은퇴한 Streamlit 런타임 불변식은 `docs/archive/INVARIANTS_STREAMLIT.md`.)

---

## I-1 — 계층 분리: 프런트는 `api/` 계약만 소비

React(`web/`)는 도메인 로직을 직접 호출하지 않는다. **유일한 데이터 경로는 `web/src/api/client.ts`(fetch+SSE) → `api/routers/*`** 다. 라우터는 검증·직렬화만 하고 도메인 로직은 `store`/`sola`/`roadmap`/`scraping`/`persona` 에 위임한다. 라우터에 비즈니스 로직을 쌓지 마라.

## I-2 — API 타입 드리프트 가드

`api/` 의 Pydantic 스키마/엔드포인트를 바꾸면 **반드시** 재생성:

```bash
python scripts/gen_openapi.py && cd web && npm run gen:types
```

`web/src/api/schema.ts` 는 openapi-typescript 자동생성물이라 **손으로 고치지 않는다**. `tests/test_openapi_snapshot.py` 가 스냅샷 드리프트를 차단한다. dict 를 그대로 반환하는 엔드포인트(named schema 없음)만 `web/src/api/types.ts` 에 손수 유지.

## I-3 — 외부 HTTP 는 `scraping.http.build_session()` 경유

재시도·백오프·UA 로테이션·타임아웃이 한 곳에 모여야 한다. `api`·`sola`·`store`·`roadmap`·`persona`·`scraping` 어디서도 `requests.get/post/Session()` 직접 호출 금지(예외: `scraping/http.py` 내부). CI 가 grep 으로 검사.

## I-4 — 본문 enrich 는 `scraping.enrich` 단일 진입점

개별 기사 본문 fetch 로직이 여러 곳에 퍼지면 병렬도·캐시·예외 처리가 엇갈린다. `scraping.enrich.enrich_articles_parallel` 만 사용.

## I-5 — LLM 호출은 `sola.client` facade, 프롬프트는 `sola/prompts.py`

- 모든 LLM 호출은 `sola.client.chat(...)` / `chat_stream(...)` 단일 진입점.
- provider 는 `sola/providers/*`(`openai`·`anthropic`), `LLM_PROVIDER` 로 교체. base_url 라우팅은 `LLM_BACKEND`(groq/internal/ollama).
- 인라인 문자열 프롬프트 금지 — `sola/prompts.py` 상수만.

## I-6 — LLM/경로 설정은 `config.*` 헬퍼 경유

`LLM_PROVIDER`·`LLM_BACKEND`·`LLM_API_KEY`·`LLM_BASE_URL`·`LLM_MODEL`·`INSIGHTBOARD_DATA_ROOT`·`INSIGHTBOARD_CORS_ORIGINS` 는 `config.py` 헬퍼로 읽는다. 우선순위: ① OS 환경변수(`.env`, python-dotenv 자동 로드) → ② (과거 streamlit `st.secrets` fallback, 미설치 시 빈 값) → ③ 디폴트(Groq). 라우터·도메인 코드에서 `os.getenv` 직접 추가 금지. `.env` 는 **절대 commit 금지**(`.gitignore`).

## I-7 — 식별·감사 5필드는 `store/_audit.py` 표준

영구화되는 레코드(bookmarks·threads 등)는 `store._audit.stamp/backfill` 로 `user_id·workspace_id·created_by·created_at·updated_at` 를 채운다. 식별 주체는 `api/deps.current_identity`(현재 no-op = Phase 2 인증 교체점) 가 제공. 라우터가 식별 필드를 손으로 조립하지 마라.

## I-8 — 영구화는 `store/repository.py` seam 경유 (Phase 2 교체점)

JSONL 기반 영구화는 `store.repository.get_repository()`(`Repository`·`JsonlRepository`, `INSIGHTBOARD_STORAGE`)를 통한다 — 향후 DB 백엔드 교체점. 직접 파일 경로를 열어 쓰지 말고 repository API 를 쓴다(현재 bookmarks 적용).

## I-9 — `chat_log` 는 `chat_key` 별 파일

`store.chat_log.{save_history,load_history,reset}` 는 모두 `chat_key` 인자를 받는다. 새 키는 `data/sola/chat/{slug}.jsonl` 에 저장되며 `_safe_key()` 가 파일명 슬러그를 강제(디렉토리 traversal 차단). 인자 생략 시 `default` 후방 호환.

## I-10 — XSS: React 기본 escape, `dangerouslySetInnerHTML` 금지

React 는 기본적으로 텍스트를 escape 한다. `dangerouslySetInnerHTML` 사용 금지(불가피하면 sanitize). 백엔드에서 외부 문자열을 HTML 로 합성해 내려보내지 마라(프런트가 데이터로 받아 렌더).

## I-11 — 화면 인계 URL 패턴 `?from=<kind>&dept=&lv3=`

보드/인사이트/매트릭스 카드 → SOLA 드로어 인계는 `?from=` 쿼리 단일 패턴. `web/src/components/Layout.tsx` 가 `?from=` 감지 시 드로어 자동 오픈, `AssistantDrawer` 의 `handoffPrefill(from, dept, lv3)` 이 prefill 을 1회 자동 전송(sessionStorage 시그니처로 중복 차단). 지원 kind: `brief`/`board`·`opp`/`matrix`·`insights`/`ia_map`·`edit`. 새 인계는 이 경로를 재사용.

## I-12 — SSE 프레임 규약 `data: {json}\n\n`

스트리밍 엔드포인트(`/api/assistant/chat`·`/api/collect/stream`)는 `f"data: {json}\n\n"` 프레임을 yield 한다. 프런트는 `fetch` + `res.body.getReader()` 로 `\n\n` 분할 파싱(`streamChat`·`streamCollect`). 새 스트리밍 기능은 동일 프레임/파서 패턴을 따른다(keep-alive ping 포함).

## I-13 — CORS 는 정확 일치

`api/main.py` 의 `allow_origins` 는 `INSIGHTBOARD_CORS_ORIGINS`(프런트 도메인) 와 **정확히** 일치해야 한다(trailing slash 무관용). 프런트 배포 도메인이 바뀌면 백엔드 env 도 갱신.

## I-14 — 뉴스 조회는 결정적 최신순 (`store/news_db.py`)

`load_news_for_days`/`load_all_today`/`load_latest` 의 반환은 **`sort_at` 내림차순 + `link` 오름차순(tie-break)** 이다. `sort_at` 은 저장 컬럼이 아닌 로드 시 파생 컬럼: `published_at` 정규화(UTC ISO8601) → `collected_at` 정규화 → 일자 디렉토리 날짜 폴백. 파싱 실패 행도 목록에서 제거하지 않는다(맨 뒤). 다운스트림(`head(limit)`·`slice(0,N)`)은 이 계약에 의존하므로, **정렬 없이 concat 결과를 반환하거나 정렬 전에 limit 를 적용하는 변경 금지**. 중복 병합(I-15)은 정렬 **전** 로드 순서 기준 — "나중 = 최신 저장본" 전제가 깨지면 enrich 보강본 우선 규칙이 뒤집힌다. 회귀 가드: `tests/test_news_ordering.py`.

## I-15 — 기사 식별은 article_id, 중복은 필드 단위 병합 (`store/article_id.py`·`news_db._merge_duplicates`)

기사 식별자는 **정규화 URL 해시 `article_id`** — 정규화는 추적 파라미터(utm_* 등)만 제거하고 식별 파라미터(articleId·idxno·seq 등)는 유지한다(전체 쿼리 제거 금지 — 다른 기사가 합쳐진다). 원본 `link` 는 변형·유실 금지. 같은 article_id 의 중복 레코드는 행 단위 승자 선택이 아니라 **필드 단위 병합**(게시시각=가장 이른 원본, 본문=가장 풍부, 이미지·LLM=최신)으로 합친다. 식별·병합은 전부 로드 시 파생 — parquet 원본을 재작성하지 않는다. 규칙을 바꾸면 `IDENTITY_VERSION`/`MERGE_VERSION` 을 올려 파생 데이터(article_task_links 등)를 재빌드한다. 회귀 가드: `tests/test_article_identity.py`.

## I-16 — 기사↔작업 매칭은 links 저장본 경유 (`store/links_db.py`)

전체 윈도우(뉴스 N일 × 작업정의)의 매칭 소비(기회 매트릭스·히트맵·matches API·제안서 근거)는 `links_db.matches_for_window()` 를 경유한다 — 화면 요청마다 `score_matches` 를 직접 돌리지 마라(과거 셀 클릭마다 전체 코퍼스 재계산). 예외: 부분 뉴스셋(키워드 필터 등)은 라이브 계산 허용. links 는 **파생 데이터**: 원본은 뉴스 parquet·로드맵이며, `MATCHING_VERSION`/`IDENTITY_VERSION` 이 바뀌면 stale → 자동 재빌드된다(수동 복구 불필요, 관리자 재빌드는 `POST /api/matches/rebuild-links`). 수집 요청 안에서 동기 인덱싱 금지 — 선워밍은 일일 cron 말미가 담당. 회귀 가드: `tests/test_links_db.py`.
