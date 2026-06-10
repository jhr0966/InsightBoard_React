"""수집 트리거 — 버튼/`?refresh=now` → 수집 현황 모달 플래그 + 모달 내 수집 실행."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


_FLAGS = ("_do_dm_collect", "_sc_collect_modal_pending", "_sc_collect_modal_result")


@pytest.fixture(autouse=True)
def reset_state():
    import streamlit as st
    st.query_params.clear()
    for k in ("_dm_refresh_toast", "persona", *_FLAGS):
        st.session_state.pop(k, None)
    yield
    st.query_params.clear()
    for k in ("_dm_refresh_toast", *_FLAGS):
        st.session_state.pop(k, None)


# ── 트리거 번역 — 버튼 pending / ?refresh=now → 모달 플래그 ──────────
# '지금 뉴스 수집' 버튼은 `_sc_collect_modal_pending` 을 세팅, 레거시
# `_do_dm_collect` pending / `?refresh=now` 딥링크는 `_consume_refresh_if_any` 가
# 모달 플래그로 번역한다. 실 수집은 모달 본문(_run_collect_for_modal)이 담당.

def test_collect_button_pending_translates_to_modal_flag():
    from ui import data_management_v2 as dm
    import streamlit as st

    st.session_state["_do_dm_collect"] = True
    with patch("scraping.run_daily.collect_batch") as mock_cb:
        assert dm._consume_refresh_if_any() is True
    mock_cb.assert_not_called()  # render 도중 동기 수집은 더 이상 안 함
    assert st.session_state.get("_sc_collect_modal_pending") is True
    # pending 은 1회 소비 (다음 run 에서 재번역 안 됨)
    assert "_do_dm_collect" not in st.session_state


def test_refresh_query_translates_to_modal_flag_and_strips_query():
    from ui import data_management_v2 as dm
    import streamlit as st

    st.query_params["refresh"] = "now"
    assert dm._consume_refresh_if_any() is True
    assert st.session_state.get("_sc_collect_modal_pending") is True
    assert "refresh" not in st.query_params
    # 쿼리가 제거됐고 pending 도 없으므로 재진입 시 noop (모달 플래그는 별개)
    assert dm._consume_refresh_if_any() is False


# ── _run_collect_for_modal — 실 수집 + 결과 dict ────────────────────

def test_run_collect_uses_persona_keywords():
    from ui import data_management_v2 as dm
    from scraping.run_daily import CollectionReport

    fake = CollectionReport(
        saved=[{"source": "naver", "keywords": ["비전 검사"], "count": 5, "path": "x.parquet"}],
        errors=[],
    )
    with patch("ui.board_v2._collect_keywords_for_persona",
               return_value=["비전 검사", "도장 검사"]) as mock_kw, \
         patch("scraping.run_daily.collect_batch", return_value=fake) as mock_cb:
        result = dm._run_collect_for_modal()

    mock_kw.assert_called_once()
    mock_cb.assert_called_once()
    args, kwargs = mock_cb.call_args
    assert args[0] == ["비전 검사", "도장 검사"]
    assert result["ok"] is True
    assert "2개 키워드" in result["message"]
    assert "5건" in result["message"]
    assert result["total_articles"] == 5
    assert result["total_files"] == 1


def test_run_collect_passes_on_step_and_updates_progress():
    """collect_batch 의 on_step 콜백이 progress 핸들을 갱신한다."""
    from ui import data_management_v2 as dm
    from scraping.run_daily import CollectionReport

    fake = CollectionReport(
        saved=[{"source": "naver", "keywords": ["X"], "count": 2, "path": "x"}],
        errors=[],
    )

    def _fake_collect(kws, *, on_step=None, **kwargs):
        if on_step:
            on_step("naver", "X", 2)
            on_step("google", "X", 0)
        return fake

    prog = MagicMock()
    with patch("ui.board_v2._collect_keywords_for_persona", return_value=["X"]), \
         patch("scraping.run_daily.collect_batch", side_effect=_fake_collect):
        result = dm._run_collect_for_modal(prog)
    assert result["ok"] is True
    assert prog.progress.call_count == 2
    # 진행 텍스트에 소스·키워드·건수
    _, kwargs = prog.progress.call_args_list[0]
    assert "naver" in kwargs.get("text", "") and "2건" in kwargs.get("text", "")


def test_run_collect_partial_errors_in_message():
    """일부 에러 + 일부 성공 → ok 결과 메시지에 '일부 오류 N건' + errors 목록."""
    from ui import data_management_v2 as dm
    from scraping.run_daily import CollectionReport

    fake = CollectionReport(
        saved=[{"source": "naver", "keywords": ["X"], "count": 3, "path": "x"}],
        errors=[{"source": "google", "keyword": "X", "error": "rate"}],
    )
    with patch("ui.board_v2._collect_keywords_for_persona", return_value=["X"]), \
         patch("scraping.run_daily.collect_batch", return_value=fake):
        result = dm._run_collect_for_modal()
    assert result["ok"] is True
    assert "일부 오류 1건" in result["message"]
    assert result["errors"] == ["google · X: rate"]


def test_run_collect_error_result_when_all_failed():
    """전부 실패(saved=[], errors=N) → ok=False + 첫 오류 메시지."""
    from ui import data_management_v2 as dm
    from scraping.run_daily import CollectionReport

    fake = CollectionReport(
        saved=[],
        errors=[{"source": "naver", "keyword": "X", "error": "boom"}],
    )
    with patch("ui.board_v2._collect_keywords_for_persona", return_value=["X"]), \
         patch("scraping.run_daily.collect_batch", return_value=fake):
        result = dm._run_collect_for_modal()
    assert result["ok"] is False
    assert "boom" in result["message"]
    assert result["errors"]


def test_run_collect_falls_back_to_default_keywords():
    """관심사가 비어도 스킵하지 않고 기본 키워드(자동화·AI)로 collect_batch 호출."""
    from ui import data_management_v2 as dm
    from scraping.run_daily import CollectionReport

    fake = CollectionReport(
        saved=[{"source": "tech", "keywords": [], "count": 4, "path": "t.parquet"}],
        errors=[],
    )
    with patch("ui.board_v2._collect_keywords_for_persona", return_value=[]), \
         patch("scraping.run_daily.collect_batch", return_value=fake) as mock_cb:
        result = dm._run_collect_for_modal()
    mock_cb.assert_called_once()
    assert mock_cb.call_args.args[0] == ["자동화", "AI"]
    assert result["ok"] is True
    assert "자동화" in result["message"] and "AI" in result["message"]


def test_run_collect_records_run_log_with_manual_trigger():
    from ui import data_management_v2 as dm
    from scraping.run_daily import CollectionReport

    fake = CollectionReport(saved=[], errors=[])
    with patch("ui.board_v2._collect_keywords_for_persona", return_value=["X"]), \
         patch("scraping.run_daily.collect_batch", return_value=fake), \
         patch("store.run_log.record_run") as mock_log:
        dm._run_collect_for_modal()
    mock_log.assert_called_once()
    assert mock_log.call_args.kwargs.get("trigger") == "manual"


def test_run_collect_always_clears_caches_even_on_collect_failure():
    """collect_batch 가 예외를 던져도 캐시는 무효화 + ok=False 결과."""
    from ui import data_management_v2 as dm

    with patch.object(dm._dm_stats, "clear") as c1, \
         patch.object(dm._sc_browse_records, "clear") as c2, \
         patch("ui.board_v2._collect_keywords_for_persona", return_value=["X"]), \
         patch("scraping.run_daily.collect_batch", side_effect=RuntimeError("net")):
        result = dm._run_collect_for_modal()
    c1.assert_called_once()
    c2.assert_called_once()
    assert result["ok"] is False
    assert "net" in result["message"]


# ── 수집 현황 모달 본문 — 결과 요약 렌더 + 재실행 가드 + 닫기 ─────────

def test_modal_body_renders_result_summary():
    from ui import data_management_v2 as dm
    import streamlit as st

    st.session_state["_sc_collect_modal_pending"] = True
    st.session_state["_sc_collect_modal_result"] = {
        "ok": True, "message": "✓ 2개 키워드로 7건 수집 (2개 파일).",
        "total_articles": 7, "total_files": 2, "n_keywords": 2,
        "used_default": False, "n_feeds": 1,
        "errors": ["tech · AITimes: timeout"],
    }
    captured: list[str] = []
    with patch("streamlit.html", side_effect=lambda s: captured.append(str(s))), \
         patch("streamlit.button", return_value=False):
        dm._collect_modal_body()
    joined = "".join(captured)
    assert "7건" in joined and "2개 파일" in joined        # 결과 메시지
    assert "수집 기사" in joined and "저장 파일" in joined  # KPI 라벨
    assert "오류 1건" in joined and "timeout" in joined     # 오류 목록


def test_modal_body_escapes_external_error_strings():
    """오류 문자열의 HTML 은 escape 되어 나간다 (XSS 방어)."""
    from ui import data_management_v2 as dm

    html_out = dm._collect_result_summary_html({
        "ok": False, "message": "<b>주의</b>", "total_articles": 0,
        "total_files": 0, "n_keywords": 0, "used_default": False,
        "n_feeds": 0, "errors": ["naver: <script>alert(1)</script>"],
    })
    assert "<script>" not in html_out
    assert "&lt;script&gt;" in html_out
    assert "<b>주의</b>" not in html_out


def test_modal_body_does_not_recollect_when_result_exists():
    """결과가 세션에 있으면 collect 재실행 금지(1회 실행 가드)."""
    from ui import data_management_v2 as dm
    import streamlit as st

    st.session_state["_sc_collect_modal_result"] = {
        "ok": True, "message": "✓", "total_articles": 1, "total_files": 1,
        "n_keywords": 1, "used_default": False, "n_feeds": 0, "errors": [],
    }
    with patch.object(dm, "_run_collect_for_modal") as mock_run, \
         patch("streamlit.html"), patch("streamlit.button", return_value=False):
        dm._collect_modal_body()
    mock_run.assert_not_called()


def test_modal_close_clears_flags_and_reruns():
    from ui import data_management_v2 as dm
    import streamlit as st

    st.session_state["_sc_collect_modal_pending"] = True
    st.session_state["_sc_collect_modal_result"] = {
        "ok": True, "message": "✓", "total_articles": 1, "total_files": 1,
        "n_keywords": 1, "used_default": False, "n_feeds": 0, "errors": [],
    }
    with patch("streamlit.html"), \
         patch("streamlit.button", return_value=True), \
         patch("streamlit.rerun") as mock_rerun:
        dm._collect_modal_body()
    assert "_sc_collect_modal_pending" not in st.session_state
    assert "_sc_collect_modal_result" not in st.session_state
    mock_rerun.assert_called_once()


def test_render_collect_modal_noop_without_flag():
    from ui import data_management_v2 as dm
    with patch("streamlit.dialog") as mock_dlg:
        dm._render_collect_modal_if_open()
    mock_dlg.assert_not_called()


def test_news_modal_skipped_while_collect_modal_pending():
    """수집 모달 pending 중에는 기사 모달을 띄우지 않는다 (dialog 1개/run 제한)."""
    from ui import data_management_v2 as dm
    import streamlit as st

    st.session_state["_sc_collect_modal_pending"] = True
    st.session_state["_sc_open_news"] = "https://x"
    with patch("streamlit.dialog") as mock_dlg:
        dm._render_news_modal_if_open()
    mock_dlg.assert_not_called()
    st.session_state.pop("_sc_open_news", None)


# ── 런 이력 → 모달 결과 재열람 (⚙ 수집 설정 [보기]) ─────────────────

_RUN_ENTRY = {
    "run_id": "20260610-080000-ab12",
    "ts": "2026-06-10T08:00:00+00:00",
    "trigger": "manual",
    "ok": True,
    "total_articles": 7,
    "total_files": 2,
    "duration_s": 12.3,
    "sources": [
        {"source": "naver", "count": 4, "keywords": ["자동화", "AI"], "ok": True},
        {"source": "google", "count": 2, "keywords": ["AI"], "ok": True},
        {"source": "myrss", "count": 1, "keywords": [], "ok": True},
    ],
    "error_sources": [],
    "errors": [],
}


def test_run_log_to_modal_result_full_entry():
    from ui import data_management_v2 as dm

    result = dm._run_log_to_modal_result(dict(_RUN_ENTRY))
    assert result["ok"] is True
    assert result["total_articles"] == 7
    assert result["total_files"] == 2
    assert result["n_keywords"] == 2          # 자동화·AI 합집합
    assert result["n_feeds"] == 1             # myrss (naver/google/tech 제외)
    assert result["errors"] == []
    assert result["from_log"] is True
    assert result["run_id"] == "20260610-080000-ab12"
    # 메시지에 시각·트리거·건수
    assert "06-10" in result["message"] and "08:00" in result["message"]
    assert "수동" in result["message"] and "7건" in result["message"]


def test_run_log_to_modal_result_errors_formatted():
    from ui import data_management_v2 as dm

    run = dict(_RUN_ENTRY, ok=False,
               errors=[{"source": "google", "keyword": "X", "error": "rate"}])
    result = dm._run_log_to_modal_result(run)
    assert result["ok"] is False
    assert result["errors"] == ["google · X: rate"]
    assert "오류 1건" in result["message"]


def test_run_log_to_modal_result_defends_missing_fields():
    """과거 로그(필드 누락)도 안전하게 변환 — ok 는 errors 유무로 유추."""
    from ui import data_management_v2 as dm

    result = dm._run_log_to_modal_result({})
    assert result["ok"] is True               # errors 없음 → 정상 취급
    assert result["total_articles"] == 0
    assert result["total_files"] == 0
    assert result["n_keywords"] == 0
    assert result["n_feeds"] == 0
    assert result["errors"] == []
    assert result["from_log"] is True

    # errors 만 있고 ok 누락 → 오류로 유추 + 문자열 에러도 수용
    result2 = dm._run_log_to_modal_result({"errors": ["boom"]})
    assert result2["ok"] is False
    assert result2["errors"] == ["boom"]


def test_open_run_result_modal_sets_flags_and_reruns():
    from ui import data_management_v2 as dm
    import streamlit as st

    with patch("streamlit.rerun") as mock_rerun:
        dm._open_run_result_modal(dict(_RUN_ENTRY))
    assert st.session_state.get("_sc_collect_modal_pending") is True
    result = st.session_state.get("_sc_collect_modal_result")
    assert result and result["from_log"] is True and result["total_articles"] == 7
    mock_rerun.assert_called_once()


def test_history_view_button_opens_modal_without_recollect():
    """[📡 마지막 수집 결과 보기] 클릭 → 플래그 세팅 + 모달이 collect 없이 로그 결과 표시."""
    from ui import data_management_v2 as dm
    import streamlit as st

    # 1) 이력 버튼 클릭 — 첫 st.button(마지막 결과 보기)만 True
    def _btn(label, *a, **k):
        return "마지막 수집 결과 보기" in str(label)

    with patch("store.run_log.load_runs", return_value=[dict(_RUN_ENTRY)]), \
         patch("streamlit.button", side_effect=_btn), \
         patch("streamlit.caption"), patch("streamlit.rerun") as mock_rerun:
        dm._render_run_history_view_buttons()
    assert st.session_state.get("_sc_collect_modal_pending") is True
    assert st.session_state.get("_sc_collect_modal_result", {}).get("from_log") is True
    mock_rerun.assert_called_once()

    # 2) 모달 본문 — 결과가 이미 있으므로 collect_batch 재실행 금지, 로그 결과 표시
    captured: list[str] = []
    with patch("scraping.run_daily.collect_batch") as mock_cb, \
         patch.object(dm, "_run_collect_for_modal") as mock_run, \
         patch("streamlit.html", side_effect=lambda s: captured.append(str(s))), \
         patch("streamlit.button", return_value=False):
        dm._collect_modal_body()
    mock_cb.assert_not_called()
    mock_run.assert_not_called()
    joined = "".join(captured)
    assert "지난 수집 결과" in joined and "7건" in joined


def test_history_view_buttons_noop_without_runs():
    from ui import data_management_v2 as dm
    import streamlit as st

    with patch("store.run_log.load_runs", return_value=[]), \
         patch("streamlit.button") as mock_btn, \
         patch("streamlit.caption") as mock_cap:
        dm._render_run_history_view_buttons()
    mock_btn.assert_not_called()
    mock_cap.assert_called_once()
    assert "_sc_collect_modal_pending" not in st.session_state


# ── 토스트 렌더 — kind 별 색상 (다른 경로가 여전히 사용) ─────────────

def test_refresh_toast_renders_ok_message():
    from ui import data_management_v2 as dm
    import streamlit as st
    captured = []
    with patch("streamlit.html", side_effect=lambda s: captured.append(s)):
        st.session_state["_dm_refresh_toast"] = ("ok", "✓ 잘 됐어요")
        dm._render_refresh_toast_if_needed()
    assert captured and "잘 됐어요" in captured[0]
    assert "_dm_refresh_toast" not in st.session_state


def test_refresh_toast_renders_warn_message():
    from ui import data_management_v2 as dm
    import streamlit as st
    captured = []
    with patch("streamlit.html", side_effect=lambda s: captured.append(s)):
        st.session_state["_dm_refresh_toast"] = ("warn", "ℹ️ 경고")
        dm._render_refresh_toast_if_needed()
    assert captured and "경고" in captured[0]
    # warn 색상 — 노란색 (#FFFBEB)
    assert "#FFFBEB" in captured[0]


def test_refresh_toast_backward_compat_true_payload():
    """이전 코드가 True 만 set 한 경우도 기본 메시지로 렌더."""
    from ui import data_management_v2 as dm
    import streamlit as st
    captured = []
    with patch("streamlit.html", side_effect=lambda s: captured.append(s)):
        st.session_state["_dm_refresh_toast"] = True
        dm._render_refresh_toast_if_needed()
    assert captured and "캐시" in captured[0]
