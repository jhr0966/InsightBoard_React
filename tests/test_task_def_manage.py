"""작업 정의 관리 UI + 폼 + manage 탭 라우팅 (PR-6)."""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest


# ── 헬퍼 ────────────────────────────────────────────────

def _sample_json(pid="A1", **extra) -> str:
    d = {
        "process_id": pid,
        "process_name": f"이름 {pid}",
        "process_description": "설명",
        "objectives": ["목표1"],
        "overall_quality_risks": [{"risk": "R", "consequence": "C"}],
        "automation_potential_areas": [{"area": "AR", "technology": "T", "expected_effect": "E"}],
        "org_meta": {"team": "T", "dept": "D", "process": "P", "task": "X"},
    }
    d.update(extra)
    return json.dumps(d, ensure_ascii=False)


class _Ctx:
    def __enter__(self): return self
    def __exit__(self, *a): return False


# ═══════════════════════════════════════════════════════
# roadmap.task_def_form — TaskDefForm 데이터클래스
# ═══════════════════════════════════════════════════════

def test_form_empty_defaults():
    from roadmap.task_def_form import TaskDefForm
    f = TaskDefForm()
    assert f.process_id == ""
    assert f.objectives == []
    assert f.overall_quality_risks == []
    assert f.automation_potential_areas == []
    assert f.org_meta == {}


def test_form_from_db_row_extracts_all_fields():
    from roadmap.task_def_form import TaskDefForm
    from store import task_defs_db

    task_defs_db.upsert("A1", _sample_json("A1"), task_def_text="줄글 정의서")
    row = task_defs_db.get("A1")
    f = TaskDefForm.from_db_row(row)
    assert f.process_id == "A1"
    assert f.process_name == "이름 A1"
    assert f.process_description == "설명"
    assert f.objectives == ["목표1"]
    assert f.overall_quality_risks == [{"risk": "R", "consequence": "C"}]
    assert f.automation_potential_areas == [
        {"area": "AR", "technology": "T", "expected_effect": "E"}
    ]
    assert f.org_meta["team"] == "T"
    assert f.org_meta["dept"] == "D"
    assert f.task_def_text == "줄글 정의서"


def test_form_from_db_row_handles_none():
    from roadmap.task_def_form import TaskDefForm
    f = TaskDefForm.from_db_row(None)
    assert f.process_id == ""


def test_form_from_db_row_normalizes_str_risks_to_dict():
    """과거 데이터: risks 가 str 리스트인 경우 dict 로 정규화."""
    from roadmap.task_def_form import TaskDefForm
    from store import task_defs_db
    js = json.dumps({
        "process_id": "L1",
        "org_meta": {"team": "T", "dept": "D"},
        "overall_quality_risks": ["str리스크"],  # 과거 포맷
    }, ensure_ascii=False)
    task_defs_db.upsert("L1", js)
    f = TaskDefForm.from_db_row(task_defs_db.get("L1"))
    assert f.overall_quality_risks == [{"risk": "str리스크", "consequence": ""}]


def test_form_to_json_round_trip():
    from roadmap.task_def_form import TaskDefForm
    from store import task_defs_db
    task_defs_db.upsert("A1", _sample_json("A1"))
    f = TaskDefForm.from_db_row(task_defs_db.get("A1"))
    js = f.to_json()
    obj = json.loads(js)
    assert obj["process_id"] == "A1"
    assert obj["org_meta"]["team"] == "T"
    assert obj["objectives"] == ["목표1"]


def test_form_to_json_rejects_missing_process_id():
    from roadmap.task_def_form import TaskDefForm
    from roadmap.task_def_json import TaskDefJsonError
    f = TaskDefForm(org_meta={"team": "T", "dept": "D"})
    with pytest.raises(TaskDefJsonError, match="process_id"):
        f.to_json()


def test_form_to_json_rejects_missing_team():
    from roadmap.task_def_form import TaskDefForm
    from roadmap.task_def_json import TaskDefJsonError
    f = TaskDefForm(process_id="X1", org_meta={"dept": "D"})
    with pytest.raises(TaskDefJsonError, match="team"):
        f.to_json()


def test_form_to_json_strips_empty_objectives_and_risks():
    """빈 값/공백만 있는 항목은 제거."""
    from roadmap.task_def_form import TaskDefForm
    f = TaskDefForm(
        process_id="X1",
        org_meta={"team": "T", "dept": "D"},
        objectives=["", "  ", "유효목표"],
        overall_quality_risks=[
            {"risk": "", "consequence": ""},
            {"risk": "유효리스크", "consequence": ""},
        ],
    )
    obj = json.loads(f.to_json())
    assert obj["objectives"] == ["유효목표"]
    assert obj["overall_quality_risks"] == [{"risk": "유효리스크"}]


