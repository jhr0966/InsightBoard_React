"""Reusable HTML component builders for the Streamlit UI.

The helpers return escaped HTML strings. Use `render_html(...)` to render
them through Streamlit's native HTML element instead of Markdown escaping.
"""
from __future__ import annotations

import html as _html
import re as _re
from collections.abc import Iterable
from pathlib import Path
from urllib.parse import quote as _quote

import streamlit as st


_SVG_DATAURI_RE = _re.compile(r"data:image/svg\+xml;utf8,(<svg.*?</svg>)", _re.DOTALL)
_SVG_INLINE_RE = _re.compile(r"(<svg\b[^>]*>).*?</svg>", _re.DOTALL)


@st.cache_data(show_spinner=False)
def _read_asset_cached(path_str: str, mtime_ns: int) -> str:
    return Path(path_str).read_text(encoding="utf-8")


def read_asset_text(path: Path) -> str:
    """자산(CSS/HTML 템플릿) 텍스트 — (경로, mtime) 키 캐시.

    CSS 6종·화면 템플릿을 **매 rerun 디스크에서 다시 읽던** 것을 제거. 파일을 수정하면
    mtime 변경으로 자동 재읽기되므로 개발 중 핫리로드도 그대로 동작. 없으면 빈 문자열.
    """
    try:
        return _read_asset_cached(str(path), path.stat().st_mtime_ns)
    except OSError:
        return ""


def _svg_attr(open_tag: str, name: str) -> str:
    m = _re.search(name + r"""\s*=\s*(['"])(.*?)\1""", open_tag, _re.DOTALL)
    return m.group(2) if m else ""


def prepare_screen_html(markup: str) -> str:
    """`st.html` 의 두 SVG 함정을 보정해 모든 화면의 아이콘/차트가 렌더되게 한다.

    1) ``data:image/svg+xml;utf8,<svg ... fill='#2563EB'>`` (미인코딩 data-URI) —
       색상값의 ``#`` 와 공백이 URL fragment/구분자로 잘려 이미지가 **깨진다** →
       URL 인코딩 data-URI 로 재작성.
    2) 인라인 ``<svg>...</svg>`` — `st.html` 의 sanitizer 가 통째로 **제거한다** →
       class/style/width/height 를 보존한 ``<img>``(인코딩 data-URI)로 래핑.

    템플릿 HTML 을 `st.html` 로 렌더하기 직전 한 번 통과시킨다.
    """
    if not markup or "svg" not in markup:
        return markup
    # 1) data-URI 재인코딩 (먼저 — 이후 인라인 변환이 src 안 <svg> 를 건드리지 않게)
    markup = _SVG_DATAURI_RE.sub(
        lambda m: "data:image/svg+xml," + _quote(m.group(1), safe=""),
        markup,
    )

    # 2) 남은 인라인 <svg> → <img>
    def _to_img(m: "_re.Match[str]") -> str:
        full = m.group(0)
        open_tag = m.group(1)
        attrs = ""
        for name in ("class", "style", "width", "height"):
            val = _svg_attr(open_tag, name)
            if val:
                attrs += f' {name}="{val.replace(chr(34), "&quot;")}"'
        return f'<img src="data:image/svg+xml,{_quote(full, safe="")}"{attrs} alt="" />'

    return _SVG_INLINE_RE.sub(_to_img, markup)


def render_screen_html(markup: str) -> None:
    """`prepare_screen_html` 통과 후 `st.html` 렌더 — 화면 템플릿 전용 안전 진입점."""
    st.html(prepare_screen_html(markup))


def render_html(markup: str, **_ignored) -> None:
    """Render trusted component HTML without Markdown escaping.

    Streamlit's `st.markdown(..., unsafe_allow_html=True)` can be easy to miss
    and then raw `<div>...</div>` appears in the app. Centralizing rendering via
    `st.html` makes component output consistent across pages.
    """
    st.html(markup)


_ALLOWED_TONES = {"", "info", "ok", "warn", "danger", "teal"}


