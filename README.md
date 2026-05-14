# News

조선소 작업 정의를 이해하는 LLM 어시스턴트가 외부 기술 동향을 우리 작업에 어떻게 적용할지 번역해주는 Streamlit 시스템. 3대 축:

1. **🔍 수집·enrich** (`scraping/`) — 네이버 / 구글 RSS / AI Times / 오토메이션월드, 본문 fetch + LLM 키워드·요약.
2. **🗂 로드맵·매칭** (`roadmap/`, `store/`) — 조선소 작업 정의 엑셀 → Parquet, 룰 기반 뉴스↔작업 매칭, 자동화 기회 매트릭스.
3. **🤖 SOLA LLM** (`sola/`, `persona/`) — 요약·제안서·채팅·부서 인사이트, 페르소나 자동 주입.

UI 는 업무 흐름형 5개 메뉴(`오늘의 보드 · 데이터 관리 · 인사이트 분석 · SOLA 작업실 · 산출물 보관함`) + `ui/<name>_tab.py` 모듈로 분리.

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

`tests/` 아래 단위 테스트 60+건이 LLM 호출·HTTP·디스크 IO 를 모킹해 빠르게 돕니다.
