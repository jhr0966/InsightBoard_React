"""Phase D — 표시 설정(테마·글자 크기) 저장소 + 주입."""
from __future__ import annotations

import pytest


@pytest.fixture
def isolated_prefs(tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, "DATA_ROOT", tmp_path)
    from store import ui_prefs
    monkeypatch.setattr(ui_prefs, "_path", lambda: tmp_path / "ui_prefs.json")
    return ui_prefs


def test_default_when_missing(isolated_prefs):
    assert isolated_prefs.load() == {"theme": "light", "font": "medium"}


def test_save_roundtrip(isolated_prefs):
    isolated_prefs.save(theme="dark", font="large")
    assert isolated_prefs.load() == {"theme": "dark", "font": "large"}


def test_unknown_values_normalized(isolated_prefs):
    isolated_prefs.save(theme="bogus", font="huge")
    assert isolated_prefs.load() == {"theme": "light", "font": "medium"}


def test_corrupt_file_falls_back(isolated_prefs, tmp_path):
    (tmp_path / "ui_prefs.json").write_text("{not json", encoding="utf-8")
    assert isolated_prefs.load() == {"theme": "light", "font": "medium"}


def test_all_offered_themes_have_css_mapping():
    from ui import styles
    from store import ui_prefs
    # ui_prefs 가 허용하는 테마는 모두 styles 의 CSS 맵에 존재
    for theme in ui_prefs.THEMES:
        assert theme in styles._THEME_CSS


def test_inject_user_prefs_injects_theme_and_font(isolated_prefs, monkeypatch):
    from ui import styles
    isolated_prefs.save(theme="dark", font="large")
    captured = []
    monkeypatch.setattr(styles.st, "markdown", lambda s, **k: captured.append(s))
    styles.inject_user_prefs()
    out = "".join(captured)
    assert "#0F172A" in out          # 다크 배경 토큰
    assert "zoom:1.12" in out        # 큰 글자


def test_inject_user_prefs_light_medium_is_noop(isolated_prefs, monkeypatch):
    from ui import styles
    isolated_prefs.save(theme="light", font="medium")
    captured = []
    monkeypatch.setattr(styles.st, "markdown", lambda s, **k: captured.append(s))
    styles.inject_user_prefs()
    assert captured == []            # 기본값이면 주입 없음