def _tone_class(tone: str) -> str:
    safe = tone if tone in _ALLOWED_TONES else ""
    return f" {safe}" if safe else ""


def metric_card(
    label: str,
    value: str | int,
    *,
    caption: str = "",
    icon: str = "",
    tone: str = "",
) -> str:
    """Build a compact KPI card with a large value and optional caption.

    Output starts at column 0 so that Markdown won't mistakenly treat the
    HTML as an indented code block if it ever reaches `st.markdown`.
    """
    icon_html = (
        f'<span class="metric-card-icon">{_html.escape(icon)}</span>' if icon else ""
    )
    caption_html = (
        f'<div class="metric-card-caption">{_html.escape(caption)}</div>'
        if caption else ""
    )
    return (
        f'<div class="metric-card{_tone_class(tone)}">'
        f'<div class="metric-card-top">{icon_html}'
        f'<span class="metric-card-label">{_html.escape(label)}</span>'
        f'</div>'
        f'<div class="metric-card-value">{_html.escape(str(value))}</div>'
        f'{caption_html}'
        f'</div>'
    )


def metric_grid(cards: Iterable[str]) -> str:
    """Wrap prebuilt metric cards in the standard responsive metric grid."""
    return '<div class="metric-grid">' + "".join(cards) + "</div>"


def status_card(
    title: str,
    body: str,
    *,
    status: str = "info",
    icon: str = "",
) -> str:
    """Build a status/empty-state card with a colored leading rail."""
    return (
        f'<div class="status-card{_tone_class(status)}">'
        f'<div class="status-card-icon">{_html.escape(icon or "•")}</div>'
        f'<div>'
        f'<div class="status-card-title">{_html.escape(title)}</div>'
        f'<div class="status-card-body">{_html.escape(body)}</div>'
        f'</div>'
        f'</div>'
    )


def action_card(icon: str, title: str, body: str, *, tone: str = "") -> str:
    """Build one quick-action card."""
    return (
        f'<div class="action-card{_tone_class(tone)}">'
        f'<div class="action-card-icon">{_html.escape(icon)}</div>'
        f'<div class="action-card-title">{_html.escape(title)}</div>'
        f'<div class="action-card-body">{_html.escape(body)}</div>'
        f'</div>'
    )


def action_grid(cards: Iterable[str]) -> str:
    """Wrap prebuilt action cards in the standard responsive action grid."""
    return '<div class="action-grid">' + "".join(cards) + "</div>"


def step_item(number: str | int, title: str, body: str, *, active: bool = False) -> str:
    """Build one process step for guided workflows."""
    cls = "step-item active" if active else "step-item"
    return (
        f'<div class="{cls}">'
        f'<div class="step-number">{_html.escape(str(number))}</div>'
        f'<div>'
        f'<div class="step-title">{_html.escape(title)}</div>'
        f'<div class="step-body">{_html.escape(body)}</div>'
        f'</div>'
        f'</div>'
    )


def step_guide(items: Iterable[str]) -> str:
    """Wrap prebuilt step items in the standard horizontal guide."""
    return '<div class="step-guide">' + "".join(items) + "</div>"


# ── 포커스 내비게이션 (자동 포커스 + Enter→다음 입력) ─────────────

