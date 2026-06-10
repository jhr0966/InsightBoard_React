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
import json as _json
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

import pandas as pd
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

logger = logging.getLogger(__name__)


# 탑 스토리: lead 1 + side 4 = 5
_LEAD_STORY_COUNT = 1
_SIDE_STORY_COUNT = 4


# 부서 색상 팔레트 — 보드 매트릭스 + 인사이트 매트릭스 공유 (단일 진실).
MATRIX_DEPT_COLORS: dict[str, str] = {
    "도장": "#2563EB",
    "용접": "#14B8A6",
    "의장": "#F59E0B",
    "조립": "#6366F1",
    "절단": "#0EA5E9",
}
MATRIX_DEPT_FALLBACK = "#475569"


def _sola_handoff_href(from_kind: str, **payload: str) -> str:
    """SOLA 작업실 인계 URL. from_kind 와 payload 모두 quote 처리.

    예) `_sola_handoff_href("opp", dept="도장", lv3="비전 검사")`
        → "?app_area=🤖+SOLA+작업실&from=opp&dept=도장&lv3=비전 검사"
    """
    parts = [f"app_area={quote('🤖 SOLA 작업실')}", f"from={quote(from_kind)}"]
    for k, v in payload.items():
        if v:
            parts.append(f"{k}={quote(str(v))}")
    return "?" + "&".join(parts)


def _opp_action_href(action: str, *, dept: str, lv3: str, title: str = "") -> str:
    """자동화 기회 카드 보류/채택 URL — 같은 area(보드) 머무름.

    예) `_opp_action_href("accept", dept="도장", lv3="비전 검사", title="X")`
        → "?app_area=📊+오늘의+보드&opp_action=accept&dept=&lv3=&title="
    """
    parts = [
        f"app_area={quote('📊 오늘의 보드')}",
        f"opp_action={quote(action)}",
        f"dept={quote(dept or '')}",
        f"lv3={quote(lv3 or '')}",
    ]
    if title:
        parts.append(f"title={quote(title)}")
    return "?" + "&".join(parts)


# 자동화 기회 액션 → bookmark 상태 매핑
_OPP_ACTION_TO_STATUS: dict[str, str] = {
    "accept": "adopted",
    "hold": "pending",
}


def consume_opp_action_if_any() -> tuple[str, str, str] | None:
    """`?opp_action=accept|hold&dept=&lv3=&title=` 1회 소비 → bookmark 추가.

    반환: 성공 시 (action, dept, lv3), 아니면 None.
    부수효과: bookmarks_store.add + session_state["_opp_action_toast"] +
    query strip (재실행 방지).
    """
    action = st.query_params.get("opp_action")
    dept_q = st.query_params.get("dept", "")
    lv3_q = st.query_params.get("lv3", "")
    title_q = st.query_params.get("title", "")

    if action not in _OPP_ACTION_TO_STATUS:
        return None

    status = _OPP_ACTION_TO_STATUS[action]
    bm_title = title_q or f"{dept_q} · {lv3_q} 자동화 기회"
    try:
        from store.bookmarks import Bookmark
        import uuid as _uuid
        bm = Bookmark(
            id="bm_" + _uuid.uuid4().hex[:12],
            type="proposal",
            title=bm_title,
            content="",
            tags=[dept_q, lv3_q] if (dept_q or lv3_q) else [],
            created_at="",
            status=status,
        )
        bookmarks_store.add(bm)
        verb = "채택" if action == "accept" else "보류"
        st.session_state["_opp_action_toast"] = (
            "ok", f"✅ '{bm_title[:60]}' 을 {verb} 상태로 산출물 보관함에 추가했어요."
        )
    except Exception as exc:
        st.session_state["_opp_action_toast"] = (
            "error", f"⚠️ 처리 실패: {type(exc).__name__}: {exc}",
        )

    # query strip (재실행 방지)
    for k in ("opp_action", "dept", "lv3", "title"):
        if k in st.query_params:
            del st.query_params[k]
    return (action, dept_q, lv3_q)


def render_opp_action_toast_if_needed() -> None:
    """직전 액션 직후 한 번만 노출되는 inline toast."""
    _render_inline_toast("_opp_action_toast")


def _render_inline_toast(session_key: str) -> None:
    """공용 inline toast 렌더 — session_key 에서 (kind, message) 를 1회 소비."""
    payload = st.session_state.pop(session_key, None)
    if not payload:
        return
    kind, message = payload
    bg, border, color = {
        "ok":    ("#ECFDF5", "#A7F3D0", "#064E3B"),
        "error": ("#FEF2F2", "#FECACA", "#991B1B"),
    }.get(kind, ("#F1F5F9", "#CBD5E1", "#0F172A"))
    safe = _html.escape(message)
    st.html(
        f'<div style="margin: 0 24px 14px; padding: 10px 14px; '
        f'background: {bg}; border: 1px solid {border}; border-radius: 8px; '
        f'font-size: 13px; color: {color}; font-weight: 600;">{safe}</div>'
    )


# ── ⑦ 키워드 관리 wire — × 삭제 + 즉시 수집 ──────────────────────
_KW_ACTIONS = {"del_user", "mute", "collect"}


def _kw_action_href(action: str, *, keyword: str = "") -> str:
    """키워드 관리 액션 URL — 같은 area(보드) 머무름.

    예) `_kw_action_href("mute", keyword="AI")`
        → "?app_area=📊+오늘의+보드&kw_action=mute&keyword=AI"
        `_kw_action_href("collect")`
        → "?app_area=📊+오늘의+보드&kw_action=collect"
    """
    parts = [
        f"app_area={quote('📊 오늘의 보드')}",
        f"kw_action={quote(action)}",
    ]
    if keyword:
        parts.append(f"keyword={quote(keyword)}")
    return "?" + "&".join(parts)


