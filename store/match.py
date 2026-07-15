"""룰 기반 뉴스↔작업 매칭 — 필드별 가중 + 결정적 매칭 이유 (Step 5).

점수 = Σ(뉴스 필드별 토큰 중첩 × 필드 가중) + LLM 키워드 보너스
     + 작업명 정확 일치 보너스 + (선택) TF-IDF 코사인 의미유사도.

매칭 **이유는 LLM 이 아니라 결정적 데이터**로 반환한다(개편 계획 §8):
`score_components`(성분별 점수)·`matched_terms`(기여 상위 용어)·
`matched_fields`(기여한 뉴스 필드). 사용자 표시 문장은
`render_match_reason()` 이 규칙 기반으로 조합한다.

알고리즘이 바뀌면 `MATCHING_VERSION` 을 올린다 — 파생 데이터
(article_task_links, Step 6)의 stale 판정·재빌드 기준.
품질 변경은 `scripts/evaluate_matching.py` 기준선 대비로만 채택
(v1 기준선: P@3 51.7% · 상위3 무관 혼입 80% — data/evaluation/baseline_matching_v1.json).
"""
from __future__ import annotations

import math
import re
from collections import Counter

import pandas as pd

# 매칭 알고리즘 버전 — 점수식·가중치 변경 시 +1.
MATCHING_VERSION = 2

_TOKEN_RE = re.compile(r"[가-힣A-Za-z0-9]{2,}")
_NOISE = {"작업", "공정", "기술", "관련", "통해", "대한", "위한", "그리고", "또는"}

# ── 필드별 가중 (v2) ──────────────────────────────────────────
# 기사 제목·추출 키워드는 주제 신호가 강하고, 요약(검색 스니펫)은 잡음이 많다.
# v1(모든 필드 동일 가중 합산)은 상위3 무관 혼입 80% — 필드 분리로 정밀도를 올린다.
NEWS_FIELD_WEIGHTS: dict[str, float] = {"title": 3.0, "keywords": 2.0, "summary": 1.0}
# 성분 키 이름(계획 §8 스키마) — 필드명 복수형과 무관하게 고정.
_COMPONENT_KEY = {"title": "title_match", "keywords": "keyword_match", "summary": "summary_match"}

# 작업명(task/sub_task)이 기사 제목에 **문자열 그대로** 등장하면 매우 강한 신호.
_EXACT_TASK_BONUS = 3.0

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


# 끝에 붙는 흔한 조사 — 제거해야 "결함을"과 "결함"이 같은 토큰이 된다(v2).
# 남는 어간이 2자 이상일 때만 벗긴다(예: "부품"의 "품"까지 깎지 않게).
_JOSA = ("에서의", "으로써", "에서", "에게", "부터", "까지", "으로", "이라",
         "라는", "하며", "하고", "에는", "와의", "과의",
         "을", "를", "은", "는", "이", "가", "의", "와", "과", "에", "로", "도", "만")


def _strip_josa(tok: str) -> str:
    for j in _JOSA:  # 긴 조사 우선(위 튜플 순서)
        if tok.endswith(j) and len(tok) - len(j) >= 2:
            return tok[: len(tok) - len(j)]
    return tok