def test_form_add_remove_objective():
    from roadmap.task_def_form import TaskDefForm
    f = TaskDefForm()
    f.add_objective("a")
    f.add_objective("b")
    assert f.objectives == ["a", "b"]
    f.remove_objective(0)
    assert f.objectives == ["b"]
    f.remove_objective(99)  # out of range — no-op
    assert f.objectives == ["b"]


def test_form_add_remove_risk_and_automation():
    from roadmap.task_def_form import TaskDefForm
    f = TaskDefForm()
    f.add_risk()
    f.add_automation()
    assert len(f.overall_quality_risks) == 1
    assert len(f.automation_potential_areas) == 1
    assert f.overall_quality_risks[0] == {"risk": "", "consequence": ""}
    assert "expected_effect" in f.automation_potential_areas[0]
    f.remove_risk(0)
    f.remove_automation(0)
    assert f.overall_quality_risks == []
    assert f.automation_potential_areas == []


# ═══════════════════════════════════════════════════════
# ui.task_def_manage — URL 빌더 + 렌더 헬퍼
# ═══════════════════════════════════════════════════════

def test_manage_href_points_to_taskdef_area():
    from urllib.parse import quote
    from ui.task_def_manage import _manage_href
    href = _manage_href()
    assert "app_area=" + quote("📋 작업 정의") in href
    assert "dm_grp" not in href and "dm_tab" not in href


def test_manage_href_appends_params():
    from ui.task_def_manage import _manage_href
    href = _manage_href(td_view="A1", td_q="비전")
    assert "td_view=A1" in href
    assert "td_q=" in href  # encoded


def test_manage_href_skips_empty_params():
    from ui.task_def_manage import _manage_href
    href = _manage_href(td_view="", td_q=None, td_add=False)
    assert "td_view=" not in href
    assert "td_q=" not in href
    assert "td_add=" not in href


# ── 검색 + 리스트 ───────────────────────────────────────

def test_search_rows_returns_list_all_when_empty_query():
    from ui.task_def_manage import _search_rows
    from store import task_defs_db
    task_defs_db.upsert("A1", _sample_json("A1"))
    task_defs_db.upsert("A2", _sample_json("A2"))
    rows = _search_rows("")
    assert {r["process_id"] for r in rows} == {"A1", "A2"}


def test_search_rows_filters_by_query():
    from ui.task_def_manage import _search_rows
    from store import task_defs_db
    task_defs_db.upsert("PNL-SEL-001", _sample_json("PNL-SEL-001"))
    task_defs_db.upsert("WLD-ARC-001", _sample_json("WLD-ARC-001"))
    rows = _search_rows("PNL")
    assert [r["process_id"] for r in rows] == ["PNL-SEL-001"]


def test_list_html_empty_state_with_query():
    from ui.task_def_manage import _list_html
    html = _list_html([], query="비전")
    assert "검색 결과가 없어요" in html


def test_list_html_empty_state_without_query():
    from ui.task_def_manage import _list_html
    html = _list_html([])
    assert "등록된 작업 정의가 없어요" in html


def test_list_html_renders_cards_with_pid_and_name():
    from ui.task_def_manage import _list_html
    from store import task_defs_db
    task_defs_db.upsert("A1", _sample_json("A1"))
    rows = task_defs_db.list_all()
    html = _list_html(rows, query="")
    assert "A1" in html
    assert "이름 A1" in html
    # 상세 링크 포함
    assert "td_view=A1" in html


# ── 상세 ────────────────────────────────────────────────

def test_detail_html_renders_all_sections():
    from ui.task_def_manage import _detail_html
    from store import task_defs_db
    task_defs_db.upsert("A1", _sample_json("A1"))
    row = task_defs_db.get("A1")
    html = _detail_html(row, query="")
    assert "이름 A1" in html
    assert "설명" in html
    assert "목표1" in html
    assert "R" in html and "C" in html  # risk
    assert "AR" in html and "E" in html  # automation
    # 액션 버튼 4개
    assert "수정" in html
    assert "history" in html
    assert "삭제" in html
    assert "← 목록" in html


def test_detail_html_escapes_html_injection():
    from ui.task_def_manage import _detail_html
    from store import task_defs_db
    evil = "<script>x</script>"
    js = json.dumps({
        "process_id": "EVIL",
        "process_name": evil,
        "process_description": evil,
        "org_meta": {"team": "T", "dept": "D"},
    }, ensure_ascii=False)
    task_defs_db.upsert("EVIL", js)
    html = _detail_html(task_defs_db.get("EVIL"), query="")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_history_html_returns_empty_when_no_history():
    from ui.task_def_manage import _history_html
    assert _history_html("NOPE") == ""


