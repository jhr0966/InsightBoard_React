"""오늘의 보드 — v2 디자인 적용.

핸드오프 `dashboard-full v2.html` 의 main 컬럼 + 4 KPI 카드 + 탑 스토리 섹션
(lead + side stories) 실데이터 바인딩. SOLA 브리핑/트렌드/매트릭스/키워드는
별도 PR (각각 chart SVG, LLM summary 등 추가 작업 필요).

CLAUDE.md 규칙:
  - on_click 금지 → 모든 인터랙션 disabled (visual handoff 단계)
  - HTML 직접 출력 시 사용자 문자열은 html.escape() 적용
"""
from __future__ import annotations

import html as _html
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

from config import ASSETS_DIR
from persona.schema import Persona
from roadmap.query import load_latest as _load_roadmap
from store import bookmarks as bookmarks_store
from store import news_db as _news_db
from store.match import score_matches as _score_matches
from sola.opportunity import score_cells as _score_cells
from ui import app_shell
from ui.styles import inject_screen_css


# 탑 스토리: lead 1 + side 4 = 5
_LEAD_STORY_COUNT = 1
_SIDE_STORY_COUNT = 4

_SOURCE_GRADIENTS = {
    "AI Times": "linear-gradient(135deg,#DC2626,#F87171)",
    "오토메이션월드": "linear-gradient(135deg,#D97706,#F59E0B)",
    "Google RSS": "linear-gradient(135deg,#047857,#14B8A6)",
    "네이버 기술": "linear-gradient(135deg,#6D28D9,#A78BFA)",
}
_DEFAULT_GRADIENT = "linear-gradient(135deg,#475569,#94A3B8)"


def _story_age(when: str) -> str:
    if not when:
        return ""
    try:
        ts = when.replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        secs = int((datetime.now(timezone.utc) - dt).total_seconds())
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


def _lead_story_html(row: pd.Series) -> str:
    """탑 스토리 lead — 큰 카드."""
    title = _html.escape(str(row.get("title", "") or "(제목 없음)"))
    body_raw = str(row.get("content", "") or "").strip()[:240]
    if len(str(row.get("content", "") or "")) > 240:
        body_raw += "…"
    body = _html.escape(body_raw)
    source = str(row.get("source", "") or "")
    source_safe = _html.escape(source)
    gradient = _SOURCE_GRADIENTS.get(source, _DEFAULT_GRADIENT)
    when = str(row.get("collected_at", "") or row.get("published_at", "") or "")
    age = _html.escape(_story_age(when))

    return f"""<article class="db-lead">
      <div class="db-lead-img">
        <span class="db-img-stripe"></span>
        <span class="db-img-label">{source_safe}</span>
      </div>
      <div class="db-lead-body">
        <div class="db-lead-tags">
          <span class="db-tag db-tag-strong">★ 강한 매칭</span>
          <span class="db-src"><span class="db-src-mark" style="background:{gradient};"></span>{source_safe}</span>
          <span class="db-time">{age}</span>
        </div>
        <h3 class="db-lead-h">{title}</h3>
        {f'<p class="db-lead-p">{body}</p>' if body else ''}
      </div>
    </article>"""


def _side_story_html(row: pd.Series) -> str:
    """탑 스토리 사이드 — 작은 카드."""
    title = _html.escape(str(row.get("title", "") or "(제목 없음)"))
    body_raw = str(row.get("content", "") or "").strip()[:120]
    if len(str(row.get("content", "") or "")) > 120:
        body_raw += "…"
    body = _html.escape(body_raw)
    source = str(row.get("source", "") or "")
    source_safe = _html.escape(source)
    gradient = _SOURCE_GRADIENTS.get(source, _DEFAULT_GRADIENT)
    when = str(row.get("collected_at", "") or row.get("published_at", "") or "")
    age = _html.escape(_story_age(when))

    return f"""<article class="db-story">
      <div class="db-story-meta">
        <span class="db-src"><span class="db-src-mark" style="background:{gradient};"></span>{source_safe}</span>
        <span class="db-time">{age}</span>
      </div>
      <h4 class="db-story-h">{title}</h4>
      {f'<p class="db-story-p">{body}</p>' if body else ''}
    </article>"""