def consume_kw_action_if_any() -> tuple[str, str] | None:
    """`?kw_action=del_user|mute|collect&keyword=` 1회 소비.

    - del_user: persona.interest_lv3 / interest_tasks 에서 keyword 제거 → save
    - mute:    persona.muted_keywords 에 keyword 추가(중복 제거) → save
    - collect: persona 의 모든 키워드(자동 추출 제외) 로 collect_batch 실행

    반환: 성공 시 (action, keyword), 알 수 없는 action 이면 None (쿼리 유지).
    부수효과: persona save / scraping 실행 / session_state["_kw_action_toast"] /
    query strip.
    """
    action = st.query_params.get("kw_action")
    keyword = (st.query_params.get("keyword", "") or "").strip()

    if action not in _KW_ACTIONS:
        return None

    try:
        from persona import store as persona_store
        persona = app_shell.get_persona()

        if action == "del_user":
            removed = False
            if keyword in persona.interest_tasks:
                persona.interest_tasks = [k for k in persona.interest_tasks if k != keyword]
                removed = True
            if keyword in persona.interest_lv3:
                persona.interest_lv3 = [k for k in persona.interest_lv3 if k != keyword]
                removed = True
            persona_store.save(persona)
            st.session_state["persona"] = persona
            if removed:
                st.session_state["_kw_action_toast"] = (
                    "ok", f"✅ '{keyword}' 키워드를 관심사에서 제거했어요."
                )
            else:
                st.session_state["_kw_action_toast"] = (
                    "ok", f"ℹ️ '{keyword}' 은(는) 관심사에 없어요."
                )

        elif action == "mute":
            if not keyword:
                return (action, keyword)
            muted = list(persona.muted_keywords or [])
            if keyword not in muted:
                muted.append(keyword)
                persona.muted_keywords = muted
                persona_store.save(persona)
                st.session_state["persona"] = persona
            st.session_state["_kw_action_toast"] = (
                "ok", f"🔕 '{keyword}' 키워드를 자동 추출에서 숨겼어요."
            )

        elif action == "collect":
            # 관심사가 비어도 기본 키워드(자동화·AI)로 폴백 + 키워드 무관 소스
            # (tech·RSS)는 항상 수집 → '지금 뉴스 수집' 이 빈 페르소나에서도 동작.
            kws, used_default = _collect_keywords_with_default(persona)
            extra_feeds = _collect_extra_feeds()
            from scraping.run_daily import collect_batch
            report = collect_batch(kws, max_results=10, extra_feeds=extra_feeds)
            try:  # 런 로그 기록 — '수집 헬스' 가 읽음. 로깅 실패가 수집을 깨면 안 됨.
                from store import run_log
                run_log.record_run(report, trigger="board")
            except Exception:  # noqa: BLE001
                pass
            n_files = report.total_files
            n_articles = report.total_articles
            n_err = len(report.errors)
            if n_err and n_articles == 0:
                st.session_state["_kw_action_toast"] = (
                    "error",
                    f"⚠️ 수집 실패: {report.errors[0].get('error','unknown')}",
                )
            else:
                kw_label = (
                    "기본 키워드(자동화·AI)" if used_default else f"{len(kws)}개 키워드"
                )
                st.session_state["_kw_action_toast"] = (
                    "ok",
                    f"✅ {kw_label}로 {n_articles}건 수집 "
                    f"({n_files}개 파일){f', 일부 오류 {n_err}건' if n_err else ''}.",
                )
            try:
                _board_kpis.clear()
            except Exception:
                pass
    except Exception as exc:
        st.session_state["_kw_action_toast"] = (
            "error", f"⚠️ 처리 실패: {type(exc).__name__}: {exc}",
        )

    # query strip (재실행 방지)
    for k in ("kw_action", "keyword"):
        if k in st.query_params:
            del st.query_params[k]
    return (action, keyword)


def _collect_keywords_for_persona(persona: Persona) -> list[str]:
    """수집 대상 키워드 — 페르소나 관심사(중복 제거, 빈 값 제거)."""
    raw = list(persona.interest_tasks or []) + list(persona.interest_lv3 or [])
    seen: set[str] = set()
    out: list[str] = []
    for kw in raw:
        k = (kw or "").strip()
        if k and k not in seen:
            seen.add(k)
            out.append(k)
    return out


# 페르소나 관심사가 비어 있을 때 네이버/구글 검색에 쓰는 기본 키워드.
# (tech 사이트·커스텀 RSS 는 키워드 무관하게 항상 수집되므로 여기엔 키워드 기반
#  소스용 폴백만 둔다.) 이게 있어야 '지금 뉴스 수집' 이 빈 페르소나에서도 동작한다.
DEFAULT_COLLECT_KEYWORDS: tuple[str, ...] = ("자동화", "AI")


def _collect_keywords_with_default(persona: Persona) -> tuple[list[str], bool]:
    """수집 키워드 — 페르소나 관심사, 비어 있으면 기본 키워드(자동화·AI)로 폴백.

    반환: (키워드 리스트(항상 1개 이상), 기본 키워드 폴백 사용 여부).
    """
    kws = _collect_keywords_for_persona(persona)
    if kws:
        return kws, False
    return list(DEFAULT_COLLECT_KEYWORDS), True


def _collect_extra_feeds() -> list[tuple[str, str]]:
    """현재 등록된 커스텀 RSS 출처 — `collect_batch(extra_feeds=)` 형태."""
    try:
        from store import sources as _src_store
        return [(c.name, c.url) for c in _src_store.custom_sources()]
    except Exception:
        return []


def render_kw_action_toast_if_needed() -> None:
    """⑦ 키워드 관리 액션 직후 한 번만 노출되는 inline toast."""
    _render_inline_toast("_kw_action_toast")


