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

from urllib.parse import quote

from config import ASSETS_DIR
from persona.schema import Persona
from store import bookmarks as bookmarks_store
from store.bookmarks import Bookmark
from ui import app_shell
from ui.styles import inject_screen_css


_ARCHIVE_TEMPLATE = ASSETS_DIR / "v2" / "screens" / "archive_main.html"

# 칸반 컬럼당 최대 노출 카드 수 — 초과분은 "+N건 더 보기" 로 표시
_MAX_CARDS_PER_COL = 4

# 칸반 컬럼 키 — `?expand=` 의 단위
_COL_KEYS = ("pending", "adopted", "rejected")


def _expanded_cols_from_query() -> frozenset[str]:
    """`?expand=pending,adopted` → {"pending","adopted"}.

    유효 값만 통과시킨다(미지 키 무시). 빈 값이면 빈 frozenset.
    """
    raw = (st.query_params.get("expand") or "").strip()
    if not raw:
        return frozenset()
    toks = (t.strip() for t in raw.split(","))
    return frozenset(t for t in toks if t in _COL_KEYS)


def _archive_expand_href(col: str, current: frozenset[str]) -> str:
    """현재 expanded set 을 기준으로 `col` 토글한 URL.

    - col 이 이미 포함 → 제거 (접기)
    - col 이 미포함 → 추가 (펴기)
    빈 set 이면 `expand` 파라미터 자체를 생략(깨끗한 URL).
    """
    new_set = (current - {col}) if col in current else (current | {col})
    parts = [f"app_area={quote('📦 산출물 보관함')}"]
    if new_set:
        ordered = [c for c in _COL_KEYS if c in new_set]
        parts.append(f"expand={quote(','.join(ordered))}")
    return "?" + "&".join(parts)

# 카드 액션 URL 매핑 — `?action=...` 키를 set_status 의 값으로 변환.
_STATUS_TOAST: dict[str, str] = {
    "adopted": "✅ 채택함으로 옮겼습니다",
    "rejected": "🗂 보류함으로 옮겼습니다",
    "pending": "↩ 대기로 되돌렸습니다",
}

_ACTION_TO_STATUS: dict[str, str] = {
    "adopt": "adopted",
    "reject": "rejected",
    "restore": "pending",
}


def _archive_action_href(action: str, bm_id: str) -> str:
    """카드 액션 링크 — 같은 화면에 머무르면서 액션만 트리거."""
    parts = [
        f"app_area={quote('📦 산출물 보관함')}",
        f"action={quote(action)}",
        f"bm_id={quote(bm_id)}",
    ]
    return "?" + "&".join(parts)


def _edit_handoff_href(bm: Bookmark) -> str:
    """수정 버튼 → SOLA 작업실 인계 (`from=edit&bm_id=&title=`).

    board_v2 와 동일 패턴이지만 archive 는 bm_id + title 을 stateless 로 전달.
    """
    parts = [
        f"app_area={quote('🤖 SOLA 작업실')}",
        "from=edit",
        f"bm_id={quote(bm.id or '')}",
        f"title={quote((bm.title or '')[:80])}",
    ]
    return "?" + "&".join(parts)


def _consume_action_if_any() -> tuple[str, str] | None:
    """`?action=...&bm_id=...` 가 있으면 1회 소비 후 set_status.

    Returns: (status, bm_id) 가 적용되면 그 튜플, 아니면 None.
    부수효과: 캐시 invalidate + query_params 에서 action/bm_id 제거.
    """
    action = st.query_params.get("action")
    bm_id = st.query_params.get("bm_id")
    if not action or not bm_id or action not in _ACTION_TO_STATUS:
        return None
    new_status = _ACTION_TO_STATUS[action]
    try:
        bookmarks_store.set_status(bm_id, new_status)
    except Exception:
        pass
    # 캐시 invalidate — 다음 렌더에서 최신 칸반 반영
    _oa_stats_and_cards.clear()
    # query 정리 — 재방문 / 새로고침에서 액션 재실행 방지
    for k in ("action", "bm_id"):
        if k in st.query_params:
            del st.query_params[k]
    return (new_status, bm_id)


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
    if with_actions and bm.id:
        # 1순위 카드만 액션 노출 — 같은 화면 유지 + status 변경
        edit_href = _edit_handoff_href(bm)
        actions_html = (
            '<div class="oa-card-actions">'
            f'<a class="oa-act oa-act-good" href="{_archive_action_href("adopt", bm.id)}" target="_self">채택</a>'
            f'<a class="oa-act" href="{edit_href}" target="_self">수정</a>'
            f'<a class="oa-act oa-act-warn" href="{_archive_action_href("reject", bm.id)}" target="_self">기각</a>'
            '</div>'
        )

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


def _restore_action_html(bm: Bookmark) -> str:
    """채택/기각 컬럼 1순위 카드에 노출되는 '되돌리기' 액션."""
    if not bm.id:
        return ""
    return (
        '<div class="oa-card-actions">'
        f'<a class="oa-act" href="{_archive_action_href("restore", bm.id)}" target="_self">'
        '↶ 대기로 되돌리기</a>'
        '</div>'
    )


