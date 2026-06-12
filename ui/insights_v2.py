"""인사이트 분석 — v2 디자인 적용.

헤더 4 stats (분석 뉴스 / 신규 트렌드 / 매칭 공정 / PoC 후보) + app-side
카운트를 실데이터로 (store/news_db, store/trends, store/match, sola/opportunity,
store/bookmarks). 트렌드 차트·매트릭스·키워드 리스트 시각은 시안 데이터 유지.
"""
from __future__ import annotations

import html as _html
from urllib.parse import quote

import streamlit as st

from config import ASSETS_DIR
from persona.schema import Persona
from roadmap.query import load_latest as _load_tasks
from store import bookmarks as bookmarks_store
from store import news_db as _news_db
from store import trends as _trends
from store.match import DEFAULT_SEMANTIC_WEIGHT as _SEM_W, score_matches as _score_matches
from sola.opportunity import score_cells as _score_cells
from ui import app_shell
from ui import components as _components
from ui._safe import guard
from ui.styles import inject_screen_css


# 트렌드 키워드 색상 팔레트 — rank 별
_TKW_COLORS = ["#2563EB", "#14B8A6", "#F59E0B", "#6366F1", "#0EA5E9", "#94A3B8"]

# 인사이트 분석 area 키 (트렌드 키워드 클릭 시 머무름)
_IA_AREA_KEY = "🔎 인사이트 분석"


def _tkw_select_href(keyword: str = "") -> str:
    """트렌드 키워드 클릭 → 같은 area + `?tkw=<keyword>` (빈 값이면 토글 해제).

    URL 에 tkw 를 남겨두면 process map · 매트릭스 helper 가 필터 인자로 사용한다.
    """
    parts = [f"app_area={quote(_IA_AREA_KEY)}"]
    if keyword:
        parts.append(f"tkw={quote(keyword)}")
    return "?" + "&".join(parts)


def _news_filter_by_keyword(news_df, keyword: str):
    """뉴스 DataFrame 을 키워드 substring(대소문자 무시) 으로 필터.

    검색 컬럼: title, summary, summary_llm, keywords, keywords_llm, content.
    빈 keyword 면 원본 반환. 컬럼 없으면 빈 결과(빈 df 와 동일 dtype).
    """
    if news_df is None or news_df.empty or not keyword:
        return news_df
    hay_cols = [c for c in ("title", "summary", "summary_llm", "keywords",
                             "keywords_llm", "content") if c in news_df.columns]
    if not hay_cols:
        return news_df.iloc[0:0]
    import pandas as _pd
    mask = _pd.Series(False, index=news_df.index)
    for col in hay_cols:
        mask |= news_df[col].fillna("").astype(str).str.contains(
            keyword, regex=False, case=False
        )
    return news_df[mask]


@st.cache_data(ttl=60)
def _tkw_list_html(selected_kw: str | None = None) -> str:
    """ia-tkw-item 6개 동적 빌드. top_keywords + emergence 결합 + 클릭 wire.

    Args:
        selected_kw: 사용자가 선택한 트렌드 키워드. None 이면 rank 1 활성(기본).
            매칭되는 키워드에 ia-tkw-on 활성 클래스 + href 는 토글 해제(빈 tkw).
    """
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
    has_explicit_selection = bool(selected_kw)
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
        is_active = (kw == selected_kw) if has_explicit_selection else (i == 0)
        active_cls = " ia-tkw-on" if is_active else ""
        # 활성 항목 클릭 → 해제(빈 tkw). 비활성 클릭 → 그 키워드 선택.
        href = _tkw_select_href("" if is_active else kw)
        aria = ' aria-current="true"' if is_active else ""
        title = (f"필터 해제 — 전체 데이터 보기" if is_active
                 else f"이 키워드로 매핑·매트릭스 필터")
        parts.append(
            f'<a class="ia-tkw-item{active_cls}" href="{href}" target="_self" '
            f'title="{_html.escape(title)}"{aria}>'
            f'<span class="ia-tkw-rank">{rank}</span>'
            f'<span class="ia-tkw-body">'
            f'<span class="ia-tkw-name">{_html.escape(kw)}{new_badge}</span>'
            f'<span class="ia-tkw-meta">{count}건</span>'
            f'</span>'
            f'<span class="ia-tkw-bar"><span style="width:{bar_pct}%; background:{color};"></span></span>'
            f'<span class="ia-tkw-delta {delta_cls}">{delta_label}</span>'
            f'</a>'
        )
    return "\n".join(parts)


