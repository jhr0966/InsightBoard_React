import streamlit as st
import pandas as pd
import io
import re
import html
import json
from pathlib import Path
from scraper import (
    search_naver_news,
    fetch_latest_tech_news,
    enrich_articles_parallel,
    articles_to_dataframe,
)
import insights
import cardnews
from local_store import LocalNewsRepository
from shipyard_store import ingest_shipyard_excel, REQUIRED_COLUMNS, load_latest_shipyard_tasks, create_fake_shipyard_tasks
from proposal_engine import suggest_for_tasks, proposals_to_markdown, save_proposals_artifacts
from workspace_overview import build_workspace_metrics
from workspace_ui import render_workspace
from data_quality import render_data_quality
from proposal_filters import render_task_filters


def _safe_filename(text: str, fallback: str = "news") -> str:
    cleaned = re.sub(r"[^0-9A-Za-z가-힣_-]+", "_", text or "").strip("_")
    return cleaned[:40] or fallback

# ── 💡 향후 스크래핑할 사이트를 추가하려면 이 딕셔너리에 추가만 하시면 됩니다! ──
TARGET_SITES = {
    "AITimes": "https://www.aitimes.com",
    "오토메이션월드": "https://automation-world.co.kr",
    # 예시 추가: "전자신문": "https://www.etnews.com",
}

def _show_debug():
    log = st.session_state.debug_log
    if log:
        st.markdown(f'<div class="debug-box">{log}</div>', unsafe_allow_html=True)
    else:
        st.info("디버그 체크박스를 켜고 검색하면 셀렉터 탐색 과정이 여기에 표시됩니다.")

# ─────────────────────────────────────────────
# 페이지 설정 및 전역 CSS
# ─────────────────────────────────────────────
st.set_page_config(page_title="통합 뉴스 스크래퍼", page_icon="📰", layout="wide", initial_sidebar_state="expanded")

