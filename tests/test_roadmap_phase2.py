"""작업 정의 엑셀 Phase 2 — 매칭/카드/SOLA 컨텍스트에 task_def_json 활용."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from roadmap import ingest, task_def_json as tdj
from roadmap.task_def_json import flatten_for_match, first_objective
from sola.opportunity import score_cells
from store.match import score_matches


FIXTURE = Path(__file__).parent / "fixtures" / "sample_task_def.xlsx"


@pytest.fixture
def sample_tasks_df():
    """샘플 엑셀 → 정규화된 DataFrame (32행, task_def_json 포함)."""
    df_raw = pd.read_excel(FIXTURE)
    return ingest.normalize_columns(df_raw)


# ── flatten_for_match / first_objective ─────────────────────

def test_flatten_for_match_empty_returns_empty():
    assert flatten_for_match("") == ""
    assert flatten_for_match(None) == ""
    assert flatten_for_match("not json") == ""


def test_flatten_for_match_combines_all_textual_signals():
    df = pd.read_excel(FIXTURE)
    flat = flatten_for_match(df["공정정의서(JSON)"].iloc[0])
    # process_name + description + objectives + risks + automation areas
    assert "판넬 선별" in flat
    assert "BOM" in flat              # objectives
    assert "주판 방향 오배재" in flat   # quality risks
    assert "부재번호 자동 인식" in flat  # automation areas
    # Non-empty
    assert len(flat) > 100


def test_first_objective_returns_first_or_empty():
    df = pd.read_excel(FIXTURE)
    obj = first_objective(df["공정정의서(JSON)"].iloc[0])
    assert obj == "BOM 기준 주판 수입 검수"
    # empty / invalid
    assert first_objective("") == ""
    assert first_objective(None) == ""
    assert first_objective("{not json") == ""


# ── store.match — task_def_json 텍스트가 매칭에 영향 ─────────

def test_score_matches_uses_task_def_json_keywords(sample_tasks_df):
    """JSON 정의서의 자동화 영역 키워드 ("RFID OCR 부재번호") 가 뉴스와 매칭."""
    news = pd.DataFrame([
        {"title": "RFID OCR 부재번호 자동 인식 도입 사례",
         "summary": "검수 오류 방지", "keywords": "RFID OCR",
         "source": "AI Times", "link": "http://x/1"},
    ])
    matches = score_matches(news, sample_tasks_df, top_k=3)
    # task_def_json 의 automation area "부재번호 자동 인식 · RFID·OCR" 이
    # 매칭 토큰에 포함되어야 — 판넬 선별 작업과 매칭
    assert not matches.empty
    target = matches[matches["task"].str.contains("선별", na=False)]
    assert not target.empty, "task_def_json 매칭 실패 — 판넬 선별 매칭 안 됨"


def test_score_matches_works_without_task_def_json():
    """task_def_json 컬럼이 없어도 정상 동작 (기존 엑셀 호환)."""
    roadmap_no_tdj = pd.DataFrame([
        {"dept": "도장", "lv3": "비전 검사", "task": "AI 비전 검사",
         "task_def": "AI 비전 기반 결함 검사"},
    ])
    news = pd.DataFrame([
        {"title": "AI 비전 검사 도입", "summary": "", "keywords": "AI 비전",
         "source": "x", "link": "http://x"},
    ])
    matches = score_matches(news, roadmap_no_tdj, top_k=3)
    assert not matches.empty


# ── sola.opportunity — sample_objectives 컬럼 추가 ──────────

def test_score_cells_includes_sample_objectives_column(sample_tasks_df):
    news = pd.DataFrame([
        {"title": "RFID OCR 부재번호 자동 인식", "summary": "검수 오류 방지",
         "keywords": "RFID", "source": "x", "link": "http://x/1"},
    ])
    cells = score_cells(news, sample_tasks_df)
    assert "sample_objectives" in cells.columns
    # 매칭된 cell 의 objective 가 채워짐 (sample_objective 가 비어있을 수도
    # 있지만 컬럼은 항상 존재)
    if not cells.empty:
        # 적어도 1개 cell 은 objective 가 채워짐
        non_empty = cells[cells["sample_objectives"].astype(str).str.strip() != ""]
        assert not non_empty.empty, "task_def_json 이 있는 row 인데 objective 0건"


def test_score_cells_objectives_empty_when_no_task_def_json():
    """task_def_json 컬럼이 없으면 sample_objectives 는 빈 값."""
    roadmap_no_tdj = pd.DataFrame([
        {"dept": "도장", "lv3": "비전 검사", "task": "AI 비전 검사",
         "task_def": "AI 비전 결함 검사"},
    ])
    news = pd.DataFrame([
        {"title": "AI 비전 검사 도입", "summary": "", "keywords": "AI 비전",
         "source": "x", "link": "http://x"},
    ])
    cells = score_cells(news, roadmap_no_tdj)
    assert "sample_objectives" in cells.columns
    if not cells.empty:
        # 모두 빈 값 (호환성 — 기존 엑셀에 영향 없음)
        assert (cells["sample_objectives"].astype(str).str.strip() == "").all()


def test_score_cells_empty_input_includes_objectives_in_empty_cols():
    """빈 입력 시도 _empty() 가 sample_objectives 컬럼 포함."""
    cells = score_cells(pd.DataFrame(), pd.DataFrame())
    assert "sample_objectives" in cells.columns


# ── board ④ 카드 — objective HTML 노출 ──────────────────────

def test_board_opp_card_includes_objective_when_present():
    from ui import board_v2

    row = pd.Series({
        "dept": "판넬조립부", "lv3": "선별", "cell_score": 21.0,
        "matched_news": 1, "matched_tasks": 1,
        "sample_tasks": "선별",
        "sample_news": "RFID OCR 부재번호 자동 인식",
        "sample_objectives": "BOM 기준 주판 수입 검수",
    })
    html = board_v2._opp_card_html(row)
    assert "🎯 BOM 기준 주판 수입 검수" in html
    assert "db-prop-objective" in html


def test_board_opp_card_omits_objective_when_absent():
    """sample_objectives 빈 값이면 objective HTML 미렌더 (기존 호환)."""
    from ui import board_v2

    row = pd.Series({
        "dept": "도장", "lv3": "비전", "cell_score": 50.0,
        "matched_news": 5, "matched_tasks": 3,
        "sample_tasks": "AI 비전", "sample_news": "",
        "sample_objectives": "",
    })
    html = board_v2._opp_card_html(row)
    assert "🎯" not in html
    assert "db-prop-objective" not in html


def test_board_opp_card_escapes_objective_for_xss():
    from ui import board_v2

    row = pd.Series({
        "dept": "X", "lv3": "Y", "cell_score": 1.0,
        "matched_news": 1, "matched_tasks": 1,
        "sample_tasks": "", "sample_news": "",
        "sample_objectives": "<script>alert(1)</script>",
    })
    html = board_v2._opp_card_html(row)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
