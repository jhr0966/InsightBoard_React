"""오늘의 보드: 페르소나 기반 인사이트 + 빠른 행동 + 사이드 채팅."""
from __future__ import annotations

import html
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from persona.schema import Persona
from roadmap.query import load_latest as load_roadmap
from sola import trend_brief
from sola.client import is_configured as llm_ready
from sola.insight import insight_for_dept
from store import trends
from store.match import score_matches
from store.news_db import load_all_today, load_news_for_days
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


def _persona_welcome(persona: Persona) -> str:
    """페르소나 카드 HTML 반환 (메인에 출력)."""
    if not persona.is_set():
        return (
            '<div class="card-flat">'
            '⬅️ <b>사이드바</b>에서 페르소나를 설정하면 맞춤 인사이트가 표시됩니다.'
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
) -> str:
    """사이드 채팅에 주입할 페이지 컨텍스트."""
    lines = []
    if persona.is_set():
        lines.append(f"사용자 부서: {persona.dept or '미설정'}, 직무: {persona.job or '미설정'}")
    if trend_ctx:
        lines.append(trend_ctx)
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

    # 홈 트렌드 위젯 페이로드 (메인·컨텍스트 양쪽 재사용)
    trend_payload = _compute_home_trend_payload(news)
    brief_text = st.session_state.get("_home_brief_text", "")
    trend_ctx = _build_trend_context(brief_text, trend_payload)
    page_ctx = _build_page_context(persona, news_ctx, insight_text, trend_ctx=trend_ctx)

    with main_and_chat(
        "home",
        page_context_fn=lambda: page_ctx,
        persona=persona,
        hint="현재 오늘의 보드(페르소나 · 매칭 뉴스 · AI 인사이트)를 컨텍스트로 대화합니다.",
    ) as main:
        with main:
            # 페르소나 welcome
            st.markdown(_persona_welcome(persona), unsafe_allow_html=True)

            # 메트릭 3개
            m1, m2, m3 = st.columns(3)
            m1.metric("오늘 뉴스", f"{len(news):,}건")
            m2.metric("로드맵 작업", f"{len(roadmap):,}건")
            enr = int((news["content"].astype(str).str.len() >= 50).sum()) if not news.empty and "content" in news.columns else 0
            m3.metric("본문 확보", f"{enr:,}건")

            if not news.empty:
                # 🧠 SOLA 한 줄 + emergence 칩 위젯 — news 만 있으면 표시 (roadmap 무관)
                wcol1, wcol2 = st.columns([5, 1])
                with wcol1:
                    st.markdown(
                        _trend_widget_html(brief_text, trend_payload["emergence"]),
                        unsafe_allow_html=True,
                    )
                with wcol2:
                    st.markdown("<div style='margin-top:1.6rem;'></div>", unsafe_allow_html=True)
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
                st.markdown(
                    '<div class="card-flat" style="margin-top:1.5rem;">'
                    '로드맵 업로드와 뉴스 수집을 먼저 진행하세요. '
                    '<b>🧱 데이터 관리</b> 메뉴로 이동.</div>',
                    unsafe_allow_html=True,
                )
            else:
                # 부서 뉴스 + 인사이트 2:1
                st.markdown("<div style='margin-top:1.5rem;'></div>", unsafe_allow_html=True)
                if chat_open:
                    # 채팅 패널 열려있으면 메인이 좁아지니 카드 세로 배치.
                    section_label("우리 부서 관련 뉴스")
                    st.markdown(news_html, unsafe_allow_html=True)
                    section_label("우리 부서 AI 인사이트")
                    st.markdown(insight_html, unsafe_allow_html=True)
                else:
                    left, right = st.columns([2, 1], gap="large")
                    with left:
                        section_label("우리 부서 관련 뉴스")
                        st.markdown(news_html, unsafe_allow_html=True)
                    with right:
                        section_label("우리 부서 AI 인사이트")
                        st.markdown(insight_html, unsafe_allow_html=True)

            # 빠른 행동
            st.markdown("<div style='margin-top:1.8rem;'></div>", unsafe_allow_html=True)
            section_label("빠른 행동")
            st.markdown(
                """
                <div class="quick-grid">
                  <div class="quick-tile">
                    <div class="quick-tile-icon">🔍</div>
                    <div class="quick-tile-title">데이터 관리</div>
                    <div class="quick-tile-desc">뉴스 수집·Enrich와 로드맵 업로드를 준비.</div>
                  </div>
                  <div class="quick-tile">
                    <div class="quick-tile-icon">📊</div>
                    <div class="quick-tile-title">인사이트 분석</div>
                    <div class="quick-tile-desc">트렌드·매칭·자동화 기회를 한 흐름으로 확인.</div>
                  </div>
                  <div class="quick-tile">
                    <div class="quick-tile-icon">💬</div>
                    <div class="quick-tile-title">SOLA 작업실</div>
                    <div class="quick-tile-desc">요약·과제 후보·제안서 초안을 생성.</div>
                  </div>
                  <div class="quick-tile">
                    <div class="quick-tile-icon">📝</div>
                    <div class="quick-tile-title">산출물 보관함</div>
                    <div class="quick-tile-desc">북마크·채택 과제·뉴스 콘텐츠를 재사용.</div>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
