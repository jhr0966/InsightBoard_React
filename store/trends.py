"""뉴스 트렌드 집계 — 일자별·소스별·키워드별 + 다중 일자 비교."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone

import pandas as pd


def _date_col(df: pd.DataFrame) -> pd.Series:
    """published_at 이 있으면 우선, 없으면 date 사용. 'YYYY-MM-DD' 로 정규화."""
    if "published_at" in df.columns:
        s = pd.to_datetime(df["published_at"], errors="coerce", utc=True)
        out = s.dt.strftime("%Y-%m-%d")
        return out.fillna(df.get("date", pd.Series("", index=df.index)).astype(str))
    return df.get("date", pd.Series("", index=df.index)).astype(str)


def by_date(df: pd.DataFrame) -> pd.DataFrame:
    """일자별 기사 수. 컬럼: date, count (오름차순)."""
    if df.empty:
        return pd.DataFrame(columns=["date", "count"])
    dates = _date_col(df)
    dates = dates[dates.ne("")]
    if dates.empty:
        return pd.DataFrame(columns=["date", "count"])
    return (
        dates.value_counts().rename_axis("date").reset_index(name="count")
        .sort_values("date", ignore_index=True)
    )


def by_source(df: pd.DataFrame) -> pd.DataFrame:
    """소스별 기사 수. 컬럼: source, count."""
    if df.empty or "source" not in df.columns:
        return pd.DataFrame(columns=["source", "count"])
    return (
        df.groupby("source", dropna=False).size()
        .reset_index(name="count").sort_values("count", ascending=False, ignore_index=True)
    )


def top_keywords(df: pd.DataFrame, top_n: int = 20) -> pd.DataFrame:
    """키워드(컬럼 'keywords', comma-separated) 빈도 상위 N."""
    if df.empty or "keywords" not in df.columns:
        return pd.DataFrame(columns=["keyword", "count"])
    tokens = _all_keyword_tokens(df)
    if not tokens:
        return pd.DataFrame(columns=["keyword", "count"])
    return pd.DataFrame(Counter(tokens).most_common(top_n), columns=["keyword", "count"])


# ── 다중 일자 트렌드 ──────────────────────────────────────────

# 키워드로서 의미 없는 한국어 조사·문법 조각·일반 동사/부사 — 트렌드·키워드 관리에서
# 제외(예: '것으로', '등', '관련'). LLM/룰 추출이 가끔 본문 문법 토큰을 키워드로
# 올리는데('것으로 전망', '대한 우려' 등) 트렌드 차트를 의미 없게 만든다.
_KEYWORD_STOPWORDS: frozenset[str] = frozenset({
    "것으로", "것이다", "것", "등", "및", "이번", "관련", "대한", "위한", "위해",
    "통해", "오늘", "지난", "이날", "우리", "한다", "했다", "된다", "되다", "하는",
    "그리고", "하지만", "또한", "이런", "저런", "그런", "더", "수", "때", "중",
    "전망", "계획", "예정", "밝혔다", "전했다", "말했다", "대해", "통한", "따라",
    "이라고", "라고", "에서", "으로", "에게", "부터", "까지", "보다", "처럼",
    "기자", "사진", "제공", "무단", "전재", "배포", "금지", "저작권",
})


def _is_meaningful_keyword(tok: str) -> bool:
    """키워드로 셀 가치가 있는 토큰인지 — 불용어/한 글자 한글/순수 기호 제외."""
    t = tok.strip()
    if not t or t in _KEYWORD_STOPWORDS:
        return False
    # 한 글자 한글(조사·접속사 잔재)은 제외 — 영문/숫자 한 글자는 드물어도 유지.
    if len(t) == 1 and "가" <= t <= "힣":
        return False
    # 순수 기호/구두점만 → 제외.
    if not any(c.isalnum() for c in t):
        return False
    return True


def _all_keyword_tokens(df: pd.DataFrame) -> list[str]:
    """LLM 키워드 우선, 없으면 룰 키워드. 불용어·무의미 토큰은 제외."""
    tokens: list[str] = []
    for col in ("keywords_llm", "keywords"):
        if col in df.columns:
            for cell in df[col].fillna("").astype(str):
                tokens.extend(
                    t.strip() for t in cell.split(",")
                    if _is_meaningful_keyword(t)
                )
    return tokens


def daily_volume(df: pd.DataFrame, days: int = 7, *, now: datetime | None = None) -> pd.DataFrame:
    """최근 `days` 일 일자별 기사 수. 데이터 없는 일자도 0 으로 채워 반환.

    Returns 컬럼: date(YYYY-MM-DD, 오름차순), count.
    """
    if days < 1:
        raise ValueError("days must be >= 1")
    cur = now or datetime.now(timezone.utc)
    date_index = [(cur - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days - 1, -1, -1)]
    base = pd.DataFrame({"date": date_index, "count": 0})

    if df.empty:
        return base

    actual = by_date(df)
    if actual.empty:
        return base
    merged = base.merge(actual, on="date", how="left", suffixes=("_zero", ""))
    merged["count"] = merged["count"].fillna(0).astype(int)
    return merged[["date", "count"]]


def keyword_emergence(
    today_df: pd.DataFrame,
    base_df: pd.DataFrame,
    *,
    top_n: int = 10,
    min_count: int = 1,
) -> dict[str, pd.DataFrame]:
    """today 와 base(이전 기간) 키워드 집합 차이.

    Returns dict:
        - "new"        : today 에는 있고 base 에는 없는 키워드 (등장)
        - "gone"       : base 에는 있고 today 에는 없는 키워드 (사라짐)
        - "rising"     : 둘 다 있지만 today 가 더 큰 키워드 (delta 내림차순)
    각 DataFrame 컬럼: keyword, today, base, delta (rising 만)
                      또는 keyword, count (new/gone).
    """
    today_kw = pd.DataFrame(
        Counter(_all_keyword_tokens(today_df)).items(), columns=["keyword", "today"]
    )
    base_kw = pd.DataFrame(
        Counter(_all_keyword_tokens(base_df)).items(), columns=["keyword", "base"]
    )

    if today_kw.empty and base_kw.empty:
        empty = pd.DataFrame(columns=["keyword", "count"])
        return {
            "new": empty.copy(),
            "gone": empty.copy(),
            "rising": pd.DataFrame(columns=["keyword", "today", "base", "delta"]),
        }

    merged = today_kw.merge(base_kw, on="keyword", how="outer").fillna(0)
    merged["today"] = merged["today"].astype(int)
    merged["base"] = merged["base"].astype(int)

    new_df = (
        merged[(merged["base"] == 0) & (merged["today"] >= min_count)]
        .rename(columns={"today": "count"})[["keyword", "count"]]
        .sort_values("count", ascending=False, ignore_index=True)
        .head(top_n)
    )
    gone_df = (
        merged[(merged["today"] == 0) & (merged["base"] >= min_count)]
        .rename(columns={"base": "count"})[["keyword", "count"]]
        .sort_values("count", ascending=False, ignore_index=True)
        .head(top_n)
    )
    rising = merged[(merged["today"] > 0) & (merged["base"] > 0)].copy()
    rising["delta"] = rising["today"] - rising["base"]
    rising_df = (
        rising[rising["delta"] > 0]
        .sort_values("delta", ascending=False, ignore_index=True)
        [["keyword", "today", "base", "delta"]]
        .head(top_n)
    )

    return {"new": new_df, "gone": gone_df, "rising": rising_df}


# ── 적응형 키워드 트렌드 (보드 ⑤ — 주간↔일간) ─────────────────────

def _bucket_date_series(df: pd.DataFrame) -> pd.Series | None:
    """버킷팅용 UTC datetime 시리즈 — published_at 우선, 없으면 collected_at."""
    if "published_at" in df.columns:
        return pd.to_datetime(df["published_at"], errors="coerce", utc=True)
    if "collected_at" in df.columns:
        return pd.to_datetime(df["collected_at"], errors="coerce", utc=True)
    return None


def keyword_buckets(
    df: pd.DataFrame, buckets: int, unit_days: int, *, now: datetime | None = None
) -> tuple[list[str], list[dict]]:
    """top-6 키워드의 버킷별(주간 unit_days=7 / 일간 1) 출현 빈도.

    Returns (labels, [{name, counts:list[int]}]) — counts 길이 = buckets.
    라벨: 주간 'W14'~'금주', 일간 'M/D'~'오늘'. (보드 `_bucketed_keyword_series` 포팅)
    """
    if df is None or df.empty:
        return [], []
    dt = _bucket_date_series(df)
    if dt is None:
        return [], []
    work = df.assign(_dt=dt).dropna(subset=["_dt"])
    if work.empty:
        return [], []
    cur = now or datetime.now(timezone.utc)

    def _bucket_idx(t: pd.Timestamp) -> int:
        days_ago = (cur - t.to_pydatetime()).days
        return int((buckets - 1) - (days_ago // unit_days))

    work = work.assign(_w=work["_dt"].apply(_bucket_idx))
    work = work[(work["_w"] >= 0) & (work["_w"] < buckets)]
    if work.empty:
        return [], []
    top_df = top_keywords(work, top_n=6)
    if top_df.empty:
        return [], []

    series: list[dict] = []
    for kw in top_df["keyword"].astype(str).tolist():
        counts = [0] * buckets
        for w, sub in work.groupby("_w"):
            mask = pd.Series(False, index=sub.index)
            for col in ("keywords_llm", "keywords"):
                if col in sub.columns:
                    mask |= sub[col].fillna("").astype(str).str.contains(kw, regex=False, case=False)
            counts[int(w)] = int(mask.sum())
        series.append({"name": kw, "counts": counts})

    labels: list[str] = []
    for i in range(buckets):
        b_dt = cur - timedelta(days=(buckets - 1 - i) * unit_days)
        if i == buckets - 1:
            labels.append("금주" if unit_days >= 7 else "오늘")
        elif unit_days >= 7:
            labels.append(f"W{b_dt.isocalendar().week:02d}")
        else:
            labels.append(f"{b_dt.month}/{b_dt.day}")
    return labels, series


def keyword_delta(counts: list[int]) -> tuple[int, bool]:
    """첫 1/3 평균 → 마지막 1/3 평균 변화율(%). (pct, is_new).

    is_new=True 는 비교할 과거 기준이 없는 첫 등장(표시는 '신규'). 선행 무데이터
    버킷(0)은 잘라내고 실제 데이터 구간에서만 비교. (보드 `_delta_info` 포팅)
    """
    trimmed = list(counts or [])
    while trimmed and trimmed[0] == 0:
        trimmed.pop(0)
    if not trimmed:
        return 0, False
    if len(trimmed) < 3:
        return (100, True) if sum(trimmed) > 0 else (0, False)
    n = len(trimmed)
    third = max(n // 3, 1)
    head = sum(trimmed[:third]) / third
    tail = sum(trimmed[-third:]) / third
    if head == 0:
        return (100, True) if tail > 0 else (0, False)
    return round((tail - head) / head * 100), False


def adaptive_keyword_trend(df: pd.DataFrame, *, now: datetime | None = None) -> dict:
    """보드 ⑤ 적응형 트렌드 페이로드 — 주간 8칸 기본, 데이터 누적이 2주 이하면
    일간 14칸으로 자동 전환. series 각 항목에 total/delta/is_new, 최상위 어노테이션.

    Returns: {mode, labels, series:[{keyword,counts,total,delta,is_new}], anno|None}
    """
    labels, series = keyword_buckets(df, buckets=8, unit_days=7, now=now)
    mode = "weekly"
    if series:
        weeks_with_data = sum(
            1 for w in range(len(labels)) if any(s["counts"][w] > 0 for s in series)
        )
        if weeks_with_data <= 2:
            d_labels, d_series = keyword_buckets(df, buckets=14, unit_days=1, now=now)
            if d_series:
                labels, series, mode = d_labels, d_series, "daily"

    if not series:
        return {"mode": mode, "labels": [], "series": [], "anno": None}

    out_series = []
    for s in series[:6]:
        delta, is_new = keyword_delta(s["counts"])
        out_series.append({
            "keyword": s["name"], "counts": s["counts"],
            "total": int(sum(s["counts"])), "delta": int(delta), "is_new": is_new,
        })

    chart = series[:4]
    top_s = max(chart, key=lambda s: sum(s["counts"]))
    top_total = int(sum(top_s["counts"]))
    top_delta, top_new = keyword_delta(top_s["counts"])
    arrow = "↑" if (top_new or top_delta > 0) else ("↓" if top_delta < 0 else "·")
    if mode == "daily":
        sub = (f"최근 14일 {top_total}건 — 수집 초기라 일별 추이를 보여드려요. "
               "3주 이상 쌓이면 주별 추세로 전환됩니다")
    elif top_new:
        sub = f"8주 내 첫 등장 — 최근 {top_total}건, 다음 주부터 추세가 계산됩니다"
    elif abs(top_delta) >= 20:
        sub = f"8주간 {'+' if top_delta >= 0 else ''}{top_delta}% — 산업 분기점 가능성"
    else:
        sub = f"8주간 {'+' if top_delta >= 0 else ''}{top_delta}% — 추세 관찰 중"

    return {"mode": mode, "labels": labels, "series": out_series,
            "anno": {"name": top_s["name"], "arrow": arrow, "sub": sub}}


def compare_distribution(
    today_df: pd.DataFrame,
    base_df: pd.DataFrame,
    *,
    key: str = "press",
    top_n: int = 10,
) -> pd.DataFrame:
    """today vs base 분포 비교. 컬럼: key, today, base, delta (내림차순)."""
    if key not in today_df.columns and key not in base_df.columns:
        return pd.DataFrame(columns=[key, "today", "base", "delta"])
    t = today_df.groupby(key, dropna=False).size().reset_index(name="today") if key in today_df.columns else pd.DataFrame(columns=[key, "today"])
    b = base_df.groupby(key, dropna=False).size().reset_index(name="base") if key in base_df.columns else pd.DataFrame(columns=[key, "base"])
    merged = t.merge(b, on=key, how="outer").fillna(0)
    merged["today"] = merged["today"].astype(int)
    merged["base"] = merged["base"].astype(int)
    merged["delta"] = merged["today"] - merged["base"]
    return merged.sort_values("delta", ascending=False, ignore_index=True).head(top_n)
