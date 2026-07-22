"""수집 키워드 결정 (feat-collect-keywords) — 명시 > 페르소나 > 도메인 기본값.

UI '지금 수집'(빈 키워드)이 사용자 페르소나 관심 키워드로 수집되도록 회귀 방지.
"""
from __future__ import annotations

from api.routers import collect as collect_router
from config import DEFAULT_DAILY_KEYWORDS


class _P:
    """persona_store.load 대역 — 필요한 키워드 필드만."""
    def __init__(self, interest=None, derived=None, muted=None):
        self.interest_keywords = interest or []
        self.derived_interests = derived or []
        self.muted_keywords = muted or []


class _Id:
    def __init__(self, user="u1"):
        self.user_id = user
        self.workspace_id = "default"


def test_explicit_keywords_win(monkeypatch):
    monkeypatch.setattr(collect_router.persona_store, "load",
                        lambda uid: _P(interest=["무시됨"]))
    out = collect_router._resolve_keywords(["용접 로봇", " ", "AGV"], _Id())
    assert out == ["용접 로봇", "AGV"]


def test_persona_keywords_used_when_empty(monkeypatch):
    monkeypatch.setattr(collect_router.persona_store, "load",
                        lambda uid: _P(interest=["도장 검사", "막두께"],
                                       derived=["로봇 용접"], muted=["막두께"]))
    out = collect_router._resolve_keywords([], _Id())
    # interest + derived, muted 제외, 순서 보존
    assert out == ["도장 검사", "로봇 용접"]


def test_persona_keyword_cap(monkeypatch):
    many = [f"kw{i}" for i in range(20)]
    monkeypatch.setattr(collect_router.persona_store, "load",
                        lambda uid: _P(interest=many))
    out = collect_router._resolve_keywords([], _Id())
    assert out == many[:collect_router._PERSONA_KEYWORD_CAP]


def test_domain_default_when_no_persona(monkeypatch):
    monkeypatch.setattr(collect_router.persona_store, "load", lambda uid: _P())
    out = collect_router._resolve_keywords([], _Id())
    assert out == list(DEFAULT_DAILY_KEYWORDS)
    # 기본값이 조선/제조 도메인으로 좁혀졌는지(과거 광범위 "AI"/"자동화" 회귀 방지)
    assert "스마트 조선소" in out


def test_persona_load_failure_falls_back(monkeypatch):
    def _boom(uid):
        raise RuntimeError("no profile")
    monkeypatch.setattr(collect_router.persona_store, "load", _boom)
    assert collect_router._resolve_keywords([], _Id()) == list(DEFAULT_DAILY_KEYWORDS)
