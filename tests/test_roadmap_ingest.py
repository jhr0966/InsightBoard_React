"""로드맵 엑셀 정규화/검증/저장 회귀 테스트."""
from __future__ import annotations

import io

import pandas as pd

from roadmap.ingest import IngestResult, ingest_excel, normalize_columns, validate
from roadmap.query import by_dept, by_lv, filter_hierarchy, load_latest
from roadmap.schema import ALL_COLUMNS


def _make_excel_bytes(df: pd.DataFrame, sheet: str = "Master_Table") -> io.BytesIO:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, sheet_name=sheet, index=False)
    buf.seek(0)
    return buf


def test_normalize_columns_maps_korean_headers():
    raw = pd.DataFrame([
        {
            "팀": "가공팀", "부서": "가공부",
            "분류(Lv1)": "실행분과", "소분류(Lv2)": "구조내업", "공정(Lv3)": "전처리",
            "작업": "강재선별", "세부 작업": "강재선별(크레인)",
            "작업 정의": "", "SWS 표준번호": "SC0-1H45600-009-002", "SWS명": "강재 하역",
        }
    ])
    out = normalize_columns(raw)
    assert list(out.columns) == list(ALL_COLUMNS)
    assert out.loc[0, "team"] == "가공팀"
    assert out.loc[0, "lv3"] == "전처리"
    assert out.loc[0, "sws_no"] == "SC0-1H45600-009-002"


def test_validate_flags_missing_required():
    df = pd.DataFrame({c: ["x"] for c in ALL_COLUMNS})
    df["dept"] = ""
    errs = validate(df)
    assert any("dept" in e for e in errs)


def test_ingest_excel_roundtrip(tmp_path):
    raw = pd.DataFrame([
        {
            "팀": "가공팀", "부서": "가공부",
            "분류(Lv1)": "실행분과", "소분류(Lv2)": "구조내업", "공정(Lv3)": "전처리",
            "작업": "강재선별", "세부 작업": "크레인", "작업 정의": "",
            "SWS 표준번호": "SC0-1", "SWS명": "강재 하역",
        },
        {
            "팀": "가공팀", "부서": "가공부",
            "분류(Lv1)": "실행분과", "소분류(Lv2)": "구조내업", "공정(Lv3)": "가공",
            "작업": "절단", "세부 작업": "절단", "작업 정의": "",
            "SWS 표준번호": "SC0-2", "SWS명": "절단 작업",
        },
    ])
    buf = _make_excel_bytes(raw)

    result: IngestResult = ingest_excel(buf, sheet_name="Master_Table")
    assert result.ok, result.errors
    assert result.row_count == 2

    df = load_latest()
    assert len(df) == 2
    assert by_dept(df).iloc[0]["dept"] == "가공부"
    assert set(by_lv(df, "lv3")["lv3"]) == {"전처리", "가공"}
    filtered = filter_hierarchy(df, lv3="전처리")
    assert len(filtered) == 1 and filtered.iloc[0]["task"] == "강재선별"


def test_ingest_excel_falls_back_to_first_sheet():
    raw = pd.DataFrame([
        {
            "팀": "가공팀", "부서": "가공부",
            "분류(Lv1)": "실행분과", "소분류(Lv2)": "구조내업", "공정(Lv3)": "전처리",
            "작업": "강재선별",
        }
    ])
    buf = _make_excel_bytes(raw, sheet="DifferentName")
    result = ingest_excel(buf, sheet_name="Master_Table")
    assert result.ok
    assert result.row_count == 1


def test_ingest_surfaces_sqlite_sync_error(monkeypatch):
    """C3 — SQLite 동기화 실패 시 result.sqlite_error 에 표면화(Parquet 성공이라 ok 는 유지)."""
    raw = pd.DataFrame([{
        "팀": "가공팀", "부서": "가공부",
        "분류(Lv1)": "실행분과", "소분류(Lv2)": "구조내업", "공정(Lv3)": "전처리",
        "작업": "강재선별", "세부 작업": "크레인", "작업 정의": "",
        "SWS 표준번호": "SC0-1", "SWS명": "강재 하역",
    }])
    buf = _make_excel_bytes(raw)
    import roadmap.sqlite_sync as ss
    monkeypatch.setattr(ss, "sync_dataframe", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("db locked")))
    result = ingest_excel(buf, sheet_name="Master_Table", to_sqlite=True)
    assert result.ok and result.parquet_path           # Parquet 은 성공 → ok 유지
    assert "db locked" in result.sqlite_error           # 동기화 실패가 조용히 묻히지 않음
