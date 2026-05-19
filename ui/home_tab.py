"""오늘의 보드: 페르소나 기반 인사이트 + 빠른 행동 + 사이드 채팅."""
from __future__ import annotations

import html
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from persona.schema import Persona
from roadmap.query import load_latest as load_roadmap
from sola import opportunity, trend_brief
from sola.client import is_configured as llm_ready
from sola.insight import insight_for_dept
from store import trends
from store.match import score_matches
from store.news_db import load_all_today, load_news_for_days
from ui.components import (
    action_card,
    action_grid,
    metric_card,
    metric_grid,
    render_html,
    status_card,
    step_guide,
    step_item,
)
from ui.layout import main_and_chat
from ui.styles import page_header, section_label

HOME_TREND_DAYS = 7
HOME_TREND_LABEL = "최근 7일"


def _compute_home_trend_payload(
    news_today: pd.DataFrame,
    *,
    days: int = HOME_TREND_DAYS,
    now: datetime | None = None,
) -> dict:
    """홈 위젯용 트렌드 페이로드. days=1 이면 today only, days>1 이면 누적.

    Args:
        now: 테스트용 시점 주입 (UTC). 미지정 시 datetime.now(UTC).
    """
    cur = now or datetime.now(timezone.utc)
    period_df = news_today if days == 1 else load_news_for_days(days, now=cur)
    vol_df = trends.daily_volume(period_df, days=days, now=cur)

    if days > 1 and not period_df.empty:
        today_str = cur.strftime("%Y-%m-%d")
        # 스크래퍼별로 `date` 컬럼이 표시 텍스트("1시간 전", "최신 동향", RFC pubDate)
        # 일 수 있어 정규화된 `published_at` 을 우선 사용 (store/trends._date_col 동일 패턴).
        is_today = trends._date_col(period_df).eq(today_str)
        today_only = period_df[is_today]
        base_only = period_df[~is_today]
        if not today_only.empty and not base_only.empty:
            emergence = trends.keyword_emergence(today_only, base_only, top_n=5)
        else:
            emergence = _empty_emergence()
    else:
        emergence = _empty_emergence()
    return {"period_df": period_df, "vol_df": vol_df, "emergence": emergence}




def _content_ready_count(news: pd.DataFrame) -> int:
    """Return the number of news rows with enough body text for downstream analysis."""
    if news.empty or "content" not in news.columns:
        return 0
    return int((news["content"].astype(str).str.len() >= 50).sum())


def _recommended_actions(
    *,
    news_count: int,
    roadmap_count: int,
    enriched_count: int,
    persona: Persona,
    top_opportunities: pd.DataFrame,
) -> list[dict[str, str]]:
    """Build prioritized next actions for the home board.

    The order intentionally follows the product workflow: prepare data first,
    then inspect opportunities, then produce/manage SOLA outputs.
    """
    actions: list[dict[str, str]] = []

    if news_count == 0:
        actions.append({
            "icon": "📰",
            "title": "뉴스를 먼저 수집하세요",
            "body": "데이터 관리에서 키워드와 소스를 선택해 오늘 분석할 기사를 저장합니다.",
            "target": "데이터 관리",
            "tone": "warn",
        })
    elif enriched_count == 0:
        actions.append({
            "icon": "✨",
            "title": "본문 Enrich를 진행하세요",
            "body": "본문이 확보되면 요약, 키워드, 부서 매칭 품질이 좋아집니다.",
            "target": "데이터 관리",
            "tone": "warn",
        })

    if roadmap_count == 0:
        actions.append({
            "icon": "🗂",
            "title": "로드맵을 업로드하세요",
            "body": "작업 정의가 있어야 뉴스가 부서·공정·과제 후보로 연결됩니다.",
            "target": "데이터 관리",
            "tone": "teal",
        })

    if not persona.is_set():
        actions.append({
            "icon": "🎯",
            "title": "페르소나를 설정하세요",
            "body": "부서와 직무를 입력하면 오늘의 보드가 내 업무 기준으로 정렬됩니다.",
            "target": "사이드바",
            "tone": "info",
        })

    if news_count > 0 and roadmap_count > 0 and not top_opportunities.empty:
        first = top_opportunities.iloc[0]
        actions.append({
            "icon": "⚙️",
            "title": "상위 자동화 기회를 검토하세요",
            "body": f"{first['dept']} · {first['lv3']} 셀이 가장 높은 매칭 점수를 보입니다.",
            "target": "인사이트 분석",
            "tone": "ok",
        })
        actions.append({
            "icon": "💬",
            "title": "SOLA 제안서 초안을 만드세요",
            "body": "상위 기회를 선택해 요약·기대효과·실행안을 산출물로 전환합니다.",
            "target": "SOLA 작업실",
            "tone": "teal",
        })

    if not actions:
        actions.append({
            "icon": "📝",
            "title": "산출물을 정리하세요",
            "body": "북마크와 채택 과제를 확인하고 다음 회의 자료로 재사용하세요.",
            "target": "산출물 보관함",
            "tone": "info",
        })

    return actions[:4]


