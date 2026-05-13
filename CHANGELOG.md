# Changelog

모든 주요 변경은 여기에 기록한다. 포맷: [Keep a Changelog](https://keepachangelog.com/) + SemVer.
릴리스 = `main` 머지 시점.

## [Unreleased]

### Added (Phase 6-B 후속 — cron 안 enrich 자동 호출)
- `scripts/daily_scrape.py` 인자 추가 — `--enrich-max N`(기본 30, 0 이면 스킵) + `--no-llm`(본문 fetch 만, LLM 키워드·요약 끄기).
- `scripts/daily_scrape._run_enrich(*, max_n, with_llm)` — collect_batch 직후 `load_all_today()` → `content` 부족 기사 head(N) → `enrich_articles` → 소스별 그룹 `upsert_articles`. 진행 로그는 10건/완료 시 stdout.
- main 흐름에 enrich 단계 통합 — `report.total_articles > 0` + `enrich_max > 0` 일 때만 호출, `try/except Exception` 으로 격리(enrich 실패해도 cron exit 0 유지).
- `tests/test_daily_scrape_enrich.py` 8건 — enrich 호출 / `--enrich-max 0` 스킵 / 수집 0건 스킵 / 예외 격리(exit 0) / max_n cap / `--no-llm` 전달 / 기본 with_llm=True / 이미 enrich 된 기사 제외. 전체 **142/142** 통과.

### Fixed (Phase 6-A 후속 — roadmap 의존성 제거)
- `ui/home_tab.render` 의 트렌드 위젯이 `if roadmap.empty or news.empty` 분기 안에 갇혀 있어 로드맵 미업로드 onboarding 상태(뉴스만 수집된 상태)에서 위젯이 보이지 않던 버그 수정 (Codex review #21). 트렌드 위젯은 roadmap 의존성이 없으므로 `news` 만 있어도 렌더되도록 분기 분리. 부서 매칭 카드/안내는 기존대로 roadmap+news 모두 필요.
