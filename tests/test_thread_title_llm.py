"""SOLA workshop thread 제목 LLM 생성기 — 첫 메시지 → 5~12자 압축 + fallback."""
from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _isolate_cache(tmp_path, monkeypatch):
    from store import cache
    cdir = tmp_path / "cache"
    cdir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(cache, "_cache_dir", lambda: cdir)
    yield


# ── _clean_title ────────────────────────────────────────────

def test_clean_title_strips_quotes_and_whitespace():
    from sola.thread_title import _clean_title
    assert _clean_title('  "도장 비전 검사 정리"  ') == "도장 비전 검사 정리"
    assert _clean_title("`코드 리뷰`") == "코드 리뷰"
    assert _clean_title('「용접 비교」') == "용접 비교"


def test_clean_title_first_line_only():
    from sola.thread_title import _clean_title
    assert _clean_title("도장 비전 검사\n다음 줄은 무시") == "도장 비전 검사"


def test_clean_title_strips_trailing_punctuation():
    from sola.thread_title import _clean_title
    assert _clean_title("도장 검사 정리.") == "도장 검사 정리"
    assert _clean_title("용접 비교?") == "용접 비교"


def test_clean_title_truncates_too_long():
    from sola.thread_title import _clean_title, _MAX_LEN
    long = "가" * (_MAX_LEN + 5)
    out = _clean_title(long)
    assert len(out) <= _MAX_LEN


def test_clean_title_removes_emoji():
    from sola.thread_title import _clean_title
    # 이모지가 제거되어야 함
    out = _clean_title("도장 비전 ✨")
    assert "✨" not in out
    assert "도장 비전" in out


def test_clean_title_empty():
    from sola.thread_title import _clean_title
    assert _clean_title("") == ""
    assert _clean_title("   ") == ""


# ── generate — LLM / fallback / cache ─────────────────────

def test_generate_uses_llm_response():
    from sola import thread_title
    with patch("sola.thread_title.chat", return_value="도장 비전 검사 정리"):
        title = thread_title.generate("도장 비전 검사 사례 정리해줘")
    assert title == "도장 비전 검사 정리"


def test_generate_falls_back_when_llm_not_configured():
    from sola import thread_title
    from sola.client import LLMNotConfigured
    with patch("sola.thread_title.chat", side_effect=LLMNotConfigured("no key")):
        title = thread_title.generate("도장 비전 검사 사례 정리해줘")
    # truncation fallback — 첫 N자
    assert "도장 비전 검사" in title


def test_generate_falls_back_on_exception():
    from sola import thread_title
    with patch("sola.thread_title.chat", side_effect=RuntimeError("boom")):
        title = thread_title.generate("용접 자동화")
    assert "용접 자동화" in title


def test_generate_falls_back_when_response_too_short():
    """LLM 응답이 _MIN_LEN 보다 짧으면 fallback."""
    from sola import thread_title
    with patch("sola.thread_title.chat", return_value="X"):
        title = thread_title.generate("도장 비전 검사")
    # truncation fallback 사용 (X가 아니어야 함)
    assert title != "X"
    assert "도장" in title


def test_generate_caches_per_signature():
    from sola import thread_title
    with patch("sola.thread_title.chat", return_value="도장 정리") as mock_chat:
        t1 = thread_title.generate("도장 비전 검사 사례")
        t2 = thread_title.generate("도장 비전 검사 사례")
    assert t1 == t2 == "도장 정리"
    assert mock_chat.call_count == 1


def test_generate_force_bypasses_cache():
    from sola import thread_title
    with patch("sola.thread_title.chat", side_effect=["A제목", "B제목"]) as mock_chat:
        t1 = thread_title.generate("같은 메시지")
        t2 = thread_title.generate("같은 메시지", force=True)
    assert mock_chat.call_count == 2
    assert t1 == "A제목" and t2 == "B제목"


def test_generate_empty_message_returns_fallback():
    from sola import thread_title
    with patch("sola.thread_title.chat") as mock_chat:
        title = thread_title.generate("")
    mock_chat.assert_not_called()
    # store.sola_threads.title_from_first_user_message 의 빈 입력 처리
    assert title == "새 대화"


# ── UI 통합: _append_message 가 generate 사용 ─────────────

def test_append_message_uses_llm_title_for_first_user_msg():
    """첫 user 메시지에 대해 thread.title 이 LLM 결과로 업데이트된다."""
    from ui import sola_workshop_v2 as ws
    from store import sola_threads

    # _active_thread / _load_messages / chat_log.save_history / sola_threads.update 모킹
    th = sola_threads.Thread(id="th1", title="새 대화", created_at="", updated_at="",
                              message_count=0, pinned=False)
    captured = {}

    def _fake_update(thread_id, *, title=None, **kw):
        captured["title"] = title
        captured["id"] = thread_id

    with patch.object(ws, "_active_thread", return_value=th), \
         patch.object(ws, "_load_messages", return_value=[]), \
         patch("store.chat_log.save_history"), \
         patch.object(sola_threads, "update", side_effect=_fake_update), \
         patch("sola.thread_title.generate", return_value="도장 검사 정리"):
        # session_state 캐시 비우기 위해 streamlit 임포트
        import streamlit as st
        st.session_state.pop("_sola_messages_th1", None)
        ws._append_message("user", "도장 비전 검사 사례 정리해줘")

    assert captured.get("title") == "도장 검사 정리"
    assert captured.get("id") == "th1"


def test_append_message_skips_title_for_assistant_msg():
    from ui import sola_workshop_v2 as ws
    from store import sola_threads

    th = sola_threads.Thread(id="th2", title="기존 제목", created_at="", updated_at="",
                              message_count=0, pinned=False)
    captured = {}

    def _fake_update(thread_id, *, title=None, **kw):
        captured["title"] = title

    with patch.object(ws, "_active_thread", return_value=th), \
         patch.object(ws, "_load_messages", return_value=[]), \
         patch("store.chat_log.save_history"), \
         patch.object(sola_threads, "update", side_effect=_fake_update), \
         patch("sola.thread_title.generate") as mock_gen:
        import streamlit as st
        st.session_state.pop("_sola_messages_th2", None)
        ws._append_message("assistant", "답변")

    mock_gen.assert_not_called()
    # title 인자가 None (변경 없음)
    assert captured.get("title") is None


def test_append_message_skips_title_when_thread_already_named():
    """thread 에 기본값 아닌 제목이 이미 있으면 LLM 호출 안 함."""
    from ui import sola_workshop_v2 as ws
    from store import sola_threads

    th = sola_threads.Thread(id="th3", title="이미 있는 제목", created_at="",
                              updated_at="", message_count=5, pinned=False)
    with patch.object(ws, "_active_thread", return_value=th), \
         patch.object(ws, "_load_messages", return_value=[]), \
         patch("store.chat_log.save_history"), \
         patch.object(sola_threads, "update"), \
         patch("sola.thread_title.generate") as mock_gen:
        import streamlit as st
        st.session_state.pop("_sola_messages_th3", None)
        ws._append_message("user", "새 메시지")

    mock_gen.assert_not_called()
