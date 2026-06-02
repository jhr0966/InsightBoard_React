"""M1 룰 기반 뉴스↔작업 매칭. M2에서 SOLA(LLM) 로 대체된다.

뉴스 키워드와 작업(task/sub_task/task_def/sws_name) 의 토큰 중첩 점수 +
(선택) enrich LLM 키워드 가중 + (선택) TF-IDF 코사인 의미유사도 하이브리드.
"""
from __future__ import annotations

import math
import re
from collections import Counter

import pandas as pd


_TOKEN_RE = re.compile(r"[가-힣A-Za-z0-9]{2,}")
_NOISE = {"작업", "공정", "기술", "관련", "통해", "대한", "위한", "그리고", "또는"}

# enrich 된 기사의 LLM 키워드(`keywords_llm`)는 본문/룰 신호보다 강한 토픽 신호다
# (LLM 이 핵심 주제로 추출). 작업 토큰이 기사 LLM 키워드와 겹치면 1건당 이 가중치만큼
# 점수 보너스를 더한다 → enrich 된 기사가 동일 작업에 대해 더 높은 점수 (결정-2 A).
_LLM_KW_WEIGHT = 2.0

# ── 의미유사도(TF-IDF 코사인) 하이브리드 ──────────────────────────────
# 토큰 '교집합'은 같은 단어가 정확히 겹쳐야만 점수가 나서, 표현은 달라도 주제가
# 같은 기사(예: "용접 로봇" ↔ "아크 용접 자동화")를 놓친다. 작업·뉴스 문서를
# TF-IDF 벡터화해 코사인 유사도를 더하면, 흔한 단어는 낮게·희소한 핵심어는 높게
# 가중되어 '의미가 가까운' 매칭을 끌어올린다. `semantic_weight` 로 호출처가 켠다
# (기본 0 = 순수 토큰 매칭, 하위호환). 신경망 임베딩 백엔드가 생기면 `_doc_vectors`
# 만 교체하면 된다(인터페이스 유지).
DEFAULT_SEMANTIC_WEIGHT = 4.0
_SEM_MIN_COS = 0.05  # 이 미만의 코사인은 잡음으로 보고 무시


def _tokens(text: str) -> list[str]:
    return [w for w in _TOKEN_RE.findall((text or "").lower()) if w not in _NOISE]


def _row_text(row: pd.Series, cols: list[str]) -> str:
    return " ".join(str(row.get(c, "")) for c in cols)


def _build_idf(doc_token_sets: list[set[str]]) -> dict[str, float]:
    """문서별 토큰 집합 → idf. idf = ln(N / (1+df)) + 1 (smoothed, 항상 양수)."""
    n = len(doc_token_sets)
    if n == 0:
        return {}
    df: Counter = Counter()
    for toks in doc_token_sets:
        df.update(toks)
    return {t: math.log(n / (1.0 + c)) + 1.0 for t, c in df.items()}


def _tfidf_vec(counter: Counter, idf: dict[str, float]) -> tuple[dict[str, float], float]:
    """tf-idf 가중 벡터(dict) + L2 norm. tf = 1 + ln(count) (log-정규화)."""
    vec = {t: (1.0 + math.log(c)) * idf.get(t, 0.0) for t, c in counter.items() if idf.get(t)}
    norm = math.sqrt(sum(w * w for w in vec.values())) or 1.0
    return vec, norm


def _cosine(a: tuple[dict[str, float], float], b: tuple[dict[str, float], float]) -> float:
    """두 tf-idf 벡터의 코사인 유사도 (공통 키만 순회)."""
    va, na = a
    vb, nb = b
    if len(va) > len(vb):  # 작은 쪽을 순회
        va, vb = vb, va
        na, nb = nb, na
    dot = sum(w * vb.get(t, 0.0) for t, w in va.items())
    return dot / (na * nb)


