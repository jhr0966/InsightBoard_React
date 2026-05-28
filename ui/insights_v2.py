"""인사이트 분석 — v2 디자인 적용.

헤더 4 stats (분석 뉴스 / 신규 트렌드 / 매칭 공정 / PoC 후보) + app-side
카운트를 실데이터로 (store/news_db, store/trends, store/match, sola/opportunity,
store/bookmarks). 트렌드 차트·매트릭스·키워드 리스트 시각은 시안 데이터 유지.
"""
from __future__ import annotations

import html as _html

import streamlit as st

from config import ASSETS_DIR
from persona.schema import Persona
from roadmap.query import load_latest as _load_roadmap
from store import bookmarks as bookmarks_store
from store import news_db as _news_db
from store import trends as _trends
from store.match import score_matches as _score_matches
from sola.opportunity import score_cells as _score_cells
from ui import app_shell
from ui.styles import inject_screen_css


# 트렌드 키워드 색상 팔레트 — rank 별
_TKW_COLORS = ["#2563EB", "#14B8A6", "#F59E0B", "#6366F1", "#0EA5E9", "#94A3B8"]


def _tkw_list_html() -> str:
    """ia-tkw-item 6개 동적 빌드. top_keywords + emergence 결합."""
    try:
        news_30 = _news_db.load_news_for_days(days=30)
    except Exception:
        news_30 = None
    if news_30 is None or news_30.empty:
        return _tkw_empty_html()

    try:
        top_df = _trends.top_keywords(news_30, top_n=6)
    except Exception:
        return _tkw_empty_html()
    if top_df.empty:
        return _tkw_empty_html()

    # emergence — last 7 days vs prior 14 days
    new_set: set[str] = set()
    deltas: dict[str, int] = {}
    try:
        today_df = _news_db.load_news_for_days(days=7)
        # base: 7-14일 전 (간이: 30일 - 7일 ≈ base)
        base_df = news_30
        em = _trends.keyword_emergence(today_df, base_df, top_n=20)
        for _, r in em["new"].iterrows():
            new_set.add(str(r["keyword"]))
        for _, r in em["rising"].iterrows():
            today = int(r.get("today", 0))
            base = int(r.get("base", 0))
            if base > 0:
                deltas[str(r["keyword"])] = round((today - base) / base * 100)
            else:
                deltas[str(r["keyword"])] = 100
    except Exception:
        pass

    max_count = max(int(top_df["count"].max()), 1)
    parts = []
    for i, (_, row) in enumerate(top_df.iterrows()):
        kw = str(row["keyword"])
        count = int(row["count"])
        rank = f"{i+1:02d}"
        bar_pct = max(round(count / max_count * 100), 8)
        color = _TKW_COLORS[i % len(_TKW_COLORS)]
        delta = deltas.get(kw, 0)
        delta_label = f"+{delta}%" if delta > 0 else (f"−{abs(delta)}%" if delta < 0 else "0%")
        delta_cls = "ia-tkw-up" if delta > 0 else ("ia-tkw-down" if delta < 0 else "ia-tkw-flat")
        new_badge = ' <span class="ia-tkw-new">NEW</span>' if kw in new_set else ""
        active_cls = " ia-tkw-on" if i == 0 else ""
        parts.append(
            f'<button class="ia-tkw-item{active_cls}" disabled>'
            f'<span class="ia-tkw-rank">{rank}</span>'
            f'<span class="ia-tkw-body">'
            f'<span class="ia-tkw-name">{_html.escape(kw)}{new_badge}</span>'
            f'<span class="ia-tkw-meta">{count}건</span>'
            f'</span>'
            f'<span class="ia-tkw-bar"><span style="width:{bar_pct}%; background:{color};"></span></span>'
            f'<span class="ia-tkw-delta {delta_cls}">{delta_label}</span>'
            f'</button>'
        )
    return "\n".join(parts)


