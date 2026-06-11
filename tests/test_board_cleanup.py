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


# ── 보드 감사(2026-06-11): 매트릭스 버블 충돌 회피 · 스파크라인 크기 · KPI 14d ──

def _fake_cells(n: int = 3) -> pd.DataFrame:
    """matched_news/tasks 가 모두 같은 셀 n개 — 좌표 충돌 시나리오."""
    return pd.DataFrame([
        {"dept": "도장1팀", "lv3": f"작업{i}", "cell_score": 100 - i,
         "matched_news": 5, "matched_tasks": 1, "sample_tasks": ""}
        for i in range(n)
    ])


def test_matrix_bubbles_declash_when_cells_have_identical_metrics(monkeypatch):
    """동일 metric 셀들이 같은 좌표에 겹쳐 아래 버블이 클릭 불가였던 회귀 방지."""
    import re

    monkeypatch.setattr(board_v2, "_score_cells", lambda n, t: _fake_cells(3))
    monkeypatch.setattr(
        board_v2._news_db, "load_news_for_days",
        lambda days=14: pd.DataFrame({"title": ["x"], "link": ["l"]}),
    )
    monkeypatch.setattr(
        board_v2, "_load_tasks", lambda: pd.DataFrame({"dept": ["도장1팀"]})
    )
    board_v2._board_matrix_html.clear()
    html = board_v2._board_matrix_html(selected_key=None)
    coords = re.findall(r"left:(\d+)%; top:(\d+)%", html)
    assert len(coords) == 3
    assert len(set(coords)) == 3  # 세 버블 모두 서로 다른 좌표


def test_trend_sparkline_svg_has_explicit_size(monkeypatch):
    """sparkline svg 에 width/height 명시 — svg→img 변환 시 거대 렌더 회귀 방지."""
    series = [{"name": f"kw{i}", "counts": [1, 2, 3, 4, 5, 6, 7, 8]} for i in range(4)]
    monkeypatch.setattr(
        board_v2, "_weekly_keyword_series", lambda weeks=8: (["W1"] * 8, series)
    )
    board_v2._board_trend.clear()
    t = board_v2._board_trend()
    assert "width='60' height='18'" in t["kw_list"]


def test_board_kpis_opp_counts_cells_from_14d_window(monkeypatch):
    """KPI '자동화 기회'는 ④ 카드·⑥ 매트릭스와 같은 14d 윈도우를 센다."""
    def _fake_news(days=7, **_kw):
        n = 2 if days == 1 else 9  # 1d=2건, 14d=9건
        return pd.DataFrame({"title": [f"t{i}" for i in range(n)],
                             "link": [f"l{i}" for i in range(n)]})

    monkeypatch.setattr(board_v2._news_db, "load_news_for_days", _fake_news)
    monkeypatch.setattr(
        board_v2, "_load_tasks", lambda: pd.DataFrame({"dept": ["도장1팀"]})
    )
    # cells 수 = 입력 뉴스 행 수 (1d=2, 14d=9 구분용)
    monkeypatch.setattr(
        board_v2, "_score_cells",
        lambda news, tasks: pd.DataFrame({"dept": ["d"] * len(news)}),
    )
    monkeypatch.setattr(
        board_v2, "_score_matches",
        lambda *a, **k: pd.DataFrame(),
    )
    monkeypatch.setattr(
        board_v2.bookmarks_store, "summary_counts",
        lambda: {"proposal_status": {"pending": 0}},
    )
    board_v2._board_kpis.clear()
    kpis = board_v2._board_kpis()
    assert kpis["collect"] == 2          # 오늘(1d)
    assert kpis["opp"] == 9              # 14d 윈도우 셀 수


def test_brief_items_include_link_for_summary_enrichment(monkeypatch):
    """② 브리핑 items 에 link 포함 — summary 보강 루프가 원기사를 찾는 키."""
    news = pd.DataFrame({
        "title": ["A", "B", "C"],
        "link": ["l1", "l2", "l3"],
        "source": ["s"] * 3,
        "collected_at": ["2026-06-11T00:00:00+00:00"] * 3,
        "summary": ["요약A", "요약B", "요약C"],
    })
    monkeypatch.setattr(board_v2._news_db, "load_news_for_days", lambda days=3: news)
    monkeypatch.setattr(board_v2, "_load_tasks", lambda: pd.DataFrame())
    import streamlit as st
    board_v2._brief_html.clear()
    board_v2._brief_html(persona_label="t")
    items = st.session_state.get("_board_brief_items") or []
    assert items and all("link" in it and it["link"] for it in items)
    st.session_state.pop("_board_brief_items", None)
