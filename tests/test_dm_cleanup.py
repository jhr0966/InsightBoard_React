"""Phase C-3 — 데이터 관리 정리: 죽은 필터/페이저, 가짜 서브카드·통계 제거."""
from __future__ import annotations

from ui import data_management_v2 as dm


def test_strip_removes_filters_pager_subgrid_keeps_real():
    raw = dm._DM_TEMPLATE.read_text(encoding="utf-8")
    out = dm._strip_dm_mockups(raw)
    # 죽은/가짜 블록 제거
    assert "dm-filters" not in out          # 죽은 검색·필터칩·셀렉트
    assert "dm-pager" not in out            # 죽은 페이저
    assert "dm-sub-grid" not in out         # 가짜 서브카드 3종
    assert "키워드 매니저" not in out        # 가짜 서브카드 통계
    assert "셀렉터 오류" not in out          # 가짜 출처 상태
    assert "1,247" not in out               # 가짜 카운트 (필터/페이저)
    # 실데이터 placeholder + 셸/뉴스 그리드는 보존
    for ph in ("{{NEWS_CARDS}}", "{{INGEST_JOBS}}", "{{DM_TABS}}", "{{ACTIVE_SOURCES}}"):
        assert ph in out
    assert 'class="dm-shell"' in out         # 셸 닫힘 보존
    assert 'class="dm-art-grid"' in out      # 뉴스 카드 그리드 보존


def test_strip_is_noop_when_blocks_absent():
    html = '<div class="dm-shell"><main>{{NEWS_CARDS}}</main></div>'
    assert dm._strip_dm_mockups(html) == html


def test_template_edits_removed_fake_subtitle_and_schedule_and_meta():
    raw = dm._DM_TEMPLATE.read_text(encoding="utf-8")
    assert "5개 작업" not in raw                  # 가짜 잡 카운트 서브타이틀
    assert "스케줄 설정은 다음 PR" not in raw      # disabled 스케줄 버튼
    assert "dm-news-meta" not in raw              # 가짜 카운트 메타(전체 1,247/매칭 32/북마크 17)
    # 실 refresh CTA placeholder 는 보존
    assert "{{INGEST_REFRESH_CTA}}" in raw