def _build_cards_html(items: list[Bookmark], *, status_label: str,
                      with_actions_first: bool = False,
                      with_restore_first: bool = False,
                      col_key: str = "",
                      expanded: bool = False,
                      expanded_set: frozenset[str] = frozenset()) -> str:
    """컬럼 카드 리스트 → HTML. 빈 리스트는 empty placeholder.

    Args:
        col_key: 컬럼 키("pending"/"adopted"/"rejected"). "+N건 더 보기" /
            "− 접기" 토글 링크 빌드에 사용.
        expanded: True 면 모든 카드 노출 + "− 접기" 링크.
        expanded_set: 다른 컬럼 expand 상태를 보존한 토글 URL 빌드에 사용.
    """
    if not items:
        return _empty_col_html(status_label)

    if expanded:
        visible = items
        overflow = 0
    else:
        visible = items[:_MAX_CARDS_PER_COL]
        overflow = len(items) - len(visible)

    parts = []
    for idx, bm in enumerate(visible):
        card = _card_html(bm, with_actions=(with_actions_first and idx == 0))
        if with_restore_first and idx == 0:
            # 카드 article 닫기 직전에 restore action 삽입
            card = card.replace("</article>", _restore_action_html(bm) + "</article>", 1)
        parts.append(card)

    if expanded and col_key and len(items) > _MAX_CARDS_PER_COL:
        # 접기 토글 — 펴진 상태에서만 노출 (4건 이하면 굳이 노출 안 함)
        href = _archive_expand_href(col_key, expanded_set)
        parts.append(
            f'<a class="oa-col-more oa-col-more-collapse" href="{href}" '
            f'target="_self" aria-label="접기">− 접기 ({len(items)}건)</a>'
        )
    elif overflow > 0 and col_key:
        href = _archive_expand_href(col_key, expanded_set)
        parts.append(
            f'<a class="oa-col-more" href="{href}" target="_self" '
            f'aria-label="모두 보기">+ {overflow}건 더 보기</a>'
        )
    return "\n".join(parts)


@st.cache_data(ttl=30)
def _oa_stats_and_cards(expanded_csv: str = "") -> dict[str, str]:
    """헤더 4 stats + 칸반 3 컬럼 카드 HTML 일괄 계산.

    Args:
        expanded_csv: "pending,adopted" 같은 CSV. 빈 문자열이면 모든 컬럼 4건 노출.
            캐시 키에 포함되므로 expand 토글마다 새 렌더.
    """
    expanded_set = frozenset(
        c for c in expanded_csv.split(",") if c in _COL_KEYS
    ) if expanded_csv else frozenset()

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
        "cards_pending": _build_cards_html(
            pending_items, status_label="대기", with_actions_first=True,
            col_key="pending", expanded=("pending" in expanded_set),
            expanded_set=expanded_set,
        ),
        "cards_adopted": _build_cards_html(
            adopted_items, status_label="채택", with_restore_first=True,
            col_key="adopted", expanded=("adopted" in expanded_set),
            expanded_set=expanded_set,
        ),
        "cards_rejected": _build_cards_html(
            rejected_items, status_label="기각", with_restore_first=True,
            col_key="rejected", expanded=("rejected" in expanded_set),
            expanded_set=expanded_set,
        ),
    }


@st.cache_data(ttl=60)
def _archive_stats_oa() -> dict[str, int]:
    """app-side 좌측 — 보드와 동일 소스. `board_v2._archive_stats` 60초 캐시 위임."""
    from ui import board_v2  # lazy

    try:
        return board_v2._archive_stats()
    except Exception:
        summary = bookmarks_store.summary_counts()
        pending = int(summary["proposal_status"].get("pending", 0))  # type: ignore[index]
        return {"match_today": 0, "opportunities": 0, "pending_adopt": pending}


def chat_context_block(persona: Persona) -> str:
    """산출물 보관함 화면이 보여주는 모든 데이터를 LLM 컨텍스트로 packaging.

    헤더 4 stats (총/채택/대기/기각 + 채택률) + 칸반 3 컬럼 각 카드 (제목/타입/연령/태그).
    """
    parts: list[str] = ["--- 현재 화면: 산출물 보관함 (📦) ---"]
    try:
        all_items = bookmarks_store.list_all(type_="proposal")
    except Exception:
        all_items = []

    pending = [b for b in all_items if b.status == "pending"]
    adopted = [b for b in all_items if b.status == "adopted"]
    rejected = [b for b in all_items if b.status == "rejected"]
    decided = len(adopted) + len(rejected)
    rate = f"{(len(adopted)/decided)*100:.1f}%" if decided > 0 else "—"

    parts.append(
        f"현황: 총 {len(all_items)}건 · 채택 {len(adopted)}건 · 대기 {len(pending)}건 · "
        f"기각 {len(rejected)}건 · 채택률 {rate}"
    )

    def _kanban_section(label: str, items: list[Bookmark], limit: int = 4) -> None:
        if not items:
            return
        items_sorted = sorted(items, key=lambda b: b.created_at, reverse=True)
        parts.append(f"[{label}] {len(items)}건:")
        for bm in items_sorted[:limit]:
            title = (bm.title or "(제목 없음)")[:100]
            desc = (bm.content or "").strip()[:120]
            age = _age_label(bm.created_at)
            tags = ", ".join((bm.tags or [])[:3])
            parts.append(f"  - {title} ({age})")
            if desc:
                parts.append(f"    {desc}")
            if tags:
                parts.append(f"    태그: {tags}")

    _kanban_section("대기", pending)
    _kanban_section("채택", adopted)
    _kanban_section("기각", rejected)

    return "\n".join(parts)


def render() -> None:
    """산출물 보관함 v2 — topbar + app-side + main + app-sola.

    `?action=adopt|reject|restore&bm_id=...` 가 있으면 첫 단계에서 1회 소비.
    캐시 invalidate 후 본 렌더가 갱신된 칸반을 그린다.
    """
    inject_screen_css("archive")

    _acted = _consume_action_if_any()
    if _acted is not None:
        _new_status, _ = _acted
        st.toast(_STATUS_TOAST.get(_new_status, "상태를 변경했습니다"))

    persona = app_shell.get_persona()
    stats = _archive_stats_oa()
    expanded_csv = ",".join(sorted(_expanded_cols_from_query()))
    oa = _oa_stats_and_cards(expanded_csv)
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