def _recommended_actions_html(actions: list[dict[str, str]]) -> str:
    """Render recommended next actions with escaped content."""
    cards: list[str] = []
    for idx, item in enumerate(actions, start=1):
        tone = item.get("tone", "")
        tone_cls = tone if tone in {"info", "ok", "warn", "danger", "teal"} else ""
        cards.append(f"""
        <div class="next-action-card {html.escape(tone_cls)}">
          <div class="next-action-rank">{idx}</div>
          <div class="next-action-content">
            <div class="next-action-meta">
              <span>{html.escape(item.get('icon', '•'))}</span>
              <span>{html.escape(item.get('target', ''))}</span>
            </div>
            <div class="next-action-title">{html.escape(item.get('title', ''))}</div>
            <div class="next-action-body">{html.escape(item.get('body', ''))}</div>
          </div>
        </div>
        """)
    return '<div class="next-action-grid">' + "".join(cards) + "</div>"


def _top_opportunities_html(cells: pd.DataFrame, *, persona: Persona, limit: int = 5) -> str:
    """Render the top automation opportunity cells for the home board."""
    if cells.empty:
        return status_card(
            "자동화 기회가 아직 계산되지 않았습니다",
            "다음 → 🧱 데이터 관리 → 1) 로드맵 업로드 2) 키워드 수집. 두 가지가 준비되면 부서·공정 기준 상위 기회가 여기에 표시됩니다.",
            status="warn",
            icon="⚙️",
        )

    cards: list[str] = []
    for rank, (_, row) in enumerate(cells.head(limit).iterrows(), start=1):
        is_mine = bool(persona.dept and str(row["dept"]) == persona.dept)
        mine_cls = " mine" if is_mine else ""
        badge = "🎯 내 부서" if is_mine else f"TOP {rank}"
        cards.append(f"""
        <div class="opportunity-pulse-card{mine_cls}">
          <div class="opportunity-pulse-top">
            <span class="opportunity-pulse-badge">{html.escape(badge)}</span>
            <span class="opportunity-pulse-score">score {float(row['cell_score']):.1f}</span>
          </div>
          <div class="opportunity-pulse-title">{html.escape(str(row['dept']))} · {html.escape(str(row['lv3']))}</div>
          <div class="opportunity-pulse-body">작업: {html.escape(str(row['sample_tasks'])[:150])}</div>
          <div class="opportunity-pulse-body muted">뉴스: {html.escape(str(row['sample_news'])[:180])}</div>
        </div>
        """)
    return '<div class="opportunity-pulse-grid">' + "".join(cards) + "</div>"


def _empty_emergence() -> dict[str, pd.DataFrame]:
    return {
        "new": pd.DataFrame(columns=["keyword", "count"]),
        "gone": pd.DataFrame(columns=["keyword", "count"]),
        "rising": pd.DataFrame(columns=["keyword", "today", "base", "delta"]),
    }


def _chip_row(label: str, df: pd.DataFrame, *, color: str) -> str:
    """emergence DataFrame 을 작은 칩 줄 HTML 로 변환. df 비면 빈 칩."""
    if df.empty:
        chips_html = '<span style="font-size:0.78rem;color:var(--text-3);">(없음)</span>'
    else:
        chips: list[str] = []
        for _, r in df.head(5).iterrows():
            kw = html.escape(str(r["keyword"]))
            if "delta" in df.columns:
                n = f"+{int(r['delta'])}"
            else:
                n = str(int(r["count"]))
            chips.append(
                f'<span class="card-press" style="background:{color};color:#fff;'
                f'margin-right:6px;font-weight:600;">{kw} · {n}</span>'
            )
        chips_html = "".join(chips)
    return (
        f'<div style="margin-bottom:8px;">'
        f'<span style="font-size:0.82rem;color:var(--text-2);margin-right:8px;font-weight:600;">'
        f'{html.escape(label)}</span>{chips_html}</div>'
    )


