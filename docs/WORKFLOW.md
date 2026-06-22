# WORKFLOW — 작업 진행 규칙

> 권위 문서는 `CLAUDE.md`. 새 작업 시작 전 `CLAUDE.md`(규칙·라우팅)와 `DEV_GUIDELINES.md`(요약)를 먼저 본다.
> 이 파일은 멀티에이전트/머지 워크플로의 일반 절차만 담는다.


> 여러 에이전트/사람이 겹쳐 작업할 때 어떤 순서로 움직이는지.

## 0. 작업 시작 전

1. **단순 문답인가?** → `CLAUDE.md`만 보고 바로 답. 파일 열지 마라.
2. **어떤 도메인 작업인가?** → 스크래핑 / 인사이트 / 카드뉴스 중 하나 결정.
3. **라우팅 표 확인** → `DEV_GUIDELINES.md §3`에서 최소 파일 집합만 읽는다.

## 1. 브랜치 생성

`main`에서 분기:

```bash
git checkout main
git pull
git checkout -b <category>-<slug>
```

카테고리: `fix`, `feat`, `refactor`, `style`, `docs`, `chore`.

## 2. 개발 루프

```
┌─────────────┐
│ 최소 파일 읽기 │
└──────┬──────┘
       ▼
┌─────────────┐
│   수정       │ ← 계층 분리(web→api 계약), HTTP는 build_session, LLM은 sola.client
└──────┬──────┘
       ▼
┌─────────────┐
│ 로컬 검증    │ ← pytest -q + (web) npm run build + py_compile
└──────┬──────┘
       ▼
┌─────────────┐
│ 문서 갱신    │ ← CHANGELOG + SESSIONS (+ INVARIANTS if new)
└──────┬──────┘
       ▼
┌─────────────┐
│ 커밋 & 푸시  │
└─────────────┘
```

## 3. 멀티 에이전트 분업 (선택)

동일 작업에 에이전트를 여럿 쓸 때:

| 역할 | 읽는 파일 | 출력 |
|---|---|---|
| **탐색자** (Explore) | 해당 도메인 파일 1~2개 | "어디를 고쳐야 하는가" 위치 리스트 |
| **구현자** (main) | 탐색자가 찾은 파일들만 | 실제 수정 + 검증 |
| **리뷰어** (선택) | diff만 | INVARIANTS 위반·스펙 위반 체크 |

에이전트끼리 파일을 **중복 읽지 않도록** 주의. 탐색자의 보고서가 곧 구현자의 입력.

## 4. 커밋 규칙

- 메시지: `<category>: <한 줄 요약>` (예: `feat: insight board 언론사 랭킹 추가`)
- 본문: 왜(why)를 1~2문장. "무엇"은 diff가 설명한다.
- 동일 커밋에 포함:
  - 코드 변경
  - `CHANGELOG.md` [Unreleased] 항목
  - `docs/SESSIONS.md` 상단 세션 추가
  - 새 invariant 시 `docs/INVARIANTS.md`

## 5. PR / 머지

- Vercel 프리뷰(프런트) 또는 로컬 검증 결과를 PR에 남긴다.
- `main` 머지 = Vercel/Render 자동 배포. 따라서 **검증 실패 시 머지 금지**.
- 머지 후 `docs/SESSIONS.md`의 해당 세션에 "merged" 표시.

## 6. 롤백

배포된 변경이 깨진 경우:

```bash
git checkout main
git revert <broken-commit>
git push
```

롤백 커밋도 CHANGELOG에 기록 (`[Reverted]` 섹션).

## 7. 세션 종료 시

에이전트가 중단되거나 다음 세션으로 넘어갈 때:

1. `docs/SESSIONS.md` 상단에 현재 상태 요약 (진행 중 작업·남은 TODO·블로커).
2. 미커밋 변경이 있으면 브랜치명 명시.
3. 다음 세션은 `SESSIONS.md` 상단 **1개**만 읽고 복원.
