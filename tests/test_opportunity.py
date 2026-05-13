"""sola.opportunity — 부서×공정 매트릭스 점수."""
from __future__ import annotations

from unittest.mock import patch

import pandas as pd

from sola import opportunity


def _sample_news():
    return pd.DataFrame([
        {"title": "용접 자동화 로봇 도입", "press": "AI Times",
         "summary": "용접 자동화 로봇", "keywords": "용접, 자동화, 로봇", "link": "x1"},
        {"title": "강재 절단 효율화", "press": "오토메이션월드",
         "summary": "강재 절단 효율", "keywords": "강재, 절단", "link": "x2"},
        {"title": "검사 시스템 비전 AI", "press": "AI Times",
         "summary": "비전 AI 검사", "keywords": "비전 AI, 검사", "link": "x3"},
    ])


def _sample_roadmap():
    return pd.DataFrame([
        {"dept": "가공부", "lv1": "실행분과", "lv2": "구조내업", "lv3": "전처리",
         "task": "강재선별", "sub_task": "크레인", "task_def": "", "sws_no": "", "sws_name": "강재 하역"},
        {"dept": "가공부", "lv1": "실행분과", "lv2": "구조내업", "lv3": "가공",
         "task": "절단", "sub_task": "강재 절단", "task_def": "", "sws_no": "", "sws_name": "절단 작업"},
        {"dept": "조립부", "lv1": "실행분과", "lv2": "구조내업", "lv3": "형강",
         "task": "용접", "sub_task": "B/up 용접", "task_def": "", "sws_no": "", "sws_name": "용접 작업"},
    ])


def test_score_cells_returns_ranked_dept_lv3_aggregate():
    out = opportunity.score_cells(_sample_news(), _sample_roadmap())
    assert not out.empty
    assert set(out.columns) >= {"dept", "lv3", "cell_score", "avg_score",
                                "matched_news", "matched_tasks",
                                "sample_tasks", "sample_news"}
    # cell_score 내림차순
    scores = out["cell_score"].tolist()
    assert scores == sorted(scores, reverse=True)


def test_score_cells_empty_for_empty_inputs():
    out = opportunity.score_cells(pd.DataFrame(), _sample_roadmap())
    assert out.empty
    out = opportunity.score_cells(_sample_news(), pd.DataFrame())
    assert out.empty


def test_score_cells_sample_fields_populated():
    out = opportunity.score_cells(_sample_news(), _sample_roadmap())
    for _, row in out.iterrows():
        assert isinstance(row["sample_tasks"], str)
        assert isinstance(row["sample_news"], str)


def test_llm_commentary_uses_cache():
    from store import cache as cache_mod

    cache_mod.clear()
    calls = {"n": 0}

    def _fake_chat(messages, **kw):
        calls["n"] += 1
        return "이 공정은 **비전 AI** 도입이 유망합니다."

    with patch.object(opportunity, "chat", _fake_chat):
        a = opportunity.llm_commentary("가공부", "가공", "절단 효율", "절단; 강재선별")
        b = opportunity.llm_commentary("가공부", "가공", "절단 효율", "절단; 강재선별")
    assert a == b
    assert calls["n"] == 1


def test_llm_commentary_returns_empty_when_not_configured():
    from sola.client import LLMNotConfigured

    def _fake_chat(messages, **kw):
        raise LLMNotConfigured("no key")

    with patch.object(opportunity, "chat", _fake_chat):
        out = opportunity.llm_commentary("부서X", "공정Y", "뉴스", "작업")
    assert out == ""


def _sample_cells_df():
    return pd.DataFrame([
        {"dept": "가공부", "lv3": "가공", "cell_score": 5.0,
         "sample_news": "절단 효율", "sample_tasks": "절단; 강재선별"},
        {"dept": "조립부", "lv3": "형강", "cell_score": 4.2,
         "sample_news": "용접 자동화", "sample_tasks": "B/up 용접"},
        {"dept": "선각부", "lv3": "도장", "cell_score": 3.1,
         "sample_news": "도장 로봇", "sample_tasks": "외판 도장"},
    ])


def test_prefill_commentaries_returns_dict_keyed_by_dept_lv3(monkeypatch):
    from store import cache as cache_mod
    from sola import client as client_mod

    cache_mod.clear()

    def _fake_chat(messages, **kw):
        # 사용자 메시지의 dept 글자를 이어 반환 → 셀마다 다른 코멘트
        user = next(m["content"] for m in messages if m["role"] == "user")
        return "comment-for-" + user.split("\n")[0]

    monkeypatch.setattr(opportunity, "chat", _fake_chat)
    monkeypatch.setattr(client_mod, "is_configured", lambda: True)

    out = opportunity.prefill_commentaries(_sample_cells_df(), max_cells=10)
    assert set(out.keys()) == {("가공부", "가공"), ("조립부", "형강"), ("선각부", "도장")}
    assert all(v.startswith("comment-for-") for v in out.values())