def test_history_html_renders_actions():
    from ui.task_def_manage import _history_html
    from store import task_defs_db
    task_defs_db.upsert("A1", _sample_json("A1"))
    task_defs_db.upsert("A1", _sample_json("A1", objectives=["new"]))
    html = _history_html("A1")
    assert "create" in html
    assert "update" in html


# ═══════════════════════════════════════════════════════
# Action consumers — delete / save
# ═══════════════════════════════════════════════════════

def test_consume_delete_removes_row_and_sets_toast():
    from ui import task_def_manage as tdm
    from store import task_defs_db
    task_defs_db.upsert("A1", _sample_json("A1"))

    state: dict = {}

    class _QP(dict):
        def __delitem__(self, k):
            super().__delitem__(k)

    qp = _QP({"td_action": "delete", "td_pid": "A1"})
    with patch("streamlit.query_params", qp), \
         patch("streamlit.session_state", state):
        tdm.consume_td_action_if_any()

    assert task_defs_db.get("A1") is None
    assert state.get("_td_toast") is not None
    kind, msg = state["_td_toast"]
    assert kind == "ok"
    assert "A1" in msg
    # URL 에서 제거
    assert "td_action" not in qp
    assert "td_pid" not in qp


def test_consume_delete_warns_when_pid_missing():
    from ui import task_def_manage as tdm
    state: dict = {}

    class _QP(dict):
        def __delitem__(self, k):
            super().__delitem__(k)

    qp = _QP({"td_action": "delete", "td_pid": "GONE"})
    with patch("streamlit.query_params", qp), \
         patch("streamlit.session_state", state):
        tdm.consume_td_action_if_any()

    kind, msg = state["_td_toast"]
    assert kind == "warn"


def test_consume_delete_noop_without_action():
    from ui import task_def_manage as tdm
    state: dict = {}
    with patch("streamlit.query_params", {}), \
         patch("streamlit.session_state", state):
        tdm.consume_td_action_if_any()
    assert "_td_toast" not in state


def test_consume_save_creates_row_and_sets_toast():
    from ui import task_def_manage as tdm
    from roadmap.task_def_form import TaskDefForm
    from store import task_defs_db

    f = TaskDefForm(
        process_id="A1", process_name="이름",
        org_meta={"team": "T", "dept": "D"},
        objectives=["목표"],
    )
    state: dict = {"_do_td_save": {"mode": "create", "form": f}}
    with patch("streamlit.session_state", state):
        tdm.consume_td_save_if_any()

    assert task_defs_db.get("A1") is not None
    kind, msg = state["_td_toast"]
    assert kind == "ok"
    assert "추가" in msg or "수정" in msg
    assert "A1" in msg
    assert "_do_td_save" not in state


def test_consume_save_records_update_verb_when_existing():
    from ui import task_def_manage as tdm
    from roadmap.task_def_form import TaskDefForm
    from store import task_defs_db

    task_defs_db.upsert("A1", _sample_json("A1"))
    f = TaskDefForm(
        process_id="A1", process_name="새이름",
        org_meta={"team": "T", "dept": "D"},
    )
    state: dict = {"_do_td_save": {"mode": "update", "form": f}}
    with patch("streamlit.session_state", state):
        tdm.consume_td_save_if_any()

    kind, msg = state["_td_toast"]
    assert kind == "ok"
    assert "수정" in msg


def test_consume_save_reports_validation_error():
    from ui import task_def_manage as tdm
    from roadmap.task_def_form import TaskDefForm
    state: dict = {"_do_td_save": {"mode": "create", "form": TaskDefForm()}}
    with patch("streamlit.session_state", state):
        tdm.consume_td_save_if_any()
    kind, msg = state["_td_toast"]
    assert kind == "error"
    assert "검증" in msg or "process_id" in msg


# ═══════════════════════════════════════════════════════
# manage 탭 통합 — data_management_v2 dispatcher
# ═══════════════════════════════════════════════════════

def test_dm_tab_body_html_returns_placeholder_for_manage():
    """manage 본문은 Streamlit 위젯이 render() 단계에서 채움."""
    from ui import data_management_v2 as dm
    html = dm._dm_tab_body_html("manage", persona=None, dm_stats={})
    assert "td-manage-placeholder" in html


# ═══════════════════════════════════════════════════════
# 통합 round-trip — 폼 → DB → 다시 폼 (PR-6 핵심)
# ═══════════════════════════════════════════════════════

