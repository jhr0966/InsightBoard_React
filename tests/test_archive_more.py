"""산출물 칸반 "+N건 더 보기" wire — `?expand=` stateless 토글."""
from __future__ import annotations

from unittest.mock import patch
from urllib.parse import quote

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
        archive_v2._oa_stats_and_cards.clear()
    except Exception:
        pass
    yield bm


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


# ── 쿼리 파서 ───────────────────────────────────────────────

def test_expanded_cols_from_query_parses_csv():
    from ui import archive_v2
    import streamlit as st
    st.query_params.clear()
    st.query_params["expand"] = "pending,adopted"
    try:
        result = archive_v2._expanded_cols_from_query()
        assert result == frozenset({"pending", "adopted"})
    finally:
        st.query_params.clear()


def test_expanded_cols_filters_unknown_keys():
    from ui import archive_v2
    import streamlit as st
    st.query_params.clear()
    st.query_params["expand"] = "pending,nuke,rejected"
    try:
        result = archive_v2._expanded_cols_from_query()
        # nuke 만 필터링
        assert result == frozenset({"pending", "rejected"})
    finally:
        st.query_params.clear()


def test_expanded_cols_empty_when_missing():
    from ui import archive_v2
    import streamlit as st
    st.query_params.clear()
    assert archive_v2._expanded_cols_from_query() == frozenset()


# ── URL 빌더 (토글) ────────────────────────────────────────

def test_expand_href_adds_col_when_not_present():
    from ui import archive_v2
    href = archive_v2._archive_expand_href("pending", frozenset())
    assert "app_area=" + quote("📦 산출물 보관함") in href
    assert "expand=pending" in href


def test_expand_href_removes_col_when_present():
    from ui import archive_v2
    href = archive_v2._archive_expand_href("pending", frozenset({"pending"}))
    # pending 만 펴진 상태에서 토글 → expand 파라미터 자체 생략
    assert "expand=" not in href
    assert "app_area=" in href


def test_expand_href_preserves_other_cols_when_toggling_one():
    from ui import archive_v2
    # pending+adopted 펴진 상태에서 pending 토글 → adopted 만 남아야
    href = archive_v2._archive_expand_href("pending", frozenset({"pending", "adopted"}))
    assert "expand=adopted" in href
    assert "pending" not in href.split("expand=")[1].split("&")[0]


def test_expand_href_ordered_csv():
    """expand 파라미터의 컬럼 순서는 항상 (pending, adopted, rejected)."""
    from ui import archive_v2
    href = archive_v2._archive_expand_href(
        "rejected", frozenset({"adopted", "pending"})
    )
    assert "expand=" + quote("pending,adopted,rejected") in href


# ── _build_cards_html — <a> 전환 + expand 동작 ──────────────

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


def test_build_cards_more_link_is_anchor_not_disabled_button():
    from ui import archive_v2
    items = _mk_items(7)
    html = archive_v2._build_cards_html(
        items, status_label="대기", col_key="pending",
        expanded=False, expanded_set=frozenset(),
    )
    # 4건만 노출 + +3건 더 보기 링크
    assert html.count('<article class="oa-card"') == 4
    assert '<a class="oa-col-more"' in html
    assert "+ 3건 더 보기" in html
    # disabled 자취 없음
    assert "disabled" not in html


def test_build_cards_expanded_shows_all_with_collapse_link():
    from ui import archive_v2
    items = _mk_items(7)
    html = archive_v2._build_cards_html(
        items, status_label="대기", col_key="pending",
        expanded=True, expanded_set=frozenset({"pending"}),
    )
    # 모든 7건 노출
    assert html.count('<article class="oa-card"') == 7
    # 접기 링크
    assert "oa-col-more-collapse" in html
    assert "접기 (7건)" in html


def test_build_cards_no_more_link_when_fits_in_default():
    from ui import archive_v2
    items = _mk_items(3)
    html = archive_v2._build_cards_html(
        items, status_label="대기", col_key="pending",
        expanded=False, expanded_set=frozenset(),
    )
    assert "더 보기" not in html
    assert "접기" not in html


def test_build_cards_no_collapse_link_when_expanded_but_under_max():
    """4건 이하인 컬럼이 expand 되어 있어도 굳이 접기 링크 노출 안 함."""
    from ui import archive_v2
    items = _mk_items(3)
    html = archive_v2._build_cards_html(
        items, status_label="대기", col_key="pending",
        expanded=True, expanded_set=frozenset({"pending"}),
    )
    assert "접기" not in html


# ── _oa_stats_and_cards — 캐시 키 + 분기 ───────────────────

def test_oa_stats_expand_pending_only_affects_pending_col(isolated_bookmarks):
    from ui import archive_v2
    bm_mod = isolated_bookmarks
    _add_bookmarks(bm_mod, "pending", 7)
    _add_bookmarks(bm_mod, "adopted", 7)

    archive_v2._oa_stats_and_cards.clear()
    oa = archive_v2._oa_stats_and_cards("pending")

    # pending 은 7건 모두 + 접기, adopted 는 4건 + 더 보기
    assert oa["cards_pending"].count('<article class="oa-card"') == 7
    assert "접기" in oa["cards_pending"]
    assert oa["cards_adopted"].count('<article class="oa-card"') == 4
    assert "+ 3건 더 보기" in oa["cards_adopted"]


def test_oa_stats_no_expand_default_4_per_col(isolated_bookmarks):
    from ui import archive_v2
    bm_mod = isolated_bookmarks
    _add_bookmarks(bm_mod, "pending", 10)
    archive_v2._oa_stats_and_cards.clear()
    oa = archive_v2._oa_stats_and_cards("")
    assert oa["cards_pending"].count('<article class="oa-card"') == 4
    assert "+ 6건 더 보기" in oa["cards_pending"]
    # 펴진 컬럼 없음
    assert "접기" not in oa["cards_pending"]


def test_oa_stats_expand_csv_in_more_link_preserves_other_cols(isolated_bookmarks):
    """더 보기 링크가 다른 컬럼 expand 상태를 보존한다."""
    from ui import archive_v2
    bm_mod = isolated_bookmarks
    _add_bookmarks(bm_mod, "pending", 7)
    _add_bookmarks(bm_mod, "adopted", 7)
    archive_v2._oa_stats_and_cards.clear()

    # adopted 만 펴진 상태에서 렌더 — pending 의 더 보기 링크는 adopted 도 같이 포함
    oa = archive_v2._oa_stats_and_cards("adopted")
    pending_html = oa["cards_pending"]
    # pending 더 보기 href 가 expand=pending,adopted 형태
    assert "expand=" + quote("pending,adopted") in pending_html
