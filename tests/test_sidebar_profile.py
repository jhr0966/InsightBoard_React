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


def test_nav_label_uses_markdown_title_and_desc():
    """nav 버튼 라벨 = `**제목** *설명*` (CSS 가 strong=제목·em=설명으로 스타일)."""
    assert sidebar._nav_label("🔎 인사이트 분석", "트렌드 · 기회 · 매칭") == \
        "**🔎 인사이트 분석** *트렌드 · 기회 · 매칭*"
    assert sidebar._nav_label("📊 오늘의 보드", "") == "**📊 오늘의 보드**"


def test_sidebar_nav_is_widget_buttons_socket_rerun():
    """업무 흐름 nav 는 st.button 위젯(앵커 X) — 클릭 시 소켓 rerun(?app_area= 안 씀).

    I-22 재위젯화: 흰 깜빡임 제거를 위해 앵커를 st.button 으로 복원. 클릭이 세션
    app_area 만 바꾸고 URL 쿼리는 건드리지 않음(=문서 reload 없음).
    """
    from streamlit.testing.v1 import AppTest
    from persona import store as ps
    from persona.schema import Persona
    ps.reset(); ps.clear_onboarding_dismiss()
    ps.save(Persona(name="홍길동", dept="도장1팀", team="자동화1팀"))
    at = AppTest.from_file("app.py", default_timeout=60)
    at.session_state["app_area"] = "📊 오늘의 보드"
    at.run()
    assert not at.exception
    nav = [b for b in at.sidebar.button if b.key and b.key.startswith("_nav_btn_")]
    assert len(nav) == len(sidebar.AREAS)
    target = next(b for b in nav if b.key == "_nav_btn_3")   # 인사이트 분석
    target.click().run()
    assert not at.exception
    assert at.session_state["app_area"] == "🔎 인사이트 분석"
    assert "app_area" not in at.query_params      # 소켓 rerun — URL 쿼리 미사용


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