def _tokens(text: str) -> list[str]:
    out = []
    for w in _TOKEN_RE.findall((text or "").lower()):
        w = _strip_josa(w)
        if w not in _NOISE:
            out.append(w)
    return out


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
    min_score_ratio: float = 0.0,
) -> pd.DataFrame:
    """각 작업(row)별로 가장 잘 맞는 뉴스 top_k와 점수를 반환.

    min_score_ratio: 작업별 최고점 대비 이 비율 미만인 꼬리 후보를 버린다
        (0 = 끔·하위호환). 정답셋 실측(v2): 0.25 에서 상위3 무관 혼입 85%→40%,
        recall@3 78%→70% — **근거 선정**(제안서 등)은 0.25 권장, 집계(히트맵)는 0.

    Args:
        top_k: 작업당 상위 매칭 수.
        semantic_weight: >0 이면 TF-IDF 코사인 의미유사도를 `weight*cosine` 만큼
            점수에 가산(0 = 순수 토큰 매칭, 하위호환). `DEFAULT_SEMANTIC_WEIGHT` 권장.

    반환 컬럼: dept, lv1, lv2, lv3, task, sub_task, news_title, link, score,
              score_components(dict), matched_terms(list), matched_fields(list),
              matching_version
    """
    empty_cols = [
        "dept", "lv1", "lv2", "lv3", "task", "sub_task", "news_title", "link",
        "score", "score_components", "matched_terms", "matched_fields", "matching_version",
    ]
    if news_df.empty or roadmap_df.empty:
        return pd.DataFrame(columns=empty_cols)

    news_cols = [c for c in ("title", "summary", "keywords") if c in news_df.columns]
    task_cols = [c for c in ("task", "sub_task", "task_def", "sws_name", "lv3") if c in roadmap_df.columns]
    has_task_def_json = "task_def_json" in roadmap_df.columns

    # iterrows 는 행마다 Series 를 만들어 느리다 → records(dict) 1회 변환으로 대체.
    news_records = news_df.to_dict("records")
    # 전체 토큰(의미유사도 corpus 용) + 필드별 토큰(가중 채점·이유 산출용).
    news_tokens = [Counter(_tokens(_row_text(row, news_cols))) for row in news_records]
    news_field_tokens: list[dict[str, Counter]] = [
        {f: Counter(_tokens(str(row.get(f, "") or ""))) for f in NEWS_FIELD_WEIGHTS if f in news_cols}
        for row in news_records
    ]
    news_titles_lower = [str(row.get("title", "") or "").lower() for row in news_records]
    # enrich 된 기사의 LLM 키워드 토큰 집합 (가중 보너스용). enrich 안 된 기사는 빈 집합 → 무영향.
    if "keywords_llm" in news_df.columns:
        news_llm_sets = [set(_tokens(str(row.get("keywords_llm", "") or ""))) for row in news_records]
    else:
        news_llm_sets = [set() for _ in range(len(news_df))]

    # task_def_json (신엑셀) 의 평탄 텍스트도 매칭에 합산 — 자동화 영역·품질
    # 리스크·objectives 같은 풍부한 신호가 추가되어 정확도↑. JSON 파싱 비용은
    # row 당 ~0.5ms 수준 (한 번만).
    from roadmap.task_def_json import flatten_for_match

    # 작업 토큰 카운터 미리 계산 (semantic idf corpus + 본 루프 공용).
    task_records = roadmap_df.to_dict("records")
    task_counters: list[Counter] = []
    for task_row in task_records:
        task_text = _row_text(task_row, task_cols)
        if has_task_def_json:
            extra = flatten_for_match(task_row.get("task_def_json", ""))
            if extra:
                task_text = task_text + " " + extra
        task_counters.append(Counter(_tokens(task_text)))

    # idf 는 항상 계산 — 토큰 중첩 자체를 idf 로 가중해 '자동화·로봇·검사' 같은
    # 범용 단어가 여러 작업 top3 에 반복 등장하는 편중(v1 혼입 80%)을 억제한다.
    idf = _build_idf([set(c) for c in news_tokens] + [set(c) for c in task_counters])

    # 의미유사도 준비 — 켜졌을 때만 (벡터화 비용 회피).
    news_vecs: list = []
    task_vecs: list = []
    if semantic_weight > 0:
        news_vecs = [_tfidf_vec(c, idf) for c in news_tokens]
        task_vecs = [_tfidf_vec(c, idf) for c in task_counters]

    # 뉴스 필드 한국어 라벨 — 이유 문장 조합용.
    rows: list[dict] = []
    for ti, task_row in enumerate(task_records):
        tk_counter = task_counters[ti]
        if not tk_counter:
            continue
        task_keys = set(tk_counter)
        # 작업명 정확 일치 후보 — task/sub_task 원문(2자 이상)이 제목에 그대로 나오면 강신호.
        exact_names = [
            s for s in (str(task_row.get("task", "") or "").strip().lower(),
                        str(task_row.get("sub_task", "") or "").strip().lower())
            if len(s) >= 2
        ]
        scored: list[tuple[float, int, dict, list, list]] = []
        for idx in range(len(news_records)):
            comps: dict[str, float] = {}
            term_contrib: Counter = Counter()
            fields: list[str] = []
            # ① 필드별 토큰 중첩 × 가중 — 제목(3)·키워드(2)·요약(1).
            for f, w in NEWS_FIELD_WEIGHTS.items():
                fc = news_field_tokens[idx].get(f)
                if not fc:
                    continue
                common = task_keys & set(fc)
                if not common:
                    continue
                # idf 가중 중첩 — 흔한 단어(저 idf)는 낮게, 핵심어(고 idf)는 높게.
                part = sum(min(tk_counter[t], fc[t]) * idf.get(t, 1.0) for t in common) * w
                ck = _COMPONENT_KEY[f]
                comps[ck] = comps.get(ck, 0.0) + part
                fields.append(f)
                for t in common:
                    term_contrib[t] += min(tk_counter[t], fc[t]) * w * idf.get(t, 1.0)
            # ② enrich LLM 키워드 보너스 — distinct 매칭 수 기준(기존 규칙 유지).
            llm_common = task_keys & news_llm_sets[idx]
            if llm_common:
                comps["llm_keyword_match"] = _LLM_KW_WEIGHT * float(len(llm_common))
                fields.append("keywords_llm")
                for t in llm_common:
                    term_contrib[t] += _LLM_KW_WEIGHT
            # ③ 작업명 정확 일치 보너스 — 작업명 원문이 기사 제목에 그대로 등장.
            exact_hits = [s for s in exact_names if s in news_titles_lower[idx]]
            if exact_hits:
                comps["exact_task_bonus"] = _EXACT_TASK_BONUS * float(len(exact_hits))
            # ④ 의미유사도 가산 — 토큰이 정확히 안 겹쳐도 주제가 가까우면 끌어올림.
            if semantic_weight > 0:
                cos = _cosine(news_vecs[idx], task_vecs[ti])
                if cos >= _SEM_MIN_COS:
                    comps["semantic_similarity"] = round(semantic_weight * cos, 4)
            score = float(sum(comps.values()))
            if score > 0:
                terms = [t for t, _ in sorted(
                    term_contrib.items(), key=lambda kv: (-kv[1], kv[0]))][:8]
                scored.append((score, idx, comps, terms, fields))
        if not scored:
            continue
        # 동점 시 idx(입력 순서) 오름차순 — 결정적 순서 보장.
        scored.sort(key=lambda s: (-s[0], s[1]))
        if min_score_ratio > 0:
            cutoff = scored[0][0] * min_score_ratio
            scored = [s for s in scored if s[0] >= cutoff]
        for score, idx, comps, terms, fields in scored[:top_k]:
            news_row = news_records[idx]
            rows.append({
                "dept": task_row.get("dept", ""),
                "lv1": task_row.get("lv1", ""),
                "lv2": task_row.get("lv2", ""),
                "lv3": task_row.get("lv3", ""),
                "task": task_row.get("task", ""),
                "sub_task": task_row.get("sub_task", ""),
                "news_title": news_row.get("title", ""),
                "link": news_row.get("link", ""),
                "score": round(score, 4),
                "score_components": {k: round(v, 4) for k, v in comps.items()},
                "matched_terms": terms,
                "matched_fields": fields,
                "matching_version": MATCHING_VERSION,
            })
    return pd.DataFrame(rows)


