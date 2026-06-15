"""Phase B — 제안서 엔진 복원: 생성(propose) → 보관함 저장 루프.

끊겨 있던 제품 핵심 흐름(기회 → 제안서 생성 → 산출물 보관함)을 검증.
LLM·디스크·streamlit rerun 은 모킹/격리.
"""
from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest

from persona.schema import Persona
from store.bookmarks import Bookmark
from ui import sola_workshop_v2 as sw


@pytest.fixture
def isolated_bookmarks(tmp_path, monkeypatch):
    """bookmarks 가 임시 파일을 쓰도록 격리."""
    bdir = tmp_path / "bookmarks"
    bdir.mkdir(parents=True, exist_ok=True)
    from store import bookmarks as bm
    from store.repository import JsonlRepository
    # 영구화는 repository seam 경유 → 전용 tmp 파일로 향하는 repo 주입.
    repo = JsonlRepository("bookmarks")
    monkeypatch.setattr(repo, "_path", lambda: bdir / "items.jsonl")
    monkeypatch.setattr(bm, "_repo", repo)
    yield bm


@pytest.fixture(autouse=True)
def _clean_state():
    import streamlit as st
    for k in ("_do_generate_proposal", "_do_save_proposal", "_sola_action_toast"):
        st.session_state.pop(k, None)
    st.query_params.clear()
    yield
    for k in ("_do_generate_proposal", "_do_save_proposal", "_sola_action_toast"):
        st.session_state.pop(k, None)
    st.query_params.clear()


# ── _related_news_df ────────────────────────────────────────

def test_related_news_df_empty_when_no_news(monkeypatch):
    from store import news_db
    monkeypatch.setattr(news_db, "load_news_for_days", lambda days: pd.DataFrame())
    out = sw._related_news_df("도장", "비전 검사")
    assert out.empty


def test_related_news_df_falls_back_to_recent_when_no_match(monkeypatch):
    news = pd.DataFrame([
        {"title": "무관 뉴스", "summary": "xyz", "link": "http://a", "keywords": ""},
    ])
    from store import news_db
    monkeypatch.setattr(news_db, "load_news_for_days", lambda days: news)
    # 매칭 0 → 최근 뉴스 폴백 (빈 결과로 사라지지 않음)
    out = sw._related_news_df("도장", "비전 검사", limit=8)
    assert not out.empty


# ── _consume_generate_proposal_if_any ───────────────────────

def test_generate_proposal_appends_user_and_assistant(monkeypatch):
    import streamlit as st
    st.session_state["_do_generate_proposal"] = {"dept": "도장", "lv3": "비전 검사", "kind": "opp"}

    appended: list[tuple[str, str]] = []
    monkeypatch.setattr(sw, "_append_message", lambda role, content: appended.append((role, content)))
    monkeypatch.setattr(sw, "_related_news_df", lambda d, l, **k: pd.DataFrame([{"title": "t", "link": "x"}]))
    monkeypatch.setattr(sw.sola_propose, "propose_for_task",
                        lambda task, news_df, **k: "## 자동화 과제 제안서\n- 과제명: 도장 비전 검사")

    with patch("streamlit.rerun"), patch("streamlit.spinner"):
        sw._consume_generate_proposal_if_any(Persona(name="홍길동", team="A팀"))

    roles = [r for r, _ in appended]
    assert roles == ["user", "assistant"]
    assert "비전 검사" in appended[0][1]            # user 요청에 타깃 포함
    assert "제안서" in appended[1][1]               # assistant = 생성된 제안서
    toast = st.session_state.get("_sola_action_toast")
    assert toast and toast[0] == "ok" and "근거 뉴스 1건" in toast[1]


def test_generate_proposal_passes_persona_and_task(monkeypatch):
    import streamlit as st
    st.session_state["_do_generate_proposal"] = {"dept": "용접", "lv3": "비드 검사", "kind": "matrix"}
    captured = {}

    def _fake_propose(task, news_df, **kwargs):
        captured["task"] = task
        captured["persona"] = kwargs.get("persona")
        return "초안"

    monkeypatch.setattr(sw, "_append_message", lambda *a, **k: None)
    monkeypatch.setattr(sw, "_related_news_df", lambda d, l, **k: pd.DataFrame())
    monkeypatch.setattr(sw.sola_propose, "propose_for_task", _fake_propose)

    with patch("streamlit.rerun"), patch("streamlit.spinner"):
        sw._consume_generate_proposal_if_any(Persona(name="박", team="생기팀"))

    assert captured["task"]["dept"] == "용접"
    assert captured["task"]["lv3"] == "비드 검사"
    assert captured["persona"] is not None and captured["persona"].team == "생기팀"


def test_generate_proposal_noop_when_no_pending(monkeypatch):
    called = []
    monkeypatch.setattr(sw, "_append_message", lambda *a, **k: called.append(1))
    with patch("streamlit.rerun") as r:
        sw._consume_generate_proposal_if_any(Persona())
    assert called == [] and r.call_count == 0