@st.cache_data(ttl=60)
def _brief_html() -> dict[str, str]:
    """SOLA 오늘의 브리핑 — 페르소나 매칭 top 3 뉴스.

    LLM 호출 없이 score_matches 상위 3건 + 인용 pill 만 만든다.
    실제 LLM 요약/요점은 후속 PR (sola.summarize 연동).
    """
    try:
        news_df = _news_db.load_news_for_days(days=3)
    except Exception:
        news_df = None
    try:
        roadmap_df = _load_roadmap()
    except Exception:
        roadmap_df = None

    items: list[dict] = []
    if (
        news_df is not None and not news_df.empty
        and roadmap_df is not None and not roadmap_df.empty
    ):
        try:
            matches = _score_matches(news_df, roadmap_df, top_k=3)
            if not matches.empty and "score" in matches.columns:
                top = (
                    matches[matches["score"] > 0]
                    .sort_values("score", ascending=False)
                    .drop_duplicates("link")
                    .head(3)
                )
                # join with news_df for collected_at
                merged = top.merge(news_df[["link", "source", "collected_at"]], on="link", how="left", suffixes=("", "_n"))
                # fallback source if missing
                for _, r in merged.iterrows():
                    items.append({
                        "title": str(r.get("news_title", "") or r.get("title", "") or "(제목 없음)"),
                        "source": str(r.get("source", "") or ""),
                        "when": str(r.get("collected_at", "") or ""),
                    })
        except Exception:
            pass

    # fallback: 매칭 없을 때 그냥 최근 3건
    if not items and news_df is not None and not news_df.empty:
        if "collected_at" in news_df.columns:
            news_df = news_df.sort_values("collected_at", ascending=False)
        for _, r in news_df.head(3).iterrows():
            items.append({
                "title": str(r.get("title", "") or "(제목 없음)"),
                "source": str(r.get("source", "") or ""),
                "when": str(r.get("collected_at", "") or ""),
            })

    if not items:
        # 빈 상태
        return {
            "summary": '<div class="db-brief-greet">'
                       '<span class="db-brief-greet-tag">요약</span>'
                       '아직 수집된 뉴스가 없어요. 데이터 관리에서 수집을 시작하세요.'
                       '</div>',
            "list": "",
            "cites": "",
        }

    # 한 줄 요약 — 키워드 추출 없이 토픽 추정
    summary_text = (
        f"최근 매칭된 뉴스 {len(items)}건이 두드러집니다."
        if len(items) > 0 else "오늘 매칭된 뉴스가 없습니다."
    )
    summary_html = (
        '<div class="db-brief-greet">'
        '<span class="db-brief-greet-tag">요약</span>'
        f'{_html.escape(summary_text)}'
        '</div>'
    )

    # 3 numbered items
    list_parts = ['<ol class="db-brief-list">']
    for i, item in enumerate(items, start=1):
        title = _html.escape(item["title"][:120])
        list_parts.append(
            f'<li><span class="db-brief-num">{i}</span>'
            f'<div><b>{title}</b><sup class="db-cite">{i}</sup></div></li>'
        )
    list_parts.append('</ol>')
    list_html = "".join(list_parts)

    # Cite pills
    cite_parts = ['<div class="db-brief-cites">']
    for i, item in enumerate(items, start=1):
        src = _html.escape(item["source"] or "—")
        date_str = ""
        when = item["when"]
        if when:
            try:
                from datetime import datetime as _dt
                dt = _dt.fromisoformat(when.replace("Z", "+00:00"))
                date_str = f" · {dt.month:02d}/{dt.day:02d}"
            except Exception:
                pass
        cite_parts.append(
            f'<span class="db-cite-pill"><span class="db-cite-num">{i}</span>'
            f'{src}{_html.escape(date_str)}</span>'
        )
    cite_parts.append('</div>')
    cites_html = "".join(cite_parts)

    return {"summary": summary_html, "list": list_html, "cites": cites_html}