def score_matches(
    news_df: pd.DataFrame,
    roadmap_df: pd.DataFrame,
    *,
    top_k: int = 5,
    semantic_weight: float = 0.0,
) -> pd.DataFrame:
    """각 작업(row)별로 가장 잘 맞는 뉴스 top_k와 점수를 반환.

    Args:
        top_k: 작업당 상위 매칭 수.
        semantic_weight: >0 이면 TF-IDF 코사인 의미유사도를 `weight*cosine` 만큼
            점수에 가산(0 = 순수 토큰 매칭, 하위호환). `DEFAULT_SEMANTIC_WEIGHT` 권장.

    반환 컬럼: dept, lv1, lv2, lv3, task, sub_task, news_title, link, score
    """
    if news_df.empty or roadmap_df.empty:
        return pd.DataFrame(columns=[
            "dept", "lv1", "lv2", "lv3", "task", "sub_task",
            "news_title", "link", "score",
        ])

    news_cols = [c for c in ("title", "summary", "keywords") if c in news_df.columns]
    task_cols = [c for c in ("task", "sub_task", "task_def", "sws_name", "lv3") if c in roadmap_df.columns]
    has_task_def_json = "task_def_json" in roadmap_df.columns

    news_tokens = [Counter(_tokens(_row_text(row, news_cols))) for _, row in news_df.iterrows()]
    # enrich 된 기사의 LLM 키워드 토큰 집합 (가중 보너스용). enrich 안 된 기사는 빈 집합 → 무영향.
    if "keywords_llm" in news_df.columns:
        news_llm_sets = [set(_tokens(str(row.get("keywords_llm", "") or ""))) for _, row in news_df.iterrows()]
    else:
        news_llm_sets = [set() for _ in range(len(news_df))]

    # task_def_json (신엑셀) 의 평탄 텍스트도 매칭에 합산 — 자동화 영역·품질
    # 리스크·objectives 같은 풍부한 신호가 추가되어 정확도↑. JSON 파싱 비용은
    # row 당 ~0.5ms 수준 (한 번만).
    from roadmap.task_def_json import flatten_for_match

    # 작업 토큰 카운터 미리 계산 (semantic idf corpus + 본 루프 공용).
    task_counters: list[Counter] = []
    for _, task_row in roadmap_df.iterrows():
        task_text = _row_text(task_row, task_cols)
        if has_task_def_json:
            extra = flatten_for_match(task_row.get("task_def_json", ""))
            if extra:
                task_text = task_text + " " + extra
        task_counters.append(Counter(_tokens(task_text)))

    # 의미유사도 준비 — 켜졌을 때만 (벡터화 비용 회피).
    news_vecs: list = []
    task_vecs: list = []
    if semantic_weight > 0:
        idf = _build_idf([set(c) for c in news_tokens] + [set(c) for c in task_counters])
        news_vecs = [_tfidf_vec(c, idf) for c in news_tokens]
        task_vecs = [_tfidf_vec(c, idf) for c in task_counters]

    rows: list[dict] = []
    for ti, (_, task_row) in enumerate(roadmap_df.iterrows()):
        tk_counter = task_counters[ti]
        if not tk_counter:
            continue
        scored: list[tuple[float, int]] = []
        task_keys = set(tk_counter)
        for idx, nc in enumerate(news_tokens):
            common = task_keys & set(nc)
            score = float(sum(min(tk_counter[w], nc[w]) for w in common)) if common else 0.0
            # enrich LLM 키워드 보너스 — 작업 토큰과 겹치는 고유 LLM 키워드 1건당 가중 추가
            # (작업 텍스트의 토큰 중복에 휘둘리지 않게 distinct 매칭 수 기준).
            llm_common = task_keys & news_llm_sets[idx]
            if llm_common:
                score += _LLM_KW_WEIGHT * float(len(llm_common))
            # 의미유사도 가산 — 토큰이 정확히 안 겹쳐도 주제가 가까우면 끌어올림.
            if semantic_weight > 0:
                cos = _cosine(news_vecs[idx], task_vecs[ti])
                if cos >= _SEM_MIN_COS:
                    score += semantic_weight * cos
            if score > 0:
                scored.append((score, idx))
        if not scored:
            continue
        scored.sort(reverse=True)
        for score, idx in scored[:top_k]:
            news_row = news_df.iloc[idx]
            rows.append({
                "dept": task_row.get("dept", ""),
                "lv1": task_row.get("lv1", ""),
                "lv2": task_row.get("lv2", ""),
                "lv3": task_row.get("lv3", ""),
                "task": task_row.get("task", ""),
                "sub_task": task_row.get("sub_task", ""),
                "news_title": news_row.get("title", ""),
                "link": news_row.get("link", ""),
                "score": score,
            })
    return pd.DataFrame(rows)
