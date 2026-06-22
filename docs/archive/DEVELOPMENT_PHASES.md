> 📜 **아카이브 (완료·히스토리)** — React 전환 과정의 계획/기록 문서. 현재 코드와 다를 수 있다. 현행 기준은 `CLAUDE.md` · `docs/ARCHITECTURE.md` 를 보라.

# DEVELOPMENT PHASES — Streamlit + Local First

> ⚠️ **역사적 기록** — 초기 단계별 계획(2026-05). 현재 진행 중인 정리·정합 작업의 source-of-truth 는
> [`docs/REFACTOR_PLAN.md`](./REFACTOR_PLAN.md). 새 작업을 시작하기 전 이 파일이 아니라
> `REFACTOR_PLAN.md` 와 `CLAUDE.md` 를 먼저 확인할 것.


본 문서는 현재 합의된 방향(회사 정책: Streamlit, 초기 저장소: Local)을 기준으로
개발 단계를 고정하고, 바로 실행 가능한 시작 계획을 제공한다.

## 0. 범위 요약

- UI/서비스: **Streamlit 고정**
- 저장 전략: **Local First** (JSONL/Parquet) → 이후 DB 전환
- 목표: 뉴스 파이프라인 + 조선소 작업 데이터 결합 + 자동화 과제 제안

---

## 1. 최종 아키텍처(전환 포함)

```text
[Batch Pipelines]
  - News Crawlers (keyword + portal)
  - Normalize / Deduplicate / Chunk / Embed
  - Shipyard Excel Validation + Parquet Convert
        |
        v
[Storage - Phase A]
  - local data lake (raw/processed/embeddings)
  - DuckDB for query
        |
        v
[Serving]
  - Streamlit pages
    * News Explorer
    * Card News
    * Insights (wordcloud/trend)
    * Shipyard Data Upload
    * Task Proposal Generator

[Storage - Phase B]
  - PostgreSQL(+pgvector) or Qdrant migration
  - Repository implementation switch only
```

핵심 원칙은 `Repository` 추상화로 저장소 의존을 분리해, UI/도메인 로직을 유지한 채 저장소만 교체하는 것이다.

---

## 2. Phase 계획

## Phase A — Local MVP (즉시 시작)

### 목표
- DB 없이도 end-to-end 데모가 가능한 상태 확보

### 구현 항목
1. 뉴스 수집(키워드 + 특정 포털) 및 원문 저장
2. 전처리/중복 제거/요약·키워드 생성
3. LLM 처리용 chunk/embedding 생성
4. Streamlit 카드뉴스/인사이트/검색 화면 연결
5. 조선소 작업 Excel 업로드 → 검증 → Parquet 저장
6. 작업-뉴스 매칭 기반 제안서 초안 생성

### 산출물(DoD)
- `data/` 하위에 파이프라인 결과가 누적 저장됨
- Streamlit 5개 페이지가 크래시 없이 동작
- 제안서 결과(JSON/Markdown/PDF 중 1개 이상) 생성 가능

---

## Phase B — 품질/운영 강화

### 목표
- 로컬 기반 운영 안정성 확보

### 구현 항목
1. 스케줄링(주기 실행, 재시도, 실패 로그)
2. 데이터 품질 점검(중복률, 필수필드 누락률)
3. 관측성(수집 성공률, 처리시간)
4. 카드뉴스 템플릿/제안서 템플릿 버전 관리

### 산출물(DoD)
- 주간 배치 성공률 대시보드
- 실패 건 재처리(run id 기반) 가능

---

## Phase C — DB 전환

### 목표
- Local 저장을 DB로 점진 전환

### 구현 항목
1. Postgres/Vector 스키마 생성
2. Local(JSONL/Parquet) → DB 마이그레이션 스크립트
3. Repository 구현체 스위치 (`Local*Repository` → `Db*Repository`)
4. 성능/정합성 회귀검증

### 산출물(DoD)
- 동일 기능에서 저장소만 바뀐 상태로 동작
- 주요 페이지 응답속도 개선 확인

---

## 3. 로컬 데이터 표준

```text
data/
  raw/news/YYYY-MM-DD/*.jsonl
  processed/news/YYYY-MM-DD/*.parquet
  embeddings/YYYY-MM-DD/*.parquet
  shipyard/raw/*.xlsx
  shipyard/processed/*.parquet
  artifacts/cardnews/*.{png,pdf}
  artifacts/proposals/*.{json,md,pdf}
  logs/*.log
```

- 원칙: append-friendly(JSONL) + query-friendly(Parquet)
- 조회: DuckDB SQL 우선
- 파티션: `YYYY-MM-DD` 기준 분할

---

## 4. 이번 스프린트(개발 시작 체크리스트)

1. Repository 인터페이스 초안 정의
2. Local repository 구현 (뉴스/작업/제안서)
3. 뉴스 파이프라인 저장 경로 통일 (`data/raw`, `data/processed`)
4. Streamlit 페이지별 데이터 로더 연결
5. Excel 업로드 검증 규칙(필수 컬럼/타입) 추가
6. 제안서 템플릿 v1 생성
7. 최소 E2E 스모크 테스트 추가

---

## 5. 즉시 착수 원칙

- 작은 단위로 커밋(기능 1개 = 커밋 1개)
- 기능마다 DoD를 PR 설명에 명시
- 생성형 결과물은 근거 기사 URL 반드시 포함
- 실패 로그를 남기지 않는 파이프라인은 배포 금지
