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

## 환경변수 (`.env`, `.env.example` 참고)
- `VITE_API_TARGET` — dev 프록시 타깃(기본 `http://localhost:8000`)
- `VITE_API_BASE` — 프로덕션 절대 API base(비우면 동일 출처 `/api`)

## 남은 일
- 화면 데이터 패리티(보드 다이제스트·기회 매트릭스·작업정의 업로드 폼)
- openapi-typescript 로 `types.ts` 자동 생성
- 폰트(`public/fonts/`) · 칸반·모달 등 컴포넌트 확장