def test_generate_proposal_error_surfaces_as_assistant_message(monkeypatch):
    import streamlit as st
    st.session_state["_do_generate_proposal"] = {"dept": "도장", "lv3": "x", "kind": "opp"}
    appended: list[tuple[str, str]] = []
    monkeypatch.setattr(sw, "_append_message", lambda role, content: appended.append((role, content)))
    monkeypatch.setattr(sw, "_related_news_df", lambda d, l, **k: pd.DataFrame())

    def _boom(*a, **k):
        raise RuntimeError("LLM down")

    monkeypatch.setattr(sw.sola_propose, "propose_for_task", _boom)
    with patch("streamlit.rerun"), patch("streamlit.spinner"):
        sw._consume_generate_proposal_if_any(Persona())
    assert any("제안서 생성 실패" in c for r, c in appended if r == "assistant")
    assert st.session_state.get("_sola_action_toast")[0] == "error"


# ── _consume_save_proposal_if_any ───────────────────────────

def _fake_thread(title="도장 제안서"):
    from store import sola_threads
    return sola_threads.Thread(
        id="th_x", title=title, created_at="", updated_at="",
        message_count=2, pinned=False,
    )


def test_save_proposal_creates_bookmark_with_real_content(monkeypatch, isolated_bookmarks):
    import streamlit as st
    st.session_state["_do_save_proposal"] = True
    monkeypatch.setattr(sw, "_load_messages", lambda: [
        {"role": "user", "content": "생성해줘"},
        {"role": "assistant", "content": "## 제안서 본문\n- 과제명: 도장 비전"},
    ])
    monkeypatch.setattr(sw, "_active_thread", lambda: _fake_thread("도장 비전 검사 PoC"))

    with patch("streamlit.rerun"):
        sw._consume_save_proposal_if_any()

    props = isolated_bookmarks.list_all(type_="proposal")
    assert len(props) == 1
    assert props[0].content == "## 제안서 본문\n- 과제명: 도장 비전"
    assert props[0].type == "proposal"
    assert props[0].status == "pending"           # 검토 대기로 보관함에
    assert props[0].title == "도장 비전 검사 PoC"
    toast = st.session_state.get("_sola_action_toast")
    assert toast and toast[0] == "ok"


def test_save_proposal_resave_updates_not_duplicates(monkeypatch, isolated_bookmarks):
    import streamlit as st
    monkeypatch.setattr(sw, "_active_thread", lambda: _fake_thread("스레드 제목"))

    # 1차 저장
    st.session_state["_do_save_proposal"] = True
    monkeypatch.setattr(sw, "_load_messages", lambda: [{"role": "assistant", "content": "v1"}])
    with patch("streamlit.rerun"):
        sw._consume_save_proposal_if_any()
    # 2차 저장 (같은 thread → 같은 안정 id → 갱신)
    st.session_state["_do_save_proposal"] = True
    monkeypatch.setattr(sw, "_load_messages", lambda: [{"role": "assistant", "content": "v2"}])
    with patch("streamlit.rerun"):
        sw._consume_save_proposal_if_any()

    props = isolated_bookmarks.list_all(type_="proposal")
    assert len(props) == 1                          # 중복 아님
    assert props[0].content == "v2"                 # 최신 내용으로 갱신


def test_save_proposal_no_assistant_message_warns(monkeypatch, isolated_bookmarks):
    import streamlit as st
    st.session_state["_do_save_proposal"] = True
    monkeypatch.setattr(sw, "_load_messages", lambda: [{"role": "user", "content": "q"}])
    monkeypatch.setattr(sw, "_active_thread", lambda: _fake_thread())
    with patch("streamlit.rerun"):
        sw._consume_save_proposal_if_any()
    assert isolated_bookmarks.list_all(type_="proposal") == []
    assert st.session_state.get("_sola_action_toast")[0] == "warn"


def test_save_proposal_noop_when_no_pending(monkeypatch, isolated_bookmarks):
    with patch("streamlit.rerun") as r:
        sw._consume_save_proposal_if_any()
    assert isolated_bookmarks.list_all(type_="proposal") == []
    assert r.call_count == 0


def test_save_proposal_carries_handoff_tags(monkeypatch, isolated_bookmarks):
    import streamlit as st
    st.session_state["_do_save_proposal"] = True
    st.query_params["dept"] = "도장"
    st.query_params["lv3"] = "비전 검사"
    monkeypatch.setattr(sw, "_load_messages", lambda: [{"role": "assistant", "content": "본문"}])
    monkeypatch.setattr(sw, "_active_thread", lambda: _fake_thread())
    with patch("streamlit.rerun"):
        sw._consume_save_proposal_if_any()
    props = isolated_bookmarks.list_all(type_="proposal")
    assert props and set(["도장", "비전 검사"]).issubset(set(props[0].tags))


# ── _render_sola_action_toasts ──────────────────────────────

def test_render_action_toast_consumes_once(monkeypatch):
    import streamlit as st
    st.session_state["_sola_action_toast"] = ("ok", "저장됨")
    shown = []
    with patch("streamlit.toast", side_effect=lambda msg, *a, **k: shown.append(msg)):
        sw._render_sola_action_toasts()
        # 1회 소비 후 비어야 함
        sw._render_sola_action_toasts()
    assert len(shown) == 1
    assert "저장됨" in shown[0]
