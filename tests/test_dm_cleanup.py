"""데이터 관리 정리 회귀 — 템플릿 헤더화, 빈 수집잡·14일 차트, 수집 CTA 위젯화."""
from __future__ import annotations

from ui import data_management_v2 as dm


def test_template_header_only_no_fake_mockups():
    """#133 재설계 후 템플릿은 헤더(KPI 4종)만 — 옛 필터/페이저/가짜 서브카드 없음."""
    raw = dm._DM_TEMPLATE.read_text(encoding="utf-8")
    for junk in ("dm-filters", "dm-pager", "dm-sub-grid", "키워드 매니저",
                 "셀렉터 오류", "1,247", "dm-news-meta", "스케줄 설정은 다음 PR",
                 "{{NEWS_CARDS}}", "{{INGEST_JOBS}}", "{{INGEST_REFRESH_CTA}}"):
        assert junk not in raw
    # 헤더 KPI placeholder + split 마커는 보존(_render_dm_header 가 소비)
    for ph in ("{{ACTIVE_SOURCES}}", "{{TODAY_COUNT}}", "{{TOTAL_CHUNKS}}",
               "{{LAST_UPDATE}}", "{{DM_TABS}}"):
        assert ph in raw


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
    src = svg.split('src="', 1)[1].split('"', 1)[0]
    assert "#" not in src
    assert "%23" in src


def test_collect_cta_is_widget_button():
    """'지금 뉴스 수집' 은 위젯(_render_collect_button, 소켓 rerun). 앵커 빌더 없음."""
    assert not hasattr(dm, "_refresh_cta_html")
    assert hasattr(dm, "_render_collect_button")