@st.cache_data(ttl=60)
def _opportunities_html() -> str:
    """자동화 기회 4-grid — opportunity.score_cells → 카드.

    각 cell: dept × lv3 + sample_tasks/sample_news 보유. 시안의 ROI/TRL/기간/
    예산 메트릭은 score 기반 휴리스틱 (실제 cost/timeline 수집 후속 PR).
    """
    try:
        news_df = _news_db.load_news_for_days(days=14)
    except Exception:
        news_df = None
    try:
        roadmap_df = _load_roadmap()
    except Exception:
        roadmap_df = None

    if (
        news_df is None or news_df.empty
        or roadmap_df is None or roadmap_df.empty
    ):
        return _opp_empty_html()

    try:
        cells = _score_cells(news_df, roadmap_df)
    except Exception:
        return _opp_empty_html()
    if cells.empty:
        return _opp_empty_html()

    cards = []
    for _, row in cells.head(4).iterrows():
        cards.append(_opp_card_html(row))
    return "\n".join(cards)


def _opp_empty_html() -> str:
    return """<div style="
        grid-column: 1 / -1; padding: 32px 18px; text-align: center;
        color: var(--text-muted); font-size: 14px;
        border: 1px dashed var(--surface-divider); border-radius: 12px;
        background: rgba(0,0,0,0.01);">
      아직 도출된 자동화 기회가 없어요.<br>
      <span style="font-size:12.5px;">뉴스 수집 + 로드맵 업로드 후 자동으로 매칭됩니다.</span>
    </div>"""


def _opp_card_html(row: pd.Series) -> str:
    dept = _html.escape(str(row.get("dept", "") or "—"))
    lv3 = _html.escape(str(row.get("lv3", "") or "—"))
    cell_score = float(row.get("cell_score", 0) or 0)
    matched_news = int(row.get("matched_news", 0) or 0)
    matched_tasks = int(row.get("matched_tasks", 0) or 0)
    sample_tasks = str(row.get("sample_tasks", "") or "").split(" · ")[:2]
    tagline = " · ".join(sample_tasks) if sample_tasks else f"매칭 뉴스 {matched_news}건"
    tagline_safe = _html.escape(tagline[:60])

    # 점수 표시 — score 자체가 추상적이라 0-100 범위로 매핑 (cell_score 는 누적)
    roi_score = min(int(cell_score), 99)

    return f"""<article class="db-prop">
      <div class="db-prop-top">
        <span class="db-prop-status">초안 0초</span>
        <span class="db-prop-tag db-prop-tag-tech">{lv3}</span>
      </div>
      <h3 class="db-prop-h">{dept} · {lv3} 자동화 기회</h3>
      <div class="db-prop-tagline">{tagline_safe}</div>

      <div class="db-prop-metrics">
        <div><b class="db-good">{roi_score}</b><span>점수</span></div>
        <div><b>{matched_news}</b><span>매칭 뉴스</span></div>
        <div><b>{matched_tasks}</b><span>매칭 작업</span></div>
        <div><b>—</b><span>예산</span></div>
      </div>

      <div class="db-prop-actions">
        <button class="db-prop-hold" disabled>보류</button>
        <button class="db-prop-discuss" disabled>SOLA와 검토</button>
        <button class="db-prop-accept" disabled>채택</button>
      </div>
    </article>"""


@st.cache_data(ttl=60)
def _board_stories_html() -> str:
    """탑 스토리 섹션 (lead + 4 side) HTML 빌드."""
    try:
        news = _news_db.load_news_for_days(days=3)
    except Exception:
        news = None

    if news is None or news.empty:
        return """<div style="
            grid-column: 1 / -1; padding: 32px 18px; text-align: center;
            color: var(--text-muted); font-size: 14px;
            border: 1px dashed var(--surface-divider); border-radius: 12px;
            background: rgba(0,0,0,0.01);">
          아직 수집된 뉴스가 없어요.<br>
          <span style="font-size:12.5px;">데이터 관리 화면에서 수집을 시작하세요.</span>
        </div>"""

    if "collected_at" in news.columns:
        news = news.sort_values("collected_at", ascending=False)
    elif "published_at" in news.columns:
        news = news.sort_values("published_at", ascending=False)

    rows = news.head(_LEAD_STORY_COUNT + _SIDE_STORY_COUNT)
    lead_row = rows.iloc[0]
    side_rows = rows.iloc[1:]

    side_html = "".join(_side_story_html(r) for _, r in side_rows.iterrows())

    return f"""
    {_lead_story_html(lead_row)}
    <div class="db-side-stories">
      {side_html}
    </div>
    """


