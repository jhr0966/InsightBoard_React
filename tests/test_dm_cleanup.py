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


# ── 버그 수정 회귀 (빈 수집잡·새로고침·14일 차트) ────────────

def test_empty_jobs_uses_block_not_grid():
    """빈 수집잡 문구가 .dm-job grid 에 갇혀 글자마다 줄바꿈되던 버그 — display:block 강제."""
    import pandas as pd
    from unittest.mock import patch
    with patch.object(dm._news_db, "load_all_today", return_value=pd.DataFrame()):
        html = dm._ingest_jobs_html()
    assert "display:block" in html
    assert "word-break:keep-all" in html
    assert "오늘 실행된 수집잡이 없습니다" in html


def test_hist_chart_is_encoded_img_not_inline_svg():
    """st.html 이 인라인 <svg> 를 제거하므로 URL 인코딩 data-URI <img> 로 렌더 + '#' 인코딩."""
    svg = dm._hist_html()["svg"]
    assert svg.lstrip().startswith("<img")
    assert "data:image/svg+xml," in svg
    # 색상 '#' 는 src 안에서 %23 로 인코딩 (raw '#' 가 src 를 자르지 않음)
    src = svg.split('src="', 1)[1].split('"', 1)[0]
    assert "#" not in src
    assert "%23" in src


def test_collect_cta_migrated_to_widget_button():
    """'지금 뉴스 수집' 은 앵커(_refresh_cta_html, 문서 reload)에서 위젯
    (_render_collect_button, 소켓 rerun)으로 전환. 템플릿 placeholder 는 코드에서
    빈 문자열로 치환(앵커 미주입), 실 동작은 _do_dm_collect pending →
    _consume_refresh_if_any (test_collect_trigger 에서 검증)."""
    assert not hasattr(dm, "_refresh_cta_html")    # 앵커 빌더 제거됨
    assert hasattr(dm, "_render_collect_button")   # 위젯 렌더 존재
    raw = dm._DM_TEMPLATE.read_text(encoding="utf-8")
    assert "{{INGEST_REFRESH_CTA}}" in raw         # placeholder 자체는 보존