def test_full_round_trip_create_load_modify_save():
    """create → load → 일부 수정 → save → load 가 변경 사항 보존."""
    from roadmap.task_def_form import TaskDefForm
    from store import task_defs_db

    # 1) 새 작업 추가
    f1 = TaskDefForm(
        process_id="RT-001", process_name="라운드트립",
        process_description="설명1",
        org_meta={"team": "T", "dept": "D", "process": "P", "task": "X"},
        objectives=["O1", "O2"],
        overall_quality_risks=[{"risk": "R1", "consequence": "C1"}],
        automation_potential_areas=[
            {"area": "A1", "technology": "T1", "expected_effect": "E1"},
        ],
        task_def_text="줄글",
    )
    task_defs_db.upsert("RT-001", f1.to_json(), task_def_text=f1.task_def_text)

    # 2) 다시 폼으로 로드
    f2 = TaskDefForm.from_db_row(task_defs_db.get("RT-001"))
    assert f2.process_id == "RT-001"
    assert f2.process_name == "라운드트립"
    assert f2.objectives == ["O1", "O2"]
    assert f2.overall_quality_risks == [{"risk": "R1", "consequence": "C1"}]
    assert f2.automation_potential_areas == [
        {"area": "A1", "technology": "T1", "expected_effect": "E1"}
    ]
    assert f2.task_def_text == "줄글"

    # 3) 일부 수정
    f2.process_name = "라운드트립v2"
    f2.add_objective("O3")
    js2 = f2.to_json()
    task_defs_db.upsert("RT-001", js2, task_def_text=f2.task_def_text)

    # 4) 재로드 확인
    f3 = TaskDefForm.from_db_row(task_defs_db.get("RT-001"))
    assert f3.process_name == "라운드트립v2"
    assert f3.objectives == ["O1", "O2", "O3"]
    # 다른 필드는 그대로
    assert f3.overall_quality_risks == [{"risk": "R1", "consequence": "C1"}]

    # 5) history 가 2회 누적 (create + update)
    hist = task_defs_db.history("RT-001")
    assert [h["action"] for h in hist] == ["update", "create"]


def test_form_to_json_preserves_korean_unicode():
    """한국어 + 이모지 등 비ASCII 가 깨지지 않음 (ensure_ascii=False)."""
    from roadmap.task_def_form import TaskDefForm
    f = TaskDefForm(
        process_id="K1",
        process_name="판넬 선별 (Panel Loading) 📦",
        org_meta={"team": "가공팀", "dept": "판넬조립부"},
        objectives=["✅ BOM 수입 검수"],
    )
    js = f.to_json()
    # 직접 텍스트 비교 — 유니코드 보존
    assert "판넬 선별" in js
    assert "가공팀" in js
    assert "📦" in js
    obj = json.loads(js)
    assert obj["process_name"] == "판넬 선별 (Panel Loading) 📦"


def test_form_to_json_drops_empty_optional_top_level_fields():
    """선택 필드가 빈 값이면 JSON 에 포함하지 않음 (cleanliness)."""
    from roadmap.task_def_form import TaskDefForm
    f = TaskDefForm(
        process_id="C1",
        org_meta={"team": "T", "dept": "D"},
        # process_description / process_domain / objectives / risks 모두 비움
    )
    obj = json.loads(f.to_json())
    assert obj["process_id"] == "C1"
    assert "process_description" not in obj
    assert "process_domain" not in obj
    assert "objectives" not in obj
    assert "overall_quality_risks" not in obj


def test_manage_href_pid_with_special_chars_is_url_encoded():
    """공정 ID 에 슬래시/공백이 들어가도 URL 안전."""
    from ui.task_def_manage import _manage_href
    href = _manage_href(td_view="A/1 B")
    assert "td_view=A%2F1%20B" in href or "td_view=A/1 B" not in href


def test_row_card_html_links_to_td_view():
    from ui.task_def_manage import _row_card_html
    from store import task_defs_db
    task_defs_db.upsert("A1", _sample_json("A1"))
    row = task_defs_db.get("A1")
    html = _row_card_html(row, query="비전")
    assert "td_view=A1" in html
    # 검색어가 살아있어야 (뒤로가기 → 검색 결과 유지)
    assert "td_q=" in html


def test_consume_save_redirects_via_session_state():
    """저장 후 redirect 키를 통해 detail 로 가도록 manage.render 에서 처리될 준비."""
    # consume_td_save 자체는 redirect 를 설정하지 않지만, _render_form 의
    # 저장 버튼 핸들러가 설정. 여기서는 _td_redirect 키가 form 검증과 별개임을 확인.
    from ui import task_def_manage as tdm
    from roadmap.task_def_form import TaskDefForm
    from store import task_defs_db

    f = TaskDefForm(
        process_id="X1", process_name="x",
        org_meta={"team": "T", "dept": "D"},
    )
    state: dict = {"_do_td_save": {"mode": "create", "form": f},
                   "_td_redirect": "?stub"}
    with patch("streamlit.session_state", state):
        tdm.consume_td_save_if_any()

    # consume_save 는 _td_redirect 를 건드리지 않음 (render 에서 처리)
    assert state.get("_td_redirect") == "?stub"
    assert task_defs_db.get("X1") is not None