def _tkw_empty_html() -> str:
    return ('<div style="padding: 18px; text-align: center; color: var(--text-muted); '
            'font-size: 14px; border: 1px dashed var(--surface-divider); border-radius: 10px;">'
            '아직 분석할 키워드가 없어요.<br>'
            '<span style="font-size:12.5px;">뉴스 수집에서 30일분 수집 후 다시 확인하세요.</span>'
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
    # callout box 좌표 clamp — viewBox 540 × 230 안에 78×28 박스가 들어가도록.
    box_w, box_h = 78, 28
    box_x = max(0, min(cx - box_w / 2, 540 - box_w))
    # y: 점 위 우선 (cy - box_h - 4), 위쪽이 잘리면 점 아래 (cy + 10)
    box_y_above = cy - box_h - 4
    box_y = box_y_above if box_y_above >= 0 else cy + 10
    text_cx = box_x + box_w / 2
    parts.append(
        f"<g><rect x='{box_x:.0f}' y='{box_y:.0f}' width='{box_w}' height='{box_h}' rx='6' fill='#0F172A'/>"
        f"<text x='{text_cx:.0f}' y='{box_y + 12:.0f}' text-anchor='middle' font-family='Pretendard' font-size='10.5' font-weight='700' fill='#fff'>{label_safe}</text>"
        f"<text x='{text_cx:.0f}' y='{box_y + 22:.0f}' text-anchor='middle' font-family='JetBrains Mono, monospace' font-size='9' fill='#94A3B8'>{delta_str}</text></g>"
    )

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
# 색상 팔레트는 board_v2.MATRIX_DEPT_COLORS 공유 (단일 진실).


def _ia_mx_select_href(dept: str, lv3: str) -> str:
    """인사이트 매트릭스 셀 선택 URL — 같은 area + `?ia_mx_select=<dept>|<lv3>`.

    빈 dept/lv3 → 토글 해제(파라미터 생략).
    """
    parts = [f"app_area={quote(_IA_AREA_KEY)}"]
    if dept or lv3:
        parts.append(f"ia_mx_select={quote(f'{dept}|{lv3}')}")
    return "?" + "&".join(parts)


def _ia_mx_selected_key() -> str | None:
    """`?ia_mx_select=` 1회 읽기. 빈 값 → None."""
    raw = (st.query_params.get("ia_mx_select") or "").strip()
    return raw or None


@st.cache_data(ttl=60)
def _ia_matrix_svg(selected_key: str | None = None) -> str:
    """인사이트 매트릭스 — 600×420 viewBox, 좌상단 = PoC 후보.

    Args:
        selected_key: "dept|lv3" 형태로 선택된 셀. None 이면 1위.

    좌표 매핑:
      - x (left) = 40 + (1 - ease_norm) * 520 → ease 높을수록 좌측 = 쉬움
      - y (top)  = 20 + (1 - effect_norm) * 360 → effect 높을수록 상단
      - 버블 r = 14 + score_norm * 22
      - 선택된 cell = ★ halo + 두꺼운 stroke
      - 각 버블은 <a xlink:href="?ia_mx_select=..."> 로 wrap (SVG 링크)
    """
    try:
        news = _news_db.load_news_for_days(days=30)
        tasks = _load_tasks()
    except Exception:
        news = None
        tasks = None
    if news is None or news.empty or tasks is None or tasks.empty:
        return _ia_matrix_empty()

    try:
        cells = _score_cells(news, tasks).head(8)
    except Exception:
        return _ia_matrix_empty()
    if cells.empty:
        return _ia_matrix_empty()

    max_news = max(int(cells["matched_news"].max()), 1)
    max_tasks = max(int(cells["matched_tasks"].max()), 1)
    max_score = max(float(cells["cell_score"].max()), 1.0)

    # 선택된 셀 인덱스 — selected_key 매칭 우선, 없으면 1위
    selected_idx = 0
    if selected_key:
        for i, (_, row) in enumerate(cells.iterrows()):
            key = f"{row.get('dept', '') or ''}|{row.get('lv3', '') or ''}"
            if key == selected_key:
                selected_idx = i
                break

    parts = ["<svg xmlns='http://www.w3.org/2000/svg' xmlns:xlink='http://www.w3.org/1999/xlink' "
             "class='ia-mtx-svg' viewBox='0 0 600 420' preserveAspectRatio='xMidYMid meet'>"]

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
    for i, (_, row) in enumerate(cells.iterrows()):
        ease_norm = int(row.get("matched_tasks", 0) or 0) / max_tasks
        eff_norm = int(row.get("matched_news", 0) or 0) / max_news
        score_norm = float(row.get("cell_score", 0) or 0) / max_score

        cx = 40 + (1 - ease_norm) * 520  # ease 높음 = 왼쪽
        cy = 20 + (1 - eff_norm) * 360
        r = 14 + score_norm * 22

        dept_raw = str(row.get("dept", "") or "")
        lv3_raw = str(row.get("lv3", "") or "")
        from ui.board_v2 import MATRIX_DEPT_COLORS, MATRIX_DEPT_FALLBACK
        color = MATRIX_DEPT_COLORS.get(dept_raw, MATRIX_DEPT_FALLBACK)
        fill = f"rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)},0.16)"
        _raw_lbl = lv3_raw or dept_raw or "—"
        label = _html.escape(_raw_lbl[:12] + ("…" if len(_raw_lbl) > 12 else ""))
        meta = f"매칭 {int(row.get('matched_news', 0) or 0)}건"
        is_selected = (i == selected_idx)

        # 활성 셀 클릭 → 토글 해제(빈 ia_mx_select), 비활성 → 그 셀 선택
        bubble_href = (_ia_mx_select_href("", "") if is_selected
                       else _ia_mx_select_href(dept_raw, lv3_raw))
        title_attr = _html.escape(f"{dept_raw} · {lv3_raw}", quote=True)
        # SVG 링크로 wrap — 클릭 가능 영역(circle + label + meta)
        parts.append(
            f"<a xlink:href='{bubble_href}' href='{bubble_href}' target='_self' "
            f"class='ia-mtx-bubble{' ia-mtx-bubble-on' if is_selected else ''}'>"
        )
        parts.append(f"<title>{title_attr}</title>")
        if is_selected:
            # halo
            parts.append(f"<circle cx='{cx:.0f}' cy='{cy:.0f}' r='{r + 10:.0f}' "
                         f"fill='none' stroke='{color}' stroke-width='1.4' stroke-dasharray='3 3'/>")
        parts.append(f"<circle cx='{cx:.0f}' cy='{cy:.0f}' r='{r:.0f}' "
                     f"fill='{fill}' stroke='{color}' stroke-width='{2.4 if is_selected else 1.8}'/>")
        parts.append(f"<circle cx='{cx:.0f}' cy='{cy:.0f}' r='5' fill='{color}'/>")
        parts.append(f"<text x='{cx:.0f}' y='{cy + r + 14:.0f}' text-anchor='middle' "
                     f"font-family='Pretendard' font-size='11' font-weight='800' fill='#0F172A'>{label}</text>")
        parts.append(f"<text x='{cx:.0f}' y='{cy + r + 26:.0f}' text-anchor='middle' "
                     f"font-family='JetBrains Mono, monospace' font-size='9' fill='#475569' "
                     f"font-weight='700'>{meta}</text>")
        parts.append("</a>")

    parts.append("</svg>")
    return "".join(parts)


@st.cache_data(ttl=60)
def _ia_mtx_rank_html(selected_key: str | None = None) -> str:
    """매트릭스 우측 ★ PoC 후보 동적 리스트 — selected_key 셀에 ia-poc-on."""
    try:
        news = _news_db.load_news_for_days(days=30)
        tasks = _load_tasks()
    except Exception:
        news = None
        tasks = None
    if news is None or news.empty or tasks is None or tasks.empty:
        return _ia_mtx_rank_empty()

    try:
        cells = _score_cells(news, tasks).head(5)
    except Exception:
        return _ia_mtx_rank_empty()
    if cells.empty:
        return _ia_mtx_rank_empty()

    max_score = max(float(cells["cell_score"].max()), 1.0)
    # PoC 후보 = ease_norm 높음(매칭 작업 많음) + eff_norm 높음(매칭 뉴스 많음)
    max_news = max(int(cells["matched_news"].max()), 1)
    max_tasks = max(int(cells["matched_tasks"].max()), 1)

    selected_idx = 0
    if selected_key:
        for i, (_, row) in enumerate(cells.iterrows()):
            key = f"{row.get('dept', '') or ''}|{row.get('lv3', '') or ''}"
            if key == selected_key:
                selected_idx = i
                break

    def _level(norm: float) -> str:
        if norm >= 0.66:
            return "高"
        if norm >= 0.33:
            return "中"
        return "低"

    items = []
    for i, (_, row) in enumerate(cells.iterrows()):
        dept_raw = str(row.get("dept", "") or "")
        lv3_raw = str(row.get("lv3", "") or "")
        score = float(row.get("cell_score", 0) or 0)
        ease_norm = int(row.get("matched_tasks", 0) or 0) / max_tasks
        eff_norm = int(row.get("matched_news", 0) or 0) / max_news
        is_sel = (i == selected_idx)
        # ease 높을수록 난이도 低 (X축 inverted)
        effort = _level(1 - ease_norm)
        impact = _level(eff_norm)
        score_10 = round(score / max_score * 10, 1)
        sample_tasks = str(row.get("sample_tasks", "") or "").split(" · ")[:1]
        why_raw = (sample_tasks[0] if sample_tasks and sample_tasks[0]
                   else f"매칭 {int(row.get('matched_news', 0))}건 누적")
        href = (_ia_mx_select_href("", "") if is_sel
                else _ia_mx_select_href(dept_raw, lv3_raw))
        items.append(
            f'<li class="ia-poc{" ia-poc-on" if is_sel else ""}">'
            f'<a class="ia-poc-link" href="{href}" target="_self" '
            f'aria-current="{"true" if is_sel else "false"}">'
            f'<span class="ia-poc-i">{i + 1:02d}</span>'
            f'<div class="ia-poc-body">'
            f'<div class="ia-poc-name">{_html.escape(dept_raw)} · {_html.escape(lv3_raw)}</div>'
            f'<div class="ia-poc-meta">'
            f'<span class="ia-poc-effort">난이도 <b>{effort}</b></span>'
            f'<span class="ia-poc-impact">효과 <b>{impact}</b></span>'
            f'</div>'
            f'<div class="ia-poc-why">{_html.escape(why_raw[:60])}</div>'
            f'</div>'
            f'<span class="ia-poc-score">{score_10}</span>'
            f'</a>'
            f'</li>'
        )

    return f"""
        <div class="ia-mtx-rank-head">
          <span class="ia-mtx-rank-eye">★ PoC 후보 (좌상단)</span>
          <span class="ia-mtx-rank-cnt">{len(cells)}건</span>
        </div>
        <ul class="ia-poc-list">{"".join(items)}</ul>"""


def _ia_mtx_rank_empty() -> str:
    return ('<div class="ia-mtx-rank-head">'
            '<span class="ia-mtx-rank-eye">★ PoC 후보 (좌상단)</span>'
            '<span class="ia-mtx-rank-cnt">0건</span>'
            '</div>'
            '<div style="padding:18px 14px; color:var(--text-muted); font-size:13px; '
            'border:1px dashed var(--surface-divider); border-radius:10px; text-align:center;">'
            '아직 매칭된 자동화 기회가 없어요.</div>')


# ── SECTION C 히트맵 (공정 × 자동화 기술) ─────────────────────

# 자동화 기술 컬럼 — 조선소 도메인 지표 키워드(고정 셋, 7개)
_HM_TECH_COLS: tuple[str, ...] = (
    "비전", "협동 로봇", "예지보전", "디지털 트윈", "AGV", "AI", "외골격",
)


def _hm_select_href(process: str, tech: str) -> str:
    """히트맵 셀 선택 URL — `?app_area=🔎+인사이트+분석&hm_select=<proc>|<tech>`.

    빈 값 → hm_select 생략(토글 해제).
    """
    parts = [f"app_area={quote(_IA_AREA_KEY)}"]
    if process or tech:
        parts.append(f"hm_select={quote(f'{process}|{tech}')}")
    return "?" + "&".join(parts)


def _hm_selected_key() -> str | None:
    """`?hm_select=` 1회 stateless 읽기. 빈 값 → None."""
    raw = (st.query_params.get("hm_select") or "").strip()
    return raw or None


def _hm_count_in_news(news_df, process: str, tech: str) -> int:
    """뉴스 df 에서 process 와 tech 가 둘 다 substring 으로 등장하는 row 수."""
    if news_df is None or news_df.empty or not process or not tech:
        return 0
    cols = [c for c in ("title", "summary", "summary_llm", "keywords",
                         "keywords_llm", "content") if c in news_df.columns]
    if not cols:
        return 0
    import pandas as _pd
    p_mask = _pd.Series(False, index=news_df.index)
    t_mask = _pd.Series(False, index=news_df.index)
    for c in cols:
        col = news_df[c].fillna("").astype(str)
        p_mask |= col.str.contains(process, regex=False, case=False)
        t_mask |= col.str.contains(tech, regex=False, case=False)
    return int((p_mask & t_mask).sum())


def _hm_cell_class(v: int) -> str:
    """수치 → 강도 클래스(none/low/normal/mid/strong)."""
    if v <= 0:
        return "ia-hm-c ia-hm-c-empty"
    if v <= 3:
        return "ia-hm-c ia-hm-c-low"
    if v <= 7:
        return "ia-hm-c"
    if v <= 15:
        return "ia-hm-c ia-hm-c-mid"
    return "ia-hm-c ia-hm-c-strong"


def _hm_top_news(news_df, process: str, tech: str, limit: int = 3) -> list[dict]:
    """선택된 process × tech 셀에 매칭되는 뉴스 상위 N건."""
    if news_df is None or news_df.empty or not process or not tech:
        return []
    cols = [c for c in ("title", "summary", "summary_llm", "keywords",
                         "keywords_llm", "content") if c in news_df.columns]
    if not cols:
        return []
    import pandas as _pd
    p_mask = _pd.Series(False, index=news_df.index)
    t_mask = _pd.Series(False, index=news_df.index)
    for c in cols:
        col = news_df[c].fillna("").astype(str)
        p_mask |= col.str.contains(process, regex=False, case=False)
        t_mask |= col.str.contains(tech, regex=False, case=False)
    matched = news_df[p_mask & t_mask]
    if matched.empty:
        return []
    if "collected_at" in matched.columns:
        matched = matched.sort_values("collected_at", ascending=False)
    out: list[dict] = []
    for _, r in matched.head(limit).iterrows():
        out.append({
            "title": str(r.get("title", "") or "(제목 없음)"),
            "source": str(r.get("source", "") or ""),
            "press": str(r.get("press", "") or ""),
            "link": str(r.get("link", "") or ""),
        })
    return out


@st.cache_data(ttl=60)
def _ia_heatmap_html(selected_key: str | None = None) -> str:
    """공정×자동화 기술 히트맵 (동적 데이터 + 클릭 wire).

    행 = score_cells 상위 7개 공정(lv3 unique 유지순서).
    열 = `_HM_TECH_COLS` (고정 7개).
    셀 = 30일 뉴스에서 process AND tech substring 둘 다 매치된 row 수.
    """
    try:
        news_30 = _news_db.load_news_for_days(days=30)
        tasks = _load_tasks()
    except Exception:
        news_30 = None
        tasks = None
    if news_30 is None or news_30.empty or tasks is None or tasks.empty:
        return _ia_heatmap_empty()

    try:
        cells = _score_cells(news_30, tasks).head(20)
    except Exception:
        return _ia_heatmap_empty()
    if cells.empty:
        return _ia_heatmap_empty()

    # 행 = unique lv3 (등장순), 최대 7개
    seen: set[str] = set()
    rows: list[str] = []
    for _, r in cells.iterrows():
        lv3 = str(r.get("lv3", "") or "").strip()
        if lv3 and lv3 not in seen:
            seen.add(lv3)
            rows.append(lv3)
        if len(rows) >= 7:
            break
    if not rows:
        return _ia_heatmap_empty()

    cols = _HM_TECH_COLS

    # 셀 카운트
    grid: dict[tuple[str, str], int] = {}
    for proc in rows:
        for tech in cols:
            grid[(proc, tech)] = _hm_count_in_news(news_30, proc, tech)

    # 합계 (legend)
    total = sum(grid.values())

    # 헤더
    parts: list[str] = ['<div class="ia-hm">']
    parts.append('<div class="ia-hm-cols">')
    parts.append('<div></div>')
    for tech in cols:
        parts.append(f'<div class="ia-hm-col">{_html.escape(tech)}</div>')
    parts.append('</div>')

    # 데이터 행 — 각 셀은 클릭 가능 <a>
    for proc in rows:
        parts.append('<div class="ia-hm-row">')
        parts.append(f'<div class="ia-hm-rh">{_html.escape(proc)}</div>')
        for tech in cols:
            v = grid[(proc, tech)]
            cls = _hm_cell_class(v)
            key = f"{proc}|{tech}"
            is_sel = (selected_key == key)
            if is_sel:
                cls += " ia-hm-c-on"
            label = str(v) if v > 0 else "·"
            # 활성 셀 클릭 → 토글 해제, 비활성 → 새 선택
            href = (_hm_select_href("", "") if is_sel
                    else _hm_select_href(proc, tech))
            title = f"{proc} × {tech} — 매칭 뉴스 {v}건"
            parts.append(
                f'<a class="{cls}" href="{href}" target="_self" '
                f'title="{_html.escape(title, quote=True)}" '
                f'aria-current="{"true" if is_sel else "false"}">{label}</a>'
            )
        parts.append('</div>')

    # 범례
    parts.append(
        '<div class="ia-hm-legend">'
        '<span>강도:</span>'
        '<span class="ia-hm-leg-i"><span class="ia-hm-leg-d ia-hm-c-empty">·</span>없음</span>'
        '<span class="ia-hm-leg-i"><span class="ia-hm-leg-d ia-hm-c-low">3</span>약(≤3)</span>'
        '<span class="ia-hm-leg-i"><span class="ia-hm-leg-d">7</span>중(4-7)</span>'
        '<span class="ia-hm-leg-i"><span class="ia-hm-leg-d ia-hm-c-mid">15</span>강(8-15)</span>'
        '<span class="ia-hm-leg-i"><span class="ia-hm-leg-d ia-hm-c-strong">16+</span>매우 강</span>'
        '<span class="ia-hm-spacer"></span>'
        f'<span class="ia-hm-total">합계 {total}건 / 30일</span>'
        '</div>'
    )

    # 선택된 셀의 상세 strip — 상위 3 뉴스 + SOLA 인계 + 전체 보기
    if selected_key and "|" in selected_key:
        proc, tech = selected_key.split("|", 1)
        top_news = _hm_top_news(news_30, proc, tech, limit=3)
        if top_news:
            from ui.board_v2 import _sola_handoff_href as _sh
            sola_href = _sh("hm_cell", dept="", lv3=proc) + "&tech=" + quote(tech)
            clear_href = _hm_select_href("", "")
            news_items = []
            from ui import news_sources as _news_sources
            for n in top_news:
                src = _html.escape(
                    _news_sources.source_label(n["source"], n.get("press", "")) or "—")
                title = _html.escape(n["title"][:120])
                link = n["link"]
                if link:
                    news_items.append(
                        f'<li><a href="{_html.escape(link, quote=True)}" target="_blank" '
                        f'rel="noopener">{title}</a><small>{src}</small></li>'
                    )
                else:
                    news_items.append(f'<li>{title}<small>{src}</small></li>')
            parts.append(
                '<div class="ia-hm-detail">'
                f'<div class="ia-hm-detail-head">'
                f'<b>{_html.escape(proc)} × {_html.escape(tech)}</b>'
                f'<span class="ia-hm-detail-meta">매칭 뉴스 {len(top_news)}건 미리보기</span>'
                f'<a class="ia-hm-detail-clear" href="{clear_href}" target="_self">× 닫기</a>'
                f'</div>'
                f'<ul class="ia-hm-news-list">{"".join(news_items)}</ul>'
                f'<a class="ia-hm-detail-sola" href="{sola_href}" target="_self">'
                f'SOLA 작업실에서 더 보기 →</a>'
                '</div>'
            )
        else:
            clear_href = _hm_select_href("", "")
            parts.append(
                f'<div class="ia-hm-detail ia-hm-detail-empty">'
                f"'<b>{_html.escape(proc)} × {_html.escape(tech)}</b>' 매칭 뉴스가 없어요. "
                f'<a class="ia-hm-detail-clear" href="{clear_href}" target="_self">× 닫기</a>'
                f'</div>'
            )

    parts.append('</div>')
    return "".join(parts)


def _ia_heatmap_empty() -> str:
    return ('<div class="ia-hm" style="padding:32px 18px; text-align:center;'
            ' color:var(--text-muted); font-size:14px; border:1px dashed var(--surface-divider);'
            ' border-radius:12px;">아직 공정 × 자동화 기술 매칭이 없어요.<br>'
            '<span style="font-size:12.5px;">뉴스 30일분 + 작업 정의 데이터 업로드 후 자동으로 채워집니다.</span>'
            '</div>')


def _ia_matrix_empty() -> str:
    return ('<div style="padding:80px 18px; text-align:center; color:var(--text-muted);'
            ' font-size:14px; border:1px dashed var(--surface-divider); border-radius:12px;'
            ' min-height:380px; display:flex; flex-direction:column; justify-content:center;">'
            '아직 매트릭스에 그릴 자동화 기회가 없어요.<br>'
            '<span style="font-size:12.5px;">뉴스 + 작업 정의 매칭 후 자동으로 채워집니다.</span>'
            '</div>')


# ── 트렌드 → 공정 매핑 카드 (.ia-map) ───────────────────────
_IA_PC_PALETTE = [
    ("#2563EB", "rgba(37,99,235,0.10)"),
    ("#0F766E", "rgba(20,184,166,0.10)"),
    ("#4F46E5", "rgba(99,102,241,0.10)"),
]


@st.cache_data(ttl=60)
def _ia_process_map_html(selected_kw: str | None = None) -> str:
    """SECTION A 우측 — 선택 키워드 → 매칭 Lv3 공정 카드 3개.

    Args:
        selected_kw: 사용자가 선택한 트렌드 키워드. 지정 시 30일 뉴스를
            해당 키워드 substring 으로 필터링하고 chip 도 그 값으로 표시.
            None 이면 기존 동작(top trending 키워드).

    데이터:
      from chip = selected_kw (없으면 `_weekly_keyword_series` 1순위)
      cards    = `_score_cells` 상위 3개 (각 dept × lv3)
      fit %    = cell_score / max * 36 + 60 (60~96%)
      현재     = sample_tasks 첫 항목 (없으면 매칭 작업 N건)
      애로     = sample_news 첫 헤드라인 (없으면 매칭 뉴스 N건)
    """
    from ui.board_v2 import _weekly_keyword_series

    try:
        news_30 = _news_db.load_news_for_days(days=30)
        tasks_df = _load_tasks()
    except Exception:
        news_30 = None
        tasks_df = None
    if news_30 is None or news_30.empty or tasks_df is None or tasks_df.empty:
        return _ia_pmap_empty()

    # 선택된 키워드로 뉴스 필터링 (지정 시) — 필터 후 비면 empty
    if selected_kw:
        news_30 = _news_filter_by_keyword(news_30, selected_kw)
        if news_30 is None or news_30.empty:
            return _ia_pmap_empty(selected_kw=selected_kw)

    # from chip — 명시 선택이 우선, 없으면 top trending kw
    if selected_kw:
        top_kw = selected_kw
    else:
        _labels, series = _weekly_keyword_series(weeks=5)
        top_kw = series[0]["name"] if series else "—"
    top_dot_color = _IA_PC_PALETTE[0][0]

    try:
        cells = _score_cells(news_30, tasks_df).head(3)
    except Exception:
        return _ia_pmap_empty()
    if cells.empty:
        return _ia_pmap_empty(selected_kw=selected_kw)

    max_score = max(float(cells["cell_score"].max()), 1.0)
    avg_fit = int(round(cells["cell_score"].mean() / max_score * 36 + 60))
    total_news = int(cells["matched_news"].sum())

    from ui.board_v2 import _sola_handoff_href

    cards = []
    for i, (_, row) in enumerate(cells.iterrows()):
        color, bg = _IA_PC_PALETTE[i % len(_IA_PC_PALETTE)]
        dept_raw = str(row.get("dept", "") or "—")
        lv3_raw = str(row.get("lv3", "") or "—")
        dept = _html.escape(dept_raw)
        lv3 = _html.escape(lv3_raw)
        score = float(row.get("cell_score", 0) or 0)
        fit_pct = int(round(score / max_score * 36 + 60))
        detail_href = _sola_handoff_href("ia_map", dept=dept_raw, lv3=lv3_raw)

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
            <a class="ia-pc-detail" href="{detail_href}" target="_self">상세 →</a>
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


def _ia_pmap_empty(*, selected_kw: str | None = None) -> str:
    if selected_kw:
        clear_href = _tkw_select_href("")
        return (
            '<div style="padding:32px 18px; text-align:center; color:var(--text-muted);'
            ' font-size:14px; border:1px dashed var(--surface-divider); border-radius:12px;">'
            f"'<b>{_html.escape(selected_kw)}</b>' 키워드에 매핑되는 공정이 없어요.<br>"
            f'<span style="font-size:12.5px;">다른 키워드 선택 또는 '
            f'<a href="{clear_href}" target="_self" '
            f'style="color:var(--accent-primary); text-decoration:none; font-weight:700;">'
            f'전체 보기</a>.</span>'
            '</div>'
        )
    return ('<div style="padding:32px 18px; text-align:center; color:var(--text-muted);'
            ' font-size:14px; border:1px dashed var(--surface-divider); border-radius:12px;">'
            '아직 키워드 → 공정 매핑 결과가 없어요.<br>'
            '<span style="font-size:12.5px;">뉴스 30일분 + 작업 정의 데이터 업로드 후 자동으로 채워집니다.</span>'
            '</div>')


@st.cache_data(ttl=60)
def _ia_stats() -> dict[str, str]:
    """인사이트 분석 헤더 4 stats.

    Returns:
      news_30d: 최근 30일 뉴스 수
      new_trends: 이번 주 신규 emerge 키워드 수 (지난주 대비 +)
      matched_processes: 뉴스가 매칭된 Lv3 공정 unique 수
      poc_candidates: 자동화 기회 + 채택 대기 합 (검토 대기 후보)
    """
    news_30d = news_7d = tasks_df = None
    with guard("인사이트 — 뉴스(30d) 로드"):
        news_30d = _news_db.load_news_for_days(days=30)
    with guard("인사이트 — 뉴스(7d) 로드"):
        news_7d = _news_db.load_news_for_days(days=7)
    with guard("인사이트 — 작업 정의 로드"):
        tasks_df = _load_tasks()

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
        and tasks_df is not None and not tasks_df.empty
    ):
        try:
            matches = _score_matches(news_7d, tasks_df, top_k=3, semantic_weight=_SEM_W)
            if not matches.empty and "lv3" in matches.columns:
                matched_processes = int(matches[matches["score"] > 0]["lv3"].nunique())
        except Exception:
            pass

    # PoC 후보: 자동화 기회 셀(높은 매칭 점수)만. '채택 대기' 제안서와는 별개
    # 개념이라 합산하지 않는다 (이전: pending 을 더해 두 개념을 혼동시키던 버그 — 감사 지적).
    poc_candidates = 0
    if (
        news_7d is not None and not news_7d.empty
        and tasks_df is not None and not tasks_df.empty
    ):
        try:
            cells = _score_cells(news_7d, tasks_df)
            poc_candidates += int(len(cells))
        except Exception:
            pass

    return {
        "news_30d": str(n_30d),
        "new_trends": (f"+{new_trends}" if new_trends > 0 else "0"),
        "matched_processes": str(matched_processes),
        "poc_candidates": str(poc_candidates),
    }