def _tkw_empty_html() -> str:
    return ('<div style="padding: 18px; text-align: center; color: var(--text-muted); '
            'font-size: 14px; border: 1px dashed var(--surface-divider); border-radius: 10px;">'
            '아직 분석할 키워드가 없어요.<br>'
            '<span style="font-size:12.5px;">데이터 관리에서 30일분 수집 후 다시 확인하세요.</span>'
            '</div>')


_IA_TEMPLATE = ASSETS_DIR / "v2" / "screens" / "insights_main.html"


# ── 트렌드 차트 (5주, 5 series) ────────────────────────────
_IA_CHART_COLORS = ["#2563EB", "#14B8A6", "#F59E0B"]  # top 3 highlighted
_IA_CHART_MUTE = "#CBD5E1"


@st.cache_data(ttl=60)
def _ia_chart_parts() -> dict[str, str]:
    """인사이트 트렌드 차트 — 5주 × top-5 키워드 (3 강조 + 2 mute).

    Returns: dict with svg, legend, pill.
    Empty: returns dict with 'empty' = HTML 카드 (svg/legend/pill 은 빈문자).
    """
    from ui.board_v2 import _weekly_keyword_series, _delta_pct

    labels, series = _weekly_keyword_series(weeks=5)
    if not series:
        empty_svg = ('<div style="padding:60px 18px; text-align:center; color:var(--text-muted);'
                     ' font-size:14px; border:1px dashed var(--surface-divider); border-radius:12px;'
                     ' min-height:200px; display:flex; flex-direction:column; justify-content:center;">'
                     '아직 트렌드를 그릴 데이터가 부족해요.<br>'
                     '<span style="font-size:12.5px;">30일 이상 수집 후 5주 출현 빈도가 누적되면 표시됩니다.</span>'
                     '</div>')
        return {"svg": empty_svg, "legend": "", "pill": ""}

    series = series[:5]
    y_max = max((max(s["counts"]) for s in series), default=1) or 1
    nice_max = max(int((y_max * 1.25) // 5 + 1) * 5, 5)

    # SVG viewBox 540×230, plot x:40-525 y:20-200
    x_left, x_right = 40, 525
    y_top, y_bottom = 20, 200
    n = len(labels)
    x_step = (x_right - x_left) / max(n - 1, 1) if n > 1 else 0

    def coord(i: int, v: int) -> tuple[float, float]:
        x = x_left + i * x_step
        y = y_bottom - (v / nice_max) * (y_bottom - y_top)
        return x, y

    # Grid + Y/X axis
    parts = [
        "<svg xmlns='http://www.w3.org/2000/svg' class='ia-chart-svg' viewBox='0 0 540 230'>",
        "<g stroke='#E5E7EB' stroke-width='0.6'>",
    ]
    for ratio in (0, 0.25, 0.5, 0.75, 1):
        y = y_bottom - ratio * (y_bottom - y_top)
        parts.append(f"<line x1='40' y1='{y:.0f}' x2='540' y2='{y:.0f}'/>")
    parts.append("</g>")

    # Y labels
    parts.append("<g font-family='JetBrains Mono, monospace' font-size='8.5' fill='#94A3B8' font-weight='700'>")
    for ratio in (0, 0.25, 0.5, 0.75, 1):
        y = y_bottom - ratio * (y_bottom - y_top)
        val = round(nice_max * ratio)
        parts.append(f"<text x='35' y='{y + 3:.0f}' text-anchor='end'>{val}</text>")
    parts.append("</g>")

    # X labels — labels list comes from board's helper (W**~금주). 인사이트는 'W-4..이번주' 라벨로 다르게.
    parts.append("<g font-family='JetBrains Mono, monospace' font-size='8.5' fill='#94A3B8' font-weight='700'>")
    for i in range(n):
        x = x_left + i * x_step
        label = "이번 주" if i == n - 1 else f"W−{n - 1 - i}"
        anchor = "end" if i == n - 1 else "middle"
        parts.append(f"<text x='{x:.0f}' y='215' text-anchor='{anchor}'>{label}</text>")
    parts.append("</g>")

    # Vertical highlight last column
    if n >= 2:
        hl_x = x_left + (n - 2) * x_step + 10
        parts.append(f"<rect x='{hl_x:.0f}' y='20' width='{x_right - hl_x:.0f}' height='180' fill='rgba(37,99,235,0.04)'/>")

    # 2 mute series (시리즈 4, 5)
    for s in series[3:]:
        pts = " L ".join(f"{x:.0f} {y:.0f}" for x, y in (coord(i, c) for i, c in enumerate(s["counts"])))
        parts.append(f"<path d='M {pts}' stroke='{_IA_CHART_MUTE}' stroke-width='1.6' fill='none' opacity='0.7'/>")

    # 3 highlighted series (역순 — 첫 시리즈가 가장 위)
    for idx, s in enumerate(series[:3]):
        color = _IA_CHART_COLORS[idx]
        coords = [coord(i, c) for i, c in enumerate(s["counts"])]
        path_d = "M " + " L ".join(f"{x:.0f} {y:.0f}" for x, y in coords)
        if idx == 0:
            # 첫 시리즈 — gradient fill + thicker stroke
            parts.append("<defs><linearGradient id='ia-vis-fill' x1='0' y1='0' x2='0' y2='1'>"
                         "<stop offset='0%' stop-color='#2563EB' stop-opacity='0.18'/>"
                         "<stop offset='100%' stop-color='#2563EB' stop-opacity='0'/></linearGradient></defs>")
            area_d = path_d + f" L {coords[-1][0]:.0f} {y_bottom} L {coords[0][0]:.0f} {y_bottom} Z"
            parts.append(f"<path d='{area_d}' fill='url(#ia-vis-fill)'/>")
            parts.append(f"<path d='{path_d}' stroke='{color}' stroke-width='2.6' fill='none'/>")
            parts.append(f"<g fill='{color}' stroke='#fff' stroke-width='1.4'>")
            for j, (x, y) in enumerate(coords):
                r = 4.6 if j == len(coords) - 1 else 3.2
                parts.append(f"<circle cx='{x:.0f}' cy='{y:.0f}' r='{r}'/>")
            parts.append("</g>")
        else:
            parts.append(f"<path d='{path_d}' stroke='{color}' stroke-width='2' fill='none'/>")
            parts.append(f"<g fill='{color}'>")
            for x, y in coords:
                parts.append(f"<circle cx='{x:.0f}' cy='{y:.0f}' r='2.5'/>")
            parts.append("</g>")

    # Callout — top series 마지막 점
    top_name = series[0]["name"]
    top_delta = _delta_pct(series[0]["counts"])
    top_last = series[0]["counts"][-1]
    cx, cy = coord(n - 1, top_last)
    label_safe = _html.escape(top_name[:8])
    delta_str = f"{top_last}건 · {'+' if top_delta >= 0 else ''}{top_delta}%"
    parts.append(f"<g><rect x='{cx - 39:.0f}' y='{max(cy - 32, 0):.0f}' width='78' height='28' rx='6' fill='#0F172A'/>"
                 f"<text x='{cx:.0f}' y='{max(cy - 32, 0) + 16:.0f}' text-anchor='middle' font-family='Pretendard' font-size='10.5' font-weight='700' fill='#fff'>{label_safe}</text>"
                 f"<text x='{cx:.0f}' y='{max(cy - 32, 0) + 26:.0f}' text-anchor='middle' font-family='JetBrains Mono, monospace' font-size='9' fill='#94A3B8'>{delta_str}</text></g>")

    parts.append("</svg>")
    svg = "".join(parts)

    # Legend
    legend_parts = []
    for i, s in enumerate(series[:3]):
        legend_parts.append(
            f'<span class="ia-lg"><span class="ia-lg-d" style="background:{_IA_CHART_COLORS[i]};"></span>{_html.escape(s["name"])}</span>'
        )
    for s in series[3:]:
        legend_parts.append(
            f'<span class="ia-lg ia-lg-mute"><span class="ia-lg-d" style="background:{_IA_CHART_MUTE};"></span>{_html.escape(s["name"])}</span>'
        )
    legend = "".join(legend_parts)

    # Pill — top series delta
    pill_cls = "ia-trend-up" if top_delta >= 0 else "ia-trend-down"
    arrow = "▲" if top_delta >= 0 else "▼"
    pill = (f'<span class="ia-trend-pill {pill_cls}">'
            f'{arrow} {_html.escape(top_name)} {"+" if top_delta >= 0 else ""}{top_delta}% (지난 5주 비교)'
            f'</span>')

    return {"svg": svg, "legend": legend, "pill": pill}


# ── 매트릭스 (효과×난이도) ────────────────────────────────
_IA_MATRIX_COLORS_BY_DEPT: dict[str, str] = {
    "도장": "#2563EB", "용접": "#14B8A6", "의장": "#F59E0B",
    "조립": "#6366F1", "절단": "#0EA5E9",
}


@st.cache_data(ttl=60)
def _ia_matrix_svg() -> str:
    """인사이트 매트릭스 — 600×420 viewBox, 좌상단 = PoC 후보.

    좌표 매핑:
      - x (left) = 40 + (1 - ease_norm) * 520 → ease 높을수록 좌측 = 쉬움
      - y (top)  = 20 + (1 - effect_norm) * 360 → effect 높을수록 상단
      - 버블 r = 14 + score_norm * 22
      - 첫 cell = ★ selected (halo)
    """
    try:
        news = _news_db.load_news_for_days(days=30)
        roadmap = _load_roadmap()
    except Exception:
        news = None
        roadmap = None
    if news is None or news.empty or roadmap is None or roadmap.empty:
        return _ia_matrix_empty()

    try:
        cells = _score_cells(news, roadmap).head(8)
    except Exception:
        return _ia_matrix_empty()
    if cells.empty:
        return _ia_matrix_empty()

    max_news = max(int(cells["matched_news"].max()), 1)
    max_tasks = max(int(cells["matched_tasks"].max()), 1)
    max_score = max(float(cells["cell_score"].max()), 1.0)

    parts = ["<svg xmlns='http://www.w3.org/2000/svg' class='ia-mtx-svg' viewBox='0 0 600 420' preserveAspectRatio='xMidYMid meet'>"]

    # quadrant bg
    parts.extend([
        "<rect x='40' y='20' width='280' height='190' fill='rgba(21,128,61,0.06)'/>",
        "<rect x='320' y='20' width='240' height='190' fill='rgba(180,83,9,0.04)'/>",
        "<rect x='40' y='210' width='280' height='170' fill='rgba(15,23,42,0.02)'/>",
        "<rect x='320' y='210' width='240' height='170' fill='rgba(15,23,42,0.02)'/>",
    ])
    # PoC label
    parts.extend([
        "<g><rect x='50' y='32' width='118' height='22' rx='5' fill='#15803D'/>"
        "<text x='109' y='47' text-anchor='middle' font-family='Pretendard' font-size='10.5' "
        "font-weight='800' fill='#fff' letter-spacing='0.04em'>★ PoC 후보 영역</text></g>",
        "<text x='172' y='46' font-family='Pretendard' font-size='10.5' fill='#15803D' "
        "font-weight='700'>쉽고 효과 큰 — 먼저 시도</text>",
        "<text x='330' y='46' font-family='Pretendard' font-size='10.5' fill='#B45309' "
        "font-weight='700'>전략 과제 — 효과는 크나 난이도 ↑</text>",
        "<text x='48' y='372' font-family='Pretendard' font-size='10.5' fill='#94A3B8' "
        "font-weight='600'>소규모 개선 — 낮은 효과</text>",
        "<text x='330' y='372' font-family='Pretendard' font-size='10.5' fill='#94A3B8' "
        "font-weight='600'>유보 — 검토 보류</text>",
    ])
    # axes
    parts.extend([
        "<line x1='40' y1='380' x2='560' y2='380' stroke='#0F172A' stroke-width='1.4'/>",
        "<line x1='40' y1='20' x2='40' y2='380' stroke='#0F172A' stroke-width='1.4'/>",
        "<line x1='320' y1='20' x2='320' y2='380' stroke='#94A3B8' stroke-width='1' stroke-dasharray='3 3'/>",
        "<line x1='40' y1='210' x2='560' y2='210' stroke='#94A3B8' stroke-width='1' stroke-dasharray='3 3'/>",
    ])
    # ticks
    parts.append("<g font-family='JetBrains Mono, monospace' font-size='9' fill='#94A3B8' font-weight='700'>"
                 "<text x='34' y='24' text-anchor='end'>高</text>"
                 "<text x='34' y='213' text-anchor='end'>中</text>"
                 "<text x='34' y='383' text-anchor='end'>低</text></g>")
    parts.append("<g font-family='JetBrains Mono, monospace' font-size='9' fill='#94A3B8' font-weight='700'>"
                 "<text x='40' y='398' text-anchor='middle'>쉬움</text>"
                 "<text x='320' y='398' text-anchor='middle'>中</text>"
                 "<text x='560' y='398' text-anchor='middle'>어려움</text></g>")
    parts.append("<text x='300' y='416' text-anchor='middle' font-family='Pretendard' font-size='11' "
                 "fill='#475569' font-weight='700'>적용 난이도 →  현장 통합 · 안전 인증 · 정확도 임계</text>")

    # bubbles
    selected_idx = 0
    for i, (_, row) in enumerate(cells.iterrows()):
        ease_norm = int(row.get("matched_tasks", 0) or 0) / max_tasks
        eff_norm = int(row.get("matched_news", 0) or 0) / max_news
        score_norm = float(row.get("cell_score", 0) or 0) / max_score

        cx = 40 + (1 - ease_norm) * 520  # ease 높음 = 왼쪽
        cy = 20 + (1 - eff_norm) * 360
        r = 14 + score_norm * 22

        dept = str(row.get("dept", "") or "")
        lv3 = str(row.get("lv3", "") or "")
        color = _IA_MATRIX_COLORS_BY_DEPT.get(dept, "#475569")
        fill = f"rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)},0.16)"
        label = _html.escape(lv3[:14] or dept[:14] or "—")
        meta = f"매칭 {int(row.get('matched_news', 0) or 0)}건"

        if i == selected_idx:
            # halo
            parts.append(f"<circle cx='{cx:.0f}' cy='{cy:.0f}' r='{r + 10:.0f}' "
                         f"fill='none' stroke='{color}' stroke-width='1.4' stroke-dasharray='3 3'/>")
        parts.append(f"<circle cx='{cx:.0f}' cy='{cy:.0f}' r='{r:.0f}' "
                     f"fill='{fill}' stroke='{color}' stroke-width='{2.4 if i == selected_idx else 1.8}'/>")
        parts.append(f"<circle cx='{cx:.0f}' cy='{cy:.0f}' r='5' fill='{color}'/>")
        parts.append(f"<text x='{cx:.0f}' y='{cy + r + 14:.0f}' text-anchor='middle' "
                     f"font-family='Pretendard' font-size='11' font-weight='800' fill='#0F172A'>{label}</text>")
        parts.append(f"<text x='{cx:.0f}' y='{cy + r + 26:.0f}' text-anchor='middle' "
                     f"font-family='JetBrains Mono, monospace' font-size='9' fill='#475569' "
                     f"font-weight='700'>{meta}</text>")

    parts.append("</svg>")
    return "".join(parts)


def _ia_matrix_empty() -> str:
    return ('<div style="padding:80px 18px; text-align:center; color:var(--text-muted);'
            ' font-size:14px; border:1px dashed var(--surface-divider); border-radius:12px;'
            ' min-height:380px; display:flex; flex-direction:column; justify-content:center;">'
            '아직 매트릭스에 그릴 자동화 기회가 없어요.<br>'
            '<span style="font-size:12.5px;">뉴스 + 로드맵 매칭 후 자동으로 채워집니다.</span>'
            '</div>')


# ── 트렌드 → 공정 매핑 카드 (.ia-map) ───────────────────────
_IA_PC_PALETTE = [
    ("#2563EB", "rgba(37,99,235,0.10)"),
    ("#0F766E", "rgba(20,184,166,0.10)"),
    ("#4F46E5", "rgba(99,102,241,0.10)"),
]


@st.cache_data(ttl=60)
def _ia_process_map_html() -> str:
    """SECTION A 우측 — 선택 키워드 → 매칭 Lv3 공정 카드 3개.

    데이터:
      from chip = top trending 키워드 (`_weekly_keyword_series` 1순위)
      cards    = `_score_cells` 상위 3개 (각 dept × lv3)
      fit %    = cell_score / max * 36 + 60 (60~96%)
      현재     = sample_tasks 첫 항목 (없으면 매칭 작업 N건)
      애로     = sample_news 첫 헤드라인 (없으면 매칭 뉴스 N건)
    """
    from ui.board_v2 import _weekly_keyword_series

    try:
        news_30 = _news_db.load_news_for_days(days=30)
        roadmap_df = _load_roadmap()
    except Exception:
        news_30 = None
        roadmap_df = None
    if news_30 is None or news_30.empty or roadmap_df is None or roadmap_df.empty:
        return _ia_pmap_empty()

    # top trending kw
    _labels, series = _weekly_keyword_series(weeks=5)
    top_kw = series[0]["name"] if series else "—"
    top_dot_color = _IA_PC_PALETTE[0][0]

    try:
        cells = _score_cells(news_30, roadmap_df).head(3)
    except Exception:
        return _ia_pmap_empty()
    if cells.empty:
        return _ia_pmap_empty()

    max_score = max(float(cells["cell_score"].max()), 1.0)
    avg_fit = int(round(cells["cell_score"].mean() / max_score * 36 + 60))
    total_news = int(cells["matched_news"].sum())

    cards = []
    for i, (_, row) in enumerate(cells.iterrows()):
        color, bg = _IA_PC_PALETTE[i % len(_IA_PC_PALETTE)]
        dept = _html.escape(str(row.get("dept", "") or "—"))
        lv3 = _html.escape(str(row.get("lv3", "") or "—"))
        score = float(row.get("cell_score", 0) or 0)
        fit_pct = int(round(score / max_score * 36 + 60))

        sample_tasks = str(row.get("sample_tasks", "") or "").split(" · ")
        first_task = _html.escape(sample_tasks[0][:48]) if sample_tasks and sample_tasks[0] else ""
        matched_tasks = int(row.get("matched_tasks", 0) or 0)
        now_text = first_task if first_task else f"매칭 작업 {matched_tasks}건 후보"

        sample_news = str(row.get("sample_news", "") or "").split(" · ")
        first_news = _html.escape(sample_news[0][:80]) if sample_news and sample_news[0] else ""
        matched_news = int(row.get("matched_news", 0) or 0)
        pain_text = first_news if first_news else f"매칭 뉴스 {matched_news}건 · 현재 도메인 신호 누적 중"

        rank_tag = "★ 최적 매칭" if i == 0 else ""
        tag_cls = "ia-pc-tag-1" if i < 2 else "ia-pc-tag-2"
        tag_label = "PoC 후보" if i < 2 else "관찰 대상"

        cards.append(f"""<li class="ia-pcard{' ia-pcard-top' if i == 0 else ''}">
          <div class="ia-pc-head">
            <span class="ia-pc-icon" style="background:{bg}; color:{color};">◆</span>
            <div>
              <div class="ia-pc-name">{dept} · {lv3}{' <span class="ia-pc-rank">' + rank_tag + '</span>' if rank_tag else ''}</div>
              <div class="ia-pc-path">{dept} › {lv3} (Lv3)</div>
            </div>
            <span class="ia-pc-fit"><b>{fit_pct}%</b><small>적합도</small></span>
          </div>
          <div class="ia-pc-body">
            <div class="ia-pc-now">
              <span class="ia-pc-k">현재</span>
              <span class="ia-pc-v">{now_text}</span>
            </div>
            <div class="ia-pc-pain">
              <span class="ia-pc-k">신호</span>
              <span class="ia-pc-v">{pain_text}</span>
            </div>
          </div>
          <div class="ia-pc-foot">
            <span class="ia-pc-tag {tag_cls}">{tag_label}</span>
            <span class="ia-pc-tag">매칭 뉴스 {matched_news}건</span>
            <button class="ia-pc-detail" disabled>상세 →</button>
          </div>
        </li>""")

    return f"""<div class="ia-map">
      <div class="ia-map-head">
        <div class="ia-map-from">
          <span class="ia-map-eye">선택된 키워드</span>
          <span class="ia-map-from-chip">
            <span class="ia-map-from-dot" style="background:{top_dot_color};"></span>
            {_html.escape(top_kw)}
          </span>
        </div>
        <div class="ia-map-arrow">→</div>
        <div class="ia-map-to">
          <span class="ia-map-eye">조선소 적용 공정 (Lv3)</span>
          <span class="ia-map-to-meta">{len(cards)}건 매칭 · 평균 적합도 <b>{avg_fit}%</b> · 매칭 뉴스 {total_news}건</span>
        </div>
      </div>
      <ul class="ia-pcards">
        {"".join(cards)}
      </ul>
    </div>"""


def _ia_pmap_empty() -> str:
    return ('<div style="padding:32px 18px; text-align:center; color:var(--text-muted);'
            ' font-size:14px; border:1px dashed var(--surface-divider); border-radius:12px;">'
            '아직 키워드 → 공정 매핑 결과가 없어요.<br>'
            '<span style="font-size:12.5px;">뉴스 30일분 + 로드맵 업로드 후 자동으로 채워집니다.</span>'
            '</div>')


def _load_persona() -> Persona:
    p = st.session_state.get("persona")
    if isinstance(p, Persona):
        return p
    from persona import store as persona_store

    p = persona_store.load()
    st.session_state["persona"] = p
    return p


@st.cache_data(ttl=60)
def _ia_stats() -> dict[str, str]:
    """인사이트 분석 헤더 4 stats.

    Returns:
      news_30d: 최근 30일 뉴스 수
      new_trends: 이번 주 신규 emerge 키워드 수 (지난주 대비 +)
      matched_processes: 뉴스가 매칭된 Lv3 공정 unique 수
      poc_candidates: 자동화 기회 + 채택 대기 합 (검토 대기 후보)
    """
    try:
        news_30d = _news_db.load_news_for_days(days=30)
    except Exception:
        news_30d = None
    try:
        news_7d = _news_db.load_news_for_days(days=7)
    except Exception:
        news_7d = None
    try:
        roadmap_df = _load_roadmap()
    except Exception:
        roadmap_df = None

    n_30d = int(len(news_30d)) if news_30d is not None else 0

    # 신규 트렌드: keyword_emergence 함수가 있으면 사용
    new_trends = 0
    try:
        if news_30d is not None and not news_30d.empty:
            emergence_df = _trends.keyword_emergence(news_30d, weeks=4)
            if hasattr(emergence_df, "empty") and not emergence_df.empty:
                # 신규 emerge 만: prev=0 인 항목
                if "prev_count" in emergence_df.columns:
                    new_trends = int((emergence_df["prev_count"] == 0).sum())
                else:
                    new_trends = int(len(emergence_df))
    except Exception:
        pass

    # 매칭 공정 (Lv3 unique): 매치된 뉴스의 lv3 컬럼 카운트
    matched_processes = 0
    if (
        news_7d is not None and not news_7d.empty
        and roadmap_df is not None and not roadmap_df.empty
    ):
        try:
            matches = _score_matches(news_7d, roadmap_df, top_k=3)
            if not matches.empty and "lv3" in matches.columns:
                matched_processes = int(matches[matches["score"] > 0]["lv3"].nunique())
        except Exception:
            pass

    # PoC 후보: 자동화 기회 셀 + 채택 대기 제안서
    poc_candidates = 0
    if (
        news_7d is not None and not news_7d.empty
        and roadmap_df is not None and not roadmap_df.empty
    ):
        try:
            cells = _score_cells(news_7d, roadmap_df)
            poc_candidates += int(len(cells))
        except Exception:
            pass
    summary = bookmarks_store.summary_counts()
    poc_candidates += int(summary["proposal_status"].get("pending", 0))  # type: ignore[index]

    return {
        "news_30d": str(n_30d),
        "new_trends": (f"+{new_trends}" if new_trends > 0 else "0"),
        "matched_processes": str(matched_processes),
        "poc_candidates": str(poc_candidates),
    }


@st.cache_data(ttl=60)
def _archive_stats_ia() -> dict[str, int]:
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
    """인사이트 분석 v2 — topbar + app-side + main + app-sola."""
    inject_screen_css("insights")

    persona = _load_persona()
    stats = _archive_stats_ia()
    ia_stats = _ia_stats()
    refresh = app_shell.refresh_label_now()

    app_shell.render_topbar(
        page_title="인사이트 분석",
        eyebrow_current="인사이트 분석",
        refresh_label=refresh,
        fresh_kind="fresh",
    )
    app_shell.render_app_side(
        active_area="🔎 인사이트 분석",
        persona=persona,
        stats=stats,
    )

    app_shell.render_setup_banner_if_needed()

    template = _IA_TEMPLATE.read_text(encoding="utf-8")
    html_out = (
        template
        .replace("{{IA_NEWS_30D}}", _html.escape(ia_stats["news_30d"]))
        .replace("{{IA_NEW_TRENDS}}", _html.escape(ia_stats["new_trends"]))
        .replace("{{IA_MATCHED_PROCESSES}}", _html.escape(ia_stats["matched_processes"]))
        .replace("{{IA_POC_CANDIDATES}}", _html.escape(ia_stats["poc_candidates"]))
        .replace("{{IA_TKW_LIST}}", _tkw_list_html())
    )
    chart = _ia_chart_parts()
    html_out = (
        html_out
        .replace("{{IA_CHART_SVG}}", chart["svg"])
        .replace("{{IA_CHART_LEGEND}}", chart["legend"])
        .replace("{{IA_CHART_PILL}}", chart["pill"])
        .replace("{{IA_MATRIX_SVG}}", _ia_matrix_svg())
        .replace("{{IA_PROCESS_MAP}}", _ia_process_map_html())
    )
    st.html(html_out)

    app_shell.render_app_sola(
        context_label="인사이트 분석",
        context_sub=f"30일 뉴스 {ia_stats['news_30d']}건 · 매칭 공정 {ia_stats['matched_processes']}",
        quick_prompts=[
            ("01", "<b>비전 검사</b> 트렌드 8주 동향 요약"),
            ("02", "우리 부서 매칭률 가장 높은 <b>키워드 3개</b>는?"),
            ("03", "매트릭스 우상단 4건 중 PoC 우선순위 추천"),
        ],
        last_q="비전 검사 키워드 8주 그래프가 의미하는 게 뭐야?",
        last_a_html=(
            "확연한 상승 추세예요. <b>지난 4주에서 누적 멘션 +62%</b> 증가, "
            "주체는 현대중공업·삼성중공업·대우조선해양 등 조선소 3사. "
            "우리 공정과 직결되는 비중이 78% 라 PoC 후보 1순위."
            "<span class='muted'>방금 · 컨텍스트: 트렌드 + 매칭</span>"
        ),
        last_time="방금",
    )
