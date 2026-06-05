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
from ui import components as _components
from ui.styles import inject_screen_css


_ARCHIVE_TEMPLATE = ASSETS_DIR / "v2" / "screens" / "archive_main.html"


# 칸반 컬럼당 최대 노출 카드 수 — 초과분은 "+N건 더 보기" 로 표시
_MAX_CARDS_PER_COL = 4

# 칸반 컬럼 키 — `?expand=` 의 단위
_COL_KEYS = ("pending", "adopted", "rejected")


def _expanded_cols() -> frozenset[str]:
    """현재 펼쳐진 칸반 컬럼 set — 세션(`_oa_expanded`) 기반.

    구 `?expand=` 앵커(클릭 시 문서 reload)를 세션 토글로 대체. 유효 키만 통과.
    """
    raw = st.session_state.get("_oa_expanded")
    if isinstance(raw, frozenset):
        return frozenset(c for c in raw if c in _COL_KEYS)
    return frozenset()


def _toggle_expanded(col: str) -> None:
    """칸반 컬럼 펼침/접힘 토글(세션). 펼침 버튼이 호출한 뒤 st.rerun()."""
    cur = set(_expanded_cols())
    cur.symmetric_difference_update({col})
    st.session_state["_oa_expanded"] = frozenset(c for c in cur if c in _COL_KEYS)

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
    """카드 액션(채택/기각/되돌리기) 1회 소비 후 set_status.

    트리거는 둘 중 하나: 카드 버튼이 세팅한 `_do_archive_action`=(action, bm_id) pending
    (신규, 문서 reload 없음) 또는 레거시 `?action=…&bm_id=…` 쿼리(북마크/딥링크 호환).
    Returns: (status, bm_id) 가 적용되면 그 튜플, 아니면 None.
    부수효과: 캐시 invalidate + query_params 에서 action/bm_id 제거.
    """
    pend = st.session_state.pop("_do_archive_action", None)
    if pend:
        action, bm_id = pend[0], pend[1]
    else:
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
    _oa_data.clear()
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


def _card_html(bm: Bookmark) -> str:
    """단일 북마크 → 칸반 카드 HTML(표시 전용).

    채택/수정/기각·되돌리기 액션은 더 이상 카드 안 앵커가 아니라 컬럼 상단의 위젯
    버튼(`_render_card_actions`)이 담당한다(클릭 시 문서 reload=흰 깜빡임 제거).
    """
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


def _cards_block_html(items: list[Bookmark], *, status_label: str,
                      expanded: bool) -> str:
    """컬럼의 보이는 카드들을 `.oa-cards` 블록 HTML 로(액션·더보기 앵커 없음).

    비면 empty placeholder. expanded 가 아니면 최대 `_MAX_CARDS_PER_COL` 장만.
    '더 보기/접기' 토글과 카드 액션은 위젯 버튼(`_render_kanban_column`)이 담당한다.
    """
    if not items:
        return _empty_col_html(status_label)
    visible = items if expanded else items[:_MAX_CARDS_PER_COL]
    cards = "\n".join(_card_html(bm) for bm in visible)
    return f'<div class="oa-cards">{cards}</div>'


@st.cache_data(ttl=30)
def _oa_data() -> dict:
    """칸반 데이터 — 헤더 4 stats + 컬럼별 정렬된 items.

    카드 HTML 은 render 단계(`_cards_block_html`)에서 만들고, items 는 액션 버튼이
    bm_id/title 을 쓰도록 그대로 노출. 액션/expand 후 `_oa_data.clear()` 로 무효화.
    """
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
        "stats": {
            "total": str(total),
            "adopted": str(len(adopted_items)),
            "pending": str(len(pending_items)),
            "rejected": str(len(rejected_items)),
            "adopted_pct": adopted_pct,
        },
        "pending": pending_items,
        "adopted": adopted_items,
        "rejected": rejected_items,
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


# ── 칸반 컬럼 메타 (키 · 라벨 · 점 색 · 부제) ────────────────────
_KANBAN_COLS: tuple[tuple[str, str, str, str], ...] = (
    ("pending", "대기", "#0369A1", "SOLA가 만든 초안 · 검토 대기 중"),
    ("adopted", "채택", "#15803D", "의사결정 완료 · SOLA 컨텍스트 자동 첨부"),
    ("rejected", "기각", "#B45309", "사유와 함께 보관 · 향후 참고"),
)


def _header_html(stats: dict[str, str]) -> str:
    """`.oa-head`(stats) 헤더 HTML — 칸반 보드는 st.columns 위젯으로 별도 렌더하므로
    템플릿(`archive_main.html`)은 헤더 전용이다(보드 section 은 제거됨)."""
    return (
        _ARCHIVE_TEMPLATE.read_text(encoding="utf-8")
        .replace("{{OA_TOTAL}}", _html.escape(stats["total"]))
        .replace("{{OA_ADOPTED_PCT}}", _html.escape(stats["adopted_pct"]))
        .replace("{{OA_ADOPTED}}", _html.escape(stats["adopted"]))
        .replace("{{OA_PENDING}}", _html.escape(stats["pending"]))
        .replace("{{OA_REJECTED}}", _html.escape(stats["rejected"]))
    )


