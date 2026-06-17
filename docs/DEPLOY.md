# 배포 가이드 — 프런트(Vercel) + 백엔드(Render/Railway)

React 프런트는 Vercel, FastAPI 백엔드는 상시 호스팅(영구 디스크)로 분리한다.
서버리스(Vercel Python)는 저장소가 휘발되고 수집(scraping)이 무거워 백엔드엔 부적합.

## 1. 백엔드 — Render (Docker, 무료 플랜 기본)

1. [render.com](https://render.com) → **New → Blueprint** → 이 repo 선택 → `render.yaml` 자동 인식.
2. 환경변수(대시보드에서 입력):
   - `INSIGHTBOARD_CORS_ORIGINS` = Vercel 프런트 도메인 (예: `https://insight-board-react.vercel.app`). 여러 개면 쉼표.
   - `LLM_PROVIDER` = `anthropic` 또는 `openai`
   - `LLM_API_KEY` = (키)
   - `LLM_MODEL` = 예) `claude-sonnet-4-6`
   - `INSIGHTBOARD_DATA_ROOT` = `/app/data` (render.yaml 기본 — 무료 플랜·휘발)
3. Deploy 후 `https://<service>.onrender.com/api/health` 가 `{"status":"ok"}` 면 정상.

> **무료(Free) vs 유료 플랜**: `render.yaml` 기본은 **무료 플랜**(`plan: free`, 영구 디스크 없음)이라
> 카드 등록 없이 띄울 수 있다. 단 ① 15분 미사용 시 슬립(첫 요청 지연) ② **데이터가 재배포·슬립마다
> 초기화**(뉴스/작업정의/북마크 휘발 → 수집 재실행)된다 → 검증·데모용. **데이터 영구 보존**이 필요하면
> `render.yaml` 의 주석 처리된 `disk:` 블록을 살리고 `INSIGHTBOARD_DATA_ROOT` 를 `/data` 로 되돌린 뒤
> **유료 인스턴스**(디스크는 유료 전용)로 배포한다.

### Railway / Fly (대안)
- **Railway**: repo 연결 → Dockerfile 자동 사용(또는 `Procfile`). `RAILWAY_VOLUME` 마운트로 `/data` 영구화. 같은 env 설정.
- **Fly.io**: `fly launch` (Dockerfile 감지) + `fly volumes create data` → `/data` 마운트.

> 데이터 영구화: `INSIGHTBOARD_DATA_ROOT` 가 가리키는 경로에 디스크를 마운트해야 뉴스·작업정의·북마크가 보존된다. 미마운트 시 재배포마다 초기화.

## 2. 프런트 — Vercel

1. Project Root = `web` (Vite 자동 감지).
2. 환경변수 **`VITE_API_BASE`** = 백엔드 URL (예: `https://insightboard-api.onrender.com`). 빌드타임 변수이므로 설정 후 **재배포**.
3. 백엔드 `INSIGHTBOARD_CORS_ORIGINS` 에 이 Vercel 도메인이 포함돼 있어야 CORS 통과.

## 3. 연결 확인

- 프런트 접속 → 네트워크 탭에서 `/api/*` 요청이 백엔드 URL로 200.
- 보드/인사이트에 데이터가 차오르면 성공(없으면 백엔드에서 수집 1회 실행).

## 4. 로컬 개발

```bash
uvicorn api.main:app --reload --port 8000          # 백엔드
cd web && npm run dev                                # 프런트(:5173, /api→:8000 프록시)
```

## 참고 — 의존성
- 백엔드 이미지: `requirements-api.txt`(streamlit 제외, scraping 포함).
- Vercel 함수(선택): `api/requirements.txt`(경량, scraping 제외).
