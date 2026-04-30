from __future__ import annotations

from collections import Counter
from typing import Any

import pandas as pd
import streamlit as st

REQUIRED_FIELDS = ("title", "link", "press", "date", "summary")


def summarize_quality(articles: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(articles)
    if total == 0:
        return {"total": 0, "missing": {}, "top_press": []}

    missing_counter = Counter()
    for article in articles:
        for field in REQUIRED_FIELDS:
            if not str(article.get(field, "")).strip():
                missing_counter[field] += 1

    press_counter = Counter(str(a.get("press", "미상") or "미상") for a in articles)
    return {
        "total": total,
        "missing": dict(missing_counter),
        "top_press": press_counter.most_common(5),
    }


def render_data_quality(articles: list[dict[str, Any]]) -> None:
    st.markdown(
        """
        <div class="header-wrap">
            <span class="header-logo">🧪 데이터 품질</span>
            <span class="header-sub">필수 필드 누락/출처 분포 빠른 점검</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    quality = summarize_quality(articles)
    st.metric("검사 기사 수", f"{quality['total']}건")

    if quality["total"] == 0:
        st.warning("검사할 기사 데이터가 없습니다. 먼저 뉴스를 수집해주세요.")
        return

    rows = [
        {"field": field, "missing_count": count, "missing_ratio": round((count / quality["total"]) * 100, 2)}
        for field, count in quality["missing"].items()
    ]
    if rows:
        st.subheader("필수 필드 누락 현황")
        st.dataframe(pd.DataFrame(rows), use_container_width=True)
    else:
        st.success("필수 필드 누락이 없습니다.")

    st.subheader("상위 출처 분포")
    st.dataframe(pd.DataFrame(quality["top_press"], columns=["press", "count"]), use_container_width=True)
