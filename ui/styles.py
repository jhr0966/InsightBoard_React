"""전역 CSS 주입 + 페이지 헤더 헬퍼."""
from __future__ import annotations

import html as _html
from pathlib import Path

import streamlit as st

from config import ASSETS_DIR
from sola.client import is_configured


_V2_CSS_FILES = (
    "v2/tokens.css",
    "v2/card.css",
    "v2/shell.css",
    "v2/sidebar.css",
    "v2/streamlit-overrides.css",
    "v2/scale.css",
)


def inject_global_styles() -> None:
    """Inject v2 design tokens + Streamlit overrides + legacy styles.

    순서: tokens → card(components) → shell(v2 topbar) → sidebar(네이티브 사이드바)
    → streamlit overrides → scale.

    레거시 `assets/styles.css`(V1 디자인 시스템, 1463줄)는 더 이상 로드하지 않는다 —
    유일한 라이브 소비처였던 네이티브 사이드바 스타일을 `v2/sidebar.css` 로 이전하고,
    새로고침 시 잠깐 보이던 V1 잔재(FOUC) 를 제거 (2026-06-01).

    Streamlit `st.html("<style>")` 는 큰 `<style>` 블록을 안정적으로 mount 하지
    못함이 확인됨 (수만 자 누락). `st.markdown(unsafe_allow_html=True)` 가 다른
    코드 경로로 보존하므로 그쪽 사용 — CSS 는 자체 자산이라 escape 불필요.
    """
    parts: list[str] = []
    for rel in _V2_CSS_FILES:
        path = ASSETS_DIR / rel
        if path.exists():
            parts.append(path.read_text(encoding="utf-8"))
    if not parts:
        return
    st.markdown("<style>" + "\n".join(parts) + "</style>", unsafe_allow_html=True)


# ── 사용자 표시 설정 (테마 · 글자 크기) ──────────────────────────
# 베이스 토큰(tokens.css) 이후에 주입해 :root 오버라이드가 이기게 한다.

_FONT_ZOOM = {"small": "0.92", "medium": "", "large": "1.12"}