@st.cache_data(ttl=60)
def _archive_stats_ia() -> dict[str, int]:
    """app-side 좌측 — 보드와 동일 소스. `board_v2._archive_stats` 60초 캐시 위임."""
    from ui import board_v2  # lazy

    try:
        return board_v2._archive_stats()
    except Exception:
        summary = bookmarks_store.summary_counts()
        pending = int(summary["proposal_status"].get("pending", 0))  # type: ignore[index]
        return {"match_today": 0, "opportunities": 0, "pending_adopt": pending}


def chat_context_block(persona: Persona) -> str:
    """인사이트 분석 화면이 보여주는 모든 데이터를 LLM 컨텍스트로 packaging.

    트렌드 키워드 6 + 5주 차트 series + 매트릭스 cells + 공정 매핑 카드.
    """
    parts: list[str] = ["--- 현재 화면: 인사이트 분석 (🔎) ---"]

    # 30일 뉴스 + 작업 정의 데이터 — 캐시된 helper 들이 같은 데이터 씀
    try:
        news_30 = _news_db.load_news_for_days(days=30)
        tasks = _load_tasks()
    except Exception:
        news_30 = None
        tasks = None

    # 트렌드 키워드 top 6 (빈도 + emergence)
    if news_30 is not None and not news_30.empty:
        try:
            top = _trends.top_keywords(news_30, top_n=6)
            if not top.empty:
                parts.append("트렌드 키워드 top 6 (30일 빈도):")
                for _, r in top.iterrows():
                    parts.append(f"  - {r['keyword']}: {int(r['count'])}건")
        except Exception:
            pass

        # 신규 emergence 키워드 (7일 vs 이전)
        try:
            today_df = _news_db.load_news_for_days(days=7)
            em = _trends.keyword_emergence(today_df, news_30, top_n=5)
            new_kw = list(em.get("new", []).get("keyword", [])) if hasattr(em.get("new"), "get") else []
            if new_kw:
                parts.append(f"신규 등장 키워드 (최근 7일): {', '.join(new_kw[:5])}")
        except Exception:
            pass

    # 5주 트렌드 차트 series (board 공유 helper)
    try:
        from ui.board_v2 import _weekly_keyword_series, _delta_pct
        _labels, series = _weekly_keyword_series(weeks=5)
        if series:
            parts.append("5주 차트 — 키워드 변화율:")
            for s in series[:5]:
                d = _delta_pct(s["counts"])
                parts.append(f"  - {s['name']}: 변화율 {'+' if d>=0 else ''}{d}%")
    except Exception:
        pass

    # 매트릭스 8 cells
    if news_30 is not None and not news_30.empty and tasks is not None and not tasks.empty:
        try:
            cells = _score_cells(news_30, tasks).head(8)
            if not cells.empty:
                parts.append("기회 매트릭스 top 8 (효과×난이도):")
                for _, r in cells.iterrows():
                    parts.append(
                        f"  - {r.get('dept','')} · {r.get('lv3','')} "
                        f"(점수 {int(float(r.get('cell_score', 0) or 0))} · "
                        f"매칭 뉴스 {int(r.get('matched_news', 0) or 0)}건 · "
                        f"매칭 작업 {int(r.get('matched_tasks', 0) or 0)}건)"
                    )
        except Exception:
            pass

        # 공정 매핑 카드 (트렌드 → 공정)
        try:
            cells3 = _score_cells(news_30, tasks).head(3)
            if not cells3.empty:
                parts.append("공정 매핑 카드 (top 트렌드 키워드와 매칭되는 공정 3건):")
                for _, r in cells3.iterrows():
                    sample_news = str(r.get("sample_news", "") or "").split(" · ")[0][:80]
                    parts.append(f"  - {r.get('dept','')} · {r.get('lv3','')}")
                    if sample_news:
                        parts.append(f"    매칭 뉴스 샘플: {sample_news}")
        except Exception:
            pass

    return "\n".join(parts)


