"""공정정의서_통합 폼(2026-06+) 업로드 — 쉼표 구분자 · 배너행 스킵 · 교체 · 정규 JSON.

이 폼의 규칙:
  - 한 셀 안 항목은 **쉼표(,)** 로 나열. 가운뎃점(·)은 항목 내부 표기(구분자 아님).
  - "작업 설명"(공백 포함) → process_description.
  - 첫 행은 `◀ 계층 구조 ▶` 류 안내 배너 → 검증 전 제거.
  - 재업로드 = 데이터 **교체**(replace): 직전 데이터셋을 비우고 새 파일로.
  - 업로드마다 정규 JSON(`task_defs.json`) 통째 저장(React/백엔드 공용 계약).
"""
from __future__ import annotations

import io
import json

import pandas as pd

from roadmap import ingest
from roadmap import task_def_json as tdj
from store import task_defs_db


def _banner_row() -> dict:
    """폼 1행 — 안내 배너. 실데이터 아님(◀ ... ▶ 마커)."""
    return {
        "분과": "◀ 계층 구조 (A~E) ▶", "팀": "", "부서": "", "공정": "", "작업": "",
        "Dept_ID": "◀ 식별 ID (F~H) ▶", "Work_ID": "", "Process_ID": "",
        "작업 설명": "◀ 작업 설명 (I) ▶", "작업흐름": "◀ 작업흐름 (J) ▶",
        "주요확인사항": "", "안전주의사항": "", "주요사용장비": "",
        "품질리스크": "", "자동화가능영역": "", "이전공정": "",
        "Pre_Process_ID": "", "다음공정": "", "Post_Process_ID": "",
    }


def _data_row(**over) -> dict:
    base = {
        "분과": "7", "팀": "C팀", "부서": "C1", "공정": "가공", "작업": "절단",
        "Dept_ID": "7-C팀-C1", "Work_ID": "가공-절단", "Process_ID": "7-CT-C1-FAB-CUT",
        "작업 설명": "강재를 도면 치수로 절단하는 공정.",
        "작업흐름": "1) 세팅\n2) 절단",
        # 쉼표 구분 · 항목 내부에 가운뎃점(·) 보존돼야 함
        "주요확인사항": "NC 데이터 규격 일치, 치수 ±2mm, 드로스·버 제거, 부재번호 마킹",
        "안전주의사항": "절단 경로 내 접근 금지, 집진 설비 가동",
        "주요사용장비": "마그네틱 크레인·호이스트 (이동), 대차 (상차)",
        "품질리스크": "NC 데이터 오류→치수 불량, 부재번호 누락→자재 혼용",
        "자동화가능영역": "AI 네스팅 (딥러닝), AI 비전 검사 (AI 비전)",
        "이전공정": "", "Pre_Process_ID": "", "다음공정": "가공-선별,\n소조-배재",
        "Post_Process_ID": "7-CT-C1-FAB-SORT",
    }
    base.update(over)
    return base


def _excel_bytes(rows: list[dict]) -> io.BytesIO:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        pd.DataFrame(rows).to_excel(w, sheet_name="공정정의서_통합", index=False)
    buf.seek(0)
    return buf


# ── 쉼표 구분자 (가운뎃점은 항목 내부 보존) ──────────────────

def test_split_list_cell_uses_comma_not_middot():
    assert tdj.split_list_cell("a, b, c") == ["a", "b", "c"]
    # 가운뎃점은 항목 내부 — 쪼개지 않는다
    assert tdj.split_list_cell("크레인·호이스트 (이동), 대차") == [
        "크레인·호이스트 (이동)", "대차",
    ]
    # 구버전 호환: 세미콜론·선행 불릿은 그대로
    assert tdj.split_list_cell("- x; • y; · z") == ["x", "y", "z"]


# ── 배너행 스킵 ────────────────────────────────────────────

def test_drop_guide_rows_removes_banner():
    df = ingest.normalize_columns(pd.DataFrame([_banner_row(), _data_row()]))
    for c in df.columns:
        df[c] = df[c].astype(str).str.strip()
    kept = ingest.drop_guide_rows(df)
    assert len(kept) == 1
    assert kept.iloc[0]["process_id"] == "7-CT-C1-FAB-CUT"


# ── end-to-end: 배너 포함 업로드 → 데이터행만 적재 ─────────

def test_ingest_form_skips_banner_and_parses_lists():
    res = ingest.ingest_excel(_excel_bytes([_banner_row(), _data_row()]),
                              sheet_name="Master_Table", save_raw=False, replace=True)
    assert res.ok, res.errors
    assert res.row_count == 1            # 배너 1행 제거
    assert res.sqlite_created == 1

    rec = task_defs_db.get("7-CT-C1-FAB-CUT")
    assert rec is not None
    obj = rec["json_obj"]
    assert obj["process_description"].startswith("강재를 도면")
    # 쉼표로 4개 — 가운뎃점 항목("드로스·버 제거")은 한 덩어리로 보존
    assert obj["key_check_points"] == [
        "NC 데이터 규격 일치", "치수 ±2mm", "드로스·버 제거", "부재번호 마킹",
    ]
    assert obj["main_equipment"] == ["마그네틱 크레인·호이스트 (이동)", "대차 (상차)"]
    assert obj["overall_quality_risks"] == [
        "NC 데이터 오류→치수 불량", "부재번호 누락→자재 혼용",
    ]
    assert obj["org_meta"]["team"] == "C팀" and obj["org_meta"]["dept"] == "C1"


# ── 정규 JSON 데이터셋 (React/백엔드 계약) ──────────────────

def test_ingest_writes_canonical_json():
    res = ingest.ingest_excel(_excel_bytes([_data_row()]),
                              sheet_name="Master_Table", save_raw=False, replace=True)
    assert res.json_path
    doc = json.loads(open(res.json_path, encoding="utf-8").read())
    assert doc["schema_version"] == "1.0"
    assert doc["count"] == 1
    assert doc["task_defs"][0]["process_id"] == "7-CT-C1-FAB-CUT"


# ── 재업로드 = 교체 (병합 아님) ─────────────────────────────

def test_reupload_replaces_dataset():
    # 1차: 2건
    ingest.ingest_excel(
        _excel_bytes([_data_row(), _data_row(Process_ID="7-CT-C1-FAB-SORT", 작업="선별")]),
        sheet_name="Master_Table", save_raw=False, replace=True)
    assert task_defs_db.count() == 2

    # 2차: 새 1건만 → 교체되어 1건만 남아야 한다(직전 2건 제거)
    res = ingest.ingest_excel(
        _excel_bytes([_data_row(Process_ID="9-ZT-Z9-PNT-BLAST", 팀="Z팀", 부서="Z9",
                                공정="도장", 작업="블라스팅")]),
        sheet_name="Master_Table", save_raw=False, replace=True)
    assert res.ok, res.errors
    assert task_defs_db.count() == 1
    ids = [r["process_id"] for r in task_defs_db.list_all()]
    assert ids == ["9-ZT-Z9-PNT-BLAST"]

    # 정규 JSON 도 교체 반영(count=1)
    doc = json.loads(open(res.json_path, encoding="utf-8").read())
    assert doc["count"] == 1