def _trend_widget_html(brief_text: str, emergence: dict[str, pd.DataFrame]) -> str:
    """🧠 SOLA 한 줄 + 🆕/📈/📉 칩 3행 카드."""
    brief_safe = html.escape(brief_text) if brief_text else (
        '<span style="color:var(--text-3);">버튼을 눌러 LLM 해석을 생성하세요.</span>'
    )
    return (
        f'<div class="card" style="margin-top:1.5rem;">'
        f'<div class="card-meta">'
        f'<span class="card-press">🧠 SOLA 한 줄</span>'
        f'<span class="card-date">{html.escape(HOME_TREND_LABEL)}</span>'
        f'</div>'
        f'<div class="card-body" style="-webkit-line-clamp:4;font-size:0.95rem;'
        f'margin-bottom:10px;">{brief_safe}</div>'
        f'<div style="border-top:1px solid var(--border);padding-top:10px;">'
        f'{_chip_row("🆕 새 키워드", emergence["new"], color="#2563eb")}'
        f'{_chip_row("📈 상승 키워드", emergence["rising"], color="#16a34a")}'
        f'{_chip_row("📉 사라진 키워드", emergence["gone"], color="#9ca3af")}'
        f'</div></div>'
    )


def _build_trend_context(brief_text: str, payload: dict) -> str:
    """홈 page_context 에 합칠 트렌드 라인들."""
    lines: list[str] = []
    vol_df = payload["vol_df"]
    if not vol_df.empty:
        lines.append(
            f"\n[{HOME_TREND_LABEL} 트렌드] 일자별 기사 수: "
            + ", ".join(f"{r['date']}={r['count']}" for _, r in vol_df.iterrows())
        )
    em = payload["emergence"]
    if not em["new"].empty:
        lines.append("새 키워드(오늘만): " + ", ".join(
            f"{r['keyword']}={r['count']}" for _, r in em["new"].head(5).iterrows()
        ))
    if not em["rising"].empty:
        lines.append("상승 키워드: " + ", ".join(
            f"{r['keyword']}(+{r['delta']})" for _, r in em["rising"].head(5).iterrows()
        ))
    if brief_text:
        lines.append(f"SOLA 한 줄 해석: {brief_text}")
    return "\n".join(lines)


def _onboarding_steps_html(
    persona: Persona, *, roadmap_count: int, news_count: int,
) -> str:
    """초기 사용자용 3단계 시작 가이드.

    페르소나·로드맵·뉴스가 차례대로 준비되면 각 step 이 active(녹색) 처리된다.
    이미 모든 단계가 완료된 사용자에게는 호출 측에서 표시 자체를 생략한다.
    """
    return step_guide([
        step_item(
            1, "프로필 설정",
            "좌측 ⬅️ 아바타를 눌러 부서·직무·관심 공정을 입력하세요.",
            active=persona.is_set(),
        ),
        step_item(
            2, "로드맵 업로드",
            "🧱 데이터 관리 → '로드맵 업로드' 탭에서 작업 정의(CSV/Excel)를 올리세요.",
            active=roadmap_count > 0,
        ),
        step_item(
            3, "뉴스 수집",
            "🧱 데이터 관리 → '뉴스 수집' 탭에서 키워드 입력 후 📥 수집·저장을 누르세요. 본문·이미지가 함께 저장됩니다.",
            active=news_count > 0,
        ),
    ])


