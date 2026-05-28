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
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
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


# 트렌드 차트 4 series 색상 (Azure/Teal/Amber/Indigo)
_TREND_COLORS = ["#2563EB", "#14B8A6", "#F59E0B", "#6366F1"]
# 키워드 리스트 6색 (4 series + Sky + Slate)
_TREND_KW_COLORS = _TREND_COLORS + ["#0EA5E9", "#64748B"]


def _weekly_keyword_series(weeks: int = 8) -> tuple[list[str], list[dict]]:
    """top-6 키워드의 주별 출현 빈도. weeks 개 버킷.

    Returns: (week_labels, [{name, counts:list[int]} ...]) — week_labels 는
    'W14'~'금주' 형식, counts 는 weeks 길이.
    """
    try:
        news = _news_db.load_news_for_days(days=weeks * 7)
    except Exception:
        return [], []
    if news is None or news.empty:
        return [], []

    # date 컬럼 정규화
    if "published_at" in news.columns:
        dt = pd.to_datetime(news["published_at"], errors="coerce", utc=True)
    elif "collected_at" in news.columns:
        dt = pd.to_datetime(news["collected_at"], errors="coerce", utc=True)
    else:
        return [], []
    news = news.assign(_dt=dt).dropna(subset=["_dt"])
    if news.empty:
        return [], []

    now = datetime.now(timezone.utc)
    # 주차 인덱스: 0 = 가장 오래된 주, weeks-1 = 금주
    def _week_idx(t: pd.Timestamp) -> int:
        days_ago = (now - t.to_pydatetime()).days
        idx = (weeks - 1) - (days_ago // 7)
        return int(idx)

    news = news.assign(_w=news["_dt"].apply(_week_idx))
    news = news[(news["_w"] >= 0) & (news["_w"] < weeks)]
    if news.empty:
        return [], []

    # top-6 키워드 후보
    try:
        top_df = _trends.top_keywords(news, top_n=6)
    except Exception:
        return [], []
    if top_df.empty:
        return [], []

    series: list[dict] = []
    for kw in top_df["keyword"].astype(str).tolist():
        counts = [0] * weeks
        for _w, sub in news.groupby("_w"):
            mask = pd.Series(False, index=sub.index)
            for col in ("keywords_llm", "keywords"):
                if col in sub.columns:
                    mask |= sub[col].fillna("").astype(str).str.contains(
                        kw, regex=False, case=False
                    )
            counts[int(_w)] = int(mask.sum())
        series.append({"name": kw, "counts": counts})

    # 주차 라벨: ISO week 의 마지막 2자리, 마지막은 '금주'
    labels: list[str] = []
    for i in range(weeks):
        wk_dt = now - timedelta(days=(weeks - 1 - i) * 7)
        if i == weeks - 1:
            labels.append("금주")
        else:
            labels.append(f"W{wk_dt.isocalendar().week:02d}")
    return labels, series


def _path_d(counts: list[int], y_max: int) -> str:
    """8-week counts → SVG path 'M ... L ...' (viewBox 560×200)."""
    if not counts:
        return ""
    x_left, x_right = 30, 540
    y_top, y_bottom = 20, 180
    n = len(counts)
    if n == 1:
        x_step = 0
    else:
        x_step = (x_right - x_left) / (n - 1)
    points = []
    for i, c in enumerate(counts):
        x = x_left + i * x_step
        y = y_bottom - (c / y_max) * (y_bottom - y_top) if y_max > 0 else y_bottom
        points.append(f"{x:.0f} {y:.0f}")
    return "M " + " L ".join(points)


def _sparkline_d(counts: list[int]) -> str:
    """sparkline 60×18 viewBox path."""
    if not counts:
        return ""
    mx = max(counts) or 1
    n = len(counts)
    x_step = 60 / max(n - 1, 1)
    points = []
    for i, c in enumerate(counts):
        x = i * x_step
        y = 17 - (c / mx) * 15
        points.append(f"{x:.0f} {y:.1f}")
    return "M " + " L ".join(points)


def _delta_pct(counts: list[int]) -> int:
    """첫 1/3 평균 → 마지막 1/3 평균 변화율 (%)."""
    if not counts or len(counts) < 3:
        return 0
    n = len(counts)
    third = max(n // 3, 1)
    head = sum(counts[:third]) / third
    tail = sum(counts[-third:]) / third
    if head == 0:
        return 100 if tail > 0 else 0
    return round((tail - head) / head * 100)


@st.cache_data(ttl=60)
def _board_trend() -> dict[str, str]:
    """⑤ 트렌드 섹션 — 동적 SVG + 키워드 리스트.

    Returns dict with placeholders:
      svg_paths, xticks, anno_name, anno_sub,
      y_4..y_1 (Y-axis 라벨), kw_list (6 li rows)
    """
    labels, series = _weekly_keyword_series(weeks=8)
    if not series:
        empty = ('<div style="grid-column:1/-1; padding:32px 18px; text-align:center;'
                 ' color:var(--text-muted); font-size:14px; border:1px dashed'
                 ' var(--surface-divider); border-radius:12px;">'
                 '아직 트렌드를 그릴 수 있는 데이터가 부족해요.<br>'
                 '<span style="font-size:12.5px;">30일 이상 수집 후 키워드 출현 빈도가 누적되면 표시됩니다.</span>'
                 '</div>')
        return {
            "svg_paths": "", "xticks": "", "anno_name": "", "anno_sub": "",
            "y_4": "", "y_3": "", "y_2": "", "y_1": "",
            "kw_list": "", "empty": empty,
        }

    # 차트는 상위 4 시리즈만, 키워드 리스트는 6개 전체
    chart_series = series[:4]
    y_max = max((max(s["counts"]) for s in chart_series), default=1) or 1
    # Y label nice round (1.25× 마진)
    nice_max = max(int((y_max * 1.25) // 5 + 1) * 5, 5)

    # SVG paths
    svg_lines = []
    for i, s in enumerate(chart_series):
        d = _path_d(s["counts"], nice_max)
        color = _TREND_COLORS[i]
        dash = ' stroke-dasharray=\'3 3\'' if i == 3 else ''
        svg_lines.append(
            f"<path d='{d}' fill='none' stroke='{color}' "
            f"stroke-width='2.2' stroke-linecap='round'{dash}/>"
        )
    # 어노 marker: top series 마지막 점
    top_counts = chart_series[0]["counts"]
    last_x = 540
    last_y = 180 - (top_counts[-1] / nice_max) * 160 if nice_max > 0 else 180
    svg_lines.append(
        f"<circle cx='{last_x:.0f}' cy='{last_y:.0f}' r='5' fill='#fff' "
        f"stroke='{_TREND_COLORS[0]}' stroke-width='2.4'/>"
    )

    # X-axis ticks
    xticks = "".join(f"<span>{_html.escape(l)}</span>" for l in labels)

    # 어노테이션 — 가장 큰 delta 키워드
    deltas = [(s["name"], _delta_pct(s["counts"])) for s in chart_series]
    deltas.sort(key=lambda x: x[1], reverse=True)
    top_name, top_delta = deltas[0]
    anno_name = f"{_html.escape(top_name)} {'↑' if top_delta > 0 else ('↓' if top_delta < 0 else '·')}"
    anno_sub = (f"8주간 {'+' if top_delta >= 0 else ''}{top_delta}% — 산업 분기점 가능성"
                if abs(top_delta) >= 20
                else f"8주간 {'+' if top_delta >= 0 else ''}{top_delta}% — 추세 관찰 중")

    # Y labels — 4 ticks
    y_4 = str(nice_max)
    y_3 = str(round(nice_max * 0.75))
    y_2 = str(round(nice_max * 0.5))
    y_1 = str(round(nice_max * 0.25))

    # 키워드 리스트 (6개)
    kw_parts = []
    for i, s in enumerate(series[:6]):
        color = _TREND_KW_COLORS[i]
        delta = _delta_pct(s["counts"])
        if delta >= 20:
            num_cls, delta_str = "db-good", f"+{delta}%"
        elif delta <= -20:
            num_cls, delta_str = "db-bad", f"{delta}%"
        else:
            num_cls = "db-flat"
            delta_str = f"+{delta}%" if delta >= 0 else f"{delta}%"
        spark_d = _sparkline_d(s["counts"])
        spark_svg = (
            f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 60 18' "
            f"preserveAspectRatio='none'><path d='{spark_d}' fill='none' "
            f"stroke='{color}' stroke-width='1.4'/></svg>"
        )
        kw_parts.append(
            f'<li class="db-kw-row">'
            f'<span class="db-kw-dot" style="background:{color};"></span>'
            f'<span class="db-kw-name">{_html.escape(s["name"])}</span>'
            f'<span class="db-kw-spark">{spark_svg}</span>'
            f'<b class="db-kw-num {num_cls}">{delta_str}</b>'
            f'</li>'
        )
    kw_list = "\n".join(kw_parts)

    return {
        "svg_paths": "\n".join(svg_lines),
        "xticks": xticks,
        "anno_name": anno_name,
        "anno_sub": anno_sub,
        "y_4": y_4, "y_3": y_3, "y_2": y_2, "y_1": y_1,
        "kw_list": kw_list,
        "empty": "",
    }


@st.cache_data(ttl=60)
def _board_matrix_html() -> str:
    """⑥ 기회 매트릭스 — score_cells 상위 6개를 ROI×난이도 좌표로 매핑.

    좌표 휴리스틱 (cell metric 만 사용):
      - ROI 축 (top%) : matched_news 정규화 → 클수록 상단
      - 난이도 축 (left%) : matched_tasks 정규화 → 클수록 우측 (= 적용 가능
        작업 많음 = 실행 쉬움). X축 라벨 '← 실행 난이도' 와 일치.
      - 버블 크기 (px) : cell_score 정규화 → 14~32px
      - 우상단(쉬움+ROI높음) → db-mx-strong, 좌하단 → db-mx-soft 토글
    """
    try:
        news_df = _news_db.load_news_for_days(days=14)
        roadmap_df = _load_roadmap()
    except Exception:
        news_df = None
        roadmap_df = None

    if news_df is None or news_df.empty or roadmap_df is None or roadmap_df.empty:
        return _matrix_empty_html()

    try:
        cells = _score_cells(news_df, roadmap_df).head(6)
    except Exception:
        return _matrix_empty_html()
    if cells.empty:
        return _matrix_empty_html()

    max_news = max(int(cells["matched_news"].max()), 1)
    max_tasks = max(int(cells["matched_tasks"].max()), 1)
    max_score = max(float(cells["cell_score"].max()), 1.0)

    bubbles = []
    detail_row = cells.iloc[0]
    for _, row in cells.iterrows():
        roi_norm = int(row.get("matched_news", 0) or 0) / max_news
        ease_norm = int(row.get("matched_tasks", 0) or 0) / max_tasks
        score_norm = float(row.get("cell_score", 0) or 0) / max_score

        top_pct = 90 - roi_norm * 78
        left_pct = 10 + ease_norm * 80
        size_px = round(14 + score_norm * 18)

        label = str(row.get("lv3", "") or row.get("dept", "") or "—")
        title = f"{row.get('dept', '')} · {label}"

        extra_cls = ""
        if left_pct >= 55 and top_pct <= 40:
            extra_cls = " db-mx-strong"
        elif left_pct <= 35 and top_pct >= 60:
            extra_cls = " db-mx-soft"

        bubbles.append(
            f'<button class="db-mx-bubble{extra_cls}" '
            f'style="left:{left_pct:.0f}%; top:{top_pct:.0f}%;" '
            f'title="{_html.escape(title)}" disabled>'
            f'<span class="db-mx-bsize" style="--s: {size_px}px;"></span>'
            f'<span class="db-mx-blabel">{_html.escape(label[:14])}</span>'
            f'</button>'
        )

    # detail panel — 1위 cell
    detail_label = _html.escape(str(detail_row.get("lv3", "") or "—"))
    detail_dept = _html.escape(str(detail_row.get("dept", "") or ""))
    roi_val = int(detail_row.get("matched_news", 0) or 0)
    ease_val = int(detail_row.get("matched_tasks", 0) or 0)
    score_val = round(float(detail_row.get("cell_score", 0) or 0))
    sample_tasks = str(detail_row.get("sample_tasks", "") or "").split(" · ")[:1]
    why_text = (
        f"{detail_dept} 영역의 {detail_label} 작업과 매칭 뉴스 {roi_val}건이 누적, "
        f"관련 작업 {ease_val}건이 잠재 적용 대상."
        if not sample_tasks or not sample_tasks[0]
        else f"{detail_dept} · {_html.escape(sample_tasks[0])[:80]} — 매칭 뉴스 {roi_val}건."
    )

    return f"""<div class="db-matrix-wrap">
        <div class="db-matrix">
          <div class="db-mx-ylabel">ROI 점수 →</div>
          <div class="db-mx-xlabel">← 실행 난이도</div>
          <div class="db-mx-plot">
            <div class="db-mx-line db-mx-line-v"></div>
            <div class="db-mx-line db-mx-line-h"></div>
            <span class="db-mx-q db-mx-q-tl">예측 R&amp;D</span>
            <span class="db-mx-q db-mx-q-tr db-mx-q-strong">즉시 PoC 후보</span>
            <span class="db-mx-q db-mx-q-bl">관찰 대기</span>
            <span class="db-mx-q db-mx-q-br">소규모 트라이얼</span>
            {"".join(bubbles)}
          </div>
        </div>
        <aside class="db-mx-detail">
          <div class="db-mx-detail-eye">선택됨 · 1위</div>
          <h4 class="db-mx-detail-h">{detail_dept} · {detail_label}</h4>
          <div class="db-mx-stats">
            <div><b class="db-good">{score_val}</b><span>종합 점수</span></div>
            <div><b>{roi_val}</b><span>매칭 뉴스</span></div>
            <div><b>{ease_val}</b><span>매칭 작업</span></div>
          </div>
          <p class="db-mx-why">{why_text}</p>
          <button class="db-mx-cta" disabled>
            제안서 작업장에서 보기
          </button>
        </aside>
      </div>"""


def _board_kw_mgr_html(persona: Persona) -> str:
    """⑦ 내 키워드 관리 — SOLA 자동 추출 + 페르소나 관심사 그룹.

    Group 1: top_keywords(news_30d) 상위 6개 (히트 = count, tier dot)
    Group 2: persona.interest_lv3 + interest_tasks (최대 4) — 30d 본문 substring
             count 로 히트 산출
    Summary: 키워드 수 / 예상 일별 수집량(전체 30d/30) / 출처 수
    """
    try:
        news_30 = _news_db.load_news_for_days(days=30)
    except Exception:
        news_30 = None
    if news_30 is None or news_30.empty:
        return _kw_mgr_empty_html()

    # Group 1
    try:
        top_df = _trends.top_keywords(news_30, top_n=6)
    except Exception:
        top_df = None
    auto_chips: list[str] = []
    if top_df is not None and not top_df.empty:
        max_c = max(int(top_df["count"].max()), 1)
        for _, r in top_df.iterrows():
            kw = str(r["keyword"])
            c = int(r["count"])
            ratio = c / max_c
            dot_cls = (
                "db-good-dot" if ratio >= 0.5
                else "db-mid-dot" if ratio >= 0.2
                else "db-low-dot"
            )
            auto_chips.append(
                f'<span class="db-kchip">'
                f'<span class="db-kchip-dot {dot_cls}"></span>'
                f'{_html.escape(kw)}'
                f'<span class="db-kchip-hits">{c}</span>'
                f'<button class="db-kchip-x" disabled>×</button>'
                f'</span>'
            )

    # Group 2 — persona 관심사
    user_terms = list(persona.interest_tasks) + list(persona.interest_lv3)
    # 중복 제거 유지순서
    seen = set()
    user_terms = [t for t in user_terms if t and not (t in seen or seen.add(t))][:4]

    user_chips: list[str] = []
    if user_terms:
        hay_cols = [c for c in ("title", "summary", "summary_llm", "keywords",
                                 "keywords_llm", "content") if c in news_30.columns]
        for term in user_terms:
            hits = 0
            if hay_cols:
                mask = pd.Series(False, index=news_30.index)
                for col in hay_cols:
                    mask |= news_30[col].fillna("").astype(str).str.contains(
                        term, regex=False, case=False
                    )
                hits = int(mask.sum())
            user_chips.append(
                f'<span class="db-kchip db-kchip-user">'
                f'{_html.escape(term)}'
                f'<span class="db-kchip-hits">{hits}</span>'
                f'<button class="db-kchip-x" disabled>×</button>'
                f'</span>'
            )

    add_inline = (
        '<span class="db-kw-add-inline">'
        '+ 키워드 추가 + 즉시 수집'
        '</span>'
    )

    # Summary
    total_kw = len(auto_chips) + len(user_chips)
    daily_avg = round(len(news_30) / 30) if len(news_30) > 0 else 0
    n_sources = int(news_30["source"].nunique()) if "source" in news_30.columns else 0

    g1_head = (
        f'<div class="db-kwg-head">'
        f'<span class="db-kwg-mark">★ SOLA 자동 추출 {len(auto_chips)}</span>'
        f'<span class="db-kwg-meta">최근 30일 빈도 상위</span>'
        f'</div>'
    )
    g1_chips = (
        f'<div class="db-kwg-chips">{"".join(auto_chips)}</div>'
        if auto_chips
        else '<div class="db-kwg-chips"><span class="db-kwg-meta">아직 추출된 키워드가 없어요.</span></div>'
    )

    g2_head = (
        f'<div class="db-kwg-head">'
        f'<span class="db-kwg-mark db-kwg-mark-user">◉ 내가 추가 {len(user_chips)}</span>'
        f'<span class="db-kwg-meta">페르소나 관심사 기반 · 우선 가중치</span>'
        f'</div>'
    )
    g2_chips_inner = "".join(user_chips) + add_inline
    if not user_chips:
        g2_chips_inner = (
            '<span class="db-kwg-meta">페르소나에서 관심 작업을 선택하면 여기에 표시됩니다.</span>'
            + add_inline
        )

    summary = (
        f'<div class="db-kw-summary">'
        f'<div class="db-kw-sum-num"><span>{total_kw}</span><small>개</small></div>'
        f'<div class="db-kw-sum-sep"></div>'
        f'<div class="db-kw-sum-info">'
        f'<div class="db-kw-sum-t">최근 30일 평균 <b>~ {daily_avg}건/일</b> 수집 · 출처 {n_sources}개</div>'
        f'<div class="db-kw-sum-s">희소(주황) 키워드는 시그널이 옅을 수 있어요 — 30일 모니터링 후 재평가됩니다.</div>'
        f'</div>'
        f'<button class="db-kw-sum-cta" disabled>지금 즉시 수집 실행</button>'
        f'</div>'
    )

    return f"""<div class="db-kw-mgr">
        <div class="db-kwg">{g1_head}{g1_chips}</div>
        <div class="db-kwg">{g2_head}<div class="db-kwg-chips">{g2_chips_inner}</div></div>
        {summary}
      </div>"""


def _kw_mgr_empty_html() -> str:
    return ('<div style="padding: 32px 18px; text-align: center; color: var(--text-muted);'
            ' font-size: 14px; border: 1px dashed var(--surface-divider); border-radius: 12px;">'
            '아직 키워드를 분석할 데이터가 없어요.<br>'
            '<span style="font-size:12.5px;">데이터 관리에서 수집을 시작하세요.</span>'
            '</div>')


def _matrix_empty_html() -> str:
    return ('<div style="padding: 32px 18px; text-align: center; color: var(--text-muted);'
            ' font-size: 14px; border: 1px dashed var(--surface-divider); border-radius: 12px;">'
            '아직 매트릭스에 그릴 자동화 기회가 없어요.<br>'
            '<span style="font-size:12.5px;">뉴스 + 로드맵 매칭 후 자동으로 채워집니다.</span>'
            '</div>')


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

    # ── 2.5) LLM 미설정 안내 (설정 완료 시 no-op) ──
    app_shell.render_setup_banner_if_needed()

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
        .replace("{{BOARD_TREND}}", _board_trend_block_html())
        .replace("{{BOARD_MATRIX}}", _board_matrix_html())
        .replace("{{BOARD_KW_MGR}}", _board_kw_mgr_html(persona))
    )
    brief = _brief_html()
    html_out = (
        html_out
        .replace("{{BRIEF_SUMMARY}}", brief["summary"])
        .replace("{{BRIEF_LIST}}", brief["list"])
        .replace("{{BRIEF_CITES}}", brief["cites"])
    )
    st.html(html_out)


def _board_trend_block_html() -> str:
    """{{BOARD_TREND}} 자리에 들어갈 트렌드 섹션 전체 HTML 빌드."""
    t = _board_trend()
    if t["empty"]:
        return t["empty"]
    return f"""<div class="db-trend">
            <div class="db-trend-chart">
              <div class="db-trend-y">
                <span>{t["y_4"]}</span>
                <span>{t["y_3"]}</span>
                <span>{t["y_2"]}</span>
                <span>{t["y_1"]}</span>
                <span>0</span>
              </div>
              <div class="db-trend-plot">
                <svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 560 200' preserveAspectRatio='none' class='db-trend-svg' style='width:100%; height:100%;'>
                  <line x1='0' y1='40'  x2='560' y2='40'  stroke='#E5E7EB' stroke-dasharray='2 4'/>
                  <line x1='0' y1='80'  x2='560' y2='80'  stroke='#E5E7EB' stroke-dasharray='2 4'/>
                  <line x1='0' y1='120' x2='560' y2='120' stroke='#E5E7EB' stroke-dasharray='2 4'/>
                  <line x1='0' y1='160' x2='560' y2='160' stroke='#E5E7EB' stroke-dasharray='2 4'/>
                  {t["svg_paths"]}
                </svg>
                <div class="db-trend-x">{t["xticks"]}</div>
                <div class="db-trend-anno" style="right: 8px; top: 8px;">
                  <div class="db-anno-arrow"></div>
                  <div>
                    <div class="db-anno-t">{t["anno_name"]}</div>
                    <div class="db-anno-s">{t["anno_sub"]}</div>
                  </div>
                </div>
              </div>
            </div>
            <ul class="db-kw-list">
              {t["kw_list"]}
            </ul>
          </div>"""
