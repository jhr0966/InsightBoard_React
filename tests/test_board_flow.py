from __future__ import annotations

import pandas as pd

from ui import board_tab


def test_insight_flow_html_marks_active_steps():
    html = board_tab._insight_flow_html(
        news_ready=True,
        roadmap_ready=True,
        has_opportunities=False,
    )

    assert html.startswith('<div class="step-guide">')
    assert html.count('class="step-item active"') == 2
    assert "트렌드 확인" in html
    assert "SOLA 제안" in html


def test_opportunity_to_sola_state_primes_navigation_and_filters():
    row = {"dept": "생산기술", "lv3": "용접"}

    state = board_tab._opportunity_to_sola_state(row)

    assert state == {
        "app_area": "🤖 SOLA 작업실",
        "sola_mode": "자동화 과제 제안서",
        "prop_dept": "생산기술",
        "prop_lv3": "용접",
        "board_dept": "생산기술",
        "board_lv3": "용접",
    }


def test_opportunity_flow_context_includes_top_candidates():
    cells = pd.DataFrame([
        {
            "dept": "생산기술",
            "lv3": "용접",
            "cell_score": 7.5,
            "sample_tasks": "용접 자동화",
            "sample_news": "로봇 도입",
        }
    ])

    ctx = board_tab._opportunity_flow_context(cells)

    assert "자동화 기회 후보" in ctx
    assert "생산기술 / 용접 score=7.5" in ctx
    assert "tasks=용접 자동화" in ctx


def test_opportunity_flow_context_empty():
    assert board_tab._opportunity_flow_context(pd.DataFrame()) == "자동화 기회 후보: 없음"