def _persona_welcome(persona: Persona) -> str:
    """페르소나 카드 HTML 반환 (메인에 출력)."""
    if not persona.is_set():
        return (
            '<div class="card">'
            '<div style="font-size:1.4rem;font-weight:700;color:var(--text-1);'
            'letter-spacing:-0.02em;margin-bottom:6px;">처음 시작하시나요?</div>'
            '<div style="color:var(--text-2);font-size:0.95rem;">'
            '아래 <b>3단계</b>를 차례대로 마치면 부서별 맞춤 뉴스·자동화 기회·AI 인사이트가 '
            '자동으로 정렬됩니다. 완료된 단계는 <b>녹색</b>으로 바뀝니다.'
            '</div>'
            '</div>'
        )
    chips_html = ""
    for label, val in (("부서", persona.dept), ("직무", persona.job), ("팀", persona.team)):
        if val:
            chips_html += (
                f'<span class="card-press">{html.escape(label)}</span>'
                f'<span style="color:var(--text-2);font-size:0.85rem;margin:0 14px 0 6px;">'
                f'{html.escape(val)}</span>'
            )
    name = html.escape(persona.name or "사용자")
    return f"""
    <div class="card">
      <div style="font-size:1.4rem;font-weight:700;color:var(--text-1);letter-spacing:-0.02em;
                  margin-bottom:6px;">안녕하세요, {name} 님</div>
      <div style="display:flex;flex-wrap:wrap;align-items:center;gap:6px;">{chips_html}</div>
    </div>
    """


def _dept_news_cards(persona: Persona, roadmap: pd.DataFrame, news: pd.DataFrame) -> tuple[str, list[dict]]:
    """부서 매칭 뉴스 카드 HTML + 컨텍스트용 dict 리스트 반환."""
    if not persona.dept:
        target = roadmap
        caption = "부서 미설정 — 전체 매칭 점수 상위로 표시합니다."
    else:
        target = roadmap[roadmap["dept"] == persona.dept]
        if target.empty:
            return (
                f'<div class="card-flat">로드맵에 \'{html.escape(persona.dept)}\' 작업이 없습니다.</div>',
                [],
            )
        caption = ""

    if persona.interest_lv3:
        sub = target[target["lv3"].astype(str).isin(persona.interest_lv3)]
        if not sub.empty:
            target = sub

    matches = score_matches(news, target, top_k=2)
    if matches.empty:
        return ('<div class="card-flat">매칭되는 뉴스가 없습니다.</div>', [])

    top = matches.sort_values("score", ascending=False).drop_duplicates("link").head(6)

    parts: list[str] = []
    ctx_items: list[dict] = []
    if caption:
        parts.append(f'<div style="font-size:0.78rem;color:var(--text-3);margin-bottom:8px;">{caption}</div>')

    for _, row in top.iterrows():
        related = news[news["link"] == row["link"]].head(1)
        body = ""
        if not related.empty:
            r = related.iloc[0]
            body = str(r.get("summary_llm") or r.get("summary") or "")
        parts.append(f"""
        <div class="card" style="margin-bottom:12px;">
          <div class="card-meta">
            <span class="card-press">{html.escape(str(row['dept']))}</span>
            <span class="card-date">{html.escape(str(row['lv3']))} · {html.escape(str(row['task']))}</span>
            <span class="card-num">score {row['score']:.1f}</span>
          </div>
          <div class="card-title" style="-webkit-line-clamp:2;">{html.escape(str(row['news_title']))}</div>
          <div class="card-body" style="-webkit-line-clamp:3;">{html.escape(body[:240])}</div>
          <div class="card-link"><a href="{html.escape(str(row['link']))}" target="_blank">원문 보기 →</a></div>
        </div>
        """)
        ctx_items.append({
            "title": str(row["news_title"]),
            "dept": str(row["dept"]),
            "lv3": str(row["lv3"]),
            "task": str(row["task"]),
            "summary": body[:200],
        })
    return ("".join(parts), ctx_items)


def _dept_insight_card(persona: Persona, news: pd.DataFrame) -> tuple[str, str]:
    """부서 AI 인사이트 카드 HTML + raw 텍스트 반환."""
    if not persona.dept:
        return ('<div class="card-flat" style="font-size:0.85rem;color:var(--text-3);">부서 미설정</div>', "")
    if not llm_ready():
        return (
            '<div class="card-flat" style="font-size:0.85rem;color:var(--text-3);">'
            'LLM 미설정 — <code>.env</code> 의 <code>LLM_API_KEY</code> 후 표시됩니다.</div>',
            "",
        )
    text = insight_for_dept(persona.dept, news)
    return (
        f'<div class="card"><div class="card-meta">'
        f'<span class="card-press">{html.escape(persona.dept)} · AI 인사이트</span></div>'
        f'<div class="card-body" style="-webkit-line-clamp:8;font-size:0.92rem;">'
        f'{html.escape(text)}</div></div>',
        text,
    )


