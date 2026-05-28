"""산출물 보관함 — v2 디자인 적용.

헤더 4 stats + 칸반 컬럼 카운트 (대기/채택/기각) + **칸반 카드 동적 렌더**
를 store.bookmarks 에서 실시간 계산. type=proposal 만 칸반에 노출 (브리핑/
보고서는 추가 PR 에서 별 칸반).

빈 컬럼은 빈상태 placeholder ("아직 산출물이 없어요") 노출.
"""
from __future__ import annotations

import html as _html
from datetime import datetime, timezone

import streamlit as st

from config import ASSETS_DIR
from persona.schema import Persona
from roadmap.query import load_latest as _load_roadmap
from store import bookmarks as bookmarks_store
from store.bookmarks import Bookmark
from store import news_db as _news_db
from store.match import score_matches as _score_matches
from sola.opportunity import score_cells as _score_cells
from ui import app_shell
from ui.styles import inject_screen_css


_ARCHIVE_TEMPLATE = ASSETS_DIR / "v2" / "screens" / "archive_main.html"

# 칸반 컬럼당 최대 노출 카드 수 — 초과분은 "+N건 더 보기" 로 표시
_MAX_CARDS_PER_COL = 4


def _load_persona() -> Persona:
    p = st.session_state.get("persona")
    if isinstance(p, Persona):
        return p
    from persona import store as persona_store

    p = persona_store.load()
    st.session_state["persona"] = p
    return p


def _age_label(created_at: str) -> str:
    """ISO 시각 → '2시간 전' / '어제' / '5월 17일' 같은 라벨."""
    if not created_at:
        return ""
    try:
        # 'YYYY-MM-DDTHH:MM:SS+00:00' 또는 'YYYY-MM-DDTHH:MM:SS' 형태
        ts = created_at.replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - dt
        secs = int(delta.total_seconds())
        if secs < 60:
            return "방금"
        if secs < 3600:
            return f"{secs // 60}분 전"
        if secs < 86400:
            return f"{secs // 3600}시간 전"
        if secs < 172800:
            return "어제"
        if secs < 86400 * 30:
            return f"{secs // 86400}일 전"
        return f"{dt.month}월 {dt.day}일"
    except Exception:
        return ""


def _type_label_class(t: str) -> tuple[str, str]:
    """bookmark.type → ('제안서', 'oa-tag-prop')."""
    mapping = {
        "proposal": ("제안서", "oa-tag-prop"),
        "news": ("뉴스", "oa-tag-news"),
        "opportunity": ("기회", "oa-tag-opp"),
        "task": ("작업", "oa-tag-task"),
    }
    return mapping.get(t, (t or "산출물", ""))


def _card_html(bm: Bookmark, *, with_actions: bool = False) -> str:
    """단일 북마크 → 칸반 카드 HTML."""
    type_label, type_cls = _type_label_class(bm.type)
    title = _html.escape(bm.title or "(제목 없음)")
    desc = _html.escape((bm.content or "").strip()[:120])
    if len(bm.content or "") > 120:
        desc += "…"
    bm_id = _html.escape(bm.id[:12] if bm.id else "")
    age = _html.escape(_age_label(bm.created_at))

    tag_chips = ""
    for tag in (bm.tags or [])[:3]:
        tag_chips += f'<span class="oa-mini">{_html.escape(tag)}</span>'

    actions_html = ""
    if with_actions:
        actions_html = """
        <div class="oa-card-actions">
          <button class="oa-act oa-act-good" disabled>채택</button>
          <button class="oa-act" disabled>수정</button>
          <button class="oa-act oa-act-warn" disabled>기각</button>
        </div>
        """

    return f"""<article class="oa-card">
      <div class="oa-card-top">
        <span class="oa-tag {type_cls}">{_html.escape(type_label)}</span>
        <span class="oa-card-id">{bm_id}</span>
      </div>
      <h4 class="oa-card-t">{title}</h4>
      {f'<p class="oa-card-d">{desc}</p>' if desc else ''}
      {f'<div class="oa-card-tags">{tag_chips}</div>' if tag_chips else ''}
      <div class="oa-card-foot">
        <span class="oa-card-age">{age}</span>
      </div>
      {actions_html}
    </article>"""


def _empty_col_html(status_label: str) -> str:
    return f"""<div class="oa-col-empty" style="
        padding: 24px 14px; text-align: center;
        color: var(--text-muted); font-size: 14px; line-height: 1.5;
        border: 1px dashed var(--surface-divider); border-radius: 10px;
        background: rgba(0,0,0,0.01);
      ">
      아직 {status_label} 산출물이 없어요.<br>
      <span style="font-size: 12.5px;">SOLA 작업실에서 제안서를 만들면 여기로 모입니다.</span>
    </div>"""


def _build_cards_html(items: list[Bookmark], *, status_label: str, with_actions_first: bool = False) -> str:
    """컬럼 카드 리스트 → HTML. 빈 리스트는 empty placeholder."""
    if not items:
        return _empty_col_html(status_label)

    visible = items[:_MAX_CARDS_PER_COL]
    overflow = len(items) - len(visible)

    parts = []
    for idx, bm in enumerate(visible):
        parts.append(_card_html(bm, with_actions=(with_actions_first and idx == 0)))
    if overflow > 0:
        parts.append(
            f'<button class="oa-col-more" disabled>+ {overflow}건 더 보기</button>'
        )
    return "\n".join(parts)


