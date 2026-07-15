"""개인화 뉴스 랭킹 — links × 페르소나 규칙 조합 (개편 Step 9, LLM 미사용).

"부서·직무·담당업무를 고려해 필요한 정보를 제공"의 실체:
  점수 = 신선도 + 관심 키워드 일치 + (links 기반) 관심 공정/작업 연결 가중.
"왜 내 업무와 관련 있는가" 문장도 **저장된 매칭 이유를 규칙으로 조합**한다 —
기사×사용자마다 LLM 을 돌리지 않는다(계획 §8: 비용·확장성).

`RANKING_VERSION` 은 피드백 이벤트(store/feedback.py)에 기록되어, 나중에
"이 랭킹 버전에서 노출된 기사를 사용자가 열었는가"를 평가할 수 있게 한다.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

RANKING_VERSION = 1

# 가중치 — 규칙 기반 v1. 조정 시 RANKING_VERSION +1 (피드백 평가 비교 기준).
_W_FRESH_MAX = 2.0        # 48시간 내 신선도 최대 가점(선형 감쇠)
_FRESH_WINDOW_H = 48.0
_W_KW_HIT = 2.0           # 관심 키워드 1개 일치당 (상위 3개까지)
_W_PROC_LINK = 0.35       # 관심 공정/작업과 연결된 links 점수 × 이 배율
_W_ANY_LINK = 0.08        # 그 외 작업과 연결된 links 점수 × 이 배율(도메인 관련성)
_MAX_KW_HITS = 3


def _persona_signals(persona) -> tuple[list[str], set[str]]:
    """페르소나 → (관심 키워드 목록, 관심 공정/작업 이름 집합)."""
    kws: list[str] = []
    for k in (list(getattr(persona, "interest_keywords", []) or [])
              + list(getattr(persona, "derived_interests", []) or [])):
        k = str(k).strip()
        if k and k not in kws:
            kws.append(k)
    procs: set[str] = set()
    for p in (list(getattr(persona, "interest_lv3", []) or [])
              + list(getattr(persona, "interest_tasks", []) or [])):
        p = str(p).strip()
        if p:
            procs.add(p)
    for m in (getattr(persona, "matched_processes", []) or []):
        if isinstance(m, dict):
            name = str(m.get("process") or m.get("lv3") or "").strip()
            if name:
                procs.add(name)
            for t in (m.get("tasks") or []):
                t = str(t).strip()
                if t:
                    procs.add(t)
    return kws, procs


def _age_hours(sort_at: str, now: datetime) -> float:
    try:
        dt = datetime.fromisoformat(str(sort_at).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return _FRESH_WINDOW_H
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return max(0.0, (now - dt).total_seconds() / 3600)


def rank_articles(
    news_df: pd.DataFrame,
    persona,
    links_df: pd.DataFrame | None,
    *,
    limit: int = 5,
    exclude_article_ids: set[str] | None = None,
    now: datetime | None = None,
) -> list[dict]:
    """개인화 상위 기사 — [{article_id, link, title, …, why, score, linked_task}].

    exclude_article_ids: 사용자가 '관련 없음' 처리한 기사(피드백 dismiss) 제외.
    결정적: 동점은 sort_at desc → link asc.
    """
    if news_df is None or news_df.empty:
        return []
    cur = now or datetime.now(timezone.utc)
    kws, procs = _persona_signals(persona)
    excluded = exclude_article_ids or set()

    # article_id → 이 기사가 연결된 작업 links (관심 공정 우선 정렬용 원자료)
    by_article: dict[str, list[dict]] = {}
    if links_df is not None and not links_df.empty:
        for r in links_df.to_dict("records"):
            by_article.setdefault(str(r.get("article_id", "")), []).append(r)

    out: list[tuple[float, str, str, dict]] = []
    for rec in news_df.to_dict("records"):
        aid = str(rec.get("article_id", ""))
        if aid in excluded:
            continue
        text = " ".join(str(rec.get(c, "")) for c in
                        ("title", "keywords", "keywords_llm", "summary")).lower()
        score = 0.0
        # ① 신선도 — 48h 선형 감쇠
        age = _age_hours(str(rec.get("sort_at", "")), cur)
        score += max(0.0, (_FRESH_WINDOW_H - age) / _FRESH_WINDOW_H) * _W_FRESH_MAX
        # ② 관심 키워드 일치
        hit_kws = [k for k in kws if k.lower() in text][:_MAX_KW_HITS]
        score += _W_KW_HIT * len(hit_kws)
        # ③ links — 관심 공정/작업 연결이면 강가중, 그 외 연결은 약가중
        best_link: dict | None = None
        best_w = 0.0
        for lk in by_article.get(aid, []):
            names = {str(lk.get("lv3", "")), str(lk.get("task", "")), str(lk.get("sub_task", ""))}
            w = _W_PROC_LINK if (names & procs) else _W_ANY_LINK
            contrib = float(lk.get("score", 0) or 0) * w
            score += contrib
            if contrib > best_w:
                best_w, best_link = contrib, lk
        if score <= 0:
            continue
        why = _why_sentence(hit_kws, best_link, procs)
        out.append((score, str(rec.get("sort_at", "")), str(rec.get("link", "")), {
            "article_id": aid, "link": rec.get("link", ""), "title": rec.get("title", ""),
            "press": rec.get("press", ""), "source": rec.get("source", ""),
            "image_url": rec.get("image_url", ""), "sort_at": rec.get("sort_at", ""),
            "excerpt": str(rec.get("content", "") or rec.get("summary", ""))[:240],
            "why": why, "score": round(score, 3),
            "linked_task": (f"{best_link.get('dept', '')} · {best_link.get('task', '')}"
                            if best_link is not None else ""),
            "ranking_version": RANKING_VERSION,
        }))
    out.sort(key=lambda x: (-x[0], x[1], x[2]))
    return [item for _, _, _, item in out[:limit]]


def _why_sentence(hit_kws: list[str], best_link: dict | None, procs: set[str]) -> str:
    """"왜 내 업무와 관련 있는가" — 저장된 매칭 근거 + 페르소나 신호의 규칙 조합."""
    parts: list[str] = []
    if best_link is not None:
        names = {str(best_link.get("lv3", "")), str(best_link.get("task", ""))}
        task_label = str(best_link.get("task") or best_link.get("lv3") or "")
        terms = [str(t) for t in (best_link.get("matched_terms") or [])][:3]
        if names & procs:
            head = f"내 관심 공정의 ‘{task_label}’ 작업과 연결"
        else:
            head = f"‘{task_label}’ 작업과 연결"
        if terms:
            head += f" — 기사의 ‘{'·'.join(terms)}’ 신호"
        parts.append(head)
    if hit_kws:
        parts.append(f"관심 키워드 ‘{'·'.join(hit_kws)}’ 언급")
    return " · ".join(parts)