_FOCUS_NAV_JS = r"""
<script>
/* focus-nav %(nonce)s */
(function () {
  var SEL = %(sel)s;
  var SUBMIT = %(submit)s;  /* 마지막 입력 Enter 시 클릭할 버튼 selector (null=비활성) */
  var CTRL = %(ctrl)s;      /* Ctrl/⌘+Enter 시 클릭할 버튼 selector (null=비활성) */
  var CHIPS = %(chips)s;    /* 콤마→Enter 변환할 태그 입력 scope selector (null=비활성) */
  /* st.html(unsafe_allow_javascript=True) → 메인 문서 realm 에서 실행.
     components.v1.html 폴백(iframe) → window.parent 로 같은 문서에 접근. */
  var doc, win;
  try {
    win = window.frameElement ? window.parent : window;
    doc = win.document;
  } catch (err) {
    return; /* cross-origin 등 접근 불가 시 무해하게 종료 */
  }

  function visible(el) {
    return !el.disabled && el.getClientRects().length > 0;
  }
  function inputsIn(sel) {
    var nodes = doc.querySelectorAll(sel + " input, " + sel + " textarea");
    return Array.prototype.filter.call(nodes, visible);
  }
  function isPlainTextInput(el) {
    /* selectbox/multiselect(BaseWeb combobox)는 Enter 가 옵션 선택이므로 제외. */
    if (!el || el.tagName !== "INPUT") { return false; }
    if (el.closest('[data-baseweb="select"]')) { return false; }
    var t = (el.getAttribute("type") || "text").toLowerCase();
    return ["text", "search", "number", "email", "password", "url", "tel"].indexOf(t) >= 0;
  }

  /* (b) Enter → scope 안 다음 visible 입력으로 이동 (capture-phase keydown).
     주입(rerun·단계 전환)마다 이전 핸들러를 제거하고 재부착한다 — window 마커
     `__newsFocusNav` 가 중복 부착을 막고, iframe 폴백에서 옛 realm 이 파괴돼
     리스너가 죽는 문제도 함께 해결한다. Tab 은 브라우저 기본 동작 그대로. */
  if (win.__newsFocusNav && win.__newsFocusNav.fn) {
    doc.removeEventListener("keydown", win.__newsFocusNav.fn, true);
  }
  function onKeydown(e) {
    if (e.isComposing) { return; }
    var nav = win.__newsFocusNav;
    var el = e.target;
    if (!nav || !el) { return; }

    /* (c) 태그 입력(BaseWeb select + 새 옵션 허용)에서 콤마 → Enter 변환:
       콤마를 누르면 입력 중인 키워드가 즉시 칩(버블)으로 등록되게 한다.
       값이 비어있으면 그대로 두어 빈 칩 생성을 막는다. */
    if (e.key === "," && nav.chips && el.tagName === "INPUT"
        && el.closest(nav.chips) && el.closest('[data-baseweb="select"]')
        && el.value && el.value.trim()) {
      e.preventDefault();
      e.stopPropagation();
      el.dispatchEvent(new KeyboardEvent("keydown", {
        key: "Enter", code: "Enter", keyCode: 13, which: 13,
        bubbles: true, cancelable: true,
      }));
      return;
    }

    if (e.key !== "Enter") { return; }

    /* (e) Ctrl/⌘+Enter → 어느 입력에서든 단계 진행 버튼 클릭 (값 커밋 후). */
    if ((e.ctrlKey || e.metaKey) && !e.shiftKey && !e.altKey && nav.ctrl) {
      if (!el.closest || !el.closest(nav.sel)) { return; }
      e.preventDefault();
      e.stopPropagation();
      if (el.blur) { el.blur(); }
      win.setTimeout(function () {
        var btn = doc.querySelector(nav.ctrl);
        if (btn) { btn.click(); }
      }, 180);
      return;
    }

    if (e.shiftKey || e.ctrlKey || e.metaKey || e.altKey) { return; }
    if (!isPlainTextInput(el) || !el.closest(nav.sel)) { return; }
    var list = inputsIn(nav.sel);
    var i = list.indexOf(el);
    if (i < 0) { return; }
    if (i >= list.length - 1) {
      /* (d) 마지막 입력에서 Enter → blur 로 값 커밋 후 지정 버튼 클릭(=다음 단계).
         클릭은 rerun 으로 DOM 이 교체될 수 있어 지연 후 재조회한다. */
      if (!nav.submit) { return; } /* 미지정 시 기본 동작 유지(Streamlit Enter 커밋) */
      e.preventDefault();
      e.stopPropagation();
      el.blur();
      win.setTimeout(function () {
        var btn = doc.querySelector(nav.submit);
        if (btn) { btn.click(); }
      }, 180);
      return;
    }
    e.preventDefault();
    e.stopPropagation();
    list[i + 1].focus(); /* 현재 입력 blur → Streamlit 값 커밋 자연 발생 */
  }
  win.__newsFocusNav = { sel: SEL, submit: SUBMIT, ctrl: CTRL, chips: CHIPS, fn: onKeydown };
  doc.addEventListener("keydown", onKeydown, true);

  /* (a) scope 안 첫 입력 자동 포커스 — 모달/위젯 마운트가 늦을 수 있어 폴링.
     이미 다른 input/textarea 에 포커스가 있으면 건드리지 않는다(타이핑 보호). */
  var tries = 0;
  var timer = setInterval(function () {
    tries += 1;
    var act = doc.activeElement;
    if (act && (act.tagName === "INPUT" || act.tagName === "TEXTAREA")) {
      clearInterval(timer);
      return;
    }
    var list = inputsIn(SEL);
    if (list.length) {
      clearInterval(timer);
      list[0].focus();
      return;
    }
    if (tries > 30) { clearInterval(timer); }
  }, 100);
})();
</script>
"""


