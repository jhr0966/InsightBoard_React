"""store.bookmarks — JSONL 영구화 + 상태/만료 정책."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

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


def test_default_status_is_pending():
    bookmarks.clear()
    bookmarks.add(Bookmark(id="p1", type="proposal", title="t"))
    saved = bookmarks.list_all()[0]
    assert saved.status == "pending"
    assert saved.decision_note == ""
    assert saved.decided_at == ""


def test_from_dict_backfills_missing_status():
    """옛 JSONL record (status 필드 없는 것) 호환."""
    bm = Bookmark.from_dict({"id": "x", "type": "proposal", "title": "old"})
    assert bm.status == "pending"
    assert bm.decision_note == ""

    # 잘못된 status 값도 pending 으로 fallback
    bm2 = Bookmark.from_dict({"id": "y", "type": "proposal", "title": "z", "status": "garbage"})
    assert bm2.status == "pending"


def test_set_status_updates_decision_note_and_decided_at():
    bookmarks.clear()
    bookmarks.add(Bookmark(id="p1", type="proposal", title="t"))
    assert bookmarks.set_status("p1", "adopted", note="회의 채택") is True

    saved = bookmarks.list_all()[0]
    assert saved.status == "adopted"
    assert saved.decision_note == "회의 채택"
    assert saved.decided_at  # 자동 채워짐


def test_set_status_returns_false_when_not_found():
    bookmarks.clear()
    assert bookmarks.set_status("nope", "adopted") is False


def test_set_status_rejects_invalid_value():
    bookmarks.clear()
    bookmarks.add(Bookmark(id="p1", type="proposal", title="t"))
    with pytest.raises(ValueError):
        bookmarks.set_status("p1", "garbage")


def _iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat()


def test_expire_old_removes_pending_past_cutoff():
    bookmarks.clear()
    now = datetime(2026, 5, 12, 12, 0, tzinfo=timezone.utc)
    old = now - timedelta(days=31)
    fresh = now - timedelta(days=10)

    bookmarks.add(Bookmark(id="old_pending", type="proposal", title="old", created_at=_iso(old)))
    bookmarks.add(Bookmark(id="fresh_pending", type="proposal", title="fresh", created_at=_iso(fresh)))

    removed = bookmarks.expire_old(days=30, now=now)
    assert removed == 1

    ids = {b.id for b in bookmarks.list_all()}
    assert ids == {"fresh_pending"}


def test_expire_old_preserves_adopted_even_when_ancient():
    """채택된 제안서는 N일이 지나도 영구 보존."""
    bookmarks.clear()
    now = datetime(2026, 5, 12, 12, 0, tzinfo=timezone.utc)
    very_old = now - timedelta(days=365)

    bookmarks.add(Bookmark(
        id="old_adopted", type="proposal", title="채택", created_at=_iso(very_old),
        status="adopted",
    ))
    bookmarks.add(Bookmark(
        id="old_rejected", type="proposal", title="거절", created_at=_iso(very_old),
        status="rejected",
    ))

    removed = bookmarks.expire_old(days=30, now=now)
    # rejected 는 삭제, adopted 는 보존
    assert removed == 1
    ids = {b.id for b in bookmarks.list_all()}
    assert ids == {"old_adopted"}


def test_expire_old_targets_only_specified_types():
    """기본은 제안서만. 다른 타입은 만료되지 않는다."""
    bookmarks.clear()
    now = datetime(2026, 5, 12, 12, 0, tzinfo=timezone.utc)
    old = now - timedelta(days=100)

    bookmarks.add(Bookmark(id="old_news", type="news", title="n", created_at=_iso(old)))
    bookmarks.add(Bookmark(id="old_opp", type="opportunity", title="o", created_at=_iso(old)))
    bookmarks.add(Bookmark(id="old_prop", type="proposal", title="p", created_at=_iso(old)))

    removed = bookmarks.expire_old(days=30, now=now)
    assert removed == 1  # 제안서만 삭제
    ids = {b.id for b in bookmarks.list_all()}
    assert ids == {"old_news", "old_opp"}


def test_expire_old_preserves_when_created_at_unparseable():
    bookmarks.clear()
    now = datetime(2026, 5, 12, tzinfo=timezone.utc)
    bookmarks.add(Bookmark(id="weird", type="proposal", title="t", created_at="invalid-date"))

    removed = bookmarks.expire_old(days=30, now=now)
    assert removed == 0
    assert len(bookmarks.list_all()) == 1