def _build_page_context(
    persona: Persona,
    news_items: list[dict],
    insight_text: str,
    trend_ctx: str = "",
    recommended_actions: list[dict[str, str]] | None = None,
    top_opportunities: pd.DataFrame | None = None,
) -> str:
    """사이드 채팅에 주입할 페이지 컨텍스트."""
    lines = []
    if persona.is_set():
        lines.append(f"사용자 부서: {persona.dept or '미설정'}, 직무: {persona.job or '미설정'}")
    if trend_ctx:
        lines.append(trend_ctx)
    if recommended_actions:
        lines.append("\n추천 다음 행동:")
        for item in recommended_actions[:4]:
            lines.append(f"- {item.get('target', '')}: {item.get('title', '')} — {item.get('body', '')}")
    if top_opportunities is not None and not top_opportunities.empty:
        lines.append("\n자동화 기회 Top:")
        for _, row in top_opportunities.head(5).iterrows():
            lines.append(
                f"- {row['dept']} / {row['lv3']} score={row['cell_score']:.1f}; "
                f"tasks={row['sample_tasks']}"
            )
    if insight_text:
        lines.append(f"\n부서 AI 인사이트:\n{insight_text}")
    if news_items:
        lines.append("\n표시 중인 부서 매칭 뉴스 (상위):")
        for it in news_items[:5]:
            lines.append(f"- [{it['dept']}/{it['lv3']}/{it['task']}] {it['title']}")
            if it["summary"]:
                lines.append(f"    {it['summary']}")
    return "\n".join(lines)