_BOARD_TEMPLATE = ASSETS_DIR / "v2" / "screens" / "board_main.html"


def _load_persona() -> Persona:
    p = st.session_state.get("persona")
    if isinstance(p, Persona):
        return p
    from persona import store as persona_store

    p = persona_store.load()
    st.session_state["persona"] = p
    return p


def _persona_greet(persona: Persona) -> str:
    """헤더 인사: '박정훈 책임' / '자동화기술팀' / '사용자' 우선순위."""
    if persona.name and persona.job:
        return f"{persona.name} {persona.job}"
    if persona.name:
        return persona.name
    if persona.dept:
        return persona.dept
    return "사용자"


def _persona_short(persona: Persona) -> str:
    """본문 '박정훈님이' 같은 호칭."""
    return persona.name or persona.dept or "사용자"


def _greet_summary_html(persona: Persona, kpis: dict[str, int]) -> str:
    """인사 요약 — persona / data 상태에 맞춰 동적 문구.

    case 1: 페르소나 미설정 → 설정 CTA
    case 2: 페르소나 설정 + 오늘 수집 0 → 수집 시작 CTA
    case 3: 페르소나 + 데이터 있음 → 실제 카운트 요약
    """
    if not persona.is_set():
        return (
            '👋 아직 페르소나가 설정되지 않았어요. '
            '<a href="?persona_editor=1" target="_self" '
            'style="color:var(--accent-primary); font-weight:700; text-decoration:none;">'
            '페르소나를 설정</a>하면 부서·직무·관심 공정에 맞춘 매칭과 SOLA 답변을 받을 수 있어요.'
        )

    collect = kpis.get("collect", 0)
    match = kpis.get("match", 0)
    opp = kpis.get("opp", 0)
    if collect == 0:
        return (
            '아직 오늘 수집된 뉴스가 없어요. '
            '<a href="?app_area=%F0%9F%A7%B1+%EB%8D%B0%EC%9D%B4%ED%84%B0+%EA%B4%80%EB%A6%AC" '
            'target="_self" style="color:var(--accent-primary); font-weight:700; '
            'text-decoration:none;">데이터 관리</a>에서 첫 수집을 시작하세요.'
        )

    parts = [f'지난 24시간 동안 <b>{collect}건</b>이 들어왔어요.']
    if match > 0:
        parts.append(f'페르소나 기준으로 <b>{match}건</b>이 매칭됐어요.')
    if opp > 0:
        parts.append(f'그중 <b>자동화 기회 {opp}건</b>이 두드러집니다.')
    return " ".join(parts)


@st.cache_data(ttl=60)
def _board_kpis() -> dict[str, int]:
    """4 KPI 실데이터 계산 — 60초 캐시. 실패 시 0 폴백 (시각 화면은 항상 렌더).

    Returns:
      collect: 오늘 수집된 뉴스 수
      match:   강한 매칭 (score>0) 뉴스 수
      opp:     자동화 기회 셀 수 (dept × lv3)
      pending: 채택 대기 제안서 수
    """
    try:
        news_df = _news_db.load_news_for_days(days=1)
    except Exception:
        news_df = None
    try:
        roadmap_df = _load_roadmap()
    except Exception:
        roadmap_df = None

    collect = int(len(news_df)) if news_df is not None else 0

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

    return {
        "collect": collect,
        "match": match_count,
        "opp": opp_count,
        "pending": pending,
    }


def _archive_stats() -> dict[str, int]:
    """app-side 좌측 카운트 — 보드 KPI 와 동일 소스 재사용."""
    kpis = _board_kpis()
    return {
        "match_today": kpis["match"],
        "opportunities": kpis["opp"],
        "pending_adopt": kpis["pending"],
    }


