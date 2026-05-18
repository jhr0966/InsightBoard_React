from __future__ import annotations

from ui import sola_tab


def test_workspace_cards_html_shows_work_types_and_counts():
    html = sola_tab._workspace_cards_html(
        news_count=12,
        roadmap_count=5,
        proposal_count=2,
        ready=True,
    )

    assert html.startswith('<div class="action-grid">')
    assert "뉴스 요약" in html
    assert "자동화 과제 제안서" in html
    assert "저장된 제안서 2건" in html
    assert html.count('<div class="action-card ') == 4


def test_workspace_readiness_html_warns_missing_items():
    html = sola_tab._workspace_readiness_html(ready=False, news_count=0, roadmap_count=3)

    assert "SOLA 실행 전 준비가 필요합니다" in html
    assert "뉴스 수집" in html
    assert "LLM 설정" in html
    assert "로드맵 업로드" not in html


def test_workspace_readiness_html_ok_when_ready():
    html = sola_tab._workspace_readiness_html(ready=True, news_count=3, roadmap_count=2)

    assert "SOLA 산출물 생성 준비 완료" in html
    assert 'class="status-card ok"' in html


def test_bookmark_workbench_state_routes_to_workbench():
    from ui import bookmarks_tab

    state = bookmarks_tab._workbench_state_for_bookmark("abc")

    assert state == {
        "app_area": "🤖 SOLA 작업실",
        "pw_select": "bm:abc",
        "pw_active_source": "",
        "pw_mode": "✏️ 수정",
    }
