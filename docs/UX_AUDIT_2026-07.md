# UX_AUDIT_2026-07 — UI/UX 감사 결과 · 실행 계획

> 2026-07-22 전 화면 코드 감사 결과와 **PR 단위 실행 계획**. 이 문서가 실행 세션의
> 단일 인계 문서다 — 실행자는 아래 PR을 위에서부터 순서대로, **PR당 한 목적**으로 진행한다.
> ⚠ 파일:라인 은 감사 시점 앵커다 — 수정 전 반드시 현재 코드에서 위치를 재확인할 것.

## 감사 요약

앱 셸(반응형 3단 브레이크포인트·모바일 오프캔버스·전역검색·워크플로 네비)은 건실.
발견된 문제는 크게 4계열:

1. **오류가 "데이터 없음"으로 위장** — 거의 모든 화면이 쿼리 `isError` 를 처리하지 않아,
   백엔드 장애 시 "기사가 없어요/사례가 없어요" 류 빈 상태를 보여줌 (무료 호스팅 특성상
   슬립·재배포가 잦아 실제로 자주 노출되는 경로).
2. **무음 실패** — 저장·삭제·토글 등 뮤테이션 다수가 `onError` 없음. 특히
   온보딩 저장 실패 시 마법사가 멈춘 것처럼 보임(첫 사용 경험 차단),
   페르소나 로드 실패 시 영구 "불러오는 중…" 스피너.
3. **플래그십 흐름 단선** — 사례→제안서 핸드오프(`이 사례로 제안서 →`)가 사례 식별자를
   전달하지 않아 라벨·SOLA 프리필·사례 주입이 모두 동작하지 않음.
4. **모달·접근성 기본기** — Modal 에 Esc 닫기/포커스 트랩 없음, `dismissible={false}` 인데
   ✕ 는 동작, 수집 진행 모달의 ✕ 는 실행 중 no-op(고장처럼 보임), SOLA 드로어 오버레이에
   백드롭 없음(태블릿), 클릭 가능한 div/tr 에 키보드 접근 불가.

---

## 실행 계획 (PR 순서대로)

### PR-A `fix-ux-error-states` — 오류 상태·뮤테이션 피드백 전면 정비 🔴

**목적**: "오류 = 빈 화면" 위장과 무음 실패를 없앤다. 실패는 항상 보이게.

A-1. 쿼리 `isError` 분기 추가 (빈 상태와 구분되는 오류 라인 + 가능하면 재시도 버튼):
- `Persona.tsx:38` — **최우선**: 로드 실패 시 영구 스피너 → 오류 메시지+재시도.
- `Board.tsx:69` digest / `:151` opps / `:180` keywords
- `Feed.tsx:67` 뉴스 목록 ("수집을 시작하세요" 오안내 해소)
- `Cases.tsx:60` 목록·요약 / `Proposals.tsx:200` Archive / `TaskDefs.tsx:77` 목록, `:97` 상세
- `Insights.tsx:60~101` — 쿼리 6종은 탭당 공용 오류 라인 1개로 처리(개별 6개 만들지 말 것)
- 공용 패턴 권장: `components/ui` 에 `<LoadError onRetry={..}>` 소형 컴포넌트 1개 추가 후 재사용.

A-2. 뮤테이션 `onError` 토스트 (+ 일부 성공 피드백):
- `Onboarding.tsx:17` save — **최우선**(실패 시 마법사 정지 문제)
- `Persona.tsx:19` save · `:33` reset
- `Board.tsx:45` dismiss · `:56` save
- `Proposals.tsx:183` remove(onError) · `:178` setStatus(성공 토스트 "상태를 옮겼어요" 추가)
- `TaskDefs.tsx:95` del · `Collect.tsx:262` toggle · `:264` remove
- `Cases.tsx:30` — 제외/대기 전환도 구체 문구("제외했어요"/"검토 대기로 되돌렸어요")

**수용 기준**: 백엔드를 내린 상태(또는 fetch mock)에서 각 화면이 "오류+재시도"를 표시,
빈 상태 문구가 나오지 않음. 모든 삭제/저장/토글 실패에 danger 토스트.

### PR-B `fix-case-handoff` — 사례→제안서 흐름 배선 🔴

**목적**: "이 사례로 제안서 →"가 실제로 사례를 실어 나르게 한다 (자산화 수직 흐름의 마지막 조각).

- `Cases.tsx:107` — `/proposals?from=case&case_id=<id>&work=<target_work>` 로 식별자 전달.
- `Proposals.tsx:50` `HANDOFF_LABEL` 에 `case: "📚 사례에서 인계됨"` 추가(+`opp` 누락분).
- `Proposals.tsx` — `case_id` 수신 시: target_work 로 작업정의 자동 선택 시도, 생성 요청에
  해당 사례가 주입되도록(백엔드 generate 가 approved 사례를 근거 기사 기준으로 넣으므로,
  프런트에선 우선 자동 선택+안내 배너까지. 사례 강제 주입이 필요하면 generate API 에
  `case_ids` 옵션 추가 — 스키마 변경 시 OpenAPI 재생성 필수).
- `AssistantDrawer.tsx:7` `handoffPrefill` 에 `case` 분기 — "이 사례를 우리 작업에 적용하는
  제안서 초안을 검토해줘" 류 프리필.

**수용 기준**: 사례 카드에서 버튼 클릭 → 제안 생성 탭에 "사례에서 인계됨" 배너 + SOLA
프리필 표시. (가능하면) 생성된 제안서 응답 cases 에 해당 사례 포함.