def _md_bold_to_html(text: str) -> str:
    """`**키워드**` 마크다운만 `<b>` 로 변환, 그 외는 모두 HTML escape.

    LLM 응답의 굵은 키워드 강조를 안전하게 렌더하기 위함. ** 외 다른 마크다운
    (헤더·리스트·링크 등)은 처리하지 않는다 (시스템 프롬프트가 금지함).
    """
    if not text:
        return ""
    parts = re.split(r"(\*\*[^*\n]+\*\*)", text)
    out: list[str] = []
    for p in parts:
        if p.startswith("**") and p.endswith("**") and len(p) > 4:
            out.append(f"<b>{_html.escape(p[2:-2])}</b>")
        else:
            out.append(_html.escape(p))
    return "".join(out)


# ── 보드 음성으로 듣기 (TTS) — Web Speech API 인라인 재생 ───────


def _tts_button_html(text: str, *, label: str = "음성으로 듣기",
                     cls: str = "db-act db-act-tts") -> str:
    """간단 TTS 버튼 — onclick 에서 Web Speech API 호출 (서버 무관).

    - 텍스트는 `json.dumps` 로 JS 안전 인코딩 → `data-tts` 속성에 escape
    - 클릭 시 `JSON.parse(this.dataset.tts)` → `SpeechSynthesisUtterance(ko-KR)`
    - 같은 페이지에 여러 버튼 가능, 새 재생 시 직전 재생 cancel
    - 빈 텍스트면 빈 문자열 반환(버튼 미노출)
    """
    payload = (text or "").strip()
    if not payload:
        return ""
    safe_attr = _html.escape(_json.dumps(payload, ensure_ascii=False), quote=True)
    return (
        f'<button class="{cls}" type="button" data-tts="{safe_attr}" '
        f'onclick="(function(b){{var s=window.speechSynthesis;if(!s)return;'
        f"s.cancel();var u=new SpeechSynthesisUtterance(JSON.parse(b.dataset.tts));"
        f"u.lang='ko-KR';u.rate=1.0;u.pitch=1.0;s.speak(u);}})(this);\" "
        f'title="이 문단을 음성으로 재생합니다 (브라우저 TTS)">'
        f'<img src="data:image/svg+xml;utf8,<svg xmlns=\'http://www.w3.org/2000/svg\' '
        f'width=\'11\' height=\'11\' viewBox=\'0 0 24 24\' fill=\'none\' stroke=\'#475569\' '
        f'stroke-width=\'2.4\' stroke-linecap=\'round\' stroke-linejoin=\'round\'>'
        f'<polygon points=\'11 5 6 9 2 9 2 15 6 15 11 19 11 5\'/>'
        f'<path d=\'M19.07 4.93a10 10 0 010 14.14M15.54 8.46a5 5 0 010 7.07\'/>'
        f'</svg>" width="11" height="11" alt="" />{_html.escape(label)}</button>'
    )