# 다크 — 토큰 + 핵심 크롬 + 네이티브 위젯(config 라이트를 다크로) 오버라이드.
_DARK_CSS = """
:root{
  --bg-base:#0F172A; --bg-gradient-from:#0F172A; --bg-gradient-to:#1E293B;
  --surface-page:#0F172A; --surface-card:#1E293B; --surface-soft:#172033;
  --surface-divider:#334155; --surface-inset-bg:rgba(15,23,42,.6);
  --surface-glass-bg:rgba(30,41,59,.72); --surface-glass-border:rgba(255,255,255,.08);
  --text-primary:#F1F5F9; --text-secondary:rgba(241,245,249,.74); --text-muted:rgba(241,245,249,.52);
}
body:has(.db-topbar) .stApp{ background:#0F172A !important; }
/* sticky 헤더 배경 — 라이트는 --v2-bg(#F3F5F8), 다크는 앱 배경(#0F172A)과 맞춰
   아래로 스크롤되는 카드가 헤더 밑으로 비치지 않게 한다. */
body:has(.db-topbar) .db-topbar{ background:#0F172A !important; }
body:has(.db-topbar) [data-testid="stSidebar"]{ background:#1E293B !important; border-right:1px solid #334155 !important; }
body:has(.db-topbar) [data-testid="stColumn"]:has(.side-chat-marker){ background:#1E293B !important; border-color:#334155 !important; }
body:has(.db-topbar) [data-testid="stMain"] [data-testid="stVerticalBlockBorderWrapper"]{ background:#1E293B !important; border-color:#334155 !important; }
body:has(.db-topbar) [data-testid="stTextInput"] input,
body:has(.db-topbar) [data-testid="stTextArea"] textarea{ background:#0F172A !important; color:#F1F5F9 !important; border-color:#334155 !important; }
/* baseweb 입력 래퍼(base-input/input/textarea)가 흰색으로 남아 입력창이 다크에서
   하얗게 보이던 문제 — 래퍼까지 다크화 (Streamlit 1.58 DOM). */
body:has(.db-topbar) [data-baseweb="base-input"],
body:has(.db-topbar) [data-baseweb="input"],
body:has(.db-topbar) [data-baseweb="textarea"]{ background:#0F172A !important; border-color:#334155 !important; }
body:has(.db-topbar) [data-baseweb="select"] > div{ background:#0F172A !important; border-color:#334155 !important; color:#F1F5F9 !important; }
/* placeholder — 다크 입력 배경(#0F172A)에 기본 회색 placeholder 가 묻혀 안 보이던
   문제. 밝은 muted 색으로 가시화 (native st.text_input/text_area + baseweb 래퍼). */
body:has(.db-topbar) [data-testid="stTextInput"] input::placeholder,
body:has(.db-topbar) [data-testid="stTextArea"] textarea::placeholder,
body:has(.db-topbar) [data-baseweb="input"] input::placeholder,
body:has(.db-topbar) [data-baseweb="base-input"] input::placeholder,
body:has(.db-topbar) [data-baseweb="textarea"] textarea::placeholder{ color:rgba(241,245,249,.50) !important; -webkit-text-fill-color:rgba(241,245,249,.50) !important; opacity:1 !important; }
body:has(.db-topbar) button[kind="secondary"]{ background:#1E293B !important; color:#F1F5F9 !important; border-color:#334155 !important; }
body:has(.db-topbar) [data-testid="stMain"] label,
body:has(.db-topbar) [data-testid="stMain"] [data-testid="stMarkdownContainer"]{ color:#F1F5F9 !important; }
/* 사이드바 고정 표면(그라데이션/틴트) 다크화 */
body:has(.db-topbar) .persona-profile-card,
body:has(.db-topbar) .persona-profile-card-empty{ background:#172033 !important; }
body:has(.db-topbar) .persona-profile-head-empty{ background:#0F172A !important; border-color:#334155 !important; color:#94A3B8 !important; }
body:has(.db-topbar) .sidebar-nav-item.active{ background:rgba(96,165,250,.16) !important; border-color:rgba(96,165,250,.30) !important; }
/* 콜아웃 배너 — 라이트 고정색(amber/blue)이라 다크에서 밝은 섬으로 떠 보임 → 다크 틴트 변형 */
body:has(.db-topbar) .app-llm-banner{ background:rgba(180,83,9,.18) !important; border-color:rgba(180,83,9,.42) !important; color:#FCD34D !important; }
body:has(.db-topbar) .app-llm-banner b{ color:#FCD34D !important; }
body:has(.db-topbar) .ws-brief-handoff{ background:rgba(37,99,235,.16) !important; border-color:rgba(37,99,235,.36) !important; color:#BFDBFE !important; }
/* 네이티브 selectbox/드롭다운 팝오버 — body 루트 포털이라 토큰만으론 안 잡힘.
   라이트 흰 메뉴가 다크 위에 뜨던 문제 → 메뉴/옵션 다크화. */
body:has(.db-topbar) [data-baseweb="popover"] [data-baseweb="menu"],
body:has(.db-topbar) [data-baseweb="popover"] ul[role="listbox"],
body:has(.db-topbar) [data-baseweb="popover"] [role="listbox"]{ background:#1E293B !important; border-color:#334155 !important; }
body:has(.db-topbar) [data-baseweb="popover"] li[role="option"],
body:has(.db-topbar) [data-baseweb="popover"] [role="option"]{ background:#1E293B !important; color:#F1F5F9 !important; }
body:has(.db-topbar) [data-baseweb="popover"] li[role="option"]:hover,
body:has(.db-topbar) [data-baseweb="popover"] [role="option"][aria-selected="true"]{ background:#334155 !important; }
/* st.dialog(온보딩 등) 모달 표면 다크화 */
body:has(.db-topbar) [data-testid="stDialog"] [role="dialog"],
body:has(.db-topbar) [role="dialog"][aria-modal="true"]{ background:#1E293B !important; color:#F1F5F9 !important; }
/* 다크 토스트/팝오버 일반 표면 */
body:has(.db-topbar) [data-testid="stToast"]{ background:#1E293B !important; color:#F1F5F9 !important; border:1px solid #334155 !important; }
/* ⌘K 팔레트 아이콘 박스 — 다크에서 본문보다 어둡게 해 대비 확보 */
body:has(.db-topbar) .v2-cmdk-ic{ background:#0F172A !important; }
"""

# 강조 색상 테마 (라이트 베이스 + accent 토큰 교체) — 네이티브 primary 버튼도 추종.
_ACCENT_BTN = ('body:has(.db-topbar) button[kind="primary"]{ '
               'background:var(--accent-primary) !important; border-color:var(--accent-primary) !important; }')
_OCEAN_CSS = (":root{ --accent-primary:#0D9488; --accent-hover:#0F766E; --accent-active:#115E59; "
              "--accent-ring:rgba(13,148,136,.22); --accent-glow:rgba(13,148,136,.18); }" + _ACCENT_BTN)
_SUNSET_CSS = (":root{ --accent-primary:#E11D48; --accent-hover:#BE123C; --accent-active:#9F1239; "
               "--accent-ring:rgba(225,29,72,.22); --accent-glow:rgba(225,29,72,.18); }" + _ACCENT_BTN)

