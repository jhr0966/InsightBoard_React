"""엑셀 업로드 diff 미리보기 + 확인 (PR-5)."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest


FIXTURE = Path(__file__).parent / "fixtures" / "sample_task_def.xlsx"


def _row(**kw) -> dict:
    from roadmap.schema import ALL_COLUMNS
    base = {c: "" for c in ALL_COLUMNS}
    base.update(kw)
    return base


def _json(process_id="PNL-SEL-001", name="판넬 선별", **extra) -> str:
    d = {"process_id": process_id, "process_name": name, "objectives": ["검수"]}
    d.update(extra)
    return json.dumps(d, ensure_ascii=False)


# ── DiffPreview 자체 ─────────────────────────────────────

def test_diff_preview_dataclass_defaults():
    from roadmap.sqlite_sync import DiffPreview
    d = DiffPreview()
    assert d.added == []
    assert d.updated == []
    assert d.unchanged == []
    assert d.kept == []
    assert d.skipped == 0
    assert d.total_apply == 0


def test_diff_preview_total_apply():
    from roadmap.sqlite_sync import DiffPreview
    d = DiffPreview(added=[("A1", "n")], updated=[("A2", "n"), ("A3", "n")])
    assert d.total_apply == 3


# ── compute_diff — 신규 ─────────────────────────────────

def test_compute_diff_all_new_when_db_empty():
    from roadmap.sqlite_sync import compute_diff
    df = pd.DataFrame([
        _row(team="T", dept="D", process_id="A1", task_def_json=_json("A1", "이름A1")),
        _row(team="T", dept="D", process_id="A2", task_def_json=_json("A2")),
    ])
    diff = compute_diff(df)
    assert {pid for pid, _ in diff.added} == {"A1", "A2"}
    assert diff.updated == []
    assert diff.unchanged == []
    assert diff.kept == []
    assert diff.total_apply == 2
    # 표시 이름은 process_name 우선
    pids_names = dict(diff.added)
    assert pids_names["A1"] == "이름A1"


def test_compute_diff_marks_updated_when_json_changes():
    from roadmap.sqlite_sync import compute_diff, sync_dataframe
    # 1차 적재
    df1 = pd.DataFrame([_row(team="T", dept="D", process_id="A1",
                              task_def_json=_json("A1", objectives=["old"]))])
    sync_dataframe(df1)
    # 2차 — objectives 가 다름
    df2 = pd.DataFrame([_row(team="T", dept="D", process_id="A1",
                              task_def_json=_json("A1", objectives=["new"]))])
    diff = compute_diff(df2)
    assert diff.added == []
    assert [pid for pid, _ in diff.updated] == ["A1"]
    assert diff.unchanged == []


def test_compute_diff_marks_unchanged_when_json_identical():
    from roadmap.sqlite_sync import compute_diff, sync_dataframe
    # 동일 행 두 번 — compute_diff 호출 시 unchanged 로 분류돼야
    row = _row(team="T", dept="D", process_id="A1", task_def_json=_json("A1"))
    sync_dataframe(pd.DataFrame([row]))
    diff = compute_diff(pd.DataFrame([row]))
    assert diff.added == []
    assert diff.updated == []
    assert diff.unchanged == ["A1"]


def test_compute_diff_lists_kept_for_db_rows_not_in_upload():
    from roadmap.sqlite_sync import compute_diff, sync_dataframe
    # DB 에 2건 적재
    sync_dataframe(pd.DataFrame([
        _row(team="T", dept="D", process_id="A1", task_def_json=_json("A1")),
        _row(team="T", dept="D", process_id="A2", task_def_json=_json("A2")),
    ]))
    # 업로드는 A1 + 새 A3
    df_up = pd.DataFrame([
        _row(team="T", dept="D", process_id="A1", task_def_json=_json("A1")),
        _row(team="T", dept="D", process_id="A3", task_def_json=_json("A3")),
    ])
    diff = compute_diff(df_up)
    assert [pid for pid, _ in diff.added] == ["A3"]
    assert diff.unchanged == ["A1"]
    assert {pid for pid, _ in diff.kept} == {"A2"}


def test_compute_diff_counts_skipped_rows():
    from roadmap.sqlite_sync import compute_diff
    df = pd.DataFrame([
        _row(team="T", dept="D", process_id="A1", task_def_json=_json("A1")),
        _row(team="T", dept="", process_id="A2", task_def_json=_json("A2")),  # dept 없음
        _row(team="T", dept="D", task_def_json=""),                            # pid 없음
    ])
    diff = compute_diff(df)
    assert len(diff.added) == 1
    assert diff.skipped == 2


def test_compute_diff_empty_upload_lists_all_kept():
    from roadmap.sqlite_sync import compute_diff, sync_dataframe
    sync_dataframe(pd.DataFrame([
        _row(team="T", dept="D", process_id="A1", task_def_json=_json("A1")),
        _row(team="T", dept="D", process_id="A2", task_def_json=_json("A2")),
    ]))
    diff = compute_diff(pd.DataFrame())
    assert diff.added == []
    assert diff.updated == []
    assert {pid for pid, _ in diff.kept} == {"A1", "A2"}


def test_compute_diff_does_not_write():
    """compute_diff 는 read-only — DB 카운트가 그대로."""
    from roadmap.sqlite_sync import compute_diff
    from store import task_defs_db
    df = pd.DataFrame([_row(team="T", dept="D", process_id="A1",
                             task_def_json=_json("A1"))])
    compute_diff(df)
    assert task_defs_db.count() == 0


# ── _display_name ───────────────────────────────────────

def test_display_name_prefers_process_name():
    from roadmap.sqlite_sync import _display_name
    js = json.dumps({"process_id": "X1", "process_name": "이름X1"})
    assert _display_name(js, "X1") == "이름X1"


def test_display_name_falls_back_to_process_id():
    from roadmap.sqlite_sync import _display_name
    js = json.dumps({"process_id": "X1"})
    assert _display_name(js, "X1") == "X1"
    # invalid → pid
    assert _display_name("not json", "X9") == "X9"
    assert _display_name(json.dumps([1, 2]), "X9") == "X9"


# ── _compute_pending_diff — UI helper ───────────────────

def test_pending_diff_returns_diff_from_excel_bytes():
    from ui import data_management_v2 as dm
    data = FIXTURE.read_bytes()
    diff, err = dm._compute_pending_diff(data, 0)
    assert err is None
    # 빈 DB → 31 added + 1 skipped (fixture 1건 JSON 빈 행)
    assert len(diff.added) == 31
    assert diff.skipped == 1
    assert diff.kept == []


def test_pending_diff_invalid_bytes_returns_error_message():
    from ui import data_management_v2 as dm
    diff, err = dm._compute_pending_diff(b"not an xlsx", 0)
    assert diff is None
    assert err and "엑셀 읽기 실패" in err


# ── UI _render_task_def_upload pending 흐름 — 미리보기 단계 ─

def test_render_task_def_upload_button_label_changed_to_preview():
    """업로드 화면에 미리보기 버튼 라벨 노출 (구 '저장' 직행 X)."""
    import io
    from ui import data_management_v2 as dm

    fake_uploaded = type("F", (), {
        "name": "x.xlsx",
        "seek": lambda self, n=0: None,
        "read": lambda self: b"",
    })()

    captured: list[tuple[str, dict]] = []
    def _btn(label, **kw):
        captured.append((label, kw))
        return False  # 클릭 안 함

    with patch("streamlit.file_uploader", return_value=fake_uploaded), \
         patch("streamlit.session_state", new={}), \
         patch("streamlit.html"), \
         patch("streamlit.caption"), \
         patch("streamlit.columns", return_value=(_StubCtx(), _StubCtx())), \
         patch("streamlit.selectbox", return_value="Sheet1"), \
         patch("pandas.ExcelFile") as XL, \
         patch("pandas.read_excel", return_value=pd.DataFrame({"a": [1]})), \
         patch("streamlit.dataframe"), \
         patch("streamlit.button", side_effect=_btn):
        XL.return_value.sheet_names = ["Sheet1"]
        dm._render_task_def_upload()

    labels = [c[0] for c in captured]
    assert any("미리보기" in lab for lab in labels)


class _StubCtx:
    def __enter__(self): return self
    def __exit__(self, *a): return False


def test_render_diff_preview_apply_button_sets_ingest_pending():
    """[✅ N건 적용] → _do_task_def_ingest 페이로드를 session_state 에 설정 + pending 제거."""
    from ui import data_management_v2 as dm
    from roadmap.sqlite_sync import DiffPreview

    pending = {"filename": "x.xlsx", "sheet": 0, "data": b"DATA"}
    state: dict = {"_task_def_pending": pending}

    # 두 번째 버튼(적용)만 True 반환
    calls = {"n": 0}
    def _btn(label, **kw):
        calls["n"] += 1
        return calls["n"] == 2

    fake_diff = DiffPreview(added=[("A1", "이름A1")])
    with patch.object(dm, "_compute_pending_diff", return_value=(fake_diff, None)), \
         patch("streamlit.session_state", new=state), \
         patch("streamlit.html"), \
         patch("streamlit.caption"), \
         patch("streamlit.markdown"), \
         patch("streamlit.expander", return_value=_StubCtx()), \
         patch("streamlit.columns", return_value=(_StubCtx(), _StubCtx())), \
         patch("streamlit.error"), \
         patch("streamlit.rerun"), \
         patch("streamlit.button", side_effect=_btn):
        dm._render_task_def_diff_preview(pending)

    # apply 버튼이 ingest 페이로드를 채움 + pending 제거
    assert "_do_task_def_ingest" in state
    assert state["_do_task_def_ingest"] == ("x.xlsx", 0, b"DATA")
    assert "_task_def_pending" not in state


def test_render_diff_preview_cancel_button_clears_pending():
    from ui import data_management_v2 as dm
    from roadmap.sqlite_sync import DiffPreview

    pending = {"filename": "x.xlsx", "sheet": 0, "data": b"DATA"}
    state: dict = {"_task_def_pending": pending}

    calls = {"n": 0}
    def _btn(label, **kw):
        calls["n"] += 1
        return calls["n"] == 1  # 취소만 True

    fake_diff = DiffPreview(added=[("A1", "이름A1")])
    with patch.object(dm, "_compute_pending_diff", return_value=(fake_diff, None)), \
         patch("streamlit.session_state", new=state), \
         patch("streamlit.html"), \
         patch("streamlit.caption"), \
         patch("streamlit.markdown"), \
         patch("streamlit.expander", return_value=_StubCtx()), \
         patch("streamlit.columns", return_value=(_StubCtx(), _StubCtx())), \
         patch("streamlit.error"), \
         patch("streamlit.rerun"), \
         patch("streamlit.button", side_effect=_btn):
        dm._render_task_def_diff_preview(pending)

    assert "_do_task_def_ingest" not in state
    assert "_task_def_pending" not in state


def test_render_diff_preview_apply_disabled_when_zero_apply():
    """unchanged 만 있는 경우 적용 버튼이 disabled."""
    from ui import data_management_v2 as dm
    from roadmap.sqlite_sync import DiffPreview

    pending = {"filename": "x.xlsx", "sheet": 0, "data": b"DATA"}
    state: dict = {"_task_def_pending": pending}

    captured: list[dict] = []
    def _btn(label, **kw):
        captured.append({"label": label, **kw})
        return False

    fake_diff = DiffPreview(unchanged=["A1", "A2"])  # apply=0
    with patch.object(dm, "_compute_pending_diff", return_value=(fake_diff, None)), \
         patch("streamlit.session_state", new=state), \
         patch("streamlit.html"), \
         patch("streamlit.caption"), \
         patch("streamlit.markdown"), \
         patch("streamlit.expander", return_value=_StubCtx()), \
         patch("streamlit.columns", return_value=(_StubCtx(), _StubCtx())), \
         patch("streamlit.error"), \
         patch("streamlit.rerun"), \
         patch("streamlit.button", side_effect=_btn):
        dm._render_task_def_diff_preview(pending)

    # 적용 버튼은 disabled
    apply_btn = next(c for c in captured if "적용" in c["label"] or "변경 사항 없음" in c["label"])
    assert apply_btn.get("disabled") is True