def _tts_disabled_html(label: str = "음성으로 듣기") -> str:
    """TTS 대상 텍스트가 없을 때 disabled 버튼."""
    return (
        f'<button class="db-act db-act-tts" disabled title="재생할 내용이 없어요">'
        f'<img src="data:image/svg+xml;utf8,<svg xmlns=\'http://www.w3.org/2000/svg\' '
        f'width=\'11\' height=\'11\' viewBox=\'0 0 24 24\' fill=\'none\' stroke=\'#94A3B8\' '
        f'stroke-width=\'2.4\' stroke-linecap=\'round\' stroke-linejoin=\'round\'>'
        f'<polygon points=\'11 5 6 9 2 9 2 15 6 15 11 19 11 5\'/>'
        f'<path d=\'M19.07 4.93a10 10 0 010 14.14M15.54 8.46a5 5 0 010 7.07\'/>'
        f'</svg>" width="11" height="11" alt="" />{_html.escape(label)}</button>'
    )

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

    article = f"""<article class="db-lead">
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
    link = str(row.get("link", "") or "").strip()
    if link:
        return (
            f'<a href="{_html.escape(link)}" target="_blank" rel="noopener" '
            'style="text-decoration:none; color:inherit; display:block;">'
            f'{article}</a>'
        )
    return article


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

    article = f"""<article class="db-story">
      <div class="db-story-meta">
        <span class="db-src"><span class="db-src-mark" style="background:{gradient};"></span>{source_safe}</span>
        <span class="db-time">{age}</span>
      </div>
      <h4 class="db-story-h">{title}</h4>
      {f'<p class="db-story-p">{body}</p>' if body else ''}
    </article>"""
    link = str(row.get("link", "") or "").strip()
    if link:
        return (
            f'<a href="{_html.escape(link)}" target="_blank" rel="noopener" '
            'style="text-decoration:none; color:inherit; display:block;">'
            f'{article}</a>'
        )
    return article


@st.cache_data(ttl=60)
def _brief_html(persona_label: str = "") -> dict[str, str]:
    """SOLA 오늘의 브리핑 — 페르소나 매칭 top 3 뉴스 + LLM 1~2문장 요약.

    summary 텍스트는 `sola.board_brief.brief()` (디스크 캐시 + LLM 미설정
    시 룰 fallback) 가 생성. 그 외 list/cites/cta/tts_btn 은 score_matches
    상위 3건 기반.
    """
    news_df = None
    with guard("보드 브리핑 — 뉴스(3d) 로드"):
        news_df = _news_db.load_news_for_days(days=3)
    tasks_df = None
    with guard("보드 브리핑 — 작업 정의 로드"):
        tasks_df = _load_tasks()

    items: list[dict] = []
    if (
        news_df is not None and not news_df.empty
        and tasks_df is not None and not tasks_df.empty
    ):
        try:
            matches = _score_matches(news_df, tasks_df, top_k=3, semantic_weight=_SEM_W)
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
        except Exception:  # noqa: BLE001 — 데이터-경로: silent 실패가 잘못된 폴백을 부르므로 로깅
            logger.warning("데일리 브리핑 매칭-뉴스 처리 실패", exc_info=True)

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
        st.session_state.pop("_board_brief_items", None)
        return {
            "summary": '<div class="db-brief-greet">'
                       '<span class="db-brief-greet-tag">요약</span>'
                       '아직 수집된 뉴스가 없어요. 뉴스 수집에서 수집을 시작하세요.'
                       '</div>',
            "list": "",
            "cites": "",
            "cta": "",
            "tts_btn": _tts_disabled_html(),
        }

    # SOLA workshop 컨텍스트 인계용 — 다음 rerun 에서 from=brief 가 들어오면 소비
    st.session_state["_board_brief_items"] = items

    # 한 줄 요약 — LLM 1~2문장 (sola.board_brief), 실패/미설정 시 룰 fallback
    try:
        # news_df 의 summary 컬럼이 있으면 items 에도 보강 — LLM 압축 품질↑
        for item in items:
            try:
                row = news_df[news_df["link"] == item.get("link", "")].head(1) \
                    if news_df is not None and "link" in news_df.columns else None
                if row is not None and not row.empty and "summary" in row.columns:
                    item["summary"] = str(row.iloc[0].get("summary", "") or "")
            except Exception:
                pass
        from sola.board_brief import brief as _llm_brief
        summary_text = _llm_brief(items, persona_label=persona_label or "").strip()
    except Exception:
        summary_text = ""
    if not summary_text:
        summary_text = (
            f"최근 매칭된 뉴스 {len(items)}건이 두드러집니다."
            if len(items) > 0 else "오늘 매칭된 뉴스가 없습니다."
        )

    # LLM 응답의 **굵은 키워드** 마크다운만 <b> 로 변환 (그 외는 escape)
    summary_html_inner = _md_bold_to_html(summary_text)
    summary_html = (
        '<div class="db-brief-greet">'
        '<span class="db-brief-greet-tag">요약</span>'
        f'{summary_html_inner}'
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

    # CTA — SOLA 작업실로 이 3건 인계
    cta_href = _sola_handoff_href("brief")
    cta_html = (
        f'<a class="db-act db-act-primary" href="{cta_href}" target="_self">'
        f'이 {len(items)}건으로 제안서 만들기 →'
        f'</a>'
    )

    # TTS — 요약 + 번호 매긴 제목 (서버 무관 인라인 재생)
    tts_lines = [summary_text]
    for i, item in enumerate(items, start=1):
        tts_lines.append(f"{i}번. {item['title'][:160]}")
    tts_btn_html = _tts_button_html(" ".join(tts_lines))

    return {"summary": summary_html, "list": list_html, "cites": cites_html,
            "cta": cta_html, "tts_btn": tts_btn_html}


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


def _mx_selected_key() -> str | None:
    """`?mx_select=<dept>|<lv3>` URL state 1회 읽기. 빈 값 → None."""
    raw = (st.query_params.get("mx_select") or "").strip()
    return raw or None


def _mx_select_href(dept: str, lv3: str) -> str:
    """⑥ 매트릭스 셀 선택 URL — 같은 area + `mx_select=<dept>|<lv3>`.

    `_mx_select_href("도장", "비전 검사")` → "?app_area=📊+오늘의+보드&mx_select=도장%7C비전+검사"
    Empty dept/lv3 → 토글 해제(빈 mx_select 생략).
    """
    parts = [f"app_area={quote('📊 오늘의 보드')}"]
    if dept or lv3:
        parts.append(f"mx_select={quote(f'{dept}|{lv3}')}")
    return "?" + "&".join(parts)


@st.cache_data(ttl=60)
def _board_matrix_html(selected_key: str | None = None) -> str:
    """⑥ 기회 매트릭스 — score_cells 상위 6개를 ROI×난이도 좌표로 매핑.

    Args:
        selected_key: "dept|lv3" 형태로 선택된 셀. None 이면 1위 cell.
            URL `?mx_select=` 1회 stateless 인자.

    좌표 휴리스틱 (cell metric 만 사용):
      - ROI 축 (top%) : matched_news 정규화 → 클수록 상단
      - 난이도 축 (left%) : matched_tasks 정규화 → 클수록 우측 (= 적용 가능
        작업 많음 = 실행 쉬움). X축 라벨 '← 실행 난이도' 와 일치.
      - 버블 크기 (px) : cell_score 정규화 → 14~32px
      - 우상단(쉬움+ROI높음) → db-mx-strong, 좌하단 → db-mx-soft 토글
      - 선택된 버블 → db-mx-on 활성 클래스 + 상세 패널 그 셀로 갱신
    """
    news_df = None
    tasks_df = None
    with guard("기회 매트릭스 SVG — 뉴스(14d)·작업 정의 로드"):
        news_df = _news_db.load_news_for_days(days=14)
        tasks_df = _load_tasks()

    if news_df is None or news_df.empty or tasks_df is None or tasks_df.empty:
        return _matrix_empty_html()

    try:
        cells = _score_cells(news_df, tasks_df).head(6)
    except Exception:
        return _matrix_empty_html()
    if cells.empty:
        return _matrix_empty_html()

    max_news = max(int(cells["matched_news"].max()), 1)
    max_tasks = max(int(cells["matched_tasks"].max()), 1)
    max_score = max(float(cells["cell_score"].max()), 1.0)

    # 선택된 셀 결정 — 명시 선택 매칭 우선, 없으면 1위
    detail_row = cells.iloc[0]
    selected_idx = 0
    if selected_key:
        for i, (_, row) in enumerate(cells.iterrows()):
            key = f"{row.get('dept', '') or ''}|{row.get('lv3', '') or ''}"
            if key == selected_key:
                detail_row = row
                selected_idx = i
                break

    bubbles = []
    for i, (_, row) in enumerate(cells.iterrows()):
        roi_norm = int(row.get("matched_news", 0) or 0) / max_news
        ease_norm = int(row.get("matched_tasks", 0) or 0) / max_tasks
        score_norm = float(row.get("cell_score", 0) or 0) / max_score

        top_pct = 90 - roi_norm * 78
        left_pct = 10 + ease_norm * 80
        size_px = round(14 + score_norm * 18)

        label = str(row.get("lv3", "") or row.get("dept", "") or "—")
        dept_raw = str(row.get("dept", "") or "")
        lv3_raw = str(row.get("lv3", "") or "")
        title = f"{dept_raw} · {label}"
        is_selected = (i == selected_idx)

        extra_cls = ""
        if left_pct >= 55 and top_pct <= 40:
            extra_cls = " db-mx-strong"
        elif left_pct <= 35 and top_pct >= 60:
            extra_cls = " db-mx-soft"
        if is_selected:
            extra_cls += " db-mx-on"

        # 활성 셀 클릭 → 토글 해제(빈 mx_select), 비활성 → 그 셀 선택.
        href = _mx_select_href("", "") if is_selected else _mx_select_href(dept_raw, lv3_raw)
        aria = ' aria-current="true"' if is_selected else ""

        bubbles.append(
            f'<a class="db-mx-bubble{extra_cls}" '
            f'href="{href}" target="_self" '
            f'style="left:{left_pct:.0f}%; top:{top_pct:.0f}%;" '
            f'title="{_html.escape(title)}"{aria}>'
            f'<span class="db-mx-bsize" style="--s: {size_px}px;"></span>'
            f'<span class="db-mx-blabel">{_html.escape(label[:12] + ("…" if len(label) > 12 else ""))}</span>'
            f'</a>'
        )

    # detail panel — 선택된 셀(없으면 1위)
    detail_lv3_raw = str(detail_row.get("lv3", "") or "—")
    detail_dept_raw = str(detail_row.get("dept", "") or "")
    detail_label = _html.escape(detail_lv3_raw)
    detail_dept = _html.escape(detail_dept_raw)
    roi_val = int(detail_row.get("matched_news", 0) or 0)
    ease_val = int(detail_row.get("matched_tasks", 0) or 0)
    score_val = round(float(detail_row.get("cell_score", 0) or 0))
    sample_tasks = str(detail_row.get("sample_tasks", "") or "").split(" · ")[:1]
    detail_href = _sola_handoff_href("matrix", dept=detail_dept_raw, lv3=detail_lv3_raw)
    # TTS 원문은 HTML escape 이전(원문)을 사용
    why_text_raw = (
        f"{detail_dept_raw} 영역의 {detail_lv3_raw} 작업과 매칭 뉴스 {roi_val}건이 누적, "
        f"관련 작업 {ease_val}건이 잠재 적용 대상."
        if not sample_tasks or not sample_tasks[0]
        else f"{detail_dept_raw} · {sample_tasks[0][:80]} — 매칭 뉴스 {roi_val}건."
    )
    why_text = (
        f"{detail_dept} 영역의 {detail_label} 작업과 매칭 뉴스 {roi_val}건이 누적, "
        f"관련 작업 {ease_val}건이 잠재 적용 대상."
        if not sample_tasks or not sample_tasks[0]
        else f"{detail_dept} · {_html.escape(sample_tasks[0])[:80]} — 매칭 뉴스 {roi_val}건."
    )
    mx_tts_text = (
        f"{detail_dept_raw} · {detail_lv3_raw}. 종합 점수 {score_val}점. "
        f"매칭 뉴스 {roi_val}건. 매칭 작업 {ease_val}건. {why_text_raw}"
    )
    mx_tts_btn = _tts_button_html(mx_tts_text, label="듣기",
                                  cls="db-mx-tts")

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
          <div class="db-mx-detail-eye">선택됨 · {selected_idx + 1}위</div>
          <h4 class="db-mx-detail-h">{detail_dept} · {detail_label}</h4>
          <div class="db-mx-stats">
            <div><b class="db-good">{score_val}</b><span>종합 점수</span></div>
            <div><b>{roi_val}</b><span>매칭 뉴스</span></div>
            <div><b>{ease_val}</b><span>매칭 작업</span></div>
          </div>
          <p class="db-mx-why">{why_text}</p>
          <div class="db-mx-detail-actions">
            {mx_tts_btn}
            <a class="db-mx-cta" href="{detail_href}" target="_self">
              제안서 작업장에서 보기 →
            </a>
          </div>
        </aside>
      </div>"""


