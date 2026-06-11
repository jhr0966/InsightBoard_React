"""Phase C-2 — 보드 정리: 죽은 링크 재배선, 뉴스카드 클릭, 가짜/죽은 요소 제거."""
from __future__ import annotations

import pandas as pd

from ui import board_v2


# ── 죽은 .html 링크 → 실제 area 네비 재배선 (기능 보존) ──────

def test_clean_board_html_rewires_dead_html_links_to_area_nav():
    raw = (
        '<a href="data-management.html">뉴스</a>'
        '<a href="insights-analysis.html">전체</a>'
        '<a href="insights-analysis.html#trend">트렌드</a>'
        '<a href="insights-analysis.html#matrix">매트릭스</a>'
    )
    out = board_v2._clean_board_html(raw)
    # 더 이상 죽은 .html 경로 없음
    assert ".html" not in out
    # 실제 area 네비로 (URL 인코딩된 app_area)
    assert out.count("?app_area=") == 4
    from urllib.parse import quote as _q
    assert _q("🗞 뉴스 수집") in out   # 🗞 뉴스 수집
    assert "%F0%9F%94%8E" in out   # 🔎 인사이트 분석
    assert "target=\"_self\"" in out


def test_real_board_template_has_no_dead_mockup():
    raw = board_v2._BOARD_TEMPLATE.read_text(encoding="utf-8")
    # 죽은/가짜 요소 제거됨
    assert "db-cta-primary" not in raw          # hero "브리핑 듣기" CTA
    assert "SOLA에 빠른 질문" not in raw
    assert "db-tab-soon" not in raw             # 미구현 필터 칩(강한매칭/출처별/월별)
    assert "keyword-manager.html" not in raw    # 없는 화면 링크
    assert "06:08 생성" not in raw              # 가짜 brief-meta
    assert "검토 대기 4건" not in raw           # 하드코딩 리터럴
    # 실데이터 placeholder + 살아있는 섹션은 보존
    for ph in ("{{BOARD_STORIES}}", "{{BOARD_OPPORTUNITIES}}", "{{BOARD_TREND}}",
               "{{BOARD_MATRIX}}", "{{BOARD_KW_MGR}}", "{{KPI_COLLECT}}"):
        assert ph in raw


# ── 탑 스토리 카드 (2컬럼 그리드, 원문 링크 클릭) ──────────────

def _story_row(link="http://example.com/a", **extra):
    row = {
        "title": "AI 비전 도장 검사", "content": "머신비전 자동 검출",
        "source": "AI Times", "collected_at": "2026-05-30T00:00:00+00:00",
        "link": link,
    }
    row.update(extra)
    return pd.Series(row)


def test_story_card_is_clickable_when_link_present():
    html = board_v2._story_card_html(_story_row("http://example.com/card"))
    assert 'href="http://example.com/card"' in html
    assert 'target="_blank"' in html
    assert 'rel="noopener"' in html
    assert "db-story" in html


def test_story_without_link_renders_plain_article():
    html = board_v2._story_card_html(_story_row(link=""))
    assert "<a " not in html
    assert "db-story" in html


def test_story_link_is_escaped():
    html = board_v2._story_card_html(_story_row('http://x/"><script>'))
    assert "<script>" not in html
    assert "db-story" in html


def test_story_title_and_summary_are_escaped():
    html = board_v2._story_card_html(
        _story_row(title="<b>도장</b>", summary_llm='<img onerror="x">요약'),
    )
    assert "<b>" not in html
    assert "<img onerror" not in html
    assert "&lt;b&gt;도장&lt;/b&gt;" in html


def test_story_card_thumbnail_https_promoted_and_no_referrer():
    html = board_v2._story_card_html(
        _story_row(image_url="http://img.example.com/a.jpg"),
    )
    assert 'src="https://img.example.com/a.jpg"' in html
    assert 'referrerpolicy="no-referrer"' in html
    assert "db-story-img" in html


def test_story_card_rejects_non_http_image_scheme():
    html = board_v2._story_card_html(_story_row(image_url="javascript:alert(1)"))
    assert "javascript:" not in html
    assert "db-story-img-ph" in html


# ── 탑 스토리 그리드 — 최소 10장 + 2컬럼 ────────────────────

def _stories_df(n: int) -> pd.DataFrame:
    return pd.DataFrame([
        _story_row(f"http://example.com/{i}", title=f"기사 {i}").to_dict()
        for i in range(n)
    ])


def test_board_stories_grid_renders_10_cards():
    from unittest.mock import patch
    with patch.object(board_v2._news_db, "load_news_for_days",
                      return_value=_stories_df(15)):
        board_v2._board_stories_html.clear()
        out = board_v2._board_stories_html()
    assert out.count('<article class="db-story"') == 10
    assert "db-stories-note" not in out


def test_board_stories_grid_note_when_fewer_than_10():
    from unittest.mock import patch
    with patch.object(board_v2._news_db, "load_news_for_days",
                      return_value=_stories_df(3)):
        board_v2._board_stories_html.clear()
        out = board_v2._board_stories_html()
    assert out.count('<article class="db-story"') == 3
    assert "db-stories-note" in out


def test_board_css_stories_is_two_column_grid_without_dead_lead():
    css = (board_v2.ASSETS_DIR / "v2" / "screens" / "board.css").read_text(encoding="utf-8")
    block = css.split(".db-stories {", 1)[1].split("}", 1)[0]
    assert "repeat(2, minmax(0, 1fr))" in block          # 2컬럼 그리드
    assert "db-lead" not in css                          # 데드 lead CSS 제거
    assert "db-side-stories" not in css                  # 데드 side 컨테이너 제거


def test_global_css_no_longer_stacks_stories_to_one_column():
    """scale.css(B2·Phase C-2)·card.css(@container) 의 .db-stories 1fr 강제 제거 —
    좁은 폭에서도 뉴스 카드 2컬럼 유지."""
    import re
    for name in ("scale.css", "card.css"):
        css = (board_v2.ASSETS_DIR / "v2" / name).read_text(encoding="utf-8")
        css = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)  # 주석 제거
        for chunk in css.split("{")[:-1]:
            selector = chunk.rsplit("}", 1)[-1]
            if ".db-stories" in selector:
                raise AssertionError(f"{name}: .db-stories 셀렉터 잔존 — {selector.strip()!r}")