### PR-C `fix-modal-a11y` — 모달·오버레이 기본기 🟡

- `ui/index.tsx:106~118` Modal: **Esc 닫기** + `dismissible={false}` 면 ✕ 숨김 +
  간단 포커스 트랩(열릴 때 포커스 이동, Tab 순환은 최소 구현으로 충분).
- `Collect.tsx:63/130` 진행 모달 — 실행 중 ✕ 숨김(또는 "백그라운드로" 동작 부여 대신 숨김 권장).
- `Layout.tsx:54` — ≤1100px에서 SOLA 드로어 오버레이에 백드롭 추가(탭하면 닫힘, 사이드바와 동일 패턴).
- 온보딩 ✕ 문제는 dismissible 존중으로 자동 해결됨을 테스트로 확인.

### PR-D `fix-drawer-chat` — SOLA 채팅 스트림 제어 🟡

- `AssistantDrawer.tsx:104` — `abortRef.current?.abort()` 를 reset·새 전송 시 호출
  (스트림 겹침/취소 불가 해소).
- 메시지 목록 끝 ref + 새 메시지/스트림 델타마다 `scrollIntoView` (자동 스크롤).

### PR-E `chore-ux-consistency` — 카피·표기 일관화 🟢

- `Sidebar.tsx:62` "채택 대기"가 존재하지 않는 `pending` 을 읽어 항상 0 →
  `reviewing`(+`feasibility`) 합계로 교체하고 라벨도 "검토 중"으로.
- 카피: `Proposals.tsx:211` "bookmark" → "예전 보관함" · `Collect.tsx:259` "Ready" → "정상" ·
  `Topbar.tsx:35` "LIVE" → "실시간" · `TaskDefs.tsx:257` "(task_def_text)" 제거.
- 토스트 톤 통일(이모지+해요체: "삭제됨"→"🗑 삭제했어요" 등).
- 날짜 표기 통일 — `lib/time.ageLabel` 재사용으로 Board 인사말/Topbar/카드 표기 정렬.
- `Collect.tsx:288` 빠른 수집 키워드·`:333` 진단 URL 입력에 Enter 제출.
- `TaskDefs.tsx:61` 파일 input 을 스타일 버튼(label)로 감싸기.

### PR-F `feat-ux-keyboard` — 키보드 접근성 표준화 🟢 (선택 — 여유 있으면)

- 클릭 div/tr → `role="button"`+`tabIndex`+`onKeyDown`(Enter/Space) 표준화:
  `Feed.tsx:70` 카드 · `:98` 표 행 · `Insights.tsx:155,184` 카드 · `Sidebar.tsx:39`
  페르소나 카드 · `Topbar.tsx:85` 아바타(+⚙·벨 `aria-label`).
- 공용 훅/헬퍼 하나 만들어 재사용(`clickableProps(onClick)` 류).

### 보류 (기록만, 지금 안 함)

- 운영 목록 페이지네이션(Cases/Proposals Archive/TaskDefs) — 데이터 커지면.
- Feed 보기 모드(카드/표) 영속화, Topbar 검색 clear 버튼, 채팅 textarea 전환.
- 알림 벨 의미 확장(현재 reviewing 수만) — 알림 체계는 별도 기획 필요.

---

## 실행 규칙 (실행 세션 필독)

1. CLAUDE.md 준수: 브랜치 `<카테고리>-<설명>` → draft PR → CI(verify) 통과 → ready → squash 머지.
2. 프런트 전용 PR 은 `cd web && npm run build`(tsc 포함)로 검증. **PR-B 에서 generate API 를
   건드리면** `python scripts/gen_openapi.py && cd web && npm run gen:types` + 전체 pytest.
3. 각 PR 에 CHANGELOG [Unreleased] + docs/SESSIONS.md 기록 포함.
4. 라인 번호는 앵커일 뿐 — 수정 전 grep 으로 현재 위치 확인.
5. 완료 보고는 CLAUDE.md §8 패치노트 형식.

---

## 부록 — 커스텀 RSS 출처 준비 (나중에 추가용)

커스텀 RSS 는 이미 실수집에 연결돼 있다(PR #84): **수집 관리 → 출처 설정 → 이름+URL 등록**
→ 다음 수집(수동·자동 모두)부터 포함. 등록 후 수집 1회 돌려 수집 이력에서 건수 확인.

후보 (⚠ 등록 전 브라우저에서 URL 을 열어 유효한 RSS 인지 반드시 확인 — 모우/모비 계열
언론사 CMS 는 대부분 `/rss/allArticle.xml` 패턴):

| 후보 | 분야 | 예상 RSS URL |
|---|---|---|
| 로봇신문 | 로봇·자동화 | `https://www.irobotnews.com/rss/allArticle.xml` |
| 헬로티 | 스마트팩토리·산업자동화 | `https://www.hellot.net/rss/allArticle.xml` |
| 인공지능신문 | AI | `https://www.aitimes.kr/rss/allArticle.xml` |
| 산업일보 | 제조·기계 | `https://www.kidd.co.kr/rss/allArticle.xml` |
| 월간 무인화기술/조선·해양 전문지 | 조선 특화 | RSS 제공 여부 확인 필요 |

조선 전문지(코리아쉬핑가제트·쉬핑뉴스넷 등)는 RSS 미제공일 수 있음 — 미제공이면
tech_sites 에 사이트 추가(TECH_SITES/TECH_RSS 한 줄)하는 방식이 대안.
