"""InsightBoard HTTP API (FastAPI) — React 전환용 백엔드 계약.

`docs/REACT_MIGRATION_PLAN.md §3` 의 첫 구현. Streamlit UI 가 Python 직호출하던
도메인(`store/`·`roadmap/`·`sola/`)을 HTTP 계약 뒤로 옮긴다. Phase 1 은 기존
파일/SQLite 를 그대로 위임하고, 모든 응답에 식별·감사 필드(`store/_audit.py`)를
노출해 Phase 2(Postgres·멀티유저) 이전을 매끄럽게 한다.
"""
