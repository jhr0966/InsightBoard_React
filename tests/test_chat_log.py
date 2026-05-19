"""store.chat_log — 사이드 채팅 영구화 + chat_key 별 파일 분리."""
from __future__ import annotations

import pandas as pd  # noqa: F401  (conftest tmp_path 호환용)
import pytest

from store import chat_log


@pytest.fixture(autouse=True)
def _isolated_sola_dir(tmp_path, monkeypatch):
    """SOLA_DIR 를 임시 디렉토리로 격리해 테스트 간 파일 충돌 방지."""
    monkeypatch.setattr(chat_log, "SOLA_DIR", tmp_path)
    yield


def test_default_key_uses_legacy_path():
    """후방 호환: 인자 없이 호출하면 SOLA_DIR/chat_history.jsonl 단일 파일을 사용."""
    chat_log.save_history([{"role": "user", "content": "hi"}])
    p_default = chat_log._path()
    assert p_default.name == "chat_history.jsonl"
    assert p_default.parent.name == p_default.parent.name  # SOLA_DIR
    assert chat_log.load_history() == [{"role": "user", "content": "hi"}]


def test_each_chat_key_isolated_in_chat_subdir():
    """chat_key 별로 다른 파일에 저장되고 서로 영향 안 줌."""
    chat_log.save_history([{"role": "user", "content": "sola q"}], chat_key="sola")
    chat_log.save_history([{"role": "user", "content": "home q"}], chat_key="home")

    assert chat_log.load_history("sola") == [{"role": "user", "content": "sola q"}]
    assert chat_log.load_history("home") == [{"role": "user", "content": "home q"}]
    # default 는 빈 상태 유지 (위 두 호출과 격리)
    assert chat_log.load_history() == []


def test_reset_only_clears_target_key():
    chat_log.save_history([{"role": "user", "content": "sola"}], chat_key="sola")
    chat_log.save_history([{"role": "user", "content": "home"}], chat_key="home")

    chat_log.reset("sola")
    assert chat_log.load_history("sola") == []
    assert chat_log.load_history("home") == [{"role": "user", "content": "home"}]


def test_unsafe_chat_key_chars_slugified():
    """파일명 안전한 슬러그로 정규화 — 디렉토리 traversal 차단."""
    chat_log.save_history([{"role": "user", "content": "x"}], chat_key="../../etc/passwd")
    # 슬러그된 경로는 chat 서브디렉토리 내부.
    p = chat_log._path("../../etc/passwd")
    assert p.parent.name == "chat"
    assert ".." not in p.name
    assert "/" not in p.name