def test_prefill_commentaries_caps_at_max_cells(monkeypatch):
    from store import cache as cache_mod
    from sola import client as client_mod

    cache_mod.clear()
    calls = {"n": 0}

    def _fake_chat(messages, **kw):
        calls["n"] += 1
        return f"comment-{calls['n']}"

    monkeypatch.setattr(opportunity, "chat", _fake_chat)
    monkeypatch.setattr(client_mod, "is_configured", lambda: True)

    out = opportunity.prefill_commentaries(_sample_cells_df(), max_cells=2)
    assert len(out) == 2
    assert calls["n"] == 2
    # 상위 2개 셀(점수순)만 포함
    assert ("가공부", "가공") in out
    assert ("조립부", "형강") in out
    assert ("선각부", "도장") not in out


def test_prefill_commentaries_uses_cache_on_second_call(monkeypatch):
    from store import cache as cache_mod
    from sola import client as client_mod

    cache_mod.clear()
    calls = {"n": 0}

    def _fake_chat(messages, **kw):
        calls["n"] += 1
        return "shared-comment"

    monkeypatch.setattr(opportunity, "chat", _fake_chat)
    monkeypatch.setattr(client_mod, "is_configured", lambda: True)

    opportunity.prefill_commentaries(_sample_cells_df(), max_cells=10)
    first_calls = calls["n"]
    opportunity.prefill_commentaries(_sample_cells_df(), max_cells=10)
    # 같은 입력 → 모두 캐시 hit, 추가 LLM 호출 없음
    assert calls["n"] == first_calls


def test_prefill_commentaries_empty_when_llm_not_configured(monkeypatch):
    from sola import client as client_mod

    called = {"n": 0}

    def _fake_chat(messages, **kw):
        called["n"] += 1
        return "should-not-be-called"

    monkeypatch.setattr(opportunity, "chat", _fake_chat)
    monkeypatch.setattr(client_mod, "is_configured", lambda: False)

    out = opportunity.prefill_commentaries(_sample_cells_df(), max_cells=10)
    assert out == {}
    assert called["n"] == 0  # is_configured 가드로 LLM 호출 자체 안 됨


def test_prefill_commentaries_progress_callback_invoked(monkeypatch):
    from store import cache as cache_mod
    from sola import client as client_mod

    cache_mod.clear()
    monkeypatch.setattr(opportunity, "chat", lambda messages, **kw: "x")
    monkeypatch.setattr(client_mod, "is_configured", lambda: True)

    events: list[tuple[int, int]] = []

    def _cb(done: int, total: int, payload) -> None:
        events.append((done, total))
        assert isinstance(payload, tuple) and len(payload) == 3

    opportunity.prefill_commentaries(_sample_cells_df(), max_cells=3, progress_cb=_cb)
    assert events == [(1, 3), (2, 3), (3, 3)]


def test_prefill_commentaries_empty_inputs(monkeypatch):
    from sola import client as client_mod

    monkeypatch.setattr(client_mod, "is_configured", lambda: True)
    monkeypatch.setattr(opportunity, "chat", lambda messages, **kw: "x")

    assert opportunity.prefill_commentaries(pd.DataFrame(), max_cells=10) == {}
    assert opportunity.prefill_commentaries(_sample_cells_df(), max_cells=0) == {}


def test_prefill_commentaries_excludes_empty_comments(monkeypatch):
    from store import cache as cache_mod
    from sola import client as client_mod

    cache_mod.clear()

    def _fake_chat(messages, **kw):
        user = next(m["content"] for m in messages if m["role"] == "user")
        # 조립부 셀에 대해서는 빈 문자열 반환 (LLM 이 비어있는 응답을 보낸 경우)
        return "" if "조립부" in user else "ok"

    monkeypatch.setattr(opportunity, "chat", _fake_chat)
    monkeypatch.setattr(client_mod, "is_configured", lambda: True)

    out = opportunity.prefill_commentaries(_sample_cells_df(), max_cells=10)
    assert ("조립부", "형강") not in out
    assert ("가공부", "가공") in out
    assert ("선각부", "도장") in out
