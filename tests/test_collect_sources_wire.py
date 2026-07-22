"""출처 설정 실효화 (feat-sources-wire) — 토글·커스텀 RSS 가 수집에 반영되는지.

과거엔 disabled_set()·custom_sources() 가 화면 표시·헬스에만 쓰이고 수집 경로엔
연결되지 않아, UI 에서 출처를 꺼도 계속 수집되고 등록한 커스텀 RSS 는 UI 수집에서
무시됐다. `_resolve_sources_feeds` 가 이를 실제 수집 인자로 변환하는지 가드한다.
"""
from __future__ import annotations

from api.routers import collect as collect_router

_DEFAULT = ("google", "tech")


def test_explicit_sources_passthrough_no_feeds():
    src, feeds = collect_router._resolve_sources_feeds(["google"], _DEFAULT)
    assert src == ("google",) and feeds == []


def test_default_includes_custom_feeds(monkeypatch):
    from store import sources as src_store

    monkeypatch.setattr(src_store, "disabled_set", lambda: frozenset())
    monkeypatch.setattr(src_store, "custom_sources",
                        lambda: [src_store.CustomSource(name="조선해양", url="https://x/rss")])
    src, feeds = collect_router._resolve_sources_feeds(None, _DEFAULT)
    assert src == ("google", "tech")
    assert feeds == [("조선해양", "https://x/rss")]


def test_disabled_source_dropped_from_collection(monkeypatch):
    from store import sources as src_store

    # '구글 뉴스' 비활성 → google 소스가 수집에서 빠진다.
    monkeypatch.setattr(src_store, "disabled_set", lambda: frozenset({"구글 뉴스"}))
    monkeypatch.setattr(src_store, "custom_sources", lambda: [])
    src, feeds = collect_router._resolve_sources_feeds(None, _DEFAULT)
    assert src == ("tech",)
    assert feeds == []


def test_disabling_ai_times_drops_tech(monkeypatch):
    from store import sources as src_store

    monkeypatch.setattr(src_store, "disabled_set", lambda: frozenset({"AI Times"}))
    monkeypatch.setattr(src_store, "custom_sources", lambda: [])
    src, _ = collect_router._resolve_sources_feeds(None, _DEFAULT)
    assert src == ("google",)
