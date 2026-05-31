"""v2 화면 binder 회귀 베이크.

각 placeholder helper 가:
  1) 빈 데이터 상태에서 예외 없이 friendly empty 카드를 반환
  2) 합성 데이터 주입 시 placeholder 가 모두 채워지고 시안 클래스가 살아있음

st.html 경계는 다루지 않는다 (Streamlit runtime 의존 → 통합 테스트로 분리).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pandas as pd

from persona.schema import Persona


# ── 1) 빈 데이터 — 모든 helper 가 예외 없이 friendly 카드 반환 ──

def test_board_empty_state_helpers_dont_raise():
    from ui import board_v2

    with patch.object(board_v2._news_db, "load_news_for_days", return_value=pd.DataFrame()), \
         patch.object(board_v2, "_load_roadmap", return_value=pd.DataFrame()):
        # cache clear (other tests can populate)
        for fn in (
            board_v2._opportunities_html,
            board_v2._board_stories_html,
            board_v2._brief_html,
            board_v2._board_trend,
            board_v2._board_matrix_html,
        ):
            if hasattr(fn, "clear"):
                fn.clear()

        assert "기회" in board_v2._opportunities_html() or "data" in board_v2._opportunities_html().lower()
        assert "뉴스" in board_v2._board_stories_html()
        brief = board_v2._brief_html()
        assert set(brief.keys()) == {"summary", "list", "cites", "cta"}
        assert brief["cta"] == ""  # 빈 데이터에선 CTA 도 비어있음
        trend = board_v2._board_trend()
        assert trend["empty"] and not trend["svg_paths"]
        assert "매트릭스" in board_v2._board_matrix_html() or "기회" in board_v2._board_matrix_html()

        p = Persona()
        kw = board_v2._board_kw_mgr_html(p)
        assert "키워드" in kw or "데이터" in kw


def test_insights_empty_state_helpers_dont_raise():
    from ui import insights_v2

    with patch.object(insights_v2._news_db, "load_news_for_days", return_value=pd.DataFrame()), \
         patch.object(insights_v2, "_load_roadmap", return_value=pd.DataFrame()):
        for fn in (
            insights_v2._tkw_list_html,
            insights_v2._ia_chart_parts,
            insights_v2._ia_matrix_svg,
            insights_v2._ia_process_map_html,
        ):
            if hasattr(fn, "clear"):
                fn.clear()

        assert "키워드" in insights_v2._tkw_list_html()
        chart = insights_v2._ia_chart_parts()
        assert chart["legend"] == "" and chart["pill"] == ""
        assert "트렌드" in chart["svg"] or "데이터" in chart["svg"]
        assert "매트릭스" in insights_v2._ia_matrix_svg() or "기회" in insights_v2._ia_matrix_svg()
        assert "매핑" in insights_v2._ia_process_map_html() or "로드맵" in insights_v2._ia_process_map_html()


# ── 2) 합성 데이터 — 시안 클래스가 살아있음 ──

def _synthetic_news_30d() -> pd.DataFrame:
    now = datetime.now(timezone.utc)
    rows = []
    for d in range(30):
        t = (now - timedelta(days=d)).isoformat()
        for _ in range(3):
            rows.append({
                "published_at": t,
                "collected_at": t,
                "title": "도장 결함 검사 막두께 자동 측정",
                "summary": "AI 비전 분석",
                "keywords": "도장 결함 검사, AI 비전, 머신비전",
                "keywords_llm": "도장 결함 검사, AI 비전",
                "source": "AI Times",
                "link": f"http://example.com/{d}-{_}",
            })
    return pd.DataFrame(rows)


def _synthetic_cells() -> pd.DataFrame:
    return pd.DataFrame([
        {"dept": "도장", "lv3": "비전 검사", "cell_score": 95, "avg_score": 12,
         "matched_news": 40, "matched_tasks": 18, "sample_tasks": "AI 도막 검사",
         "sample_news": "현대重 PoC 38% 절감"},
        {"dept": "용접", "lv3": "비드 검사", "cell_score": 70, "avg_score": 9,
         "matched_news": 28, "matched_tasks": 12, "sample_tasks": "", "sample_news": ""},
        {"dept": "의장", "lv3": "부품 인식", "cell_score": 50, "avg_score": 7,
         "matched_news": 18, "matched_tasks": 8, "sample_tasks": "", "sample_news": ""},
    ])


def test_board_trend_with_data_emits_4_series_paths():
    from ui import board_v2

    news = _synthetic_news_30d()
    with patch.object(board_v2._news_db, "load_news_for_days", return_value=news):
        board_v2._board_trend.clear() if hasattr(board_v2._board_trend, "clear") else None
        board_v2._weekly_keyword_series.clear() if hasattr(board_v2._weekly_keyword_series, "clear") else None

        trend = board_v2._board_trend()
        assert trend["xticks"].count("<span>") == 8
        assert trend["kw_list"].count("<li") >= 1
        assert "stroke='#2563EB'" in trend["svg_paths"]


def test_board_matrix_with_data_emits_6_bubbles():
    from ui import board_v2

    with patch.object(board_v2._news_db, "load_news_for_days", return_value=pd.DataFrame([{"a": 1}])), \
         patch.object(board_v2, "_load_roadmap", return_value=pd.DataFrame([{"a": 1}])), \
         patch.object(board_v2, "_score_cells", return_value=_synthetic_cells()):
        board_v2._board_matrix_html.clear()
        html = board_v2._board_matrix_html()
        assert html.count("db-mx-bubble") == 3
        assert "db-mx-q-strong" in html
        assert "도장" in html


def test_board_kw_mgr_with_persona_emits_both_groups():
    from ui import board_v2

    news = _synthetic_news_30d()
    p = Persona(dept="도장1팀", interest_tasks=["막두께 측정"], interest_lv3=["비전 검사"])
    with patch.object(board_v2._news_db, "load_news_for_days", return_value=news):
        html = board_v2._board_kw_mgr_html(p)
        assert "SOLA 자동 추출" in html
        assert "내가 추가" in html
        assert "막두께 측정" in html


def test_insights_process_map_with_data_emits_top_card():
    from ui import insights_v2

    cells = _synthetic_cells()
    with patch.object(insights_v2._news_db, "load_news_for_days", return_value=pd.DataFrame([{"a": 1}])), \
         patch.object(insights_v2, "_load_roadmap", return_value=pd.DataFrame([{"a": 1}])), \
         patch.object(insights_v2, "_score_cells", return_value=cells), \
         patch(
             "ui.board_v2._weekly_keyword_series",
             return_value=(["W1", "W2", "W3", "W4", "이번주"],
                           [{"name": "비전 검사", "counts": [5, 8, 10, 15, 20]}]),
         ):
        insights_v2._ia_process_map_html.clear()
        html = insights_v2._ia_process_map_html()
        assert "ia-pcard-top" in html
        assert "★ 최적 매칭" in html
        assert "비전 검사" in html
        assert html.count('class="ia-pcard') >= 3


def test_insights_chart_with_data_emits_legend_and_pill():
    from ui import insights_v2, board_v2

    with patch(
        "ui.board_v2._weekly_keyword_series",
        return_value=(
            ["W1", "W2", "W3", "W4", "이번주"],
            [
                {"name": "비전 검사", "counts": [5, 8, 12, 18, 25]},
                {"name": "협동 로봇", "counts": [3, 5, 7, 10, 12]},
                {"name": "예지보전", "counts": [2, 3, 4, 6, 8]},
                {"name": "디지털트윈", "counts": [1, 2, 3, 4, 5]},
                {"name": "외골격", "counts": [0, 1, 1, 2, 3]},
            ],
        ),
    ):
        insights_v2._ia_chart_parts.clear()
        chart = insights_v2._ia_chart_parts()
        assert "ia-chart-svg" in chart["svg"]
        assert chart["legend"].count("ia-lg-mute") == 2
        assert "비전 검사" in chart["legend"]
        assert "▲" in chart["pill"] or "▼" in chart["pill"]


def test_sola_handoff_href_encodes_payload():
    from ui.board_v2 import _sola_handoff_href

    href = _sola_handoff_href("opp", dept="도장 1팀", lv3="비전 검사")
    # 5-nav area + from kind + payload 모두 포함
    assert "app_area=" in href
    assert "SOLA" in href  # 한글이 URL 인코딩된 형태로
    assert "from=opp" in href
    assert "dept=" in href and "lv3=" in href
    # 빈 payload 는 생략
    assert _sola_handoff_href("brief").count("&") == 1  # app_area + from


def test_opp_card_discuss_links_to_sola_with_from_opp():
    from ui import board_v2

    row = pd.Series({
        "dept": "도장", "lv3": "비전 검사", "cell_score": 95,
        "matched_news": 40, "matched_tasks": 18,
        "sample_tasks": "AI 도막 검사", "sample_news": "",
    })
    html = board_v2._opp_card_html(row)
    assert 'class="db-prop-discuss"' in html
    assert "from=opp" in html
    assert "dept=" in html and "lv3=" in html
    # 기존 disabled <button> 자취 없음
    assert "<button class=\"db-prop-discuss\"" not in html


def test_matrix_detail_cta_links_to_sola_with_from_matrix():
    from ui import board_v2

    cells = _synthetic_cells()
    with patch.object(board_v2._news_db, "load_news_for_days", return_value=pd.DataFrame([{"a": 1}])), \
         patch.object(board_v2, "_load_roadmap", return_value=pd.DataFrame([{"a": 1}])), \
         patch.object(board_v2, "_score_cells", return_value=cells):
        board_v2._board_matrix_html.clear()
        html = board_v2._board_matrix_html()
    assert 'class="db-mx-cta"' in html
    assert "from=matrix" in html
    # disabled button 자취 없음
    assert "<button class=\"db-mx-cta\"" not in html


def test_ia_process_map_detail_links_to_sola_with_from_ia_map():
    from ui import insights_v2

    cells = _synthetic_cells()
    with patch.object(insights_v2._news_db, "load_news_for_days", return_value=pd.DataFrame([{"a": 1}])), \
         patch.object(insights_v2, "_load_roadmap", return_value=pd.DataFrame([{"a": 1}])), \
         patch.object(insights_v2, "_score_cells", return_value=cells), \
         patch(
             "ui.board_v2._weekly_keyword_series",
             return_value=(["W1", "W2", "W3", "W4", "이번주"],
                           [{"name": "비전 검사", "counts": [5, 8, 10, 15, 20]}]),
         ):
        insights_v2._ia_process_map_html.clear()
        html = insights_v2._ia_process_map_html()
    assert 'class="ia-pc-detail"' in html
    assert html.count("from=ia_map") >= 3
    assert "<button class=\"ia-pc-detail\"" not in html


def test_board_brief_cta_routes_to_sola_with_from_brief():
    """A.7: brief CTA 가 SOLA 작업실 area + from=brief 로 라우팅."""
    from ui import board_v2
    import streamlit as st

    news = _synthetic_news_30d()
    with patch.object(board_v2._news_db, "load_news_for_days", return_value=news), \
         patch.object(board_v2, "_load_roadmap", return_value=pd.DataFrame([{"a": 1}])), \
         patch.object(board_v2, "_score_matches", return_value=pd.DataFrame()):
        board_v2._brief_html.clear() if hasattr(board_v2._brief_html, "clear") else None
        brief = board_v2._brief_html()

    assert brief["cta"]
    # SOLA 작업실 area + from=brief 가 URL 에 포함
    assert "SOLA" in brief["cta"]
    assert "from=brief" in brief["cta"]
    # session_state 에 인계 아이템 보관 (다음 area 에서 소비)
    items = st.session_state.get("_board_brief_items") or []
    assert len(items) >= 1
    assert all("title" in it for it in items)


def test_sola_composer_prefill_default_when_no_query():
    """from 쿼리 없으면 빈 prefill + 기본 placeholder + 미첨부 pins."""
    from ui import sola_workshop_v2
    import streamlit as st

    st.query_params.clear()
    prefill, placeholder, pins = sola_workshop_v2._composer_prefill()
    assert prefill == ""
    assert "무엇을 도와드릴까요" in placeholder
    assert "컨텍스트 미첨부" in pins


def test_sola_composer_prefill_from_opp():
    """?from=opp&dept&lv3 → 자동화 기회 초안 텍스트 + 컨텍스트 pins."""
    from ui import sola_workshop_v2
    import streamlit as st

    st.query_params.clear()
    st.query_params["from"] = "opp"
    st.query_params["dept"] = "도장1팀"
    st.query_params["lv3"] = "비전 검사"
    try:
        prefill, placeholder, pins = sola_workshop_v2._composer_prefill()
        assert "도장1팀 · 비전 검사" in prefill
        assert "자동화 기회" in prefill
        assert "🎯" in pins
        assert "도장1팀" in pins
    finally:
        st.query_params.clear()


def test_sola_composer_prefill_from_matrix():
    from ui import sola_workshop_v2
    import streamlit as st

    st.query_params.clear()
    st.query_params["from"] = "matrix"
    st.query_params["dept"] = "용접"
    st.query_params["lv3"] = "비드 검사"
    try:
        prefill, _placeholder, pins = sola_workshop_v2._composer_prefill()
        assert "용접 · 비드 검사" in prefill
        assert "매트릭스 1위" in prefill
        assert "🧭" in pins
    finally:
        st.query_params.clear()


def test_sola_composer_prefill_from_ia_map():
    from ui import sola_workshop_v2
    import streamlit as st

    st.query_params.clear()
    st.query_params["from"] = "ia_map"
    st.query_params["dept"] = "의장"
    st.query_params["lv3"] = "부품 인식"
    try:
        prefill, _placeholder, pins = sola_workshop_v2._composer_prefill()
        assert "의장 · 부품 인식" in prefill
        assert "공정의 현재 상황" in prefill
        assert "🔎" in pins
    finally:
        st.query_params.clear()


def test_sola_composer_prefill_from_brief_uses_session_items():
    from ui import sola_workshop_v2
    import streamlit as st

    st.query_params.clear()
    st.query_params["from"] = "brief"
    st.session_state["_board_brief_items"] = [
        {"title": "도장 비전 PoC 38% 절감"},
        {"title": "VOC 예측 디지털 트윈"},
        {"title": "협동 로봇 안전 인증"},
    ]
    try:
        prefill, _placeholder, pins = sola_workshop_v2._composer_prefill()
        assert "오늘 보드의 다음 3건" in prefill
        assert "도장 비전 PoC" in prefill
        assert "VOC 예측" in prefill
        assert "📊" in pins
        assert "뉴스 3" in pins
    finally:
        st.query_params.clear()
        st.session_state.pop("_board_brief_items", None)


def test_sola_composer_prefill_brief_empty_session_falls_back():
    """from=brief 인데 session 비어있으면 default 미첨부 pins."""
    from ui import sola_workshop_v2
    import streamlit as st

    st.query_params.clear()
    st.query_params["from"] = "brief"
    st.session_state.pop("_board_brief_items", None)
    try:
        prefill, _placeholder, pins = sola_workshop_v2._composer_prefill()
        assert prefill == ""
        assert "컨텍스트 미첨부" in pins
    finally:
        st.query_params.clear()


def test_command_palette_renders_5_nav_rows():
    """⌘K 팔레트가 5-nav + 페르소나 편집 = 6개 row 렌더."""
    from ui import app_shell
    from unittest.mock import patch

    captured = []

    def fake_html(s, *args, **kwargs):
        captured.append(s)

    with patch("streamlit.html", side_effect=fake_html):
        app_shell.render_command_palette()

    assert len(captured) == 1
    html = captured[0]
    # 5 nav rows + 1 persona row
    assert html.count('class="v2-cmdk-row"') == 6
    # render_command_palette 는 _NAV_ITEMS 의 title (이모지 없음) 만 노출, area_key (이모지 포함)는
    # href 쿼리스트링에 URL 인코딩되어 들어감.
    assert "오늘의 보드" in html
    assert "SOLA 작업실" in html
    assert "페르소나 편집" in html
    # area_key 가 quote 되어 href 에 포함
    from urllib.parse import quote
    assert quote("📊 오늘의 보드") in html
    # checkbox + backdrop + modal 마크업
    assert 'id="v2-cmdk"' in html
    assert 'class="v2-cmdk-backdrop"' in html
    assert 'class="v2-cmdk-modal"' in html


def test_archive_action_href_builds_correct_url():
    from ui import archive_v2

    href = archive_v2._archive_action_href("adopt", "bm_abc123")
    assert "app_area=" in href and "%EC%82%B0%EC%B6%9C%EB%AC%BC" in href  # quote('산출물')
    assert "action=adopt" in href
    assert "bm_id=bm_abc123" in href


def test_archive_consume_action_invokes_set_status_and_strips_query():
    from ui import archive_v2
    from unittest.mock import patch
    import streamlit as st

    st.query_params.clear()
    st.query_params["action"] = "adopt"
    st.query_params["bm_id"] = "bm_x"

    with patch.object(archive_v2.bookmarks_store, "set_status", return_value=True) as p:
        result = archive_v2._consume_action_if_any()

    assert result == ("adopted", "bm_x")
    p.assert_called_once_with("bm_x", "adopted")
    # 1회 소비 후 query strip — 새로고침으로 액션 재실행 방지
    assert "action" not in st.query_params
    assert "bm_id" not in st.query_params


def test_archive_edit_handoff_href_carries_bm_and_title():
    from ui import archive_v2
    from store.bookmarks import Bookmark

    bm = Bookmark(id="bm_99", type="proposal", title="도장 PoC 제안서",
                  content="x", tags=[], created_at="2026-05-01T00:00:00+00:00")
    href = archive_v2._edit_handoff_href(bm)
    assert "from=edit" in href
    assert "bm_id=bm_99" in href
    assert "title=" in href
    assert "SOLA" in href or "%F0%9F%A4%96" in href


def test_sola_composer_prefill_from_edit():
    from ui import sola_workshop_v2
    import streamlit as st

    st.query_params.clear()
    st.query_params["from"] = "edit"
    st.query_params["bm_id"] = "bm_99"
    st.query_params["title"] = "도장 PoC 제안서"
    try:
        prefill, _ph, pins = sola_workshop_v2._composer_prefill()
        assert "도장 PoC 제안서" in prefill
        assert "이어서 수정" in prefill
        assert "📦 기존 제안서" in pins
    finally:
        st.query_params.clear()


def test_archive_consume_action_noop_when_action_missing():
    from ui import archive_v2
    import streamlit as st

    st.query_params.clear()
    assert archive_v2._consume_action_if_any() is None

    st.query_params["action"] = "unknown_verb"
    st.query_params["bm_id"] = "bm_y"
    try:
        assert archive_v2._consume_action_if_any() is None
        # 알 수 없는 action 은 query 유지 (디버깅 용)
        assert "action" in st.query_params
    finally:
        st.query_params.clear()


def test_data_management_refresh_clears_caches_and_sets_toast():
    from ui import data_management_v2
    from unittest.mock import patch
    from scraping.run_daily import CollectionReport
    import streamlit as st

    st.query_params.clear()
    st.session_state.pop("_dm_refresh_toast", None)
    st.query_params["refresh"] = "now"

    # 캐시 clear 가 호출되는지 + collect_batch 가 호출되는지 mock
    fake_report = CollectionReport(
        saved=[{"source": "naver", "keywords": ["X"], "count": 3, "path": "x.parquet"}],
        errors=[],
    )
    targets = [
        data_management_v2._dm_stats,
        data_management_v2._ingest_jobs_html,
    ]
    with patch.object(targets[0], "clear") as c1, \
         patch.object(targets[1], "clear") as c2, \
         patch("ui.board_v2._collect_keywords_for_persona", return_value=["AI 비전"]), \
         patch("scraping.run_daily.collect_batch", return_value=fake_report) as mock_cb:
        assert data_management_v2._consume_refresh_if_any() is True
        c1.assert_called_once()
        c2.assert_called_once()
        mock_cb.assert_called_once()

    toast = st.session_state.get("_dm_refresh_toast")
    assert isinstance(toast, tuple) and toast[0] == "ok"
    assert "1개 키워드" in toast[1]
    assert "refresh" not in st.query_params

    # 재진입(쿼리 없음) 시 noop
    assert data_management_v2._consume_refresh_if_any() is False


def test_refresh_warn_toast_when_persona_has_no_keywords():
    """페르소나 관심사 없을 때 → collect 스킵 + warn 토스트."""
    from ui import data_management_v2
    from unittest.mock import patch
    import streamlit as st

    st.query_params.clear()
    st.session_state.pop("_dm_refresh_toast", None)
    st.query_params["refresh"] = "now"

    with patch("ui.board_v2._collect_keywords_for_persona", return_value=[]), \
         patch("scraping.run_daily.collect_batch") as mock_cb:
        data_management_v2._consume_refresh_if_any()
    mock_cb.assert_not_called()
    toast = st.session_state.get("_dm_refresh_toast")
    assert isinstance(toast, tuple) and toast[0] == "warn"


def test_refresh_error_toast_on_collect_exception():
    """collect_batch 가 예외를 던지면 error 토스트."""
    from ui import data_management_v2
    from unittest.mock import patch
    import streamlit as st

    st.query_params.clear()
    st.session_state.pop("_dm_refresh_toast", None)
    st.query_params["refresh"] = "now"

    with patch("ui.board_v2._collect_keywords_for_persona", return_value=["X"]), \
         patch("scraping.run_daily.collect_batch", side_effect=RuntimeError("net down")):
        data_management_v2._consume_refresh_if_any()
    toast = st.session_state.get("_dm_refresh_toast")
    assert isinstance(toast, tuple) and toast[0] == "error"
    assert "net down" in toast[1]


def test_board_matrix_label_ellipsis_when_too_long():
    from ui import board_v2

    cells = pd.DataFrame([
        {"dept": "도장", "lv3": "초장초장초장초장초장초장초장초장", "cell_score": 95,
         "matched_news": 40, "matched_tasks": 18, "sample_tasks": "", "sample_news": ""},
    ])
    with patch.object(board_v2._news_db, "load_news_for_days", return_value=pd.DataFrame([{"a": 1}])), \
         patch.object(board_v2, "_load_roadmap", return_value=pd.DataFrame([{"a": 1}])), \
         patch.object(board_v2, "_score_cells", return_value=cells):
        board_v2._board_matrix_html.clear()
        html = board_v2._board_matrix_html()
    # 12자 cap + … 추가 — '초장' × 8 = 16자 → 12자 + …
    assert "…" in html


def test_matrix_dept_colors_shared_single_dict():
    """board_v2.MATRIX_DEPT_COLORS 가 insights matrix 에서 사용되는지 import 경로 검증."""
    from ui import board_v2
    assert isinstance(board_v2.MATRIX_DEPT_COLORS, dict)
    # 5 부서 색상
    assert {"도장", "용접", "의장", "조립", "절단"}.issubset(set(board_v2.MATRIX_DEPT_COLORS.keys()))
    assert board_v2.MATRIX_DEPT_FALLBACK.startswith("#")


def test_insights_matrix_with_data_emits_halo():
    from ui import insights_v2

    cells = _synthetic_cells()
    with patch.object(insights_v2._news_db, "load_news_for_days", return_value=pd.DataFrame([{"a": 1}])), \
         patch.object(insights_v2, "_load_roadmap", return_value=pd.DataFrame([{"a": 1}])), \
         patch.object(insights_v2, "_score_cells", return_value=cells):
        insights_v2._ia_matrix_svg.clear()
        svg = insights_v2._ia_matrix_svg()
        # 1위 cell halo dashed circle
        assert svg.count("stroke-dasharray='3 3'") >= 1
        assert "ia-mtx-svg" in svg
        assert "★ PoC 후보 영역" in svg