def render() -> None:
    """오늘의 보드 v2 — topbar + app-side + main + app-sola 풀 셸 렌더."""
    # 보드 화면 전용 스타일 (.db-greet, .db-kpi, .db-stories, .db-trend 등)
    inject_screen_css("board")

    persona = _load_persona()
    stats = _archive_stats()
    refresh = app_shell.refresh_label_now()

    # ── 1) 풀폭 topbar ──
    app_shell.render_topbar(
        page_title="오늘의 보드",
        eyebrow_current="오늘의 보드",
        refresh_label=refresh,
        fresh_kind="fresh",
    )

    # ── 2) 좌측 .app-side ──
    app_shell.render_app_side(
        active_area="📊 오늘의 보드",
        persona=persona,
        stats=stats,
    )

    # ── 3) 본문 (main) — 템플릿 로드 후 placeholder 치환 ──
    _render_main(persona=persona, refresh_label=refresh)

    # ── 4) 우측 .app-sola ──
    app_shell.render_app_sola(
        context_label="오늘의 보드",
        context_sub=f"오늘 매칭 {stats['match_today']}건 · 자동화 기회 {stats['opportunities']}건",
        quick_prompts=[
            ("01", "이 페이지 <b>탑 스토리 3건</b>을 부서장 메시지로 요약해줘"),
            ("02", "<b>도장 비전 검사</b> PoC 일정·예산 초안 만들어줘"),
            ("03", "<b>트렌드</b> 그래프에서 우리 작업과 가장 관련 큰 키워드 3개는?"),
        ],
        last_q="자동화 기회 4건 중 가장 빨리 시작할 수 있는 건 뭐야?",
        last_a_html=(
            "도장 비전 검사가 가장 빨라요. <b>설비 변경 없이 카메라 1대 추가</b>로 "
            "1주 안에 시작 가능 — 게다가 도장팀이 작년에 비슷한 PoC 제안한 적이 있어 "
            "공감대도 있어요.<span class='muted'>05:54 · 컨텍스트: 자동화 기회 4건</span>"
        ),
        last_time="2분 전",
    )


def _render_main(*, persona: Persona, refresh_label: str) -> None:
    kpis = _board_kpis()
    # 델타는 yesterday snapshot 비교 후속 PR — 일단 빈 값
    template = _BOARD_TEMPLATE.read_text(encoding="utf-8")
    html_out = (
        template
        .replace("{{REFRESH_LABEL}}", _html.escape(refresh_label))
        .replace("{{PERSONA_GREET}}", _html.escape(_persona_greet(persona)))
        .replace("{{PERSONA_NAME}}", _html.escape(_persona_short(persona)))
        .replace("{{GREET_SUMMARY}}", _greet_summary_html(persona, kpis))
        .replace("{{KPI_COLLECT}}", str(kpis["collect"]))
        .replace("{{KPI_MATCH}}", str(kpis["match"]))
        .replace("{{KPI_OPP}}", str(kpis["opp"]))
        .replace("{{KPI_PENDING}}", str(kpis["pending"]))
        .replace("{{KPI_COLLECT_DELTA}}", "")
        .replace("{{KPI_MATCH_DELTA}}", "")
        .replace("{{KPI_OPP_DELTA}}", "")
        .replace("{{KPI_PENDING_DELTA}}", "")
        .replace("{{KPI_COLLECT_CLS}}", "db-delta-flat")
        .replace("{{KPI_MATCH_CLS}}", "db-delta-flat")
        .replace("{{KPI_OPP_CLS}}", "db-delta-flat")
        .replace("{{KPI_PENDING_CLS}}", "db-delta-flat")
        .replace("{{BOARD_STORIES}}", _board_stories_html())
        .replace("{{BOARD_OPPORTUNITIES}}", _opportunities_html())
    )
    brief = _brief_html()
    html_out = (
        html_out
        .replace("{{BRIEF_SUMMARY}}", brief["summary"])
        .replace("{{BRIEF_LIST}}", brief["list"])
        .replace("{{BRIEF_CITES}}", brief["cites"])
    )
    st.html(html_out)