_FIELD_LABEL = {"title": "제목", "keywords": "키워드", "summary": "요약",
                "keywords_llm": "LLM 키워드"}


def render_match_reason(row: dict) -> str:
    """매칭 근거 데이터 → 사용자 표시 한 문장 (규칙 조합 — LLM 미사용).

    예: "기사의 ‘비전 검사·표면 결함’이 작업 ‘도장 외관검사’와 연결됩니다
        (제목·LLM 키워드 일치)"
    """
    terms = [t for t in (row.get("matched_terms") or [])][:3]
    task_name = str(row.get("task") or row.get("lv3") or "").strip()
    comps = row.get("score_components") or {}
    fields = [f for f in (row.get("matched_fields") or []) if f in _FIELD_LABEL]
    bits = []
    if terms:
        bits.append(f"기사의 ‘{'·'.join(terms)}’")
    if task_name:
        bits.append(f"작업 ‘{task_name}’와 연결됩니다")
    tail = []
    if comps.get("exact_task_bonus"):
        tail.append("작업명 일치")
    if fields:
        tail.append("·".join(dict.fromkeys(_FIELD_LABEL[f] for f in fields)) + " 일치")
    sentence = " ".join(bits) if bits else "관련 신호가 감지됐습니다"
    return sentence + (f" ({', '.join(tail)})" if tail else "")