@st.cache_data(ttl=30)
def _oa_stats_and_cards() -> dict[str, str]:
    """헤더 4 stats + 칸반 3 컬럼 카드 HTML 일괄 계산."""
    items = bookmarks_store.list_all(type_="proposal")
    pending_items = [b for b in items if b.status == "pending"]
    adopted_items = [b for b in items if b.status == "adopted"]
    rejected_items = [b for b in items if b.status == "rejected"]

    # 최신순 정렬 (created_at 내림차순)
    for lst in (pending_items, adopted_items, rejected_items):
        lst.sort(key=lambda b: b.created_at, reverse=True)

    total = len(items)
    decided = len(adopted_items) + len(rejected_items)
    adopted_pct = f"{(len(adopted_items) / decided) * 100:.1f}%" if decided > 0 else "—"

    return {
        "total": str(total),
        "adopted": str(len(adopted_items)),
        "pending": str(len(pending_items)),
        "rejected": str(len(rejected_items)),
        "adopted_pct": adopted_pct,
        "cards_pending": _build_cards_html(pending_items, status_label="대기", with_actions_first=True),
        "cards_adopted": _build_cards_html(adopted_items, status_label="채택"),
        "cards_rejected": _build_cards_html(rejected_items, status_label="기각"),
    }


@st.cache_data(ttl=60)
def _archive_stats_oa() -> dict[str, int]:
    """app-side 좌측 — 보드와 동일 소스."""
    try:
        news_df = _news_db.load_news_for_days(days=1)
    except Exception:
        news_df = None
    try:
        roadmap_df = _load_roadmap()
    except Exception:
        roadmap_df = None

    match_count = 0
    opp_count = 0
    if (
        news_df is not None and not news_df.empty
        and roadmap_df is not None and not roadmap_df.empty
    ):
        try:
            matches = _score_matches(news_df, roadmap_df, top_k=3)
            if not matches.empty:
                match_count = int(matches[matches["score"] > 0]["link"].nunique())
        except Exception:
            pass
        try:
            cells = _score_cells(news_df, roadmap_df)
            opp_count = int(len(cells))
        except Exception:
            pass
    summary = bookmarks_store.summary_counts()
    pending = int(summary["proposal_status"].get("pending", 0))  # type: ignore[index]
    return {"match_today": match_count, "opportunities": opp_count, "pending_adopt": pending}


def render() -> None:
    """산출물 보관함 v2 — topbar + app-side + main + app-sola."""
    inject_screen_css("archive")

    persona = _load_persona()
    stats = _archive_stats_oa()
    oa = _oa_stats_and_cards()
    refresh = app_shell.refresh_label_now()

    app_shell.render_topbar(
        page_title="산출물 보관함",
        eyebrow_current="산출물 보관함",
        refresh_label=refresh,
        fresh_kind="accent",
    )
    app_shell.render_app_side(
        active_area="📦 산출물 보관함",
        persona=persona,
        stats=stats,
    )

    template = _ARCHIVE_TEMPLATE.read_text(encoding="utf-8")
    html_out = (
        template
        .replace("{{OA_TOTAL}}", _html.escape(oa["total"]))
        .replace("{{OA_ADOPTED_PCT}}", _html.escape(oa["adopted_pct"]))
        .replace("{{OA_ADOPTED}}", _html.escape(oa["adopted"]))
        .replace("{{OA_PENDING}}", _html.escape(oa["pending"]))
        .replace("{{OA_REJECTED}}", _html.escape(oa["rejected"]))
        .replace("{{OA_CARDS_PENDING}}", oa["cards_pending"])
        .replace("{{OA_CARDS_ADOPTED}}", oa["cards_adopted"])
        .replace("{{OA_CARDS_REJECTED}}", oa["cards_rejected"])
    )
    st.html(html_out)

    app_shell.render_app_sola(
        context_label="산출물 보관함",
        context_sub=f"총 {oa['total']} · 채택 {oa['adopted']} · 대기 {oa['pending']}",
        quick_prompts=[
            ("01", f"<b>대기 {oa['pending']}건</b> 중 가장 빨리 검토해야 할 3건은?"),
            ("02", f"<b>채택 {oa['adopted']}건</b>의 공통 성공 요인 정리"),
            ("03", f"기각 {oa['rejected']}건 — 사유 패턴 분석"),
        ],
        last_q="채택된 도장 PoC 제안서들이 공통적으로 강조한 KPI는?",
        last_a_html=(
            "공통 KPI 3가지가 두드러져요. <b>불량률 ↓</b> (5건 평균 −34%), "
            "<b>검사 공수 ↓</b> (평균 −58%), <b>ROI 회수기간</b> (평균 6.4개월). "
            "특히 ROI 가 6개월 이내인 제안이 채택률 91% 였어요."
            "<span class='muted'>방금 · 컨텍스트: 채택</span>"
        ),
        last_time="방금",
    )