def inject_focus_nav(
    scope_selector: str,
    *,
    nonce: str = "",
    submit_selector: str = "",
    ctrl_submit_selector: str = "",
    chips_selector: str = "",
) -> None:
    """입력 폼 포커스 내비게이션 주입 — ① scope 첫 input 자동 포커스 ② Enter→다음 입력.

    Streamlit ≥1.58 에서는 `st.html(..., unsafe_allow_javascript=True)` 로 메인
    문서에서 스크립트를 실행하고, 그 이전 버전에서는 `components.v1.html`(iframe,
    height=0) 폴백으로 `window.parent.document` 에 접근한다(same-origin 이라 가능).
    스크립트는 정적 문자열 + 코드 내 상수 selector/nonce 만 포함 — 사용자/외부
    데이터 미포함이라 XSS 무관 (CLAUDE.md #5).

    - 자동 포커스: 이미 다른 입력에 포커스가 있으면 건드리지 않음 (rerun 안전).
    - Enter: 텍스트 입력에서 다음 visible input/textarea 로 이동, blur 로 값 커밋.
      마지막 입력에서는 브라우저/Streamlit 기본 동작 유지. Tab 은 기본 동작.
    - `nonce` 가 바뀌면 마크업이 바뀌어 스크립트가 재실행된다 — 온보딩 단계
      전환(rerun) 후 새 단계 첫 입력에 다시 포커스하기 위해 단계 번호를 넘긴다.
    - `submit_selector`: 지정 시 **마지막** 텍스트 입력에서 Enter → blur(값 커밋)
      후 해당 버튼을 클릭한다 — 온보딩 "이름 입력 후 Enter = 다음" UX.
    - `ctrl_submit_selector`: 지정 시 scope 안 **어느 입력에서든** Ctrl/⌘+Enter →
      blur(값 커밋) 후 해당 버튼 클릭 — 온보딩 "Ctrl+Enter = 다음/완료" UX.
    - `chips_selector`: 지정 시 그 scope 안 태그 입력(multiselect
      `accept_new_options`)에서 콤마 입력 → Enter 로 변환해 키워드를 즉시
      칩(버블)으로 등록한다.
    - AppTest/헤드리스 등 미지원 환경에서도 본 렌더가 죽지 않게 가드.
    """
    import json as _json

    markup = _FOCUS_NAV_JS % {
        "sel": _json.dumps(scope_selector),
        "submit": _json.dumps(submit_selector or None),
        "ctrl": _json.dumps(ctrl_submit_selector or None),
        "chips": _json.dumps(chips_selector or None),
        "nonce": _html.escape(str(nonce)),
    }
    try:
        try:
            st.html(markup, unsafe_allow_javascript=True)
        except TypeError:  # Streamlit <1.58 — st.html 에 JS 플래그 없음
            import streamlit.components.v1 as _stc

            _stc.html(markup, height=0)
    except Exception:
        pass  # 포커스 보조는 best-effort — 실패해도 화면 기능에 영향 없음
