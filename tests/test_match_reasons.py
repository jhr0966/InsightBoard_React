"""매칭 v2 (Step 5) — 필드별 가중·결정적 매칭 이유·임계값 회귀 테스트."""
from __future__ import annotations

import pandas as pd

from store import match


def _tasks():
    return pd.DataFrame([{"dept": "도장부", "lv1": "", "lv2": "", "lv3": "도장검사",
                          "task": "도장 검사", "sub_task": "막두께 측정",
                          "task_def": "건조 도막 두께를 측정하고 외관 결함을 검사"}])


def _match(news_rows, **kw):
    return match.score_matches(pd.DataFrame(news_rows), _tasks(), top_k=5, **kw)


def test_returns_components_terms_fields_version():
    out = _match([{"title": "도막 두께 측정 자동화", "summary": "막두께 측정 로봇",
                   "keywords": "막두께, 검사", "keywords_llm": "도장 검사", "link": "a"}])
    row = out.iloc[0]
    comps = row["score_components"]
    assert comps["title_match"] > 0 and comps["keyword_match"] > 0
    assert comps["llm_keyword_match"] == 2.0 * 2  # '도장'·'검사' distinct 2개
    assert abs(row["score"] - sum(comps.values())) < 1e-6  # 성분 합 = 총점
    assert "측정" in row["matched_terms"]
    assert set(row["matched_fields"]) >= {"title", "keywords", "keywords_llm"}
    assert row["matching_version"] == match.MATCHING_VERSION >= 2


def test_title_weighted_above_summary():
    """같은 단어라도 제목 매칭(×3)이 요약 매칭(×1)보다 높은 점수."""
    out = _match([
        {"title": "막두께 신기술", "summary": "", "keywords": "", "link": "t"},
        {"title": "무관 제목", "summary": "막두께 신기술", "keywords": "", "link": "s"},
    ])
    st = float(out[out["link"] == "t"]["score"].iloc[0])
    ss = float(out[out["link"] == "s"]["score"].iloc[0])
    assert st > ss


def test_exact_task_name_bonus_in_title():
    """작업명('도장 검사')이 제목에 그대로 나오면 exact_task_bonus 가산."""
    out = _match([{"title": "조선소 도장 검사 자동화 사례", "summary": "", "keywords": "", "link": "a"}])
    assert out.iloc[0]["score_components"].get("exact_task_bonus", 0) >= match._EXACT_TASK_BONUS


def test_josa_stripped_tokens_match():
    """조사가 붙어도('결함을') 어간('결함')으로 매칭된다."""
    out = _match([{"title": "외관 결함을 잡는 AI", "summary": "", "keywords": "", "link": "a"}])
    assert not out.empty
    assert "결함" in out.iloc[0]["matched_terms"]


def test_min_score_ratio_drops_weak_tail():
    """min_score_ratio 는 작업별 최고점 대비 꼬리 후보를 버린다 (근거 선정용)."""
    news = [
        {"title": "도막 두께 측정 검사 자동화", "summary": "", "keywords": "막두께, 검사", "link": "strong"},
        {"title": "측정 장비 시장 동향", "summary": "", "keywords": "", "link": "weak"},
    ]
    all_rows = _match(news)
    assert set(all_rows["link"]) == {"strong", "weak"}
    cut = _match(news, min_score_ratio=0.5)
    assert list(cut["link"]) == ["strong"]


def test_render_match_reason_rule_based():
    out = _match([{"title": "도막 두께 측정 자동화", "summary": "", "keywords": "", "link": "a"}])
    text = match.render_match_reason(out.iloc[0].to_dict())
    assert "도장 검사" in text and "기사" in text  # 작업명·용어가 문장에 포함
    assert "제목" in text                             # 기여 필드 표기


def test_deterministic_across_runs():
    news = [{"title": f"막두께 측정 {i}", "summary": "", "keywords": "", "link": f"l{i}"}
            for i in range(5)]
    a = _match(news, semantic_weight=match.DEFAULT_SEMANTIC_WEIGHT)
    b = _match(news, semantic_weight=match.DEFAULT_SEMANTIC_WEIGHT)
    assert list(a["link"]) == list(b["link"])
    assert list(a["score"]) == list(b["score"])
