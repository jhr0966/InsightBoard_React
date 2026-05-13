"""수집 탭: 네이버 + 구글 + AI Times/오토메이션월드, 본문 enrich (M4-α)."""
from __future__ import annotations

import html

import pandas as pd
import streamlit as st

from persona.schema import Persona
from scraping import enrich as enrich_mod
from scraping import google as google_news
from scraping import naver as naver_news
from scraping import tech_sites
from sola.client import is_configured as llm_ready
from store.news_db import load_all_today, save_articles, upsert_articles
from ui.layout import main_and_chat
from ui.styles import page_header, section_label


_SOURCES = ("네이버 뉴스", "구글 뉴스", "AI Times / 오토메이션월드")


def _run_collect(selected: list[str], keyword: str, max_results: int) -> None:
    saved: list[str] = []
    errors: list[str] = []
    if "네이버 뉴스" in selected:
        try:
            articles = naver_news.search(keyword, max_results=max_results)
            path = save_articles(articles, source="naver")
            saved.append(f"네이버 {len(articles)}건 → {path.name if path else '-'}")
        except RuntimeError as e:
            errors.append(f"네이버: {e}")
    if "구글 뉴스" in selected:
        try:
            articles = google_news.search(keyword, max_results=max_results)
            path = save_articles(articles, source="google")
            saved.append(f"구글 {len(articles)}건 → {path.name if path else '-'}")
        except RuntimeError as e:
            errors.append(f"구글: {e}")
    if "AI Times / 오토메이션월드" in selected:
        articles = tech_sites.search_all(max_results_per_site=max_results)
        path = save_articles(articles, source="tech")
        saved.append(f"테크 사이트 {len(articles)}건 → {path.name if path else '-'}")

    st.session_state["ins_status"] = (
        "error" if errors and not saved else "ok",
        " · ".join(saved + errors) or "수집된 기사가 없습니다.",
    )


def _run_enrich(use_llm: bool, n: int) -> None:
    df = load_all_today()
    if df.empty:
        st.session_state["ins_status"] = ("warn", "오늘 수집된 기사가 없습니다.")
        return

    need = df[df["content"].astype(str).str.len() < 50] if "content" in df.columns else df
    target = need.head(n).to_dict(orient="records")
    if not target:
        st.session_state["ins_status"] = ("ok", "이미 모두 enrich 됨.")
        return

    prog = st.progress(0.0, text=f"본문 fetch + {'LLM' if use_llm else '룰'} 진행 중…")

    def _cb(done: int, total: int, _art: dict) -> None:
        prog.progress(done / total, text=f"[{done}/{total}] 처리 중…")

    enriched = enrich_mod.enrich_articles(target, with_llm=use_llm, progress_cb=_cb)
    prog.empty()

    # 소스별로 그룹핑 후 upsert
    by_src: dict[str, list[dict]] = {}
    for art in enriched:
        by_src.setdefault(art.get("source", "naver"), []).append(art)
    for src, items in by_src.items():
        upsert_articles(items, source=src)

    enriched_cnt = sum(1 for a in enriched if a.get("content"))
    st.session_state["ins_status"] = (
        "ok",
        f"{enriched_cnt}/{len(enriched)} 기사 본문 확보 (LLM {'사용' if use_llm else '미사용'}).",
    )


def _build_page_context(df: pd.DataFrame) -> str:
    lines = ["화면: 뉴스 수집 + 본문 Enrich"]
    if df.empty:
        lines.append("오늘 수집된 기사: 없음")
        return "\n".join(lines)
    enriched = int((df["content"].astype(str).str.len() >= 50).sum()) if "content" in df.columns else 0
    lines.append(f"오늘 수집: {len(df):,}건 · 본문 확보: {enriched:,}건")
    by_src = df.groupby("source", dropna=False).size().sort_values(ascending=False)
    lines.append("소스 분포: " + ", ".join(f"{idx}={cnt}" for idx, cnt in by_src.items()))
    lines.append("\n최근 10건 헤드라인:")
    for _, row in df.head(10).iterrows():
        title = str(row.get("title", ""))[:120]
        press = str(row.get("press", ""))
        lines.append(f"- [{press}] {title}")
    return "\n".join(lines)


