"""sola.preview — LLM 미설정 시 입력 컨텍스트 미리보기 + 각 LLM 호출 지점 통합."""
from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest

from sola import insight, propose, summarize
from sola.client import LLMNotConfigured
from sola.preview import format_messages_preview


def _raises_unset(*_a, **_kw):
    raise LLMNotConfigured("LLM_API_KEY 가 비어 있습니다 (.env 확인).")


def test_format_messages_preview_includes_all_roles_and_content():
    out = format_messages_preview(
        [
            {"role": "system", "content": "당신은 SOLA 입니다."},
            {"role": "user", "content": "오늘 트렌드 알려줘"},
            {"role": "assistant", "content": "이전 응답"},
        ]
    )
    assert "system" in out
    assert "user" in out
    assert "assistant" in out
    assert "당신은 SOLA 입니다." in out
    assert "오늘 트렌드 알려줘" in out
    assert "이전 응답" in out
    # 본문은 코드블록 안에 들어가야 (들여쓰기·줄바꿈 보존).
    assert "```text" in out
    # 기본 footer 안내 포함.
    assert "LLM_API_KEY" in out


def test_format_messages_preview_custom_header_and_no_footer():
    out = format_messages_preview(
        [{"role": "user", "content": "hi"}],
        header="🧪 테스트 헤더",
        footer_hint=False,
    )
    assert "🧪 테스트 헤더" in out
    assert "LLM_API_KEY" not in out  # footer 비활성


def test_summarize_news_returns_preview_when_llm_unset():
    df = pd.DataFrame([{"title": "용접 자동화", "press": "AITimes", "summary": "조선소", "link": "x"}])
    with patch.object(summarize, "chat", _raises_unset):
        out = summarize.summarize_news(df, max_items=5)
    # 에러 메시지가 아니라 입력 컨텍스트 미리보기여야 한다.
    assert "LLM 미설정" in out
    assert "용접 자동화" in out
    assert "system" in out
    assert "user" in out


def test_propose_for_task_returns_preview_when_llm_unset():
    news = pd.DataFrame([{"title": "용접 로봇 신기술", "press": "AITimes", "summary": "", "link": "z"}])
    task = {"dept": "가공부", "task": "강재선별"}
    with patch.object(propose, "chat", _raises_unset):
        out = propose.propose_for_task(task, news)
    assert "LLM 미설정" in out
    assert "강재선별" in out
    assert "용접 로봇 신기술" in out


def test_insight_for_dept_returns_preview_when_llm_unset():
    from store import cache

    cache.clear()
    news = pd.DataFrame([{"title": "디지털 트윈 도입", "press": "AITimes"}])
    with patch.object(insight, "chat", _raises_unset):
        out = insight.insight_for_dept("가공부", news)
    assert "LLM 미설정" in out
    assert "가공부" in out
    assert "디지털 트윈 도입" in out


def test_insight_for_dept_does_not_cache_preview():
    """preview 응답은 캐시되지 않아야 — 키 세팅 후 재호출 시 실제 LLM 응답으로 대체되어야 한다."""
    from store import cache

    cache.clear()
    news = pd.DataFrame([{"title": "디지털 트윈", "press": "X"}])

    # 1차: 미설정 → preview.
    with patch.object(insight, "chat", _raises_unset):
        first = insight.insight_for_dept("가공부", news)
    assert "LLM 미설정" in first

    # 2차: 키 세팅 후 정상 호출 → 실제 응답이 와야 한다 (이전 preview 가 캐시에 박혀있으면 안 됨).
    def _ok_chat(*_a, **_kw):
        return "✅ 부서 인사이트 한 줄"

    with patch.object(insight, "chat", _ok_chat):
        second = insight.insight_for_dept("가공부", news)
    assert "✅ 부서 인사이트 한 줄" in second
    assert "LLM 미설정" not in second


def test_refine_proposal_still_raises_to_protect_active_md():
    """`_do_refine` 가 좌측 본문을 보호할 수 있도록 refine 은 raise 동작 유지."""
    from sola import refine
    from sola.client import LLMNotConfigured

    with patch.object(refine, "chat", _raises_unset):
        with pytest.raises(LLMNotConfigured):
            refine.refine_proposal("# 제안서", "더 짧게")


def test_build_refine_messages_matches_refine_proposal_call():
    """`refine_proposal` 의 chat 호출과 `build_refine_messages` 가 동일 messages 를 만든다."""
    from sola import refine

    captured: dict = {}

    def _capture(messages, **kw):
        captured["messages"] = messages
        return "ok"

    with patch.object(refine, "chat", _capture):
        refine.refine_proposal("# 제안서", "더 짧게")
    direct = refine.build_refine_messages("# 제안서", "더 짧게")
    assert captured["messages"] == direct
