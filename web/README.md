# InsightBoard Web (React)

FastAPI(`api/`) 계약을 소비하는 React 프런트엔드. `REACT_MIGRATION_PLAN §4`.

## 스택
- Vite + React 18 + TypeScript
- React Router (5 라우트: `/`, `/insights`, `/proposals`, `/collect`, `/taskdefs`)
- TanStack Query (서버 데이터 — `REACT_PREP_INVENTORY` (S) 분류)
- 디자인 토큰 `src/styles/tokens.css` = `assets/v2/tokens.css` 승계

## 구조
```
src/
  api/client.ts     타입드 fetch + SSE 스트림(streamChat)
  api/types.ts      api/schemas.py 미러 타입
  components/
    Layout.tsx          좌 nav · 중앙 본문 · 우 어시스턴트 드로어
    AssistantDrawer.tsx SSE 챗(/api/assistant/chat) + 화면 컨텍스트 주입
  pages/            Board · Insights · Proposals · Collect · TaskDefs
```

## 개발
```bash
# 1) 백엔드 (repo 루트)
uvicorn api.main:app --reload --port 8000
# 2) 프런트 (web/)
npm install
npm run dev          # http://localhost:5173, /api → :8000 프록시(vite.config.ts)
```

## 빌드 / 검증
```bash
npm run typecheck    # tsc --noEmit
npm run build        # tsc + vite build → dist/
```

## API 타입 재생성 (계약 드리프트 방지)
`src/api/schema.ts` 는 OpenAPI 에서 자동생성, `types.ts` 가 그 모델을 alias.
계약(api/) 변경 시:
```bash
python scripts/gen_openapi.py   # web/openapi.json 갱신(repo 루트)
cd web && npm run gen:types     # schema.ts 재생성
```
`tests/test_openapi_snapshot.py` 가 `openapi.json` 과 현재 계약의 일치를 강제(어긋나면 pytest 실패).

## 환경변수 (`.env`, `.env.example` 참고)
- `VITE_API_TARGET` — dev 프록시 타깃(기본 `http://localhost:8000`)
- `VITE_API_BASE` — 프로덕션 절대 API base(비우면 동일 출처 `/api`)

## Vercel 배포

두 가지 모드. 둘 다 LLM 키 등은 Vercel 대시보드 환경변수로 설정(`LLM_PROVIDER`, `LLM_API_KEY`, `LLM_MODEL`, `LLM_BASE_URL`).

### A. 풀스택 (프런트 + API 한 프로젝트) — repo 루트 기준
- 루트 `vercel.json` 이 web 정적 빌드 + `api/index.py`(FastAPI ASGI) 서버리스 함수 + `/api/*` 라우팅을 구성.
- `api/requirements.txt`(경량) 로 함수 의존성만 설치, `.vercelignore` 로 streamlit/scraping/data 제외.
- **서버리스 제약**: 파일시스템 읽기전용 → `INSIGHTBOARD_DATA_ROOT=/tmp/data`(vercel.json env). `/tmp` 는 호출 간 휘발 → 영구 저장은 Phase 2(Postgres). 데모/읽기 위주.
- Project Root = repo 루트로 import 후 그대로 Deploy.

### B. 프런트엔드만 (API 는 별도 호스팅)
- Project Root = `web/`. `web/vercel.json` 이 SPA rewrite 처리.
- 빌드 환경변수 `VITE_API_BASE = https://<백엔드-도메인>` 로 API 위치 지정(비우면 동일 출처 `/api`).

## 남은 일
- 화면 데이터 패리티(보드 다이제스트·기회 매트릭스·작업정의 업로드 폼)
- openapi-typescript 로 `types.ts` 자동 생성
- 폰트(`public/fonts/`) · 칸반·모달 등 컴포넌트 확장
