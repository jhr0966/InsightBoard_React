> 📜 **아카이브 (완료·히스토리)** — React 전환 과정의 계획/기록 문서. 현재 코드와 다를 수 있다. 현행 기준은 `CLAUDE.md` · `docs/ARCHITECTURE.md` 를 보라.

# VIBE CODING BLUEPRINT — Streamlit 기반 뉴스+자동화 과제 시스템

> ⚠️ **역사적 기록** — 초기 비전·블루프린트(2026-05 이전). 현재 진행 중인 정리·정합 작업의 source-of-truth 는
> [`docs/REFACTOR_PLAN.md`](./REFACTOR_PLAN.md). 새 작업을 시작하기 전 이 파일이 아니라
> `REFACTOR_PLAN.md` 와 `CLAUDE.md` 를 먼저 확인할 것.


## 1) 제품 비전

본 시스템의 목적은 다음 두 축을 하나의 흐름으로 연결하는 것이다.

1. 뉴스 데이터 파이프라인: 키워드/포탈 기사 수집 → 정제 → 분석 → 카드뉴스/인사이트 제공
2. 조선소 업무혁신 파이프라인: 작업정의 데이터 업로드 → 뉴스 기술과 매칭 → 자동화 과제 제안서 생성

---

## 2) 전략 원칙

- **작게 시작해서 빠르게 반복**: MVP를 먼저 만들고, 기능은 feature flag로 확장한다.
- **데이터 계약 우선**: UI보다 article/task 스키마를 먼저 고정한다.
- **근거 기반 생성**: LLM 출력물은 항상 뉴스 원문/요약 링크를 근거로 포함한다.
- **운영 가능한 구조**: 수집 성공률, 처리량, 오류율을 측정할 수 있어야 한다.

---

## 3) 목표 아키텍처

```text
[Ingestion]
  - keyword crawler (Naver)
  - portal crawler (AITimes, 오토메이션월드 등)
        |
        v
[Normalization]
  - 중복 제거(canonical URL)
  - 날짜/출처/키워드 정규화
  - 본문 추출/요약
        |
        v
[Storage]
  - Raw zone (json/html)
  - Curated zone (parquet/db)
  - LLM zone (chunks + embeddings)
        |
        v
[Serving]
  - Streamlit Insight Board (차트/워드클라우드)
  - Streamlit Cardnews
  - Proposal Generator (작업-뉴스 매칭)
```

---

## 4) 도메인별 설계

### A. News Ingestion
- 수집 엔진은 provider 단위로 분리
  - `providers/naver.py`
  - `providers/aitimes.py`
  - `providers/automation_world.py`
- 공통 정책
  - retry/backoff
  - timeout
  - user-agent rotation
  - robots/서비스 약관 준수

### B. Data Contract

#### Article (curated)
- `article_id` (hash)
- `title`
- `source`
- `url`
- `canonical_url`
- `published_at` (UTC)
- `collected_at` (UTC)
- `summary`
- `content`
- `keywords` (list[str] 또는 csv)
- `topic_tags` (optional)

#### Task (shipyard)
- `task_id`
- `process`
- `task_name`
- `description`
- `equipment`
- `risk_level`
- `repeatability`
- `automation_level`

### C. LLM-ready 저장
- chunk 기준: 문단/문장 단위 + token 제한
- 컬럼
  - `doc_id`, `article_id`, `chunk_id`, `chunk_text`, `token_count`, `meta_json`, `embedding`
- 목적
  - 검색(RAG)
  - 과제 제안서 생성 근거 확보

### D. Insight Board
- 필수 시각화
  - 키워드 빈도 Top-N
  - 일자/시간대 트렌드
  - 출처별 점유율
  - 워드클라우드
- 확장 시각화
  - 급상승 키워드(전주 대비)
  - 기술 카테고리 히트맵

### E. Proposal Generator
- 입력: 조선소 작업 리스트 + 뉴스/기술 chunk
- 단계
  1. 작업 설명 임베딩
  2. 뉴스 chunk 유사도 검색
  3. 규칙 기반 필터(도메인 적합도)
  4. LLM 제안서 생성
- 출력 템플릿
  - 과제명
  - 적용 작업
  - 적용 기술/근거 기사
  - 기대 효과(KPI)
  - PoC 범위/기간
  - 리스크/전제조건

---

## 5) 실행 로드맵 (Local First)

### Phase A — Local MVP (1~2주)
- 로컬 저장소 구축(JSONL/Parquet) 및 경로 표준화
- 수집 안정화 + raw/curated 분리
- 날짜 정규화(상대시간 → 절대시간)
- Streamlit에서 DuckDB 기반 조회로 전환

### Phase B — Insights/LLM (1~3주)
- 워드클라우드/트렌드/필터 고도화
- chunk/embedding 파이프라인 구축
- 작업-뉴스 매칭 엔진 + 제안서 초안 생성

### Phase C — DB Migration (1~2주)
- PostgreSQL(+pgvector) 스키마 구성
- 로컬 데이터 마이그레이션 스크립트 작성
- Repository 구현체만 교체하여 서비스 연속성 유지

---

## 6) 바이브코딩 운영 규칙

- 작은 PR(200 lines 내외)로 빠르게 병합
- 기능마다 완료 조건(DoD) 명시
- 실패 로그/재처리 정책 문서화
- Prompt/Template 버전 관리 (`prompts/` 디렉터리 권장)