def render() -> None:
    persona: Persona = st.session_state.get("persona") or Persona()
    page_header(
        "뉴스 수집 + 본문 Enrich",
        "네이버 · 구글 · AI Times · 오토메이션월드",
        chat_toggle_key="ingest",
    )

    df_for_ctx = load_all_today()
    with main_and_chat(
        "ingest",
        page_context_fn=lambda: _build_page_context(df_for_ctx),
        persona=persona,
        hint="방금 수집한 뉴스 통계·헤드라인을 컨텍스트로 대화합니다.",
    ) as main:
        with main:
            col1, col2 = st.columns([3, 2])
            with col1:
                st.text_input("검색 키워드 (테크 사이트 수집엔 미사용)", key="ins_keyword",
                              placeholder="예: 조선소 자동화, 용접 로봇")
            with col2:
                st.multiselect("소스 선택", _SOURCES, default=list(_SOURCES), key="ins_sources")
            st.slider("소스당 수집 건수", min_value=5, max_value=50, value=20, step=5, key="ins_max_results")

            btn_col1, btn_col2 = st.columns(2)
            with btn_col1:
                if st.button("📥 수집·저장", type="primary"):
                    st.session_state["_do_collect"] = True
            with btn_col2:
                if st.button("✨ 본문 Enrich (LLM 키워드/요약)"):
                    st.session_state["_do_enrich"] = True

            use_llm = st.checkbox("Enrich 시 LLM 키워드·요약 사용", value=llm_ready(), disabled=not llm_ready(),
                                  help="LLM 미설정 시 본문만 가져옵니다.")
            enrich_n = st.slider("Enrich 대상 (최근 미처리 N건)", 1, 30, 10, key="ins_enrich_n")

            if st.session_state.pop("_do_collect", False):
                keyword = st.session_state.get("ins_keyword", "").strip()
                sources = st.session_state.get("ins_sources", list(_SOURCES))
                if not keyword and any(s in sources for s in ("네이버 뉴스", "구글 뉴스")):
                    st.session_state["ins_status"] = ("warn", "네이버/구글 수집에는 키워드가 필요합니다.")
                elif not sources:
                    st.session_state["ins_status"] = ("warn", "소스를 하나 이상 선택하세요.")
                else:
                    _run_collect(sources, keyword, int(st.session_state.get("ins_max_results", 20)))
                st.rerun()

            if st.session_state.pop("_do_enrich", False):
                _run_enrich(use_llm, int(st.session_state.get("ins_enrich_n", 10)))
                st.rerun()

            status = st.session_state.get("ins_status")
            if status:
                kind, msg = status
                {"ok": st.success, "warn": st.warning, "error": st.error}[kind](msg)

            st.markdown("<div style='height:1.2rem;'></div>", unsafe_allow_html=True)
            df = load_all_today()
            st.caption(
                f"오늘 저장된 전체 기사: {len(df)}건 · enrich 완료: "
                f"{int((df['content'].astype(str).str.len() >= 50).sum()) if not df.empty else 0}건"
            )

            if df.empty:
                return

            by_source = (
                df.groupby("source", dropna=False).size()
                .reset_index(name="count").sort_values("count", ascending=False, ignore_index=True)
            )
            section_label("소스별 분포")
            st.dataframe(by_source, use_container_width=True, hide_index=True)

            section_label("최근 10건 (enrich 결과 우선)")
            for _, row in df.head(10).iterrows():
                summary_show = str(row.get("summary_llm") or row.get("summary") or "")
                kw_show = str(row.get("keywords_llm") or row.get("keywords") or "")
                kw_html = (
                    "".join(
                        f'<span class="keyword-badge">{html.escape(k.strip())}</span>'
                        for k in kw_show.split(",")[:6] if k.strip()
                    )
                    if kw_show else ""
                )
                st.markdown(
                    f"""
                    <div class="news-card">
                        <div class="card-meta">
                            <span class="card-press">{html.escape(str(row.get('press', '')))}</span>
                            <span class="card-date">{html.escape(str(row.get('date', '')))}</span>
                            <span class="card-num">{html.escape(str(row.get('source', '')))}</span>
                        </div>
                        <div class="card-title">{html.escape(str(row.get('title', '')))}</div>
                        <div class="card-keywords">{kw_html}</div>
                        <div class="card-body">{html.escape(summary_show)}</div>
                        <div class="card-link"><a href="{html.escape(str(row.get('link', '')))}" target="_blank">원문 보기 →</a></div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
