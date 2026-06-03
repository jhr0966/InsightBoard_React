# News

조선소 작업 정의를 이해하는 LLM 어시스턴트가 외부 기술 동향을 우리 작업에 어떻게 적용할지 번역해주는 Streamlit 시스템. 3대 축:

1. **🔍 수집·enrich** (`scraping/`) — 네이버 / 구글 RSS / AI Times / 오토메이션월드, 본문 fetch + LLM 키워드·요약.
2. **🗂 로드맵·매칭** (`roadmap/`, `store/`) — 조선소 작업 정의 엑셀 → Parquet, 룰 기반 뉴스↔작업 매칭, 자동화 기회 매트릭스.
3. **🤖 SOLA LLM** (`sola/`, `persona/`) — 요약·제안서·채팅·부서 인사이트, 페르소나 자동 주입.

UI 는 업무 흐름형 5개 메뉴(`오늘의 보드 · 데이터 관리 · 인사이트 분석 · SOLA 작업실 · 산출물 보관함`) — **v2 디자인 시스템** 적용. 레이아웃은 `app.py` 가 소유 — 좌측 네이티브 `st.sidebar`(nav 단일 소스) + 본문 상단 in-flow 헤더(`app_shell.render_topbar`) + `st.columns([2.3, 1])`(중앙 콘텐츠 + 우측 SOLA 채팅 `chat_panel.render_side`, 모든 화면 동일). 각 화면 본문은 `ui/<name>_v2.py` 가 `assets/v2/screens/<name>_main.html` 템플릿에 실데이터를 치환해 그린다. 화면 간 인계는 `?app_area=...&from=<kind>` URL 패턴 단일 진입점(`docs/INVARIANTS.md` I-16). 디자인 토큰은 `assets/v2/*.css`, 라이트/다크 테마는 `ui/styles.py`.

## 🚀 빠른 시작 (Groq 무료 API)

LLM 백엔드 기본값은 [Groq](https://groq.com/) (무료 티어, `llama-3.3-70b-versatile`)이라 키 1개만 있으면 즉시 사용 가능.

```bash
# 1) 의존성 설치
pip install -r requirements.txt

# 2) Groq API 키 발급 후 .env 작성
#    https://console.groq.com/keys → "Create API Key" → 복사
cp .env.example .env
# .env 파일을 열어 LLM_API_KEY=gsk_xxxxx... 한 줄만 채우면 OK

# 3) 실행
streamlit run app.py
```

사이드바 하단의 LLM 상태가 🟢로 바뀌면 키가 정상 인식된 것. 🟠면 `.env`의 `LLM_API_KEY`를 다시 확인.
다른 백엔드(사내 OpenAI 호환 / 로컬 Ollama) 로 전환하려면 `.env.example`의 `LLM_BACKEND` / `LLM_BASE_URL` / `LLM_MODEL` 주석 참고.

## ☁️ Streamlit Community Cloud 배포 (`share.streamlit.io`)

`.env` 파일은 **절대 GitHub 에 올리지 말 것**. 클라우드는 별도 Secrets 관리 메커니즘을 쓴다.

1. GitHub 에 코드 푸시 (private 레포 가능). `.env` 가 추적되어 있으면 먼저 `git rm --cached .env && git commit && git push` 로 제거.
2. https://share.streamlit.io → **New app** → 본인 레포 / 브랜치 / `app.py` 선택.
3. **Advanced settings → Secrets** 에 TOML 형식으로 입력:

   ```toml
   LLM_BACKEND = "groq"
   LLM_API_KEY = "gsk_xxxxxxxxxxxxxxxxxxxxxxxxxx"
   # 디폴트와 다르게 쓰려면 아래도 추가
   # LLM_BASE_URL = "https://api.groq.com/openai/v1"
   # LLM_MODEL = "llama-3.3-70b-versatile"
   ```
4. **Deploy**. `config.py` 가 환경변수를 먼저 확인하고 없으면 자동으로 `st.secrets` 를 fallback 으로 사용 (`_env_or_secret()`). 별도 코드 수정 불필요.

배포 후 사이드바 하단 LLM 상태가 🟢 로 바뀌면 키 인식 OK.

> ⚠️ 만약 `.env` 가 이미 커밋되어 키가 git history 에 남았다면 **Groq Console → 해당 키 Delete → 새 키 발급** 후 위 Secrets 에 새 키 입력. 히스토리 정리는 `git filter-repo --path .env --invert-paths` 후 force push.

## 실행

```bash
pip install -r requirements.txt
cp .env.example .env       # LLM_API_KEY=... 채우기 (LLM 기능을 쓰려면 필수)
streamlit run app.py
```

- Python ≥ 3.10
- `lxml` 설치 실패 시 `html.parser` 로 자동 fallback.
- LLM 미설정 상태에서도 수집·로드맵·매트릭스 표시는 정상 동작하며, LLM 결과만 graceful degrade.


## 빠른 개발 환경 세팅 (Streamlit)

```bash
./scripts/dev_setup.sh
source .venv/bin/activate
make run
```

또는 수동 설치:

```bash
make install
make run
```

- Streamlit 설정: `.streamlit/config.toml`
- 개발 운영 청사진: `docs/VIBE_CODING_BLUEPRINT.md`

## 개발 문서

| 문서 | 언제 읽나 |
|---|---|
| [`CLAUDE.md`](./CLAUDE.md) | 작업 시작 전 **항상** (단일 참조점) |
| [`DEV_GUIDELINES.md`](./DEV_GUIDELINES.md) | 라우팅 표 · 검증 명령 |
| [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) | 모듈 계약 · article 스키마 |
| [`docs/INVARIANTS.md`](./docs/INVARIANTS.md) | state/위젯 불변식 |
| [`docs/WORKFLOW.md`](./docs/WORKFLOW.md) | 브랜치 → 커밋 → 머지 루프 |
| [`docs/SESSIONS.md`](./docs/SESSIONS.md) | 이전 세션 복원 (상단 1개만) |
| [`CHANGELOG.md`](./CHANGELOG.md) | 릴리스 이력 |
| [`docs/VIBE_CODING_BLUEPRINT.md`](./docs/VIBE_CODING_BLUEPRINT.md) | 제품/아키텍처/개발전략 청사진 |
| [`docs/UX_REDESIGN_PLAN.md`](./docs/UX_REDESIGN_PLAN.md) | 인사이트보드 UI/UX 전면 개편 계획 |
| [`docs/DEVELOPMENT_PHASES.md`](./docs/DEVELOPMENT_PHASES.md) | Streamlit + Local First 단계별 실행 계획 |

## 배포

Streamlit Cloud 가 `main` 브랜치를 트래킹 — **`main` 머지 = 즉시 배포**.
작업은 반드시 브랜치에서:

```bash
git checkout -b <category>-<slug>    # fix|feat|refactor|style|docs|chore
```

## 커밋 전 검증

```bash
# 스테이지된 .py 만 compile (CI 가 모든 .py 를 자동 검사)
python -m py_compile $(git diff --name-only --cached | grep '\.py$')

grep -rnE 'on_click\s*=' app.py ui/                                # 0
grep -rnE 'requests\.(get|post|Session)\(' \
     app.py ui/ sola/ store/ roadmap/ persona/ scraping/ \
     | grep -v 'scraping/http\.py:'                                # 0

pytest -q
```

> `.github/workflows/ci.yml` 이 PR 마다 동일 검증을 자동 실행합니다.

## 테스트

```bash
pytest -q
```

`tests/` 아래 단위 테스트 **720+건**(69개 파일)이 LLM 호출·HTTP·디스크 IO 를 모킹해 빠르게 돕니다.
