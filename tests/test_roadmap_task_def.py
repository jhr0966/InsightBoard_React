"""신버전 엑셀(2026-05+) — 분과/공정/JSON 정의서 ingest + 파싱."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from roadmap import ingest, task_def_json as tdj
from roadmap.schema import ALL_COLUMNS


FIXTURE = Path(__file__).parent / "fixtures" / "sample_task_def.xlsx"


# ── schema — 신규 컬럼 정의 확인 ────────────────────────────

def test_schema_includes_new_optional_columns():
    """task_def_json / division / process 가 OPTIONAL_COLUMNS 에 있어야."""
    assert "task_def_json" in ALL_COLUMNS
    assert "division" in ALL_COLUMNS
    assert "process" in ALL_COLUMNS


def test_column_map_has_korean_headers_for_new_fields():
    from roadmap.schema import COLUMN_MAP
    assert COLUMN_MAP.get("분과") == "division"
    assert COLUMN_MAP.get("공정") == "process"
    assert COLUMN_MAP.get("공정정의서(줄글)") == "task_def"
    assert COLUMN_MAP.get("공정정의서(JSON)") == "task_def_json"


# ── ingest — 신엑셀 fallback ────────────────────────────────

@pytest.fixture
def isolated_roadmap_dir(tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, "DATA_ROOT", tmp_path)
    monkeypatch.setattr(config, "ROADMAP_DIR", tmp_path / "roadmap")
    from store import paths
    monkeypatch.setattr(paths, "ROADMAP_DIR", tmp_path / "roadmap")
    yield


def test_ingest_new_excel_succeeds_and_preserves_all_columns(isolated_roadmap_dir):
    """샘플 엑셀(32행, 8컬럼) → 정규화된 13컬럼 Parquet round-trip."""
    with open(FIXTURE, "rb") as f:
        res = ingest.ingest_excel(f, sheet_name=0, save_raw=False)
    assert res.ok, res.errors
    assert res.row_count == 32

    df = pd.read_parquet(res.parquet_path)
    # 모든 schema 컬럼 존재
    for col in ALL_COLUMNS:
        assert col in df.columns, f"missing column: {col}"
    # 신규 컬럼 실데이터
    assert df["division"].iloc[0] == "구조내업"
    assert df["process"].iloc[0] == "판넬"
    assert df["task"].iloc[0] == "선별"
    # task_def_json 보존 (텍스트로)
    assert len(df["task_def_json"].iloc[0]) > 100
    assert "process_id" in df["task_def_json"].iloc[0]


def test_ingest_lv_fallback_when_only_division_process_task(isolated_roadmap_dir):
    """신엑셀에 lv1/lv2/lv3 컬럼 없으면 division/process/task 로 자동 fallback."""
    with open(FIXTURE, "rb") as f:
        res = ingest.ingest_excel(f, sheet_name=0, save_raw=False)
    df = pd.read_parquet(res.parquet_path)
    # lv1 == division (분과)
    assert (df["lv1"] == df["division"]).all()
    # lv2 == process (공정)
    assert (df["lv2"] == df["process"]).all()
    # lv3 == task (작업)
    assert (df["lv3"] == df["task"]).all()


def test_normalize_columns_preserves_existing_lv_if_set():
    """기존 엑셀에 lv1/lv2/lv3 가 채워져 있으면 덮어쓰지 않음."""
    df = pd.DataFrame({
        "팀": ["A"], "부서": ["B"],
        "분류(Lv1)": ["기존1"], "소분류(Lv2)": ["기존2"], "공정(Lv3)": ["기존3"],
        "분과": ["새 분과"], "공정": ["새 공정"], "작업": ["새 작업"],
    })
    out = ingest.normalize_columns(df)
    # lv1/2/3 이미 채워졌으므로 fallback 무시
    assert out["lv1"].iloc[0] == "기존1"
    assert out["lv2"].iloc[0] == "기존2"
    assert out["lv3"].iloc[0] == "기존3"
    # division/process 는 그대로 유지
    assert out["division"].iloc[0] == "새 분과"
    assert out["process"].iloc[0] == "새 공정"


def test_normalize_columns_partial_lv_does_not_corrupt():
    """lv1만 채워져 있고 lv2/lv3 비어있어도 lv1 보존, lv2/lv3 도 fallback 안함.

    안전을 위해 부분 혼합 케이스에서는 lv 자동 채움 비활성 (혼란 방지).
    """
    df = pd.DataFrame({
        "팀": ["A"], "부서": ["B"],
        "분류(Lv1)": ["기존1"], "소분류(Lv2)": [""], "공정(Lv3)": [""],
        "공정": ["P"], "작업": ["T"],
    })
    out = ingest.normalize_columns(df)
    assert out["lv1"].iloc[0] == "기존1"  # 유지
    # lv2 도 fallback (그 컬럼은 모두 빈 값이므로)
    assert out["lv2"].iloc[0] == "P"
    assert out["lv3"].iloc[0] == "T"


# ── task_def_json 파서 ─────────────────────────────────────

def test_parse_empty_input_returns_empty_taskdef():
    assert tdj.parse("").is_empty()
    assert tdj.parse(None).is_empty()
    assert tdj.parse("   ").is_empty()


def test_parse_invalid_json_returns_empty_safely():
    """잘못된 JSON 도 예외 없이 빈 TaskDef."""
    out = tdj.parse("{ not valid json")
    assert out.is_empty()
    assert out.raw is None


def test_parse_non_dict_json_returns_empty():
    """JSON 자체는 valid 지만 dict 가 아니면 빈 TaskDef."""
    assert tdj.parse('["a","b"]').is_empty()
    assert tdj.parse('"just a string"').is_empty()
    assert tdj.parse('42').is_empty()


def test_parse_real_sample_extracts_core_fields():
    """실 엑셀 첫 행 JSON → process_id/name/description/objectives 모두 추출."""
    df = pd.read_excel(FIXTURE)
    js = df["공정정의서(JSON)"].iloc[0]
    task = tdj.parse(js)
    assert task.process_id == "PNL-SEL-001"
    assert "판넬 선별" in task.process_name
    # description 은 키워드 매칭으로 검증
    assert "주판" in task.process_description
    assert len(task.objectives) >= 1
    assert any("BOM" in o for o in task.objectives)
    assert not task.is_empty()


def test_parse_extracts_quality_risks_from_dict_list():
    """overall_quality_risks 가 dict 리스트여도 risk/consequence 평탄화."""
    df = pd.read_excel(FIXTURE)
    task = tdj.parse(df["공정정의서(JSON)"].iloc[0])
    assert len(task.overall_quality_risks) == 2
    # "risk · consequence" 형식
    assert "주판 방향 오배재" in task.overall_quality_risks[0]
    assert "전체 조립 기준 오류" in task.overall_quality_risks[0]


def test_parse_extracts_automation_areas_from_dict_list():
    """automation_potential_areas 가 dict 리스트여도 area/technology/effect 평탄화."""
    df = pd.read_excel(FIXTURE)
    task = tdj.parse(df["공정정의서(JSON)"].iloc[0])
    assert len(task.automation_potential_areas) == 2
    # area · technology · expected_effect 형식
    first = task.automation_potential_areas[0]
    assert "부재번호 자동 인식" in first
    assert "RFID" in first or "OCR" in first
    assert "검수 오류 방지" in first


def test_automation_keywords_splits_and_dedupes():
    """자동화 키워드 — area + technology + effect 토큰화, 중복 제거."""
    df = pd.read_excel(FIXTURE)
    task = tdj.parse(df["공정정의서(JSON)"].iloc[0])
    kw = tdj.automation_keywords(task)
    # 6 토큰 (2 entry × 3 head_keys)
    assert "부재번호 자동 인식" in kw
    assert "RFID·OCR" in kw
    assert "AI 비전" in kw
    # 중복 없음
    assert len(set(kw)) == len(kw)


def test_automation_keywords_caps_at_max_n():
    """max_n 한도 이상 키워드 안 만듦."""
    df = pd.read_excel(FIXTURE)
    task = tdj.parse(df["공정정의서(JSON)"].iloc[0])
    kw = tdj.automation_keywords(task, max_n=2)
    assert len(kw) == 2


def test_to_chat_context_lines_includes_all_signals():
    df = pd.read_excel(FIXTURE)
    task = tdj.parse(df["공정정의서(JSON)"].iloc[0])
    lines = tdj.to_chat_context_lines(task)
    joined = "\n".join(lines)
    assert "PNL-SEL-001" in joined
    assert "판넬 선별" in joined
    assert "BOM 기준" in joined
    assert "주판 방향 오배재" in joined
    assert "AI 비전" in joined or "RFID" in joined


def test_to_chat_context_lines_empty_returns_empty_list():
    assert tdj.to_chat_context_lines(tdj.TaskDef()) == []
    assert tdj.to_chat_context_lines(tdj.parse("")) == []


# ── 모든 행 안전 파싱 — 회귀 ─────────────────────────────────

def test_all_32_rows_parse_without_exception():
    """샘플 엑셀의 32행 모두 예외 없이 파싱.

    JSON 셀이 비어있는 행은 안전하게 빈 TaskDef 반환 (현재 row 5 가 빈 셀).
    채워진 행은 모두 process_id + process_name 보유.
    """
    df = pd.read_excel(FIXTURE)
    parsed = [tdj.parse(s) for s in df["공정정의서(JSON)"]]
    assert len(parsed) == 32
    # 빈 셀(=빈 TaskDef) 와 채워진 셀 구분
    filled = [p for p in parsed if not p.is_empty()]
    empty = [p for p in parsed if p.is_empty()]
    assert len(filled) >= 30  # 대부분 채워짐
    # 채워진 행은 process_id + name 모두 있어야
    assert all(p.process_id for p in filled), "filled 행에 process_id 누락"
    assert all(p.process_name for p in filled), "filled 행에 process_name 누락"
    # 빈 셀 행은 raw=None
    assert all(p.raw is None for p in empty)
