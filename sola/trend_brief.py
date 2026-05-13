"""트렌드 한 줄 해석 — daily_volume + emergence 를 LLM 이 평문 1~2문장으로 압축.

호출 캐시: 동일 (period_label · top 키워드 셋 · 모델) 조합은 디스크 캐시 사용.
LLM 미설정 시 graceful — 룰 기반 fallback 문장 반환.
"""
from __future__ import annotations

import pandas as pd

from config import llm_model
from sola.client import LLMNotConfigured, chat
from sola.prompts import SYSTEM_TREND_BRIEF
from store import cache


def _fmt_volume(vol_df: pd.DataFrame) -> str:
    if vol_df.empty:
        return "(데이터 없음)"
    return ", ".join(f"{r['date']}={r['count']}" for _, r in vol_df.iterrows())


def _fmt_emergence_section(label: str, df: pd.DataFrame, value_col: str = "count") -> str:
    if df.empty:
        return f"{label}: (없음)"
    items = ", ".join(f"{r['keyword']}({r[value_col]})" for _, r in df.head(8).iterrows())
    return f"{label}: {items}"


def _rule_based_fallback(
    period_label: str,
    vol_df: pd.DataFrame,
    emergence: dict[str, pd.DataFrame],
) -> str:
    """LLM 미설정·실패 시 사용. 단순 평문."""
    total = int(vol_df["count"].sum()) if not vol_df.empty else 0
    new_kw = ", ".join(emergence.get("new", pd.DataFrame()).head(3)["keyword"].astype(str).tolist())
    rising_kw = ", ".join(emergence.get("rising", pd.DataFrame()).head(3)["keyword"].astype(str).tolist())
    parts = [f"{period_label} 동안 {total:,}건의 기사가 수집되었습니다."]
    if new_kw:
        parts.append(f"새로 등장한 키워드: {new_kw}.")
    if rising_kw:
        parts.append(f"상승 키워드: {rising_kw}.")
    if not new_kw and not rising_kw:
        parts.append("유의미한 키워드 변화는 없습니다.")
    return " ".join(parts)


def _cache_signature(
    period_label: str,
    vol_df: pd.DataFrame,
    emergence: dict[str, pd.DataFrame],
) -> str:
    """캐시 키 — 입력의 가벼운 fingerprint."""
    vol_sig = _fmt_volume(vol_df)
    new_sig = ",".join(emergence.get("new", pd.DataFrame()).head(8)["keyword"].astype(str).tolist())
    gone_sig = ",".join(emergence.get("gone", pd.DataFrame()).head(8)["keyword"].astype(str).tolist())
    rising_sig = ",".join(emergence.get("rising", pd.DataFrame()).head(8)["keyword"].astype(str).tolist())
    return f"{period_label}|{vol_sig}|new:{new_sig}|gone:{gone_sig}|rising:{rising_sig}"


def brief(
    *,
    period_label: str,
    vol_df: pd.DataFrame,
    emergence: dict[str, pd.DataFrame],
    force: bool = False,
) -> str:
    """LLM 으로 트렌드 1~2문장 해석. 캐시 우선. 미설정 시 룰 기반 fallback.

    Args:
        period_label: 사용자에게 노출되는 기간 라벨 ("최근 7일" 등).
        vol_df: trends.daily_volume 결과 (date, count).
        emergence: trends.keyword_emergence 결과 dict.
        force: 캐시 무시.
    """
    sig = _cache_signature(period_label, vol_df, emergence)
    key = cache.make_key("trend_brief", sig, llm_model() or "")
    if not force:
        hit = cache.get(key)
        if hit is not None:
            return hit

    user = (
        f"[기간] {period_label}\n"
        f"[일자별 기사 수] {_fmt_volume(vol_df)}\n"
        f"[키워드 변화]\n"
        f"  - {_fmt_emergence_section('새 키워드', emergence.get('new', pd.DataFrame()))}\n"
        f"  - {_fmt_emergence_section('상승 키워드', emergence.get('rising', pd.DataFrame()), value_col='delta')}\n"
        f"  - {_fmt_emergence_section('사라진 키워드', emergence.get('gone', pd.DataFrame()))}\n"
    )

    try:
        reply = chat(
            messages=[
                {"role": "system", "content": SYSTEM_TREND_BRIEF},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
            max_tokens=200,
        )
    except LLMNotConfigured:
        return _rule_based_fallback(period_label, vol_df, emergence)
    except Exception:  # noqa: BLE001
        return _rule_based_fallback(period_label, vol_df, emergence)

    cache.put(key, reply)
    return reply
