"""작업 정의 데이터 업로드 UI — render / 미리보기 / consume / toast."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest


FIXTURE = Path(__file__).parent / "fixtures" / "sample_task_def.xlsx"


@pytest.fixture
def isolated_dirs(tmp_path, monkeypatch):
    """ROADMAP_DIR 격리."""
    import config
    monkeypatch.setattr(config, "DATA_ROOT", tmp_path)
    monkeypatch.setattr(config, "ROADMAP_DIR", tmp_path / "roadmap")
    (tmp_path / "roadmap").mkdir(parents=True, exist_ok=True)
    from store import paths
    monkeypatch.setattr(paths, "ROADMAP_DIR", tmp_path / "roadmap")
    yield


# ── consume_task_def_upload_if_any — 업로드 페이로드 처리 ────

def test_consume_noop_when_no_pending(isolated_dirs):
    """pending 페이로드 없으면 noop."""
    from ui import data_management_v2 as dm
    import streamlit as st
    st.session_state.pop("_do_task_def_ingest", None)
    with patch("streamlit.rerun") as r:
        dm._consume_task_def_upload_if_any()
        r.assert_not_called()


def test_consume_ingest_success_clears_caches_and_sets_toast(isolated_dirs):
    """성공 ingest → 캐시 invalidate + 성공 toast."""
    from ui import data_management_v2 as dm
    import streamlit as st
    with open(FIXTURE, "rb") as f:
        data = f.read()
    st.session_state["_do_task_def_ingest"] = ("sample.xlsx", 0, data)

    targets = [dm._dm_stats, dm._ingest_jobs_html, dm._hist_html,
               dm._news_cards_html, dm._archive_stats_dm]
    with patch.object(targets[0], "clear") as c0, \
         patch.object(targets[1], "clear") as c1, \
         patch("streamlit.rerun"):
        dm._consume_task_def_upload_if_any()
        c0.assert_called_once()
        c1.assert_called_once()

    toast = st.session_state.get("_task_def_toast")
    assert toast is not None
    assert toast[0] == "ok"
    assert "32건" in toast[1] or "작업 정의 저장됨" in toast[1]
    # pending 소비됨
    assert "_do_task_def_ingest" not in st.session_state


def test_consume_ingest_invalid_excel_sets_error_toast(isolated_dirs):
    """잘못된 데이터 → error toast (전체 흐름 죽지 않음)."""
    from ui import data_management_v2 as dm
    import streamlit as st
    # 빈 bytes — pd.read_excel 실패
    st.session_state["_do_task_def_ingest"] = ("bad.xlsx", 0, b"not an excel")
    with patch("streamlit.rerun"):
        dm._consume_task_def_upload_if_any()
    toast = st.session_state.get("_task_def_toast")
    assert toast is not None
    assert toast[0] == "error"


def test_consume_ingest_validation_error_sets_error_toast(isolated_dirs):
    """validate 실패 (필수 컬럼 누락) → error toast."""
    from ui import data_management_v2 as dm
    import streamlit as st
    # 단일 컬럼만 있는 가짜 엑셀
    import io
    df = pd.DataFrame({"random_col": ["x"]})
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    st.session_state["_do_task_def_ingest"] = ("incomplete.xlsx", 0, buf.getvalue())
    with patch("streamlit.rerun"):
        dm._consume_task_def_upload_if_any()
    toast = st.session_state.get("_task_def_toast")
    assert toast is not None
    assert toast[0] == "error"
    assert "필수 컬럼" in toast[1] or "데이터" in toast[1]


# ── e2e — AppTest로 전체 app.py 구동 ────────────────────────

def _fresh_app():
    from streamlit.testing.v1 import AppTest
    from persona import store as ps
    from persona.schema import Persona
    ps.reset(); ps.clear_onboarding_dismiss()
    ps.save(Persona(name="홍길동", dept="도장1팀", team="자동화1팀"))
    at = AppTest.from_file("app.py", default_timeout=30)
    at.session_state["app_area"] = "🧱 데이터 관리"
    return at


def test_data_mgmt_renders_upload_section_with_helpful_text(isolated_dirs):
    """데이터관리 진입 + 작업 정의 탭 선택 시 업로드 섹션 노출."""
    at = _fresh_app()
    at.query_params["dm_tab"] = "task"
    at.run()
    htmls = "\n".join(h.proto.body for h in at.get("html"))
    assert "작업 정의 데이터 업로드" in htmls
    # 안내 컬럼명 노출
    assert "공정정의서(JSON)" in htmls
    # 위젯 존재
    assert len(at.get("file_uploader")) > 0
    assert not at.exception


def test_data_mgmt_ingest_pending_shows_success_toast(isolated_dirs):
    """pending payload → run 후 성공 toast (32건 ingest)."""
    with open(FIXTURE, "rb") as f:
        data = f.read()
    at = _fresh_app()
    at.session_state["_do_task_def_ingest"] = ("sample_task_def.xlsx", "시트1", data)
    at.run()
    htmls = "\n".join(h.proto.body for h in at.get("html"))
    assert "32건" in htmls or "✅" in htmls
    assert not at.exception


def test_no_legacy_term_in_main_screens():
    """사용자 노출 화면에 '로드맵' 용어 잔존 없음 (테스트 / 주석 제외)."""
    from pathlib import Path
    targets = [
        Path("assets/v2/screens/data_management_main.html"),
        Path("ui/board_v2.py"),
        Path("ui/insights_v2.py"),
        Path("ui/sidebar.py"),
        Path("ui/persona_page.py"),
        Path("ui/onboarding.py"),
        Path("ui/task_tree.py"),
    ]
    offenders: list[str] = []
    for p in targets:
        if not p.exists():
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            # 코드 식별자 (Roadmap*, roadmap_dir, load_roadmap 등)는 허용
            if "로드맵" in line:
                offenders.append(f"{p}:{i}: {line.strip()[:100]}")
    assert offenders == [], "사용자 노출 '로드맵' 잔존:\n" + "\n".join(offenders)
