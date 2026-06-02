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
    assert "%F0%9F%A7%B1" in out   # 🧱 데이터 관리
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


# ── 뉴스 카드 클릭 (원문 링크) ──────────────────────────────

def _story_row(link="http://example.com/a"):
    return pd.Series({
        "title": "AI 비전 도장 검사", "content": "머신비전 자동 검출",
        "source": "AI Times", "collected_at": "2026-05-30T00:00:00+00:00",
        "link": link,
    })


def test_lead_story_is_clickable_when_link_present():
    html = board_v2._lead_story_html(_story_row("http://example.com/lead"))
    assert 'href="http://example.com/lead"' in html
    assert 'target="_blank"' in html
    assert "db-lead" in html


def test_side_story_is_clickable_when_link_present():
    html = board_v2._side_story_html(_story_row("http://example.com/side"))
    assert 'href="http://example.com/side"' in html
    assert 'target="_blank"' in html


def test_story_without_link_renders_plain_article():
    html = board_v2._lead_story_html(_story_row(link=""))
    assert "<a href" not in html
    assert "db-lead" in html


def test_story_link_is_escaped():
    html = board_v2._side_story_html(_story_row('http://x/"><script>'))
    assert "<script>" not in html
    assert "db-story" in html
