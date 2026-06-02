"""Phase E — enrich LLM 키워드(keywords_llm) 매칭 가중 (결정-2 A)."""
from __future__ import annotations

import pandas as pd

from store import match


def _tasks():
    return pd.DataFrame([{"dept": "도장", "lv1": "", "lv2": "", "lv3": "비전 검사",
                          "task": "비전 검사", "sub_task": ""}])


def test_enrich_llm_keyword_boosts_score():
    """동일 base 기사 두 건 중, LLM 키워드에 작업어가 있는 enrich 기사가 더 높은 점수."""
    news = pd.DataFrame([
        {"title": "비전 검사 도입", "summary": "", "keywords": "", "keywords_llm": "비전 검사 자동화", "link": "a"},
        {"title": "비전 검사 도입", "summary": "", "keywords": "", "keywords_llm": "", "link": "b"},
    ])
    out = match.score_matches(news, _tasks(), top_k=5)
    sa = float(out[out["link"] == "a"]["score"].iloc[0])
    sb = float(out[out["link"] == "b"]["score"].iloc[0])
    assert sa > sb


def test_match_backward_compatible_without_keywords_llm():
    """keywords_llm 컬럼이 아예 없어도 기존 base 매칭으로 동작 (후방호환)."""
    news = pd.DataFrame([{"title": "비전 검사", "summary": "", "keywords": "", "link": "a"}])
    out = match.score_matches(news, _tasks(), top_k=5)
    assert not out.empty and float(out["score"].iloc[0]) > 0


def test_llm_keyword_only_match_is_found():
    """base(title/summary/keywords) 매칭이 없어도 LLM 키워드만으로 매칭되면 발견."""
    news = pd.DataFrame([{"title": "무관 기사", "summary": "xyz", "keywords": "",
                          "keywords_llm": "비전 검사", "link": "a"}])
    out = match.score_matches(news, _tasks(), top_k=5)
    assert not out.empty and out["link"].iloc[0] == "a"


def test_empty_keywords_llm_no_bonus():
    """빈/공백 keywords_llm 은 보너스 없음 — base 점수만."""
    news = pd.DataFrame([{"title": "비전 검사", "summary": "", "keywords": "", "keywords_llm": "   ", "link": "a"}])
    out = match.score_matches(news, _tasks(), top_k=5)
    base_only = pd.DataFrame([{"title": "비전 검사", "summary": "", "keywords": "", "link": "a"}])
    out2 = match.score_matches(base_only, _tasks(), top_k=5)
    assert float(out["score"].iloc[0]) == float(out2["score"].iloc[0])


def test_weight_constant_positive():
    assert match._LLM_KW_WEIGHT > 0