def _col_head_html(label: str, dot: str, cnt: int, meta: str) -> str:
    return (
        '<div class="oa-col-head"><div class="oa-col-head-l">'
        f'<span class="oa-col-dot" style="background:{dot};"></span>'
        f'<h3 class="oa-col-t">{_html.escape(label)}</h3>'
        f'<span class="oa-col-cnt">{cnt}</span>'
        '</div></div>'
        f'<div class="oa-col-meta">{_html.escape(meta)}</div>'
    )


def _handoff_edit_to_sola(bm: Bookmark) -> None:
    """'수정' → SOLA 작업실 인계. 세션 app_area + 쿼리(from/bm_id/title) 세팅.

    `st.query_params` 할당은 문서 reload 없이 URL 만 갱신하므로 SOLA 측 소비
    (`?from=edit&bm_id=&title=`)는 기존 경로 그대로 — SOLA 코드 변경 불필요.
    """
    st.session_state["app_area"] = "🤖 SOLA 작업실"
    st.session_state["show_persona_editor"] = False
    st.query_params["from"] = "edit"
    st.query_params["bm_id"] = bm.id or ""
    st.query_params["title"] = (bm.title or "")[:80]


def _render_card_actions(col_key: str, top_bm: Bookmark) -> None:
    """컬럼 1순위 카드 액션 — 위젯 버튼(구 카드 안 앵커 대체).

    pending: 채택 / 수정(→SOLA) / 기각. adopted·rejected: 대기로 되돌리기.
    on_click 미사용 — 클릭 시 pending/세션 세팅 후 st.rerun()(소켓 rerun)."""
    if not top_bm.id:
        return
    if col_key == "pending":
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("✅ 채택", key=f"_oa_adopt_{top_bm.id}",
                         type="primary", use_container_width=True):
                st.session_state["_do_archive_action"] = ("adopt", top_bm.id)
                st.rerun()
        with c2:
            if st.button("✏️ 수정", key=f"_oa_edit_{top_bm.id}",
                         use_container_width=True):
                _handoff_edit_to_sola(top_bm)
                st.rerun()
        with c3:
            if st.button("🗂 기각", key=f"_oa_reject_{top_bm.id}",
                         use_container_width=True):
                st.session_state["_do_archive_action"] = ("reject", top_bm.id)
                st.rerun()
    else:
        if st.button("↶ 대기로 되돌리기", key=f"_oa_restore_{top_bm.id}",
                     use_container_width=True):
            st.session_state["_do_archive_action"] = ("restore", top_bm.id)
            st.rerun()


def _render_kanban_column(col_key: str, label: str, dot: str, meta: str,
                          items: list[Bookmark], *, expanded: bool) -> None:
    """칸반 1개 컬럼 — 컨테이너(.oa-col 룩) > 헤더 + 1순위 액션 + 카드 + 더보기 버튼."""
    cnt = len(items)
    with st.container(key=f"oa_col_{col_key}"):
        st.html(_col_head_html(label, dot, cnt, meta))
        if items:
            _render_card_actions(col_key, items[0])
        st.html(_components.prepare_screen_html(
            _cards_block_html(items, status_label=label, expanded=expanded)))
        if cnt > _MAX_CARDS_PER_COL:  # 5건+ 일 때만 더보기/접기
            n_more = cnt - _MAX_CARDS_PER_COL
            lbl = f"− 접기 ({cnt}건)" if expanded else f"+ {n_more}건 더 보기"
            if st.button(lbl, key=f"_oa_more_{col_key}", use_container_width=True):
                _toggle_expanded(col_key)
                st.rerun()


def render() -> None:
    """산출물 보관함 v2 — topbar + stats 헤더(HTML) + 칸반(st.columns 위젯).

    카드 액션(채택/수정/기각/되돌리기)·더보기는 위젯 버튼이라 클릭 시 문서 reload
    (흰 깜빡임)가 없다. 액션 트리거(`_do_archive_action` / 레거시 `?action=`)는
    첫 단계에서 1회 소비 → 캐시 무효화 후 갱신된 칸반을 그린다.
    """
    inject_screen_css("archive")

    _acted = _consume_action_if_any()
    if _acted is not None:
        _new_status, _ = _acted
        st.toast(_STATUS_TOAST.get(_new_status, "상태를 변경했습니다"))

    data = _oa_data()
    refresh = app_shell.refresh_label_now()

    app_shell.render_topbar(
        page_title="산출물 보관함",
        eyebrow_current="산출물 보관함",
        refresh_label=refresh,
        fresh_kind="accent",
    )
    st.html(_components.prepare_screen_html(_header_html(data["stats"])))

    expanded = _expanded_cols()
    cols = st.columns(3, gap="small")
    for col_st, (key, label, dot, meta) in zip(cols, _KANBAN_COLS):
        with col_st:
            _render_kanban_column(
                key, label, dot, meta, data[key], expanded=(key in expanded))