def render() -> None:
    persona: Persona = st.session_state.get("persona") or Persona()
    roadmap = load_roadmap()
    news = load_all_today()

    # 페이지 헤더 (채팅 토글 포함)
    chat_open = page_header(
        "오늘의 보드",
        "핵심 변화 · 부서 맞춤 인사이트 · 추천 다음 행동",
        chat_toggle_key="home",
    )

    # 본문 컨텍스트 채우기를 위해 미리 계산
    news_html, news_ctx = ("", [])
    insight_html, insight_text = ("", "")
    if not roadmap.empty and not news.empty:
        news_html, news_ctx = _dept_news_cards(persona, roadmap, news)
        insight_html, insight_text = _dept_insight_card(persona, news)

    # 홈 트렌드/추천 행동 페이로드 (메인·컨텍스트 양쪽 재사용)
    trend_payload = _compute_home_trend_payload(news)
    brief_text = st.session_state.get("_home_brief_text", "")
    trend_ctx = _build_trend_context(brief_text, trend_payload)
    enriched_count = _content_ready_count(news)
    if not roadmap.empty and not news.empty:
        top_opportunities = opportunity.score_cells(news, roadmap, cell_level="lv3", top_k_per_task=5)
    else:
        top_opportunities = pd.DataFrame()
    recommended_actions = _recommended_actions(
        news_count=len(news),
        roadmap_count=len(roadmap),
        enriched_count=enriched_count,
        persona=persona,
        top_opportunities=top_opportunities,
    )
    page_ctx = _build_page_context(
        persona,
        news_ctx,
        insight_text,
        trend_ctx=trend_ctx,
        recommended_actions=recommended_actions,
        top_opportunities=top_opportunities,
    )

    with main_and_chat(
        "home",
        page_context_fn=lambda: page_ctx,
        persona=persona,
        hint="현재 오늘의 보드(페르소나 · 매칭 뉴스 · AI 인사이트)를 컨텍스트로 대화합니다.",
    ) as main:
        with main:
            # 페르소나 welcome
            render_html(_persona_welcome(persona), unsafe_allow_html=True)

            # 초기 사용자 — 페르소나·로드맵·뉴스 중 하나라도 비어있으면 3단계 시작 가이드
            if not persona.is_set() or roadmap.empty or news.empty:
                render_html(
                    _onboarding_steps_html(
                        persona,
                        roadmap_count=len(roadmap),
                        news_count=len(news),
                    ),
                    unsafe_allow_html=True,
                )

            # 핵심 상태 카드
            render_html(
                metric_grid([
                    metric_card("오늘 뉴스", f"{len(news):,}건", caption="수집된 최신 기사", icon="📰", tone="info"),
                    metric_card("로드맵 작업", f"{len(roadmap):,}건", caption="매칭 가능한 작업 정의", icon="🗂", tone="teal"),
                    metric_card("본문 확보", f"{enriched_count:,}건", caption="요약·키워드 분석 준비", icon="✨", tone="ok" if enriched_count else "warn"),
                ]),
                unsafe_allow_html=True,
            )

            section_label("추천 다음 행동")
            render_html(_recommended_actions_html(recommended_actions), unsafe_allow_html=True)

            if not news.empty:
                # 🧠 SOLA 한 줄 + emergence 칩 위젯 — news 만 있으면 표시 (roadmap 무관)
                wcol1, wcol2 = st.columns([5, 1])
                with wcol1:
                    render_html(
                        _trend_widget_html(brief_text, trend_payload["emergence"]),
                        unsafe_allow_html=True,
                    )
                with wcol2:
                    render_html("<div style='margin-top:1.6rem;'></div>", unsafe_allow_html=True)
                    if st.button(
                        "🔄 갱신",
                        key="_home_brief_btn",
                        use_container_width=True,
                        disabled=trend_payload["period_df"].empty,
                        help="LLM 으로 최근 7일 트렌드를 한 줄로 다시 해석합니다.",
                    ):
                        st.session_state["_do_home_brief"] = True

                if st.session_state.pop("_do_home_brief", False):
                    with st.spinner("LLM 호출 중…"):
                        st.session_state["_home_brief_text"] = trend_brief.brief(
                            period_label=HOME_TREND_LABEL,
                            vol_df=trend_payload["vol_df"],
                            emergence=trend_payload["emergence"],
                        )
                    st.rerun()

            # 부서 뉴스 + 인사이트 — roadmap + news 둘 다 필요
            if roadmap.empty or news.empty:
                render_html(
                    status_card(
                        "데이터 준비가 필요합니다",
                        "다음 → 🧱 데이터 관리 (왼쪽 메뉴) → 1) 로드맵 업로드 2) 뉴스 수집. 두 가지가 준비되면 부서별 추천 뉴스·AI 인사이트·기회가 자동 표시됩니다.",
                        status="warn",
                        icon="🧱",
                    ),
                    unsafe_allow_html=True,
                )
            else:
                # 부서 뉴스 + 인사이트 2:1
                render_html("<div style='margin-top:1.5rem;'></div>", unsafe_allow_html=True)
                if chat_open:
                    # 채팅 패널 열려있으면 메인이 좁아지니 카드 세로 배치.
                    section_label("우리 부서 관련 뉴스")
                    render_html(news_html, unsafe_allow_html=True)
                    section_label("우리 부서 AI 인사이트")
                    render_html(insight_html, unsafe_allow_html=True)
                else:
                    left, right = st.columns([2, 1], gap="large")
                    with left:
                        section_label("우리 부서 관련 뉴스")
                        render_html(news_html, unsafe_allow_html=True)
                    with right:
                        section_label("우리 부서 AI 인사이트")
                        render_html(insight_html, unsafe_allow_html=True)

                render_html("<div style='margin-top:1.5rem;'></div>", unsafe_allow_html=True)
                section_label("자동화 기회 Top 5")
                render_html(_top_opportunities_html(top_opportunities, persona=persona), unsafe_allow_html=True)

            # 빠른 행동
            render_html("<div style='margin-top:1.8rem;'></div>", unsafe_allow_html=True)
            section_label("빠른 행동")
            render_html(
                action_grid([
                    action_card("🔍", "데이터 관리", "뉴스 수집·Enrich와 로드맵 업로드를 준비.", tone="teal"),
                    action_card("📊", "인사이트 분석", "트렌드·매칭·자동화 기회를 한 흐름으로 확인."),
                    action_card("💬", "SOLA 작업실", "요약·과제 후보·제안서 초안을 생성."),
                    action_card("📝", "산출물 보관함", "북마크·채택 과제·뉴스 콘텐츠를 재사용."),
                ]),
                unsafe_allow_html=True,
            )
