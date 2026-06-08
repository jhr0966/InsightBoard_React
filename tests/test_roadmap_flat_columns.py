"""flat-column 엑셀(2026-06+) — JSON 열 없이 개별 컬럼을 task_def_json 으로 조립.

분과·팀·부서·공정·작업·세부작업·Process_ID·공정설명·작업흐름·주요확인사항·
안전주의사항·주요사용장비·품질리스크·자동화가능영역·이전공정·다음공정
→ 구조화 JSON (org_meta 주입 + 매칭/SOLA 표준 키 매핑).
"""
from __future__ import annotations

import io
import json

import pandas as pd

from roadmap import ingest
from roadmap import task_def_json as tdj
from roadmap.schema import ALL_COLUMNS, COLUMN_MAP, OPTIONAL_COLUMNS


def _flat_row(**over) -> dict:
    base = {
        "분과": "구조내업", "팀": "가공팀", "부서": "가공부",
        "공정": "판넬", "작업": "판넬 선별", "세부작업": "주판 검수",
        "Process_ID": "PNL-SEL-001",
        "공정설명": "주판을 BOM 기준으로 수입 검수한다.",
        "작업흐름": "강재 반입 → 치수 검수 → 적치",
        "주요확인사항": "치수 오차\n표면 결함\n각인 확인",
        "안전주의사항": "크레인 하부 출입금지; 보호구 착용",
        "주요사용장비": "천장크레인\n버니어캘리퍼스",
        "품질리스크": "주판 혼입\n치수 불량",
        "자동화가능영역": "부재번호 자동 인식 (RFID/OCR)\n비전 치수 측정",
        "이전공정": "강재 입고",
        "다음공정": "판넬 조립",
    }
    base.update(over)
    return base


def _norm_row(**over) -> dict:
    """`assemble_from_columns` 입력용 — 정규화(코드) 컬럼명 dict.

    assemble 는 normalize_columns 가 헤더를 rename 한 *뒤* 호출되므로 코드명을 읽는다.
    """
    base = {
        "division": "구조내업", "team": "가공팀", "dept": "가공부",
        "process": "판넬", "task": "판넬 선별", "sub_task": "주판 검수",
        "process_id": "PNL-SEL-001",
        "process_description": "주판을 BOM 기준으로 수입 검수한다.",
        "work_flow": "강재 반입 → 치수 검수 → 적치",
        "key_check_points": "치수 오차\n표면 결함\n각인 확인",
        "safety_notes": "크레인 하부 출입금지; 보호구 착용",
        "main_equipment": "천장크레인\n버니어캘리퍼스",
        "quality_risks": "주판 혼입\n치수 불량",
        "automation_areas": "부재번호 자동 인식 (RFID/OCR)\n비전 치수 측정",
        "previous_process": "강재 입고",
        "next_process": "판넬 조립",
    }
    base.update(over)
    return base


def _make_excel_bytes(df: pd.DataFrame, sheet: str = "Master_Table") -> io.BytesIO:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, sheet_name=sheet, index=False)
    buf.seek(0)
    return buf


# ── 스키마 ─────────────────────────────────────────────────

def test_column_map_has_flat_headers():
    assert COLUMN_MAP["Process_ID"] == "process_id"
    assert COLUMN_MAP["공정설명"] == "process_description"
    assert COLUMN_MAP["작업흐름"] == "work_flow"
    assert COLUMN_MAP["주요확인사항"] == "key_check_points"
    assert COLUMN_MAP["안전주의사항"] == "safety_notes"
    assert COLUMN_MAP["주요사용장비"] == "main_equipment"
    assert COLUMN_MAP["품질리스크"] == "quality_risks"
    assert COLUMN_MAP["자동화가능영역"] == "automation_areas"
    assert COLUMN_MAP["이전공정"] == "previous_process"
    assert COLUMN_MAP["다음공정"] == "next_process"


def test_flat_columns_in_optional():
    for col in ("process_description", "work_flow", "key_check_points",
                "safety_notes", "main_equipment", "quality_risks",
                "automation_areas", "previous_process", "next_process"):
        assert col in OPTIONAL_COLUMNS
        assert col in ALL_COLUMNS


# ── split_list_cell ────────────────────────────────────────

def test_split_list_cell_newline():
    assert tdj.split_list_cell("a\nb\nc") == ["a", "b", "c"]


def test_split_list_cell_semicolon_and_bullets():
    assert tdj.split_list_cell("- x; • y; · z") == ["x", "y", "z"]


def test_split_list_cell_dedup_and_empty():
    assert tdj.split_list_cell("x\nx\n\ny") == ["x", "y"]
    assert tdj.split_list_cell("") == []
    assert tdj.split_list_cell(None) == []


def test_split_list_cell_single_line():
    assert tdj.split_list_cell("단일 항목") == ["단일 항목"]


# ── assemble_from_columns ──────────────────────────────────

def test_assemble_builds_payload_with_canonical_keys():
    payload = tdj.assemble_from_columns(_norm_row())
    assert payload["process_description"].startswith("주판")
    assert payload["work_flow"] == "강재 반입 → 치수 검수 → 적치"
    assert payload["key_check_points"] == ["치수 오차", "표면 결함", "각인 확인"]
    assert payload["safety_notes"] == ["크레인 하부 출입금지", "보호구 착용"]
    assert payload["main_equipment"] == ["천장크레인", "버니어캘리퍼스"]
    # 매칭/SOLA 표준 키로 매핑
    assert payload["overall_quality_risks"] == ["주판 혼입", "치수 불량"]
    assert payload["automation_potential_areas"][0].startswith("부재번호")
    assert payload["previous_process"] == "강재 입고"
    assert payload["next_process"] == "판넬 조립"
    # process_name 컬럼이 없어 세부작업으로 보강
    assert payload["process_name"] == "주판 검수"


