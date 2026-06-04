"""store.match — TF-IDF 코사인 의미유사도 하이브리드 (semantic_weight)."""
from __future__ import annotations

import pandas as pd

from store import match


def _news(rows):
    return pd.DataFrame(rows)


def test_semantic_weight_zero_is_backward_compatible():
    """semantic_weight=0(기본) 이면 순수 토큰 매칭 점수와 동일."""
    news = _news([
        {"title": "레이저 절단 신기술", "summary": "", "keywords": "", "link": "a"},
    ])
    tasks = pd.DataFrame([{"task": "절단", "sub_task": "레이저", "dept": "가공"}])
    base = match.score_matches(news, tasks, top_k=5)
    explicit0 = match.score_matches(news, tasks, top_k=5, semantic_weight=0.0)
    assert not base.empty
    assert float(base["score"].iloc[0]) == float(explicit0["score"].iloc[0])
    # 토큰 1개(레이저)+1개(절단) 중첩 = 2.0 (의미 가산 없음)
    assert float(base["score"].iloc[0]) == 2.0


def test_semantic_breaks_token_tie_by_idf_weight():
    """토큰 중첩이 동점(각 1건)이라도, 희소어를 공유한 기사가 의미유사도로 앞선다.

    '레이저'는 task1 에만(희소·고 idf), '로봇'은 여러 task 에(흔함·저 idf).
    뉴스 A=레이저공유, B=로봇공유 → raw 동점이나 semantic 켜면 A > B.
    """
    tasks = pd.DataFrame([
        {"task": "레이저 로봇", "sub_task": "", "dept": "가공"},   # task1 (대상)
        {"task": "로봇 운반", "sub_task": "", "dept": "물류"},
        {"task": "로봇 조립", "sub_task": "", "dept": "조립"},
        {"task": "로봇 도장", "sub_task": "", "dept": "도장"},
    ])
    news = _news([
        {"title": "레이저 신기술", "summary": "", "keywords": "", "link": "A"},  # 희소어 공유
        {"title": "로봇 신기술", "summary": "", "keywords": "", "link": "B"},    # 흔한어 공유
    ])

    # raw(토큰): A·B 모두 task1 과 1건 중첩 → 동점
    raw = match.score_matches(news, tasks.head(1), top_k=5)
    sa_raw = float(raw[raw["link"] == "A"]["score"].iloc[0])
    sb_raw = float(raw[raw["link"] == "B"]["score"].iloc[0])
    assert sa_raw == sb_raw == 1.0

    # semantic 켜면 task1 매칭에서 A(희소어 레이저) 가 B(흔한어 로봇) 보다 높다
    sem = match.score_matches(news, tasks, top_k=5,
                              semantic_weight=match.DEFAULT_SEMANTIC_WEIGHT)
    t1 = sem[(sem["task"] == "레이저 로봇")]
    sa = float(t1[t1["link"] == "A"]["score"].iloc[0])
    sb = float(t1[t1["link"] == "B"]["score"].iloc[0])
    assert sa > sb


def test_semantic_ignores_pairs_without_shared_tokens():
    """공유 토큰이 전혀 없으면 코사인 0 → 매칭 안 됨(잡음 방지)."""
    tasks = pd.DataFrame([{"task": "용접 로봇", "sub_task": "", "dept": "가공"}])
    news = _news([
        {"title": "환율 금리 동향", "summary": "", "keywords": "", "link": "x"},
    ])
    out = match.score_matches(news, tasks, top_k=5,
                              semantic_weight=match.DEFAULT_SEMANTIC_WEIGHT)
    assert out.empty  # 겹치는 단어 0 → 점수 0 → 제외


def test_semantic_weight_empty_inputs_safe():
    empty = pd.DataFrame()
    tasks = pd.DataFrame([{"task": "용접", "sub_task": "", "dept": "가공"}])
    assert match.score_matches(empty, tasks, semantic_weight=4.0).empty
    news = _news([{"title": "용접 로봇", "summary": "", "keywords": "", "link": "a"}])
    assert match.score_matches(news, pd.DataFrame(), semantic_weight=4.0).empty


# ── 내부 TF-IDF 헬퍼 엣지케이스 (_build_idf / _tfidf_vec / _cosine) ──

def test_build_idf_empty_corpus_returns_empty():
    assert match._build_idf([]) == {}


def test_build_idf_is_always_positive_even_for_ubiquitous_token():
    """모든 문서에 등장하는 흔한 토큰도 smoothed idf 라 양수(>0) — 음수 가중 방지."""
    idf = match._build_idf([{"로봇"}, {"로봇"}, {"로봇"}])
    assert idf["로봇"] > 0
    # 희소어가 흔한어보다 idf 높다
    idf2 = match._build_idf([{"로봇", "레이저"}, {"로봇"}, {"로봇"}])
    assert idf2["레이저"] > idf2["로봇"]


def test_tfidf_vec_empty_counter_safe_norm():
    """빈 counter → 빈 벡터 + norm 1.0(0 나눗셈 방지)."""
    from collections import Counter
    vec, norm = match._tfidf_vec(Counter(), {"로봇": 1.0})
    assert vec == {}
    assert norm == 1.0


def test_tfidf_vec_drops_tokens_without_idf():
    """idf 에 없는 토큰(코퍼스 밖)은 벡터에서 제외 — KeyError 없이 0 가중."""
    from collections import Counter
    vec, _norm = match._tfidf_vec(Counter({"로봇": 2, "미지어": 1}), {"로봇": 1.5})
    assert "로봇" in vec and "미지어" not in vec


def test_cosine_disjoint_is_zero_and_identical_is_one():
    from collections import Counter
    idf = match._build_idf([{"a", "b"}, {"b", "c"}, {"a", "c"}])
    va = match._tfidf_vec(Counter({"a": 1}), idf)
    vb = match._tfidf_vec(Counter({"b": 1}), idf)
    assert match._cosine(va, vb) == 0.0          # 공유 토큰 없음
    assert abs(match._cosine(va, va) - 1.0) < 1e-9  # 자기 자신 = 1


def test_cosine_is_symmetric_regardless_of_vector_size():
    """작은 쪽을 순회하는 최적화가 대칭성을 깨지 않는지(a·b == b·a)."""
    from collections import Counter
    idf = match._build_idf([{"a", "b", "c"}, {"a"}, {"b"}, {"c"}])
    big = match._tfidf_vec(Counter({"a": 2, "b": 1, "c": 1}), idf)
    small = match._tfidf_vec(Counter({"a": 1}), idf)
    assert abs(match._cosine(big, small) - match._cosine(small, big)) < 1e-12
