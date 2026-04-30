from streamlit.testing.v1 import AppTest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_app_renders_sidebar_modes() -> None:
    at = AppTest.from_file("app.py")
    at.run(timeout=30)

    radios = [r for r in at.radio if r.label == "작업할 기능을 선택하세요."]
    assert radios, "사이드바 모드 선택 라디오를 찾을 수 없습니다."

    mode_radio = radios[0]
    options = list(mode_radio.options)

    assert "🏠 워크스페이스" in options
    assert "🔍 네이버 뉴스 검색" in options
    assert "🚀 최신 기술 동향 (AI/자동화)" in options
    assert "🏭 조선소 작업 데이터" in options
    assert "🤝 자동화 과제 제안" in options
    assert "🧪 데이터 품질" in options
    assert "📊 인사이트 보드" in options
    assert "🎨 카드뉴스" in options


def test_each_mode_can_render_without_crash() -> None:
    at = AppTest.from_file("app.py")
    at.run(timeout=30)

    mode_radio = [r for r in at.radio if r.label == "작업할 기능을 선택하세요."][0]
    for mode in mode_radio.options:
        mode_radio.set_value(mode)
        at.run(timeout=30)

    assert True
