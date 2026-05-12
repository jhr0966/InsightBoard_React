"""store.bookmarks — JSONL 영구화."""
from __future__ import annotations

from store import bookmarks
from store.bookmarks import Bookmark


def test_add_and_list_roundtrip():
    bookmarks.clear()
    bm = Bookmark(id=bookmarks.make_id("opportunity", "가공부", "전처리"),
                  type="opportunity", title="가공부 · 전처리",
                  content="작업: 강재선별", tags=["가공부", "전처리"])
    saved = bookmarks.add(bm)
    assert saved.created_at  # 자동 채워짐

    items = bookmarks.list_all()
    assert len(items) == 1
    assert items[0].id == bm.id
    assert items[0].title == "가공부 · 전처리"


def test_filter_by_type():
    bookmarks.clear()
    bookmarks.add(Bookmark(id="a", type="opportunity", title="o"))
    bookmarks.add(Bookmark(id="b", type="proposal", title="p"))
    opp = bookmarks.list_all(type_="opportunity")
    prop = bookmarks.list_all(type_="proposal")
    assert len(opp) == 1 and opp[0].id == "a"
    assert len(prop) == 1 and prop[0].id == "b"


def test_add_dedup_same_id_overwrites():
    bookmarks.clear()
    bookmarks.add(Bookmark(id="dup", type="news", title="v1"))
    bookmarks.add(Bookmark(id="dup", type="news", title="v2"))
    items = bookmarks.list_all()
    assert len(items) == 1
    assert items[0].title == "v2"


def test_remove_returns_true_when_existed():
    bookmarks.clear()
    bookmarks.add(Bookmark(id="x", type="news", title="x"))
    assert bookmarks.has("x") is True
    assert bookmarks.remove("x") is True
    assert bookmarks.has("x") is False
    assert bookmarks.remove("x") is False


def test_make_id_stable_and_distinct():
    a = bookmarks.make_id("opportunity", "가공부", "전처리")
    b = bookmarks.make_id("opportunity", "가공부", "전처리")
    c = bookmarks.make_id("opportunity", "조립부", "전처리")
    assert a == b and a != c


def test_clear_returns_count():
    bookmarks.clear()
    bookmarks.add(Bookmark(id="1", type="news", title="x"))
    bookmarks.add(Bookmark(id="2", type="news", title="y"))
    assert bookmarks.clear() == 2
    assert bookmarks.list_all() == []
