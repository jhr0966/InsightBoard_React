"""SOLA 브리핑 LLM 강화 — sola.board_brief + UI 통합."""
from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest


@pytest.fixture(autouse=True)
def _reset_cache(tmp_path, monkeypatch):
    """디스크 캐시를 임시 디렉토리로 격리."""
    from store import cache
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(cache, "_cache_dir", lambda: cache_dir)
    yield


# ── sola/board_brief ────────────────────────────────────────

def test_brief_empty_items_returns_fallback():
    from sola.board_brief import brief
    out = brief([], persona_label="도장1팀")
    assert "오늘 매칭된 뉴스가 없습니다." in out


def test_brief_falls_back_when_llm_not_configured():
    from sola.board_brief import brief
    from sola.client import LLMNotConfigured
    items = [{"title": "AI 비전 검사", "source": "naver"}]
    with patch("sola.board_brief.chat", side_effect=LLMNotConfigured("no key")):
        out = brief(items, persona_label="도장1팀")
    # 룰 fallback — "N건 두드러집니다"
    assert "1건" in out
    assert "두드러집니다" in out


def test_brief_falls_back_on_exception():
    from sola.board_brief import brief
    items = [{"title": "X", "source": "y"}]
    with patch("sola.board_brief.chat", side_effect=RuntimeError("net")):
        out = brief(items, persona_label="L")
    # 일반 예외도 fallback
    assert "두드러집니다" in out


def test_brief_uses_llm_response_when_available():
    from sola.board_brief import brief
    items = [{"title": "AI 비전 검사 도입", "source": "naver",
              "summary": "도장 결함 자동 검사"}]
    with patch("sola.board_brief.chat", return_value="**AI 비전 검사**가 빠르게 확산되고 있습니다."):
        out = brief(items, persona_label="도장1팀")
    assert "AI 비전 검사" in out
    assert "확산" in out


def test_brief_caches_per_signature():
    """같은 items + persona → 캐시 hit, LLM 1회만 호출."""
    from sola.board_brief import brief
    items = [{"title": "T", "source": "S"}]
    with patch("sola.board_brief.chat", return_value="요약 결과") as mock_chat:
        out1 = brief(items, persona_label="도장1팀")
        out2 = brief(items, persona_label="도장1팀")
    assert out1 == out2 == "요약 결과"
    # 캐시 hit으로 2번째 호출은 chat 호출 안 됨
    assert mock_chat.call_count == 1


def test_brief_cache_key_includes_persona_label():
    """다른 persona → 다른 캐시 키 → 별도 호출."""
    from sola.board_brief import brief
    items = [{"title": "T", "source": "S"}]
    with patch("sola.board_brief.chat", side_effect=["응답A", "응답B"]) as mock_chat:
        brief(items, persona_label="도장1팀")
        brief(items, persona_label="용접팀")
    assert mock_chat.call_count == 2


def test_brief_force_bypasses_cache():
    from sola.board_brief import brief
    items = [{"title": "T", "source": "S"}]
    with patch("sola.board_brief.chat", side_effect=["A", "B"]) as mock_chat:
        out1 = brief(items, persona_label="L")
        out2 = brief(items, persona_label="L", force=True)
    assert mock_chat.call_count == 2
    assert out1 == "A" and out2 == "B"


def test_brief_empty_llm_response_falls_back():
    """LLM 이 빈 응답이면 fallback 사용 (캐시에 빈 값 저장 방지)."""
    from sola.board_brief import brief
    items = [{"title": "T", "source": "S"}]
    with patch("sola.board_brief.chat", return_value="   "):
        out = brief(items, persona_label="L")
    assert "두드러집니다" in out


# ── _md_bold_to_html (마크다운 **굵게** → <b>) ─────────────

def test_md_bold_to_html_converts_bold_markers():
    from ui import board_v2
    out = board_v2._md_bold_to_html("**AI 비전**이 떴어요.")
    assert "<b>AI 비전</b>" in out
    assert "**" not in out


def test_md_bold_to_html_escapes_html_tags():
    from ui import board_v2
    out = board_v2._md_bold_to_html("<script>x</script>")
    assert "&lt;script&gt;" in out
    assert "<script>" not in out


def test_md_bold_to_html_mixes_bold_and_plain():
    from ui import board_v2
    out = board_v2._md_bold_to_html("**도장 비전**이 확산. 위험: <b>X</b>")
    assert "<b>도장 비전</b>" in out
    # 일반 텍스트의 <b> 는 escape
    assert "&lt;b&gt;X&lt;/b&gt;" in out


def test_md_bold_to_html_empty():
    from ui import board_v2
    assert board_v2._md_bold_to_html("") == ""


# ── _brief_html — LLM 결과를 요약 영역에 노출 ──────────────

def _news_fixture():
    return pd.DataFrame([{
        "title": "AI 비전 검사 도입",
        "summary": "도장 결함 자동 검사",
        "keywords": "AI, 비전",
        "source": "naver",
        "link": "https://x.com/1",
        "collected_at": "2026-05-31T06:00:00+00:00",
        "content": "본문",
    }])


def _matches_fixture():
    return pd.DataFrame([{
        "link": "https://x.com/1",
        "news_title": "AI 비전 검사 도입",
        "score": 0.9,
    }])


def test_brief_html_summary_uses_llm_response():
    from ui import board_v2
    with patch.object(board_v2._news_db, "load_news_for_days", return_value=_news_fixture()), \
         patch.object(board_v2, "_load_roadmap", return_value=pd.DataFrame([{"a": 1}])), \
         patch.object(board_v2, "_score_matches", return_value=_matches_fixture()), \
         patch("sola.board_brief.brief", return_value="**AI 비전 검사**가 부서 핵심 시그널입니다."):
        board_v2._brief_html.clear()
        brief = board_v2._brief_html(persona_label="도장1팀")
    # 요약 텍스트가 LLM 응답으로 채워짐 + <b> 마크다운 변환
    assert "<b>AI 비전 검사</b>" in brief["summary"]
    assert "부서 핵심 시그널" in brief["summary"]


def test_brief_html_summary_falls_back_to_text_when_llm_empty():
    """sola.board_brief 가 빈 문자열 반환 시에도 기존 fallback 텍스트 노출."""
    from ui import board_v2
    with patch.object(board_v2._news_db, "load_news_for_days", return_value=_news_fixture()), \
         patch.object(board_v2, "_load_roadmap", return_value=pd.DataFrame([{"a": 1}])), \
         patch.object(board_v2, "_score_matches", return_value=_matches_fixture()), \
         patch("sola.board_brief.brief", return_value=""):
        board_v2._brief_html.clear()
        brief = board_v2._brief_html(persona_label="도장")
    assert "두드러집니다" in brief["summary"] or "1건" in brief["summary"]


def test_brief_html_cache_key_includes_persona_label():
    """다른 persona → 캐시 분리 → LLM 두 번 호출."""
    from ui import board_v2
    with patch.object(board_v2._news_db, "load_news_for_days", return_value=_news_fixture()), \
         patch.object(board_v2, "_load_roadmap", return_value=pd.DataFrame([{"a": 1}])), \
         patch.object(board_v2, "_score_matches", return_value=_matches_fixture()), \
         patch("sola.board_brief.brief", side_effect=["응답A", "응답B"]) as mock_brief:
        board_v2._brief_html.clear()
        b1 = board_v2._brief_html(persona_label="도장1팀")
        b2 = board_v2._brief_html(persona_label="용접팀")
    assert "응답A" in b1["summary"]
    assert "응답B" in b2["summary"]
    assert mock_brief.call_count == 2
