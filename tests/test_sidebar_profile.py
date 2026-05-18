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
    assert "persona-profile-avatar" in html
    assert 'href="?persona_editor=1"' in html
    assert "아바타를 눌러 프로필 편집" in html
    assert "생산기술 · 자동화" in html
    assert "&lt;script&gt;x&lt;/script&gt;" in html
    assert "용접&lt;script&gt;" in html
    assert "<script>" not in html


def test_persona_profile_card_unset_defaults():
    html = sidebar._persona_card_html(Persona())

    assert "사용자" in html
    assert "부서 미설정" in html
    assert "직무 미설정" in html
    assert "관심 공정 미설정" in html


def test_persona_page_options_helpers_handle_empty_and_columns():
    import pandas as pd

    assert persona_page._options(pd.DataFrame(), "dept") == [""]
    df = pd.DataFrame({"dept": ["B", "A", None], "lv3": ["용접", "검사", None]})
    assert persona_page._options(df, "dept") == ["", "A", "B"]
    assert persona_page._lv3_options(df) == ["검사", "용접"]