@st.cache_data(ttl=60)
def _board_kw_mgr_html(persona: Persona) -> str:
    """⑦ 내 키워드 관리 — SOLA 자동 추출 + 페르소나 관심사 그룹.

    Group 1: top_keywords(news_30d) 상위 6개 (히트 = count, tier dot)
    Group 2: persona.interest_lv3 + interest_tasks (최대 4) — 30d 본문 substring
             count 로 히트 산출
    Summary: 키워드 수 / 예상 일별 수집량(전체 30d/30) / 출처 수
    """
    news_30 = None
    with guard("키워드 관리 — 뉴스(30d) 로드"):
        news_30 = _news_db.load_news_for_days(days=30)
    if news_30 is None or news_30.empty:
        return _kw_mgr_empty_html()

    # Group 1
    muted = {str(m).strip() for m in (persona.muted_keywords or []) if str(m).strip()}
    top_df = None
    with guard("키워드 관리 — 상위 키워드 산출"):
        # 숨김 키워드를 고려해 여유롭게 가져온 뒤 필터링.
        top_df = _trends.top_keywords(news_30, top_n=6 + len(muted))
    auto_chips: list[str] = []
    if top_df is not None and not top_df.empty:
        # 숨김 처리 + 상위 6개로 truncate
        rows = [r for _, r in top_df.iterrows() if str(r["keyword"]) not in muted][:6]
        max_c = max((int(r["count"]) for r in rows), default=1)
        for r in rows:
            kw = str(r["keyword"])
            c = int(r["count"])
            ratio = c / max_c if max_c else 0
            dot_cls = (
                "db-good-dot" if ratio >= 0.5
                else "db-mid-dot" if ratio >= 0.2
                else "db-low-dot"
            )
            x_href = _kw_action_href("mute", keyword=kw)
            auto_chips.append(
                f'<span class="db-kchip">'
                f'<span class="db-kchip-dot {dot_cls}"></span>'
                f'{_html.escape(kw)}'
                f'<span class="db-kchip-hits">{c}</span>'
                f'<a class="db-kchip-x" href="{x_href}" target="_self" '
                f'title="자동 추출에서 숨기기">×</a>'
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
            x_href = _kw_action_href("del_user", keyword=term)
            user_chips.append(
                f'<span class="db-kchip db-kchip-user">'
                f'{_html.escape(term)}'
                f'<span class="db-kchip-hits">{hits}</span>'
                f'<a class="db-kchip-x" href="{x_href}" target="_self" '
                f'title="관심사에서 제거">×</a>'
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
        f'<a class="db-kw-sum-cta" href="{_kw_action_href("collect")}" '
        f'target="_self">지금 즉시 수집 실행</a>'
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
            '<span style="font-size:12.5px;">뉴스 수집에서 수집을 시작하세요.</span>'
            '</div>')


def _matrix_empty_html() -> str:
    return ('<div style="padding: 32px 18px; text-align: center; color: var(--text-muted);'
            ' font-size: 14px; border: 1px dashed var(--surface-divider); border-radius: 12px;">'
            '아직 매트릭스에 그릴 자동화 기회가 없어요.<br>'
            '<span style="font-size:12.5px;">뉴스 + 작업 정의 매칭 후 자동으로 채워집니다.</span>'
            '</div>')


@st.cache_data(ttl=60)
def _opportunities_html() -> str:
    """자동화 기회 4-grid — opportunity.score_cells → 카드.

    각 cell: dept × lv3 + sample_tasks/sample_news 보유. 시안의 ROI/TRL/기간/
    예산 메트릭은 score 기반 휴리스틱 (실제 cost/timeline 수집 후속 PR).
    """
    news_df = None
    with guard("기회 매트릭스 — 뉴스(14d) 로드"):
        news_df = _news_db.load_news_for_days(days=14)
    tasks_df = None
    with guard("기회 매트릭스 — 작업 정의 로드"):
        tasks_df = _load_tasks()

    if (
        news_df is None or news_df.empty
        or tasks_df is None or tasks_df.empty
    ):
        return _opp_empty_html()

    try:
        cells = _score_cells(news_df, tasks_df)
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
      <span style="font-size:12.5px;">뉴스 수집 + 작업 정의 데이터 업로드 후 자동으로 매칭됩니다.</span>
    </div>"""


def _opp_card_html(row: pd.Series) -> str:
    dept_raw = str(row.get("dept", "") or "—")
    lv3_raw = str(row.get("lv3", "") or "—")
    dept = _html.escape(dept_raw)
    lv3 = _html.escape(lv3_raw)
    cell_score = float(row.get("cell_score", 0) or 0)
    matched_news = int(row.get("matched_news", 0) or 0)
    matched_tasks = int(row.get("matched_tasks", 0) or 0)
    sample_tasks = str(row.get("sample_tasks", "") or "").split(" · ")[:2]
    tagline = " · ".join(sample_tasks) if sample_tasks else f"매칭 뉴스 {matched_news}건"
    tagline_safe = _html.escape(tagline[:60])

    # 신엑셀 정의서의 objective (목표 한 줄) — 있으면 카드에 추가 노출
    objective_raw = str(row.get("sample_objectives", "") or "").strip()
    objective_html = ""
    if objective_raw:
        obj_safe = _html.escape(objective_raw[:80])
        objective_html = f'<div class="db-prop-objective" style="font-size:12.5px; color:#1E3A8A; margin:4px 0 0; line-height:1.45;">🎯 {obj_safe}</div>'

    # 점수 표시 — score 자체가 추상적이라 0-100 범위로 매핑 (cell_score 는 누적)
    roi_score = min(int(cell_score), 99)

    discuss_href = _sola_handoff_href("opp", dept=dept_raw, lv3=lv3_raw)
    hold_href = _opp_action_href("hold", dept=dept_raw, lv3=lv3_raw, title=f"{dept_raw} · {lv3_raw} 자동화 기회")
    accept_href = _opp_action_href("accept", dept=dept_raw, lv3=lv3_raw, title=f"{dept_raw} · {lv3_raw} 자동화 기회")

    return f"""<article class="db-prop">
      <div class="db-prop-top">
        <span class="db-prop-status">초안 0초</span>
        <span class="db-prop-tag db-prop-tag-tech">{lv3}</span>
      </div>
      <h3 class="db-prop-h">{dept} · {lv3} 자동화 기회</h3>
      <div class="db-prop-tagline">{tagline_safe}</div>
      {objective_html}

      <div class="db-prop-metrics">
        <div><b class="db-good">{roi_score}</b><span>점수</span></div>
        <div><b>{matched_news}</b><span>매칭 뉴스</span></div>
        <div><b>{matched_tasks}</b><span>매칭 작업</span></div>
        <div><b>—</b><span>예산</span></div>
      </div>

      <div class="db-prop-actions">
        <a class="db-prop-hold" href="{hold_href}" target="_self" title="보류 — 산출물 보관함에 대기 상태로 추가">보류</a>
        <a class="db-prop-discuss" href="{discuss_href}" target="_self">SOLA와 검토 →</a>
        <a class="db-prop-accept" href="{accept_href}" target="_self" title="채택 — 산출물 보관함에 채택 상태로 추가">채택</a>
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
          <span style="font-size:12.5px;">뉴스 수집 화면에서 수집을 시작하세요.</span>
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


def _clean_board_html(html: str) -> str:
    """보드 템플릿의 죽은 `*.html` 섹션 링크를 실제 area 네비(`?app_area=`)로 재배선.

    "뉴스 라이브러리 →"=뉴스 수집, "전체 보러가기/트렌드/매트릭스 작업장 →"=인사이트.
    기능을 없애지 않고 살린다(사용자 지시). keyword-manager 링크는 템플릿에서 제거됨.
    """
    from urllib.parse import quote as _q
    data_href = "?app_area=" + _q("🗞 뉴스 수집")
    ins_href = "?app_area=" + _q("🔎 인사이트 분석")
    return (
        html
        .replace('href="data-management.html"', f'href="{data_href}" target="_self"')
        .replace('href="insights-analysis.html#trend"', f'href="{ins_href}" target="_self"')
        .replace('href="insights-analysis.html#matrix"', f'href="{ins_href}" target="_self"')
        .replace('href="insights-analysis.html"', f'href="{ins_href}" target="_self"')
    )


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
        from urllib.parse import quote as _q
        href = "?app_area=" + _q("🗞 뉴스 수집")
        return (
            '아직 오늘 수집된 뉴스가 없어요. '
            f'<a href="{href}" '
            'target="_self" style="color:var(--accent-primary); font-weight:700; '
            'text-decoration:none;">뉴스 수집</a>에서 첫 수집을 시작하세요.'
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
    news_df = None
    with guard("보드 KPI — 뉴스(1d) 로드"):
        news_df = _news_db.load_news_for_days(days=1)
    tasks_df = None
    with guard("보드 KPI — 작업 정의 로드"):
        tasks_df = _load_tasks()

    collect = int(len(news_df)) if news_df is not None else 0

    match_count = 0
    opp_count = 0
    if (
        news_df is not None and not news_df.empty
        and tasks_df is not None and not tasks_df.empty
    ):
        try:
            matches = _score_matches(news_df, tasks_df, top_k=3, semantic_weight=_SEM_W)
            if not matches.empty:
                match_count = int(matches[matches["score"] > 0]["link"].nunique())
        except Exception:
            pass
        try:
            cells = _score_cells(news_df, tasks_df)
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


def chat_context_block(persona: Persona) -> str:
    """오늘의 보드 화면이 보여주는 모든 데이터를 LLM 컨텍스트로 packaging.

    사용자가 이 화면을 보다가 SOLA 작업실에서 "이 카드 뭐야?" "트렌드 1위는?"
    같은 질문을 했을 때 LLM 이 화면 콘텐츠를 인식하고 답할 수 있도록.

    이미 cached helper(`_board_kpis`/`_brief_html`/`_score_cells` 등)가 같은
    데이터를 계산해두므로 재호출은 캐시 hit — 추가 비용 거의 없음.
    """
    parts: list[str] = ["--- 현재 화면: 오늘의 보드 (📊) ---"]

    # ① KPI 4
    try:
        kpis = _board_kpis()
        parts.append(
            f"오늘 KPI: 수집 {kpis['collect']}건 · 매칭 {kpis['match']}건 · "
            f"자동화 기회 {kpis['opp']}건 · 채택 대기 {kpis['pending']}건"
        )
    except Exception:
        pass

    # ② SOLA 브리핑 — 보드 진입 시 _brief_html 이 session 에 저장한 items 재사용
    items = st.session_state.get("_board_brief_items") or []
    if items:
        parts.append("② SOLA 브리핑 top 3 매칭 뉴스:")
        for i, it in enumerate(items[:3], 1):
            t = (it.get("title") or "")[:120]
            src = it.get("source") or "—"
            parts.append(f"  {i}. {t} ({src})")

    # ③ + ④ + ⑤ + ⑥ — 매칭/기회 데이터 재사용
    news = None
    tasks = None
    with guard("채팅 컨텍스트 — 뉴스(14d)·작업 정의 로드"):
        news = _news_db.load_news_for_days(days=14)
        tasks = _load_tasks()

    # ③ 탑스토리 — 최근 3일 매칭 강한 뉴스 헤드라인
    if news is not None and not news.empty and tasks is not None and not tasks.empty:
        try:
            recent = _news_db.load_news_for_days(days=3)
            if not recent.empty:
                if "collected_at" in recent.columns:
                    recent = recent.sort_values("collected_at", ascending=False)
                parts.append("③ 탑 스토리 (최근 3일):")
                for _, r in recent.head(5).iterrows():
                    t = str(r.get("title", ""))[:100]
                    s = str(r.get("source", ""))
                    parts.append(f"  - {t} ({s})")
        except Exception:
            pass

        # ④ 자동화 기회 4 (objectives 포함 — Phase 2)
        try:
            cells = _score_cells(news, tasks).head(4)
            if not cells.empty:
                parts.append("④ 자동화 기회 top 4:")
                for _, r in cells.iterrows():
                    parts.append(
                        f"  - {r.get('dept','')} · {r.get('lv3','')} "
                        f"(점수 {int(float(r.get('cell_score', 0) or 0))} · "
                        f"매칭 뉴스 {int(r.get('matched_news', 0) or 0)}건 · "
                        f"매칭 작업 {int(r.get('matched_tasks', 0) or 0)}건)"
                    )
                    sample = str(r.get("sample_tasks", "") or "").split(" · ")[0][:60]
                    if sample:
                        parts.append(f"    샘플 작업: {sample}")
                    obj = str(r.get("sample_objectives", "") or "").strip()
                    if obj:
                        parts.append(f"    목표: {obj[:100]}")
        except Exception:
            pass

        # 1위 cell 의 작업 정의 (task_def_json) 상세 — SOLA 가 "1위의 품질
        # 리스크/자동화 영역" 같은 깊은 질문에 답할 수 있게.
        try:
            cells = _score_cells(news, tasks).head(1)
            if not cells.empty and "task_def_json" in tasks.columns:
                top_cell = cells.iloc[0]
                first_task = str(top_cell.get("sample_tasks", "") or "").split(" · ")[0]
                if first_task:
                    rm = tasks[
                        (tasks["dept"] == top_cell["dept"])
                        & (tasks["lv3"] == top_cell["lv3"])
                        & (tasks.get("task", "") == first_task)
                    ]
                    if not rm.empty:
                        from roadmap.task_def_json import parse as _parse_tdj
                        from roadmap.task_def_json import to_chat_context_lines as _ctx_lines
                        task = _parse_tdj(rm.iloc[0].get("task_def_json", ""))
                        ctx_lines = _ctx_lines(task)
                        if ctx_lines:
                            parts.append("  1위 cell 작업 정의 상세:")
                            parts.extend(ctx_lines)
        except Exception:
            pass

        # ⑥ 매트릭스 1위 cell 상세
        try:
            cells = _score_cells(news, tasks).head(6)
            if not cells.empty:
                top = cells.iloc[0]
                parts.append(
                    f"⑥ 매트릭스 1위(즉시 PoC 후보): {top.get('dept','')} · {top.get('lv3','')} "
                    f"— 점수 {int(float(top.get('cell_score', 0) or 0))}"
                )
        except Exception:
            pass

    # ⑤ 트렌드 8주 키워드
    try:
        labels, series = _weekly_keyword_series(weeks=8)
        if series:
            parts.append("⑤ 트렌드 (최근 8주, 키워드 변화율):")
            for s in series[:6]:
                d = _delta_pct(s["counts"])
                parts.append(f"  - {s['name']}: 변화율 {'+' if d>=0 else ''}{d}%")
    except Exception:
        pass

    # ⑦ 키워드 관리 — 페르소나 관심사
    user_kw = list(persona.interest_lv3 or []) + list(persona.interest_tasks or [])
    if user_kw:
        parts.append(f"⑦ 내가 추가한 키워드: {', '.join(user_kw[:6])}")

    return "\n".join(parts)


def render() -> None:
    """오늘의 보드 v2 — topbar + app-side + main + app-sola 풀 셸 렌더."""
    # 보드 화면 전용 스타일 (.db-greet, .db-kpi, .db-stories, .db-trend 등)
    inject_screen_css("board")

    # ── 0) 자동화 기회 보류/채택 액션 — 위젯 인스턴스화 이전 1회 소비 ──
    # 영구화 + 캐시 invalidate (자동화 기회 카드/매트릭스/KPI 갱신 위해)
    if consume_opp_action_if_any():
        # bookmarks_store 변경 → 보드/SOLA 의 stats 캐시 새로고침 필요
        try:
            _archive_stats.clear()
        except Exception:
            pass

    # ── 0.5) ⑦ 키워드 관리 액션(× 삭제 / mute / collect) 1회 소비 ──
    if consume_kw_action_if_any():
        try:
            _board_kpis.clear()
        except Exception:
            pass

    persona = app_shell.get_persona()
    stats = _archive_stats()
    refresh = app_shell.refresh_label_now()

    # ── 1) 풀폭 topbar ──
    app_shell.render_topbar(
        page_title="오늘의 보드",
        eyebrow_current="오늘의 보드",
        refresh_label=refresh,
        fresh_kind="fresh",
    )

    # ── 2) LLM 미설정 안내 (설정 완료 시 no-op) ──
    app_shell.render_setup_banner_if_needed()
    render_opp_action_toast_if_needed()
    render_kw_action_toast_if_needed()

    # ── 3) 본문 (main) — 템플릿 로드 후 placeholder 치환 ──
    _render_main(persona=persona, refresh_label=refresh)


def _render_main(*, persona: Persona, refresh_label: str) -> None:
    kpis = _board_kpis()
    # 델타는 yesterday snapshot 비교 후속 PR — 일단 빈 값
    template = _components.read_asset_text(_BOARD_TEMPLATE)
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
        .replace("{{BOARD_MATRIX}}", _board_matrix_html(selected_key=_mx_selected_key()))
        .replace("{{BOARD_KW_MGR}}", _board_kw_mgr_html(persona))
    )
    # persona 라벨을 캐시 키로 — 부서·직무 바뀌면 브리핑 재생성
    brief = _brief_html(persona_label=persona.label() or "")
    html_out = (
        html_out
        .replace("{{BRIEF_SUMMARY}}", brief["summary"])
        .replace("{{BRIEF_LIST}}", brief["list"])
        .replace("{{BRIEF_CITES}}", brief["cites"])
        .replace("{{BRIEF_CTA}}", brief["cta"])
        .replace("{{BRIEF_TTS_BTN}}", brief.get("tts_btn", ""))
    )
    html_out = _clean_board_html(html_out)
    st.html(_components.prepare_screen_html(html_out))


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
