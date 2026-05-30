"""SOLA thread store — CRUD · 정렬 · 자동 제목 · A.3 잔재 마이그레이션."""
from __future__ import annotations

import pytest


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    """SOLA_DIR/DATA_ROOT 를 임시 디렉토리로 격리 — chat_log 와 sola_threads 동시."""
    import config
    monkeypatch.setattr(config, "DATA_ROOT", tmp_path)
    monkeypatch.setattr(config, "SOLA_DIR", tmp_path / "sola")
    (tmp_path / "sola").mkdir(parents=True, exist_ok=True)
    from store import chat_log, sola_threads
    monkeypatch.setattr(chat_log, "SOLA_DIR", tmp_path / "sola")
    monkeypatch.setattr(sola_threads, "SOLA_DIR", tmp_path / "sola")
    yield


# ── CRUD ────────────────────────────────────────────────────

def test_create_then_list(isolated):
    from store import sola_threads
    t1 = sola_threads.create("도장 PoC")
    t2 = sola_threads.create()  # 기본 제목 "새 대화"
    ids = [t.id for t in sola_threads.list_threads()]
    assert set(ids) == {t1.id, t2.id}
    assert t1.title == "도장 PoC"
    assert t2.title == "새 대화"
    assert t1.id.startswith("th_") and len(t1.id) > 5


def test_get_returns_none_for_missing(isolated):
    from store import sola_threads
    assert sola_threads.get("th_nonexistent") is None


def test_update_fields_and_touch(isolated):
    from store import sola_threads
    import time
    t = sola_threads.create("원본")
    original_updated = t.updated_at
    time.sleep(1.1)  # touch 차이 보장 (1초 이상)
    sola_threads.update(t.id, title="수정", message_count=12, pinned=True)
    after = sola_threads.get(t.id)
    assert after.title == "수정"
    assert after.message_count == 12
    assert after.pinned is True
    assert after.updated_at > original_updated  # touch 작동


def test_update_touch_false_keeps_updated_at(isolated):
    from store import sola_threads
    t = sola_threads.create("a")
    original = t.updated_at
    sola_threads.update(t.id, title="b", touch=False)
    assert sola_threads.get(t.id).updated_at == original


def test_delete_removes_thread_and_chat_log(isolated):
    from store import sola_threads, chat_log
    t = sola_threads.create("삭제테스트")
    chat_log.save_history(
        [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "ok"}],
        t.id,
    )
    assert len(chat_log.load_history(t.id)) == 2
    assert sola_threads.delete(t.id) is True
    assert sola_threads.get(t.id) is None
    assert chat_log.load_history(t.id) == []  # 메시지 파일도 정리됨


def test_delete_nonexistent_returns_false(isolated):
    from store import sola_threads
    assert sola_threads.delete("th_nonexistent") is False


# ── 정렬 ────────────────────────────────────────────────────

def test_list_threads_pinned_first_then_updated_desc(isolated):
    from store import sola_threads
    import time
    a = sola_threads.create("a")
    time.sleep(1.1)
    b = sola_threads.create("b")
    time.sleep(1.1)
    c = sola_threads.create("c")
    sola_threads.update(a.id, pinned=True, touch=False)  # a 가 pinned
    order = [t.title for t in sola_threads.list_threads()]
    # pinned a 가 맨 위, 나머지는 updated_at 내림차순 → c, b
    assert order == ["a", "c", "b"]


# ── 자동 제목 ───────────────────────────────────────────────

def test_title_from_first_user_message_strips_newlines_and_caps():
    from store import sola_threads
    out = sola_threads.title_from_first_user_message(
        "도장 PoC 일정이\n4개월이면 무리일까?\n그리고 ROI는 어떻게 잡지?"
    )
    assert "\n" not in out
    assert out.startswith("도장 PoC")
    assert len(out) <= 36


def test_title_empty_input_returns_default():
    from store import sola_threads
    assert sola_threads.title_from_first_user_message("") == "새 대화"


# ── ensure_active ──────────────────────────────────────────

def test_ensure_active_creates_when_empty(isolated):
    from store import sola_threads
    th = sola_threads.ensure_active()
    assert th.id.startswith("th_")
    assert len(sola_threads.list_threads()) == 1


def test_ensure_active_returns_specified(isolated):
    from store import sola_threads
    t1 = sola_threads.create()
    t2 = sola_threads.create()
    active = sola_threads.ensure_active(t2.id)
    assert active.id == t2.id


def test_ensure_active_falls_back_to_most_recent(isolated):
    """active_id 가 존재하지 않으면 가장 최근 thread 로."""
    from store import sola_threads
    import time
    a = sola_threads.create("a")
    time.sleep(1.1)
    b = sola_threads.create("b")  # 더 최근
    active = sola_threads.ensure_active("th_nonexistent_xxxxx")
    assert active.id == b.id


# ── A.3 잔재 (sola_main chat_key) 마이그레이션 ───────────────

def test_migrate_legacy_main_creates_thread_from_existing_messages(isolated):
    from store import sola_threads, chat_log
    chat_log.save_history(
        [{"role": "user", "content": "첫 질문"},
         {"role": "assistant", "content": "답변"}],
        sola_threads.LEGACY_MAIN_THREAD_ID,
    )
    th = sola_threads.migrate_legacy_main_if_needed()
    assert th is not None
    assert th.title == "첫 질문"
    assert th.message_count == 2
    # 새 thread 의 chat_key 로 메시지 복사됨
    assert len(chat_log.load_history(th.id)) == 2


def test_migrate_legacy_noop_when_no_legacy_messages(isolated):
    from store import sola_threads
    assert sola_threads.migrate_legacy_main_if_needed() is None
    assert sola_threads.list_threads() == []


def test_migrate_legacy_noop_when_threads_already_exist(isolated):
    """이미 thread 가 있으면 마이그 안 함 (수동 import 우회)."""
    from store import sola_threads, chat_log
    sola_threads.create("기존")
    chat_log.save_history(
        [{"role": "user", "content": "Q"}],
        sola_threads.LEGACY_MAIN_THREAD_ID,
    )
    assert sola_threads.migrate_legacy_main_if_needed() is None