def _inject_global_styles() -> None:
    css = Path("assets/styles.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


_inject_global_styles()

# ─────────────────────────────────────────────
# 세션 상태 초기화
# ─────────────────────────────────────────────
NEWS_REPOSITORY = LocalNewsRepository()
bootstrap_naver = NEWS_REPOSITORY.load_latest_articles("naver")
bootstrap_tech = NEWS_REPOSITORY.load_latest_articles("tech")

for k, v in [
    ("articles_naver", bootstrap_naver),
    ("keyword_naver", ""),
    ("debug_log", ""),
    ("articles_tech", bootstrap_tech),
    ("proposal_results", []),
    ("proposal_artifacts", {}),
    ("cn_last_png", b""),
    ("cn_deck_zip", b""),
]:
    if k not in st.session_state:
        st.session_state[k] = v

# ─────────────────────────────────────────────
# 사이드바 메뉴 (화면 분리)
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ 메뉴 선택")
    app_mode = st.radio(
        "작업할 기능을 선택하세요.",
        [
            "🏠 워크스페이스",
            "🔍 네이버 뉴스 검색",
            "🚀 최신 기술 동향 (AI/자동화)",
            "🏭 조선소 작업 데이터",
            "🤝 자동화 과제 제안",
            "🧪 데이터 품질",
            "📊 인사이트 보드",
            "🎨 카드뉴스",
        ],
        label_visibility="collapsed"
    )
    st.markdown("---")
    st.markdown("💡 **Tip**: 각 탭별로 수집된 데이터는 다른 탭으로 이동해도 유지됩니다.")

# ─────────────────────────────────────────────
# 공통 UI 렌더링 함수 (재사용)
# ─────────────────────────────────────────────
def render_cards_html(arts, index_map):
    """카드뉴스를 그려주는 HTML 헬퍼 함수.

    index_map: id(article) -> 전체 목록 기준 1-based 번호
    """
    if not arts:
        st.info("조건에 맞는 기사가 없습니다.")
        return

    cols_per_row = 3
    rows = [arts[i:i+cols_per_row] for i in range(0, len(arts), cols_per_row)]
    for row in rows:
        cols = st.columns(cols_per_row, gap="medium")
        for col, art in zip(cols, row):
            with col:
                title_raw   = art.get("title", "제목 없음")
                press_raw   = art.get("press", "")
                date_raw    = art.get("date", "")
                link_raw    = art.get("link", "#")
                summary_raw = art.get("summary", "")
                content_raw = art.get("content", "")
                img_url_raw = art.get("img_url", "")
                num         = index_map.get(id(art), 0)

                body_source = content_raw if len(content_raw) > 50 else summary_raw
                if len(body_source) > 300:
                    body_source = body_source[:300] + "..."

                # ── XSS 방어: 스크랩한 모든 문자열을 HTML 이스케이프 ──
                title   = html.escape(title_raw)
                press   = html.escape(press_raw)
                date    = html.escape(date_raw)
                body    = html.escape(body_source) if body_source else "본문 내용 없음"
                # URL은 속성 컨텍스트이므로 quote=True로 " ' 도 이스케이프, 스킴 검증
                link    = html.escape(link_raw, quote=True) if link_raw.startswith(("http://", "https://")) else "#"
                img_url = html.escape(img_url_raw, quote=True) if img_url_raw.startswith(("http://", "https://")) else ""

                keywords_str = art.get("keywords", "")
                kw_html = ""
                if keywords_str:
                    kw_list = [k.strip() for k in keywords_str.split(',') if k.strip()]
                    kw_badges = "".join(
                        f'<span class="keyword-badge">#{html.escape(k)}</span>' for k in kw_list
                    )
                    kw_html = f'<div class="card-keywords">{kw_badges}</div>'

                press_html = f'<span class="card-press">{press}</span>' if press else ""
                date_html  = f'<span class="card-date">{date}</span>'   if date  else ""

                if img_url:
                    img_html = f'<img src="{img_url}" class="card-img" alt="기사 썸네일">'
                else:
                    img_html = '<div class="card-img-placeholder">No Image</div>'

                st.markdown(f"""
<div class="news-card">
{img_html}
<div class="card-meta">
{press_html}{date_html}
<span class="card-num">#{num}</span>
</div>
<div class="card-title">{title}</div>
{kw_html}
<div class="card-body">{body}</div>
<div class="card-link"><a href="{link}" target="_blank" rel="noopener noreferrer">원문 보기 →</a></div>
</div>
""", unsafe_allow_html=True)


def _table_column_config():
    return {
        "링크": st.column_config.LinkColumn("링크", display_text="열기"),
        "이미지URL": st.column_config.LinkColumn("이미지URL", display_text="보기"),
        "제목": st.column_config.TextColumn("제목", width="medium"),
        "발행시각(UTC)": st.column_config.TextColumn("발행시각(UTC)", width="small"),
        "본문내용": st.column_config.TextColumn("본문내용", width="large"),
        "추출키워드": st.column_config.TextColumn("추출키워드", width="medium"),
    }


def render_results(articles, keyword_display, session_key_prefix, mode="naver"):
    if not articles:
        return

    # 전체 목록 기준 1-based 고유 번호 (id 기반이라 동일 dict 오매칭 없음)
    index_map = {id(a): i + 1 for i, a in enumerate(articles)}

    # 필터링 로직
    all_kws = set()
    for art in articles:
        if art.get("keywords"):
            for k in art["keywords"].split(","):
                if k.strip():
                    all_kws.add(k.strip())

    st.markdown("##### 🏷️ 키워드 필터링")
    selected_kws = st.multiselect(
        "기사에서 추출된 핵심 단어로 결과를 필터링해보세요.",
        options=sorted(list(all_kws)),
        default=[],
        key=f"filter_{session_key_prefix}"
    )

    if selected_kws:
        filtered_articles = []
        for art in articles:
            art_kws = [k.strip() for k in art.get("keywords", "").split(",") if k.strip()]
            if any(k in art_kws for k in selected_kws):
                filtered_articles.append(art)
    else:
        filtered_articles = articles

    df = articles_to_dataframe(filtered_articles)

    st.markdown(f"""
    <div class="result-bar">
        <span style="font-size:.85rem;color:var(--text-2);">조회 기준</span>
        <span class="result-kw">"{html.escape(keyword_display)}"</span>
        <span class="result-count">— 총 {len(articles)}건 중 {len(filtered_articles)}건 표시</span>
        <span class="result-badge">완료</span>
    </div>
    """, unsafe_allow_html=True)

    csv_buf = io.StringIO()
    df.to_csv(csv_buf, encoding="utf-8-sig")
    csv_name = f"news_{_safe_filename(keyword_display, session_key_prefix)}_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.csv"
    st.download_button(
        label="⬇ CSV 다운로드",
        data=csv_buf.getvalue().encode("utf-8-sig"),
        file_name=csv_name,
        mime="text/csv",
        key=f"dl_{session_key_prefix}"
    )

    st.markdown("<hr>", unsafe_allow_html=True)

    # ── 탭 렌더링 동적 분기 처리 ──
    if mode == "naver":
        # 네이버는 탭 분리 없이 통합 표시
        tab_card, tab_table = st.tabs(["🗞 통합 카드뉴스", "📊 데이터 테이블"])
        with tab_card:
            render_cards_html(filtered_articles, index_map)
        with tab_table:
            st.dataframe(df, use_container_width=True, height=500, column_config=_table_column_config())

    elif mode == "tech":
        # 최신 동향은 스크래핑된 사이트(Press) 목록을 파악하여 동적으로 탭 생성
        presses = []
        for art in filtered_articles:
            if art["press"] not in presses:
                presses.append(art["press"])

        if not presses:
            st.info("선택한 키워드가 포함된 기사가 없습니다.")
            return

        tab_titles = [f"🗞 {p}" for p in presses] + ["📊 전체 데이터 테이블"]
        tabs = st.tabs(tab_titles)

        for i, p_name in enumerate(presses):
            with tabs[i]:
                site_arts = [a for a in filtered_articles if a["press"] == p_name]
                render_cards_html(site_arts, index_map)

        with tabs[-1]:
            st.dataframe(df, use_container_width=True, height=500, column_config=_table_column_config())

# ─────────────────────────────────────────────
# 화면 1: 네이버 뉴스 검색
# ─────────────────────────────────────────────
if app_mode == "🏠 워크스페이스":
    metrics = build_workspace_metrics(st.session_state)
    render_workspace(metrics)

# ─────────────────────────────────────────────
# 화면 1: 네이버 뉴스 검색
# ─────────────────────────────────────────────
elif app_mode == "🔍 네이버 뉴스 검색":
    st.markdown("""
    <div class="header-wrap">
        <span class="header-logo">📰 네이버 뉴스 스크래퍼</span>
        <span class="header-sub">키워드 기반 최신순 검색</span>
    </div>
    """, unsafe_allow_html=True)

    col_inp, col_btn, col_opt, col_debug = st.columns([4, 1, 1, 1])
    with col_inp:
        keyword = st.text_input("키워드", value=st.session_state.keyword_naver, placeholder="검색할 키워드 (예: 인공지능, 기후변화...)", label_visibility="collapsed")
    with col_btn:
        search_clicked = st.button("검색", use_container_width=True, key="btn_naver")
    with col_opt:
        max_results = st.selectbox("수집 건수", [5, 10, 15, 20, 30], index=1, label_visibility="visible", key="max_naver")
    with col_debug:
        debug_mode = st.checkbox("🔧 디버그", value=False, key="dbg_naver")

    if search_clicked and keyword.strip():
        st.session_state.keyword_naver = keyword.strip()
        st.session_state.articles_naver = []

        import io as _io, contextlib
        status_box = st.empty()
        prog_bar   = st.progress(0)
        status_box.markdown(f"🔍 **'{html.escape(keyword)}'** 검색 중...")

        try:
            log_buf = _io.StringIO()
            with contextlib.redirect_stdout(log_buf):
                arts_list = search_naver_news(keyword.strip(), max_results=max_results, debug=debug_mode)
            st.session_state.debug_log = log_buf.getvalue()

            if not arts_list:
                status_box.empty(); prog_bar.empty()
                st.warning("⚠️ 검색 결과 0건")
            else:
                total = len(arts_list)

                def on_progress(done, total_, art):
                    prog_bar.progress(int(done / total_ * 100))
                    title_preview = html.escape((art.get("title", "") if art else "")[:40])
                    status_box.markdown(f"📄 기사 수집 중 **{done}/{total_}** — {title_preview}...")

                enrich_articles_parallel(arts_list, progress_cb=on_progress)

                st.session_state.articles_naver = arts_list
                saved = NEWS_REPOSITORY.save_articles_batch("naver", arts_list, keyword=keyword.strip())
                status_box.empty(); prog_bar.empty()
                st.success(f"✅ 네이버 뉴스 **{total}건** 수집 완료!")
                if saved:
                    st.caption(f"💾 로컬 저장 완료: {saved['processed']}")
        except Exception as e:
            status_box.empty(); prog_bar.empty()
            st.error(f"❌ 오류 발생: {e}")
    if st.session_state.articles_naver:
        render_results(st.session_state.articles_naver, st.session_state.keyword_naver, "naver", mode="naver")
        if debug_mode: _show_debug()
    else:
        st.markdown("""<div style="margin-top:4rem;text-align:center;color:var(--text-3);">
            <div style="font-size:3rem;margin-bottom:1rem;">🔎</div>
            <div>키워드를 입력하고 검색 버튼을 눌러주세요.</div>
        </div>""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 화면 2: 최신 기술 동향 (사이트 선택형 탭 분리)
# ─────────────────────────────────────────────
elif app_mode == "🚀 최신 기술 동향 (AI/자동화)":
    st.markdown("""
    <div class="header-wrap">
        <span class="header-logo">🚀 최신 기술 동향 스크래퍼</span>
        <span class="header-sub">특정 사이트 메인 기사 집중 수집</span>
    </div>
    """, unsafe_allow_html=True)

    # ✅ 스크래핑할 사이트 목록을 체크박스로 선택할 수 있도록 UI 추가
    selected_site_names = st.multiselect(
        "📰 수집할 사이트 선택",
        options=list(TARGET_SITES.keys()),
        default=list(TARGET_SITES.keys()),
        help="향후 코드 상단 TARGET_SITES 변수에 URL만 추가하면 이 목록에 자동으로 나타납니다."
    )

    col1, col2, col3 = st.columns([1, 3, 1])
    with col1:
        tech_max_results = st.selectbox("수집 건수 (각 사이트당)", [5, 10, 15, 20], index=1, key="max_tech")
    with col3:
        tech_debug = st.checkbox("🔧 디버그", value=False, key="dbg_tech")

    st.markdown("버튼을 누르면 위에서 선택된 사이트들의 홈페이지 메인에 노출된 최신 기사들을 자동으로 수집하고 탭으로 분류합니다.")
    fetch_tech_clicked = st.button("🔄 최신 기사 일괄 수집하기", use_container_width=True)

    if fetch_tech_clicked:
        if not selected_site_names:
            st.error("수집할 사이트를 최소 1개 이상 선택해주세요.")
        else:
            st.session_state.articles_tech = []
            collected = []

            status_box = st.empty()
            prog_bar   = st.progress(0)

            active_targets = [(name, TARGET_SITES[name]) for name in selected_site_names]
            num_sites = len(active_targets)
            weight_per_site = 100 / num_sites

            import io as _io, contextlib
            log_buf = _io.StringIO()

            try:
                for site_idx, (site_name, site_url) in enumerate(active_targets):
                    status_box.markdown(f"🌐 **{html.escape(site_name)}** 메인 페이지 접속 중...")

                    with contextlib.redirect_stdout(log_buf):
                        raw_arts = fetch_latest_tech_news(site_name, site_url, max_results=tech_max_results, debug=tech_debug)
                    total = len(raw_arts)

                    if total == 0:
                        # 빈 사이트라도 진행률은 전진
                        prog_bar.progress(int((site_idx + 1) * weight_per_site))
                        status_box.markdown(f"⚠️ **{html.escape(site_name)}** 기사 없음 — 다음 사이트로 진행")
                        continue

                    def on_progress(done, total_, art, _site_idx=site_idx, _site_name=site_name):
                        progress = int((_site_idx * weight_per_site) + ((done / total_) * weight_per_site))
                        prog_bar.progress(min(progress, 100))
                        title_preview = html.escape((art.get("title", "") if art else "")[:30])
                        status_box.markdown(f"📄 **{html.escape(_site_name)}** 기사 수집 중 **{done}/{total_}** — {title_preview}...")

                    enrich_articles_parallel(raw_arts, progress_cb=on_progress)
                    collected.extend(raw_arts)

                st.session_state.articles_tech = collected
                saved = NEWS_REPOSITORY.save_articles_batch("tech", collected, keyword="selected_portals")
                st.session_state.debug_log = log_buf.getvalue()
                status_box.empty(); prog_bar.empty()
                if collected:
                    st.success(f"✅ 선택된 사이트 기사 총 **{len(collected)}건** 수집 완료!")
                    if saved:
                        st.caption(f"💾 로컬 저장 완료: {saved['processed']}")
                else:
                    st.warning("⚠️ 수집된 기사가 0건입니다. 디버그 체크박스를 켜고 다시 시도해 원인을 확인해보세요.")

                st.session_state.articles_tech = collected
                saved = NEWS_REPOSITORY.save_articles_batch("tech", collected, keyword="selected_portals")
                st.session_state.debug_log = log_buf.getvalue()
                status_box.empty(); prog_bar.empty()
                if collected:
                    st.success(f"✅ 선택된 사이트 기사 총 **{len(collected)}건** 수집 완료!")
                    if saved:
                        st.caption(f"💾 로컬 저장 완료: {saved['processed']}")
                else:
                    st.warning("⚠️ 수집된 기사가 0건입니다. 디버그 체크박스를 켜고 다시 시도해 원인을 확인해보세요.")

            except Exception as e:
                st.session_state.debug_log = log_buf.getvalue()
                status_box.empty(); prog_bar.empty()
                st.error(f"❌ 수집 중 오류 발생: {e}")

    # 결과 출력 (mode="tech"를 넘겨주면 탭이 자동으로 나뉨)
    if st.session_state.articles_tech:
        render_results(st.session_state.articles_tech, "선택 사이트 최신 기사", "tech", mode="tech")
        if tech_debug: _show_debug()
    elif tech_debug and st.session_state.debug_log:
        _show_debug()
    else:
        st.markdown("""<div style="margin-top:4rem;text-align:center;color:var(--text-3);">
            <div style="font-size:3rem;margin-bottom:1rem;">🤖</div>
            <div>원하는 사이트를 선택하고 [최신 기사 일괄 수집하기] 버튼을 눌러 트렌드를 파악해보세요.</div>
        </div>""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 화면 3: 인사이트 보드 (스켈레톤)
# ─────────────────────────────────────────────
elif app_mode == "📊 인사이트 보드":
    st.markdown("""
    <div class="header-wrap">
        <span class="header-logo">📊 인사이트 보드</span>
        <span class="header-sub">수집 기사 집계 · 트렌드 · 언론사 랭킹</span>
    </div>
    """, unsafe_allow_html=True)

    pool = list(st.session_state.articles_naver) + list(st.session_state.articles_tech)
    if not pool:
        st.info("먼저 [네이버 뉴스 검색] 또는 [최신 기술 동향] 탭에서 기사를 수집하세요.")
    else:
        st.caption(f"분석 대상: 총 **{len(pool)}건**")
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("언론사별 기사 수")
            st.bar_chart(insights.by_press(pool), x="press", y="count", use_container_width=True)
        with c2:
            st.subheader("키워드 빈도 Top 20")
            st.bar_chart(insights.by_keyword(pool, top_n=20), x="keyword", y="count", use_container_width=True)
        st.subheader("일자별 기사 수")
        st.bar_chart(insights.trend_by_date(pool), x="date", y="count", use_container_width=True)

# ─────────────────────────────────────────────
# 화면 4: 조선소 작업 데이터 (Phase 1)
# ─────────────────────────────────────────────
elif app_mode == "🏭 조선소 작업 데이터":
    st.markdown("""
    <div class="header-wrap">
        <span class="header-logo">🏭 조선소 작업 데이터</span>
        <span class="header-sub">엑셀 업로드 · 검증 · Parquet 저장</span>
    </div>
    """, unsafe_allow_html=True)

    st.caption("필수 컬럼: " + ", ".join(REQUIRED_COLUMNS))
    st.caption("샘플 컬럼 예시: team, process, task_name (예: 생산팀/조립/취부)")

    c_sample1, c_sample2 = st.columns([1, 2])
    with c_sample1:
        fake_rows = st.slider("페이크 데이터 행 수", min_value=10, max_value=100, value=30, step=10)
    with c_sample2:
        if st.button("🧪 페이크 조선소 데이터 생성", use_container_width=True):
            fake_result = create_fake_shipyard_tasks(row_count=fake_rows)
            if fake_result.is_valid:
                st.success(f"✅ 페이크 데이터 생성 완료: {fake_result.row_count}행")
                st.caption(f"parquet 저장: {fake_result.parquet_path}")
            else:
                st.error("❌ 페이크 데이터 생성 실패")
                for err in fake_result.errors:
                    st.warning(f"- {err}")

    st.markdown("---")
    uploaded = st.file_uploader(
        "작업 데이터 엑셀(.xlsx)을 업로드하세요.",
        type=["xlsx"],
        accept_multiple_files=False,
    )

    if uploaded is not None:
        if st.button("업로드 처리 시작", use_container_width=True):
            result = ingest_shipyard_excel(uploaded.name, uploaded)
            if result.is_valid:
                st.success(f"✅ 업로드 성공: {result.row_count}행")
                st.caption(f"raw 저장: {result.raw_path}")
                st.caption(f"parquet 저장: {result.parquet_path}")
            else:
                st.error("❌ 검증 실패")
                for err in result.errors:
                    st.warning(f"- {err}")
                if result.raw_path:
                    st.caption(f"raw 저장: {result.raw_path}")

# ─────────────────────────────────────────────
# 화면 5: 자동화 과제 제안 (Phase 1)
# ─────────────────────────────────────────────
elif app_mode == "🤝 자동화 과제 제안":
    st.markdown("""
    <div class="header-wrap">
        <span class="header-logo">🤝 자동화 과제 제안</span>
        <span class="header-sub">작업 데이터 × 뉴스 매칭 기반 제안</span>
    </div>
    """, unsafe_allow_html=True)

    tasks_df = load_latest_shipyard_tasks()
    filtered_tasks_df = render_task_filters(tasks_df) if not tasks_df.empty else tasks_df
    news_pool = list(st.session_state.articles_naver) + list(st.session_state.articles_tech)

    c1, c2 = st.columns(2)
    with c1:
        st.metric("작업 데이터", f"{len(filtered_tasks_df)}건")
    with c2:
        st.metric("뉴스 풀", f"{len(news_pool)}건")

    if filtered_tasks_df.empty:
        st.info("먼저 [🏭 조선소 작업 데이터]에서 엑셀 업로드를 완료하세요.")
    elif not news_pool:
        st.info("먼저 [🔍 네이버 뉴스 검색] 또는 [🚀 최신 기술 동향]에서 뉴스를 수집하세요.")
    else:
        top_k = st.slider("작업별 추천 기사 수", min_value=1, max_value=5, value=3)
        if st.button("제안 생성", use_container_width=True):
            proposals = suggest_for_tasks(filtered_tasks_df, news_pool, top_k=top_k)
            st.session_state.proposal_results = proposals
            st.session_state.proposal_artifacts = save_proposals_artifacts(proposals)

        proposals = st.session_state.proposal_results
        if proposals:
            rows = [
                {
                    "task_id": p["task_id"],
                    "task_name": p["task_name"],
                    "process": p["process"],
                    "추천기사수": p["recommendation_count"],
                }
                for p in proposals
            ]
            st.subheader("제안 요약")
            st.dataframe(pd.DataFrame(rows), use_container_width=True, height=320)

            markdown_text = proposals_to_markdown(proposals)
            json_text = json.dumps(proposals, ensure_ascii=False, indent=2)
            c1, c2 = st.columns(2)
            with c1:
                st.download_button(
                    "⬇ 제안서 Markdown 다운로드",
                    data=markdown_text.encode("utf-8"),
                    file_name="automation_proposals.md",
                    mime="text/markdown",
                )
            with c2:
                st.download_button(
                    "⬇ 제안서 JSON 다운로드",
                    data=json_text.encode("utf-8"),
                    file_name="automation_proposals.json",
                    mime="application/json",
                )
            if st.session_state.proposal_artifacts:
                st.caption(f"artifact(json): {st.session_state.proposal_artifacts.get('json', '')}")
                st.caption(f"artifact(md): {st.session_state.proposal_artifacts.get('markdown', '')}")

            st.subheader("작업별 상세 추천")
            for p in proposals:
                with st.expander(f"{p['task_id']} · {p['task_name']} ({p['process']})", expanded=False):
                    if not p["recommendations"]:
                        st.caption("추천 가능한 기사가 없습니다.")
                        continue
                    for idx, rec in enumerate(p["recommendations"], start=1):
                        st.markdown(
                            f"{idx}. **{html.escape(rec['title'])}** "
                            f"(score={rec['score']}, overlap={', '.join(rec['overlap_terms'])})"
                        )
                        if rec.get("link", "").startswith(("http://", "https://")):
                            st.markdown(f"- 원문: {rec['link']}")
                        if rec.get("summary"):
                            st.caption(rec["summary"])

# ─────────────────────────────────────────────
# 화면 6: 데이터 품질
# ─────────────────────────────────────────────
elif app_mode == "🧪 데이터 품질":
    quality_pool = (st.session_state.articles_naver or []) + (st.session_state.articles_tech or [])
    render_data_quality(quality_pool)

# ─────────────────────────────────────────────
# 화면 7: 카드뉴스 (스켈레톤)
# ─────────────────────────────────────────────
elif app_mode == "🎨 카드뉴스":
    st.markdown("""
    <div class="header-wrap">
        <span class="header-logo">🎨 카드뉴스</span>
        <span class="header-sub">기사를 카드형 HTML/이미지로 렌더</span>
    </div>
    """, unsafe_allow_html=True)

    pool = list(st.session_state.articles_naver) + list(st.session_state.articles_tech)
    if not pool:
        st.info("먼저 [네이버 뉴스 검색] 또는 [최신 기술 동향] 탭에서 기사를 수집하세요.")
    else:
        titles = [f"{i+1}. {html.escape(a.get('title',''))}" for i, a in enumerate(pool)]
        idx = st.selectbox("카드로 렌더할 기사 선택", range(len(pool)), format_func=lambda i: titles[i])
        template = st.selectbox("템플릿", cardnews.available_templates())
        st.markdown(cardnews.render_html(pool[idx], template=template), unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🖼 선택 기사 PNG 생성", use_container_width=True):
                try:
                    png_bytes = cardnews.render_png(pool[idx], template=template)
                    st.session_state.cn_last_png = png_bytes
                    st.success("PNG 생성 완료")
                except Exception as e:
                    st.error(f"PNG 생성 실패: {e}")

            if st.session_state.get("cn_last_png"):
                st.download_button(
                    "⬇ 선택 기사 PNG 다운로드",
                    data=st.session_state.cn_last_png,
                    file_name=f"cardnews_{idx+1}.png",
                    mime="image/png",
                    use_container_width=True,
                )

        with c2:
            deck_size = st.slider("덱 생성 기사 수", min_value=1, max_value=min(10, len(pool)), value=min(3, len(pool)))
            if st.button("📦 PNG 덱 ZIP 생성", use_container_width=True):
                try:
                    deck_pngs = cardnews.render_deck(pool[:deck_size], template=template)
                    zip_buf = io.BytesIO()
                    import zipfile as _zipfile
                    with _zipfile.ZipFile(zip_buf, mode="w", compression=_zipfile.ZIP_DEFLATED) as zf:
                        for i, png in enumerate(deck_pngs, start=1):
                            zf.writestr(f"cardnews_{i}.png", png)
                    st.session_state.cn_deck_zip = zip_buf.getvalue()
                    st.success(f"ZIP 생성 완료 ({deck_size}장)")
                except Exception as e:
                    st.error(f"ZIP 생성 실패: {e}")

            if st.session_state.get("cn_deck_zip"):
                st.download_button(
                    "⬇ PNG 덱 ZIP 다운로드",
                    data=st.session_state.cn_deck_zip,
                    file_name="cardnews_deck.zip",
                    mime="application/zip",
                    use_container_width=True,
                )
