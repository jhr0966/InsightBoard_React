"""자동화 과제 제안서 — 작업 1건 + **작업과 매칭된 근거 기사**로 제안서 생성.

Step 8 (`fix-proposal-grounding`): 과거엔 최근 뉴스 df 의 앞쪽 N건(작업과 무관,
정렬 수정 전엔 가장 오래된 기사)을 "[관련 뉴스]"로 넣어 일반론 제안서가 나왔다.
이제 저장된 links(`store.links_db`)에서 **선택 작업과 실제 매칭된 기사**를
관련도·신선도·출처 다양성으로 선별하고, 매칭 용어·이유까지 프롬프트에 주입한다.
생성 결과에는 근거 목록이 함께 반환되어 제안서↔근거 관계가 저장된다.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pandas as pd

from persona import context as persona_ctx
from persona.schema import Persona
from roadmap import task_def_json as tdj
from sola.client import LLMNotConfigured, chat
from sola.preview import format_messages_preview
from sola.prompts import SYSTEM_PROPOSE
from store.match import render_match_reason

# 근거 선정 파라미터 — min_score_ratio 0.25 는 정답셋 실측값
# (상위3 무관 혼입 85%→40%, data/evaluation/report_matching_v2.json).
_EVIDENCE_MIN_RATIO = 0.25
_MAX_PER_SOURCE = 2          # 출처 다양성 — 같은 언론사/출처 최대 2건
_FRESH_DAYS = 7              # 신선 기사 가점 구간
_FRESH_BONUS = 1.15          # 7일 내 기사 점수 ×1.15


def _task_identity(task: dict) -> dict:
    """작업 dict(taskdef JSON — scalar 또는 org_meta)에서 식별 필드 추출."""
    org = task.get("org_meta") if isinstance(task.get("org_meta"), dict) else {}
    get = lambda k: str(task.get(k) or org.get(k) or "").strip()  # noqa: E731
    return {"dept": get("dept"), "lv3": get("lv3"),
            "task": get("task"), "sub_task": get("sub_task")}


def select_evidence(
    task: dict,
    links_df: pd.DataFrame,
    news_df: pd.DataFrame,
    *,
    max_items: int = 6,
    now: datetime | None = None,
) -> list[dict]:
    """선택 작업의 근거 기사 선정 — 관련도(임계값)·신선도·출처 다양성 (계획 §11-1).

    links_df: `links_db.matches_for_window` 결과(전 작업). 여기서 이 작업의 행만
    골라 ①최고점 대비 `_EVIDENCE_MIN_RATIO` 미만 컷 ②7일 내 기사 가점
    ③같은 출처 최대 `_MAX_PER_SOURCE` 건(다양성) ④동일 article_id 중복 제거
    순으로 상위 max_items 를 뽑는다. 반환 dict 에는 매칭 용어·이유가 포함된다.
    """
    if links_df is None or links_df.empty:
        return []
    ident = _task_identity(task)
    rows = links_df
    for col in ("dept", "lv3", "task"):
        if ident[col] and col in rows.columns:
            narrowed = rows[rows[col].astype(str) == ident[col]]
            if not narrowed.empty:
                rows = narrowed
    # dept/lv3/task 어느 것도 못 좁혔으면(작업이 links 에 없음) 근거 없음 — 최근
    # 뉴스 아무거나를 근거로 위장하지 않는다(무관 근거가 일반론 제안서의 원인).
    if rows is links_df and (ident["task"] or ident["lv3"]):
        return []
    if rows.empty:
        return []
    # 같은 작업(sub_task 단위) 행이 여럿이면 기사별 최고점 행만 남긴다.
    dedup_key = "article_id" if "article_id" in rows.columns else "link"
    rows = rows.sort_values("score", ascending=False).drop_duplicates(subset=[dedup_key])
    top = float(rows["score"].max() or 0)
    if top <= 0:
        return []
    rows = rows[rows["score"] >= top * _EVIDENCE_MIN_RATIO]

    # 뉴스 메타(게시시각·출처·발췌) 결합.
    meta = {}
    if news_df is not None and not news_df.empty:
        cols = [c for c in ("link", "press", "source", "published_at_norm", "sort_at",
                            "summary", "content") if c in news_df.columns]
        meta = {str(r.get("link", "")): r for r in news_df[cols].to_dict("records")}

    cur = now or datetime.now(timezone.utc)
    fresh_floor = (cur - timedelta(days=_FRESH_DAYS)).isoformat()

    scored: list[tuple[float, dict]] = []
    for _, r in rows.iterrows():
        link = str(r.get("link", ""))
        m = meta.get(link, {})
        ts = str(m.get("published_at_norm") or m.get("sort_at") or "")
        eff = float(r.get("score", 0) or 0) * (_FRESH_BONUS if ts >= fresh_floor and ts else 1.0)
        body = str(m.get("content") or m.get("summary") or "")
        scored.append((eff, {
            "title": str(r.get("news_title", "")),
            "link": link,
            "article_id": str(r.get("article_id", "")),
            "press": str(m.get("press", "") or ""),
            "source": str(m.get("source", "") or ""),
            "published_at": ts,
            "score": round(float(r.get("score", 0) or 0), 2),
            "matched_terms": list(r.get("matched_terms") or []),
            "reason": render_match_reason(r.to_dict()),
            "excerpt": body[:240],
        }))
    scored.sort(key=lambda x: (-x[0], x[1]["link"]))

    out: list[dict] = []
    per_source: dict[str, int] = {}
    for _, ev in scored:
        src = ev["press"] or ev["source"] or "?"
        if per_source.get(src, 0) >= _MAX_PER_SOURCE:
            continue
        per_source[src] = per_source.get(src, 0) + 1
        out.append(ev)
        if len(out) >= max_items:
            break
    return out


def _format_task(task: dict) -> str:
    """작업 dict → 제안서 입력 텍스트.

    조직 계층 scalar(team/dept/...) + 구조화 작업정의(work_flow·품질리스크·자동화
    영역 등)를 함께 넣는다. 신엑셀(2026-05+) 작업은 `task` dict 자체가 구조화 JSON
    payload 이므로 `to_chat_context_lines` 로 핵심 신호를 풀어 LLM 이 공정 맥락에
    맞는 제안을 하도록 한다.
    """
    keys = ("team", "dept", "lv1", "lv2", "lv3", "task", "sub_task", "task_def", "sws_no", "sws_name")
    org_meta = task.get("org_meta") if isinstance(task.get("org_meta"), dict) else {}
    lines = [
        f"- {k}: {task.get(k) or org_meta.get(k, '')}"
        for k in keys
        if task.get(k) or org_meta.get(k)
    ]
    detail = tdj.to_chat_context_lines(tdj.parse(json.dumps(task, ensure_ascii=False)), indent="")
    if detail:
        lines.append("")
        lines.extend(detail)
    return "\n".join(lines)


def _format_evidence(evidence: list[dict]) -> str:
    """근거 기사 → 프롬프트 텍스트 — 매칭 용어·이유·게시일 포함 ([근거 N] 인용용)."""
    if not evidence:
        return "(이 작업과 매칭된 근거 기사 없음 — 일반론 제안 금지, 근거 부족을 명시할 것)"
    lines: list[str] = []
    for i, ev in enumerate(evidence, start=1):
        date = (ev.get("published_at") or "")[:10]
        head = f"[근거 {i}] {ev['title']}" + (f" — {ev['press']}" if ev.get("press") else "")
        if date:
            head += f" ({date})"
        lines.append(head)
        if ev.get("matched_terms"):
            lines.append(f"    매칭: {', '.join(ev['matched_terms'][:5])} — {ev.get('reason', '')}")
        body = str(ev.get("excerpt") or "").replace("\n", " ").strip()
        if body:
            lines.append(f"    {body}")
    return "\n".join(lines)


def propose_for_task(
    task: dict,
    news_df: pd.DataFrame,
    *,
    max_news: int = 10,
    persona: Persona | None = None,
    evidence: list[dict] | None = None,
) -> str:
    """제안서 생성. `evidence`(links 기반 근거)가 있으면 그것만 주입한다.

    evidence=None 폴백(구 호출부 호환)은 최근 뉴스 상위 max_news 를 쓰지만,
    표준 경로(`api/routers/proposals.py`)는 항상 select_evidence 결과를 넘긴다.
    """
    if evidence is None:
        cols = [c for c in ("title", "press", "summary", "link") if c in news_df.columns]
        evidence = [{
            "title": str(r.get("title", "")), "press": str(r.get("press", "")),
            "link": str(r.get("link", "")), "excerpt": str(r.get("summary", ""))[:240],
        } for r in (news_df[cols].head(max_news).to_dict("records") if not news_df.empty else [])]
    user = (
        "## [작업]\n"
        f"{_format_task(task)}\n\n"
        "## [근거 기사]\n"
        f"{_format_evidence(evidence)}"
    )
    persona_block = persona_ctx.system_block(persona) if persona else ""
    messages = [
        {"role": "system", "content": SYSTEM_PROPOSE + persona_block},
        {"role": "user", "content": user},
    ]
    try:
        return chat(messages=messages, temperature=0.3)
    except LLMNotConfigured as e:
        return format_messages_preview(
            messages,
            header=f"⚠️ LLM 미설정 ({e}) — 제안서 생성 시 전달될 입력 컨텍스트",
        )
