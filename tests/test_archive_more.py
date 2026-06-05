"""산출물 칸반 위젯화 — expand 세션 토글 + 카드 블록(앵커 제거) + 액션 pending."""
from __future__ import annotations

import pytest


@pytest.fixture
def isolated_bookmarks(tmp_path, monkeypatch):
    """bookmarks 임시 디렉토리 격리 + 캐시 클리어."""
    bookmarks_dir = tmp_path / "bookmarks"
    bookmarks_dir.mkdir(parents=True, exist_ok=True)
    from store import bookmarks as bm
    monkeypatch.setattr(bm, "_path", lambda: bookmarks_dir / "items.jsonl")
    from ui import archive_v2
    try:
        archive_v2._oa_data.clear()
    except Exception:
        pass
    import streamlit as st
    for k in ("_oa_expanded", "_do_archive_action"):
        st.session_state.pop(k, None)
    yield bm
    st.session_state.pop("_oa_expanded", None)


def _add_bookmarks(bm_mod, status: str, n: int):
    """status 컬럼에 n개 합성 bookmark 추가."""
    from store.bookmarks import Bookmark
    for i in range(n):
        bm_mod.add(Bookmark(
            id=f"bm_{status}_{i:02d}",
            type="proposal",
            title=f"{status} 카드 {i}",
            content="",
            tags=[],
            created_at=f"2026-05-{30 - i:02d}T06:00:00+00:00",
            status=status,
        ))


def _mk_items(n: int, status: str = "pending"):
    from store.bookmarks import Bookmark
    return [
        Bookmark(
            id=f"x{i:02d}", type="proposal", title=f"X{i}",
            content="", tags=[], created_at=f"2026-05-{30 - i:02d}T06:00:00+00:00",
            status=status,
        )
        for i in range(n)
    ]


# ── expand 세션 토글 (구 ?expand= 앵커 대체) ──────────────────

def test_expanded_cols_reads_session():
    from ui import archive_v2
    import streamlit as st
    st.session_state["_oa_expanded"] = frozenset({"pending", "adopted"})
    try:
        assert archive_v2._expanded_cols() == frozenset({"pending", "adopted"})
    finally:
        st.session_state.pop("_oa_expanded", None)


def test_expanded_cols_filters_unknown_keys():
    from ui import archive_v2
    import streamlit as st
    st.session_state["_oa_expanded"] = frozenset({"pending", "nuke", "rejected"})
    try:
        assert archive_v2._expanded_cols() == frozenset({"pending", "rejected"})
    finally:
        st.session_state.pop("_oa_expanded", None)


def test_expanded_cols_empty_when_missing():
    from ui import archive_v2
    import streamlit as st
    st.session_state.pop("_oa_expanded", None)
    assert archive_v2._expanded_cols() == frozenset()


def test_toggle_expanded_adds_then_removes():
    from ui import archive_v2
    import streamlit as st
    st.session_state.pop("_oa_expanded", None)
    archive_v2._toggle_expanded("pending")
    assert archive_v2._expanded_cols() == frozenset({"pending"})
    # 다른 컬럼 토글 — 기존 보존
    archive_v2._toggle_expanded("adopted")
    assert archive_v2._expanded_cols() == frozenset({"pending", "adopted"})
    # 같은 컬럼 다시 토글 — 제거
    archive_v2._toggle_expanded("pending")
    assert archive_v2._expanded_cols() == frozenset({"adopted"})
    st.session_state.pop("_oa_expanded", None)


# ── _cards_block_html — 카드 블록(앵커·액션 없음) ─────────────

def test_cards_block_shows_max_4_when_not_expanded():
    from ui import archive_v2
    html = archive_v2._cards_block_html(_mk_items(7), status_label="대기", expanded=False)
    assert html.count('<article class="oa-card"') == 4   # 기본 4건
    assert 'class="oa-cards"' in html
    # 더 이상 액션/더보기 앵커 없음(위젯 버튼이 담당)
    assert "<a " not in html
    assert "oa-act" not in html
    assert "oa-col-more" not in html


def test_cards_block_shows_all_when_expanded():
    from ui import archive_v2
    html = archive_v2._cards_block_html(_mk_items(7), status_label="대기", expanded=True)
    assert html.count('<article class="oa-card"') == 7


def test_cards_block_empty_placeholder():
    from ui import archive_v2
    html = archive_v2._cards_block_html([], status_label="대기", expanded=False)
    assert "아직 대기 산출물이 없어요" in html


# ── _oa_data — stats + 컬럼별 items ───────────────────────────

def test_oa_data_groups_sorts_and_counts(isolated_bookmarks):
    from ui import archive_v2
    bm_mod = isolated_bookmarks
    _add_bookmarks(bm_mod, "pending", 7)
    _add_bookmarks(bm_mod, "adopted", 2)
    archive_v2._oa_data.clear()
    data = archive_v2._oa_data()

    assert data["stats"]["pending"] == "7"
    assert data["stats"]["adopted"] == "2"
    assert data["stats"]["total"] == "9"
    assert len(data["pending"]) == 7 and len(data["adopted"]) == 2
    # 최신순(created_at 내림차순) — bm_pending_00 이 2026-05-30 으로 최신
    assert data["pending"][0].id == "bm_pending_00"


# ── 액션: 버튼 pending 경로 + 수정 핸드오프 ───────────────────

def test_consume_archive_action_via_pending_sets_status(isolated_bookmarks):
    from ui import archive_v2
    import streamlit as st
    bm_mod = isolated_bookmarks
    _add_bookmarks(bm_mod, "pending", 1)
    st.session_state["_do_archive_action"] = ("adopt", "bm_pending_00")
    result = archive_v2._consume_action_if_any()
    assert result == ("adopted", "bm_pending_00")
    # 실제 status 변경
    items = bm_mod.list_all(type_="proposal")
    assert any(b.id == "bm_pending_00" and b.status == "adopted" for b in items)
    assert "_do_archive_action" not in st.session_state  # 1회 소비


def test_handoff_edit_sets_sola_area_and_query():
    from ui import archive_v2
    from store.bookmarks import Bookmark
    import streamlit as st
    st.query_params.clear()
    bm = Bookmark(id="bmX", type="proposal", title="제안서 A", content="",
                  tags=[], created_at="2026-05-30T06:00:00+00:00", status="pending")
    try:
        archive_v2._handoff_edit_to_sola(bm)
        assert st.session_state["app_area"] == "🤖 SOLA 작업실"
        assert st.query_params.get("from") == "edit"
        assert st.query_params.get("bm_id") == "bmX"
        assert st.query_params.get("title") == "제안서 A"
    finally:
        st.query_params.clear()
