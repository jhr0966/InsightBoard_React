from __future__ import annotations

from persona.schema import Persona
from ui import sidebar
from ui import persona_page


def test_persona_profile_card_escapes_and_renders_large_avatar():
    html = sidebar._persona_card_html(
        Persona(
            name="<script>x</script>",
            dept="생산기술",
            job="자동화",
            team="A팀",
            interest_lv3=["용접<script>", "검사"],
        )
    )

    assert "persona-profile-card" in html
    assert "persona-profile-head" in html        # 아바타
    assert 'href="?persona_editor=1"' in html    # 카드 전체가 설정 링크
    assert "persona-profile-edit" in html         # 편집 펜 affordance
    assert "생산기술 · 자동화" in html
    assert "&lt;script&gt;x&lt;/script&gt;" in html
    assert "용접&lt;script&gt;" in html
    assert "<script>" not in html


def test_persona_profile_card_unset_shows_setup_cta_and_is_clickable():
    html = sidebar._persona_card_html(Persona())

    # 미설정 카드도 전체가 ?persona_editor=1 링크 → 이모지·이름·안내·CTA 어디든 클릭 가능
    assert 'href="?persona_editor=1"' in html
    assert "persona-profile-card-empty" in html
    assert "프로필 미설정" in html
    assert "👤" in html                            # 프로필 이모지 아이콘
    assert "프로필 설정하기" in html                 # CTA
    # 값이 없으니 팀/관심 세부 행은 노출하지 않음 (깔끔한 미설정 카드)
    assert "persona-profile-details" not in html


def test_persona_page_options_helpers_handle_empty_and_columns():
    import pandas as pd

    assert persona_page._options(pd.DataFrame(), "dept") == [""]
    df = pd.DataFrame({"dept": ["B", "A", None], "lv3": ["용접", "검사", None]})
    assert persona_page._options(df, "dept") == ["", "A", "B"]
    assert persona_page._lv3_options(df) == ["검사", "용접"]


def test_sidebar_nav_html_uses_link_list_not_radio_buttons():
    html = sidebar._sidebar_nav_html("🔎 인사이트 분석")

    assert 'class="sidebar-nav"' in html
    assert html.count('class="sidebar-nav-item') == len(sidebar.AREAS)
    assert 'aria-current="page"' in html
    assert "%F0%9F%94%8E%20%EC%9D%B8%EC%82%AC%EC%9D%B4%ED%8A%B8%20%EB%B6%84%EC%84%9D" in html
    assert "radio" not in html.lower()
    assert "button" not in html.lower()


def test_llm_footer_ready_shows_model_only():
    """LLM 설정 완료 시 푸터에 백엔드·모델만 표시 (Groq 안내 없음)."""
    html_out = sidebar._llm_footer_html(
        ready=True, backend="groq", model="llama-3.3-70b-versatile",
    )
    assert "sidebar-dot ok" in html_out
    assert "llama-3.3-70b-versatile" in html_out
    assert "Groq 키 발급" not in html_out
    assert "console.groq.com" not in html_out


def test_llm_footer_empty_shows_groq_cta_with_key_setup_hint():
    """LLM 미설정 시 푸터가 키 발급 링크 + .env 가이드 포함."""
    html_out = sidebar._llm_footer_html(ready=False, backend="groq", model="")
    assert "sidebar-dot warn" in html_out
    assert "sidebar-footer-empty" in html_out
    assert "console.groq.com/keys" in html_out
    assert "LLM_API_KEY" in html_out
    assert "키 미설정" in html_out
