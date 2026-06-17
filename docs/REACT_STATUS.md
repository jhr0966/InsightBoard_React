# REACT_STATUS — React 전환 진행 현황 & 핸드오프 (2026-06-16)

> 대화 압축 후에도 이어갈 수 있도록 현황·결정·다음 단계를 박제. 전체 계획은
> `docs/REACT_PARITY_PLAN.md`, 준비물 카탈로그는 `docs/REACT_PREP_INVENTORY.md`.

## 한 줄 요약
Streamlit 앱(`app.py`·`ui/`)을 **FastAPI(`api/`) + React(`web/`)** 로 전환. 코드 작업
(토대→P0→P1→P2 7화면→P3→P4 호스팅설정)은 **모두 완료·main 머지**(PR #1~#17).
남은 건 **실행**: 백엔드 배포 → 폴리시 → Streamlit 은퇴.

## 완료 (PR #1~#17, main)
- **토대**: `store/_audit.py`(식별·감사 5필드), `sola/providers/`(OpenAI/anthropic 추상화, `LLM_PROVIDER`), `store/repository.py`(스토리지 seam).
- **P0**: `web/src/styles/`(tokens·4테마 themes.css·ui.css·screens/*), 앱셸(`Topbar`·`Sidebar`·nav.ts, ⌘K 미도입), 공통 컴포넌트(`components/ui` Card·KPIStatGrid·Chip·Badge·Tabs·Modal·Toast·Kanban·EmptyState), SVG 차트(`components/charts` LineChart·BarChart·Sparkline·BubbleMatrix·Heatmap).
- **P1 API (38경로, `api/routers/*`)**: taskdefs(+upload)·bookmarks·news·trends(+weekly/emergence)·opportunities·proposals(+summarize)·collect(status/runs/diagnose)·threads·assistant(SSE+context)·board·persona·prefs·sources·matches·insights(heatmap).
- **P2 7화면 풀빌드** (`web/src/pages/`): Board(7섹션)·Insights(트렌드/매트릭스/히트맵)·Collect(카드/설정·기사모달)·TaskDefs(상세·풀폼·이력)·Proposals(생성+보관함 칸반)·Persona·Onboarding(마법사).
- **P3**: 어시스턴트 추천질문 pills·핸드오프(`?from=&dept=&lv3=`)·데이터헬스·채팅 기본 펼침.
- **P4 호스팅 설정**: `Dockerfile`·`.dockerignore`·`requirements-api.txt`(scraping 포함)·`render.yaml`·`Procfile`·`docs/DEPLOY.md`.
- **검증**: pytest **1036**, web typecheck/build, Vercel 프리뷰(프런트). Codex 리뷰 2건 반영(히트맵 enrich 필드·emergence base 오늘 제외).

## 결정 (확정)
1. 차트 = **SVG 직접 구현**. 디자인 = **토큰 기반 클린 재작성 + UI/UX 폴리시**(Streamlit CSS 그대로 승계 X).
2. **⌘K 커맨드 팔레트 미도입**(윈도우·현행에서도 제거됨 → 전역 검색).
3. 채팅 드로어 **기본 펼침**(localStorage 기억).
4. **남은 작업 순서 = ① 백엔드 배포·검증 → ② 디테일 폴리시 → ③ Streamlit 은퇴(마지막).**
   - 이유: 은퇴는 되돌릴 수 없고 `app.py`·`ui/`+의존 테스트 대량 삭제 위험 → React가 실데이터로 검증된 뒤 마지막에.

## 다음 단계 (실행)

### ① 백엔드 배포 + 검증 (현재 단계)
- Render: `render.yaml` 블루프린트 → env(`INSIGHTBOARD_CORS_ORIGINS`=Vercel 도메인·`LLM_PROVIDER`·`LLM_API_KEY`·`LLM_MODEL`·`INSIGHTBOARD_DATA_ROOT=/data`) + `/data` 영구 디스크. `docs/DEPLOY.md` 참고.
- Vercel: `VITE_API_BASE`=백엔드 URL → 재배포.
- 검증: `<backend>/api/health` ok → 프런트 `/api/*` 200 → 보드에 데이터.
- **사전 점검 TODO**(중단됨): 호스팅 import 폐쇄가 streamlit 안 끌어오는지 / requirements-api 완전성 확인.

### ② 디테일 폴리시 (실데이터 위에서)
- 반응형(좌nav·중앙·우채팅 3컬럼 축소), 다크/오션/선셋 화면별 점검, 기사 본문(content) 상세(현재 모달은 요약만 — `/api/news` content 제외), 카드 밀도·줄바꿈·차트 스케일.

### ③ Streamlit 은퇴 (검증 완료 후)
- `app.py`·`ui/`·`assets/v2`·streamlit 관련 테스트(test_v2_screens·test_chat_panel·test_onboarding 등) 제거. requirements에서 streamlit 제거. README/CLAUDE 갱신.
- ⚠ 대량 삭제 + 테스트 영향 → 한 번에 하지 말고 단계적, 반드시 백엔드 검증 후.

## 개발 메모
- 화면=PR 1개 cadence. 매 PR: `npm run build`(web) + `python scripts/gen_openapi.py && cd web && npm run gen:types`(API 변경 시) + pytest. OpenAPI 스냅샷 테스트가 드리프트 가드.
- `.vercelignore` 패턴은 **leading `/` 로 루트 고정**(과거 `ui/`가 `web/src/components/ui/` 삭제한 버그).
- 백엔드 라우터는 식별필드·Identity(no-op 인증=Phase2 교체점) 적용. scraping은 지연 import(서버리스 503).