_THEME_CSS = {"light": "", "dark": _DARK_CSS, "ocean": _OCEAN_CSS, "sunset": _SUNSET_CSS}


def inject_user_prefs() -> None:
    """저장된 테마·글자 크기를 적용 — `inject_global_styles` 직후 호출.

    테마 = light(기본)/dark/ocean/sunset. 글자 크기 = small/medium/large(zoom).
    """
    from store import ui_prefs

    prefs = ui_prefs.load()
    css = _THEME_CSS.get(prefs.get("theme", "light"), "")
    zoom = _FONT_ZOOM.get(prefs.get("font", "medium"), "")
    if zoom:
        css += (f'\nbody:has(.db-topbar) [data-testid="stMain"],'
                f'\nbody:has(.db-topbar) [data-testid="stSidebar"]{{ zoom:{zoom}; }}')
    # 항상 단일 <style> 블록으로 주입한다(내용이 비어도). light(빈 CSS)와
    # dark/ocean/sunset 사이에 '주입 블록 개수'가 달라지면 Streamlit 루트 수직
    # 블록의 flex gap 이 하나 더/덜 생겨, 테마 토글 시 색뿐 아니라 레이아웃이
    # 밀린다. 개수를 고정해 토글이 색상만 바꾸게 한다.
    st.markdown("<style>" + css + "</style>", unsafe_allow_html=True)


def inject_screen_css(name: str) -> None:
    """화면별 CSS 로드 — `assets/v2/screens/<name>.css` 가 있으면 inject.

    글로벌이 아닌 화면 전용 스타일(예: 보드 화면의 .db-greet/.db-stories 등)
    을 화면 진입 시 한 번 주입한다. 같은 화면에 머무는 동안 매 rerun 마다
    재주입되지만 브라우저가 같은 텍스트를 중복 적용해도 시각적 변화는 없음.

    `inject_global_styles` 와 동일 — `st.markdown(unsafe_allow_html=True)` 사용
    (`st.html` 은 큰 `<style>` 블록 mount 실패).
    """
    path = ASSETS_DIR / "v2" / "screens" / f"{name}.css"
    if not path.exists():
        return
    st.markdown(
        f"<style>{path.read_text(encoding='utf-8')}</style>",
        unsafe_allow_html=True,
    )


def page_header(
    title: str,
    sub: str = "",
    *,
    chat_toggle_key: str | None = None,
    extra_chips: list[tuple[str, str]] | None = None,
) -> bool:
    """페이지 상단 모던 헤더.

    Args:
        title: 페이지 제목.
        sub: 부제목 (선택).
        chat_toggle_key: 채팅 패널 토글 키. 주어지면 우측에 💬 토글 버튼 노출.
        extra_chips: [(label, kind)] kind = "" | "ok" | "warn".

    Returns:
        채팅 패널 활성 여부 (chat_toggle_key 미지정 시 False).
    """
    safe_title = _html.escape(title)
    safe_sub = _html.escape(sub)

    chips_html = ""
    chip_pool = list(extra_chips or [])
    if chat_toggle_key is not None:
        chip_pool.insert(
            0,
            ("LLM 준비됨" if is_configured() else "LLM 미설정",
             "ok" if is_configured() else "warn"),
        )
    for label, kind in chip_pool:
        cls = f"app-header-chip {kind}".strip()
        chips_html += f'<span class="{cls}">{_html.escape(label)}</span>'

    st.html(
        f"""
        <div class="app-header">
          <div class="app-header-text">
            <div class="app-header-title">{safe_title}</div>
            {f'<div class="app-header-sub">{safe_sub}</div>' if sub else ''}
          </div>
          <div class="app-header-actions">{chips_html}</div>
        </div>
        """
    )

    if chat_toggle_key is None:
        return False

    # 채팅 토글 버튼 — Streamlit 위젯이라 HTML 헤더와 분리.
    # 디폴트는 펼친 상태 (채팅 패널은 첫 진입 시 열린 상태).
    open_key = f"_chat_open_{chat_toggle_key}"
    is_open = st.session_state.get(open_key, True)
    label = "💬 채팅 닫기" if is_open else "💬 이 화면에 대해 채팅"
    cols = st.columns([1, 1, 1, 1, 1])
    with cols[-1]:
        if st.button(label, key=f"_btn_chat_{chat_toggle_key}", use_container_width=True):
            st.session_state[open_key] = not is_open
            st.rerun()
    return st.session_state.get(open_key, True)


def section_label(text: str) -> None:
    """카드 그룹 위 작은 섹션 레이블."""
    st.html(f'<div class="sidebar-section">{_html.escape(text)}</div>')