def _strip_mockup_blocks(html: str) -> str:
    """정적 목업 블록 제거 (Phase C) — 실데이터/실위젯이 대체하는 시안 잔재.

    - 가짜 우측 `ia-sola` 패널: 실제 SOLA 채팅은 우측 컬럼(`chat_panel.render_side`)이 담당.
      (Phase A 로 모든 화면에 우측 채팅이 생겨 이 시안 패널은 중복·가짜였음.)
    - 죽은 `ia-filters` 스트립: 기간/공정범위/저장한 뷰 버튼이 모두 핸들러 없는 시안.
    두 마커 사이를 슬라이스해 제거 — div 균형 카운트에 의존하지 않는 안전 방식.
    """
    i = html.find('<aside class="ia-sola">')
    if i != -1:
        j = html.find('</aside>', i)
        if j != -1:
            html = html[:i] + html[j + len('</aside>'):]
    i = html.find('<div class="ia-filters">')
    if i != -1:
        j = html.find('<div class="ia-grid">', i)
        if j != -1:
            html = html[:i] + html[j:]
    return html


def render() -> None:
    """인사이트 분석 v2 — 중앙 콘텐츠(트렌드·매트릭스·히트맵). 우측 채팅은 render_side(app.py)."""
    inject_screen_css("insights")

    persona = app_shell.get_persona()
    stats = _archive_stats_ia()
    ia_stats = _ia_stats()
    refresh = app_shell.refresh_label_now()

    app_shell.render_topbar(
        page_title="인사이트 분석",
        eyebrow_current="인사이트 분석",
        refresh_label=refresh,
        fresh_kind="fresh",
    )
    app_shell.render_setup_banner_if_needed()

    # 트렌드 키워드 클릭 필터 — `?tkw=` 1회 stateless 필터(URL 유지).
    selected_kw = (st.query_params.get("tkw") or "").strip() or None
    # 매트릭스 셀 선택 — `?ia_mx_select=dept|lv3` 1회 stateless.
    selected_mx = _ia_mx_selected_key()
    # 히트맵 셀 선택 — `?hm_select=proc|tech` 1회 stateless.
    selected_hm = _hm_selected_key()

    template = _components.read_asset_text(_IA_TEMPLATE)
    html_out = (
        template
        .replace("{{IA_NEWS_30D}}", _html.escape(ia_stats["news_30d"]))
        .replace("{{IA_NEW_TRENDS}}", _html.escape(ia_stats["new_trends"]))
        .replace("{{IA_MATCHED_PROCESSES}}", _html.escape(ia_stats["matched_processes"]))
        .replace("{{IA_POC_CANDIDATES}}", _html.escape(ia_stats["poc_candidates"]))
        .replace("{{IA_TKW_LIST}}", _tkw_list_html(selected_kw=selected_kw))
    )
    chart = _ia_chart_parts()
    html_out = (
        html_out
        .replace("{{IA_CHART_SVG}}", chart["svg"])
        .replace("{{IA_CHART_LEGEND}}", chart["legend"])
        .replace("{{IA_CHART_PILL}}", chart["pill"])
        .replace("{{IA_MATRIX_SVG}}", _ia_matrix_svg(selected_key=selected_mx))
        .replace("{{IA_MTX_RANK}}", _ia_mtx_rank_html(selected_key=selected_mx))
        .replace("{{IA_HEATMAP}}", _ia_heatmap_html(selected_key=selected_hm))
        .replace("{{IA_PROCESS_MAP}}", _ia_process_map_html(selected_kw=selected_kw))
    )
    html_out = _strip_mockup_blocks(html_out)
    st.html(_components.prepare_screen_html(html_out))