def test_assemble_process_name_falls_back_to_task():
    payload = tdj.assemble_from_columns(_norm_row(sub_task=""))
    assert payload["process_name"] == "판넬 선별"


def test_assemble_empty_when_no_rich_columns():
    """공정설명 등 신 컬럼이 모두 비면 빈 dict — 구 포맷 행 보존."""
    row = {"team": "가공팀", "dept": "가공부", "task": "절단", "sub_task": "절단"}
    assert tdj.assemble_from_columns(row) == {}


# ── normalize_columns 통합 ─────────────────────────────────

def test_normalize_fills_task_def_json_for_flat_format():
    df = ingest.normalize_columns(pd.DataFrame([_flat_row()]))
    assert list(df.columns) == list(ALL_COLUMNS)
    obj = json.loads(df.loc[0, "task_def_json"])
    assert obj["process_description"].startswith("주판")
    assert obj["overall_quality_risks"] == ["주판 혼입", "치수 불량"]
    # org_meta 는 아직 미주입(sqlite_sync 가 주입) — 조립 단계엔 없음
    assert "org_meta" not in obj


def test_normalize_leaves_old_format_task_def_json_empty():
    raw = pd.DataFrame([{
        "팀": "가공팀", "부서": "가공부",
        "분류(Lv1)": "a", "소분류(Lv2)": "b", "공정(Lv3)": "c", "작업": "절단",
    }])
    df = ingest.normalize_columns(raw)
    assert df.loc[0, "task_def_json"] == ""


def test_normalize_does_not_overwrite_existing_json():
    existing = json.dumps({"process_id": "X", "process_name": "기존"}, ensure_ascii=False)
    row = _flat_row()
    row["공정정의서(JSON)"] = existing
    df = ingest.normalize_columns(pd.DataFrame([row]))
    # 이미 JSON 열이 있으면 조립하지 않고 그대로 둔다
    assert json.loads(df.loc[0, "task_def_json"])["process_name"] == "기존"


# ── ingest_excel → SQLite end-to-end ───────────────────────

def test_ingest_flat_excel_writes_sqlite_with_org_meta():
    from store import task_defs_db

    buf = _make_excel_bytes(pd.DataFrame([_flat_row()]))
    result = ingest.ingest_excel(buf, sheet_name="Master_Table")
    assert result.ok, result.errors
    assert result.sqlite_created == 1, result.sqlite_error

    rec = task_defs_db.get("PNL-SEL-001")
    assert rec is not None
    assert rec["team"] == "가공팀" and rec["dept"] == "가공부"
    obj = rec["json_obj"]
    assert obj["org_meta"]["division"] == "구조내업"
    assert obj["org_meta"]["sub_task"] == "주판 검수"
    assert obj["process_id"] == "PNL-SEL-001"
    assert obj["overall_quality_risks"] == ["주판 혼입", "치수 불량"]
    assert obj["key_check_points"] == ["치수 오차", "표면 결함", "각인 확인"]


def test_ingest_flat_excel_skips_row_without_process_id():
    from store import task_defs_db

    buf = _make_excel_bytes(pd.DataFrame([_flat_row(Process_ID="")]))
    result = ingest.ingest_excel(buf, sheet_name="Master_Table")
    assert result.ok, result.errors
    assert result.sqlite_created == 0
    assert result.sqlite_skipped == 1
    assert task_defs_db.count() == 0


# ── parse / 매칭 / 컨텍스트 활용 ───────────────────────────

def test_parse_reads_flat_fields():
    payload = tdj.assemble_from_columns(_norm_row())
    t = tdj.parse(json.dumps(payload, ensure_ascii=False))
    assert t.work_flow == "강재 반입 → 치수 검수 → 적치"
    assert t.key_check_points == ("치수 오차", "표면 결함", "각인 확인")
    assert t.safety_notes == ("크레인 하부 출입금지", "보호구 착용")
    assert t.main_equipment == ("천장크레인", "버니어캘리퍼스")
    assert t.previous_process == "강재 입고"
    assert t.next_process == "판넬 조립"
    assert not t.is_empty()


def test_flatten_for_match_includes_flat_signals():
    payload = tdj.assemble_from_columns(_norm_row())
    blob = tdj.flatten_for_match(json.dumps(payload, ensure_ascii=False))
    # 신 필드 텍스트가 매칭 평탄 텍스트에 포함되어야
    assert "표면 결함" in blob          # key_check_points
    assert "보호구 착용" in blob         # safety_notes
    assert "버니어캘리퍼스" in blob       # main_equipment
    assert "강재 반입" in blob           # work_flow


def test_chat_context_lines_includes_flat_fields():
    payload = tdj.assemble_from_columns(_norm_row())
    t = tdj.parse(json.dumps(payload, ensure_ascii=False))
    text = "\n".join(tdj.to_chat_context_lines(t))
    assert "작업 흐름" in text
    assert "주요 확인사항" in text
    assert "공정 연결" in text


def test_score_matches_uses_flat_automation_area():
    """flat 조립 JSON 의 자동화 영역 토큰이 뉴스 매칭에 반영."""
    from store.match import score_matches

    tasks = ingest.normalize_columns(pd.DataFrame([_flat_row()]))
    news = pd.DataFrame([{
        "title": "RFID·OCR 기반 부재번호 자동 인식 비전 시스템 도입",
        "summary": "조선소 판넬 공정에 비전 치수 측정 자동화 적용",
        "keywords": "RFID, OCR, 비전",
        "url": "http://example.com/a",
    }])
    matched = score_matches(news, tasks)
    # task_def_json 의 automation_potential_areas 신호로 매칭 성사
    assert not matched.empty
