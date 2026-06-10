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
# ui.task_def_manage — 버튼 내비 pending → query 번역 + 렌더 헬퍼
# ═══════════════════════════════════════════════════════

def test_consume_nav_pending_sets_query_and_clears_stale_td_keys():
    """pending 은 앵커와 동일한 td_* **전체 교체** 의미 — 스테일 td_edit 제거."""
    from ui import task_def_manage as tdm
    state: dict = {"_td_nav_pending": {"td_view": "A1", "td_q": "비전"}}
    qp: dict = {"td_edit": "A1", "td_q": "old", "app_area": "📋 작업 정의"}
    with patch("streamlit.query_params", qp), \
         patch("streamlit.session_state", state):
        tdm._consume_td_nav_pending()
    assert qp.get("td_view") == "A1"
    assert qp.get("td_q") == "비전"
    assert "td_edit" not in qp                    # 전체 교체 — 스테일 제거
    assert qp.get("app_area") == "📋 작업 정의"   # td_* 외 키는 보존
    assert "_td_nav_pending" not in state


def test_consume_nav_pending_skips_empty_values():
    from ui import task_def_manage as tdm
    state: dict = {"_td_nav_pending": {"td_q": "", "td_view": None, "td_add": "1"}}
    qp: dict = {}
    with patch("streamlit.query_params", qp), \
         patch("streamlit.session_state", state):
        tdm._consume_td_nav_pending()
    assert qp == {"td_add": "1"}


def test_consume_nav_pending_noop_without_pending():
    from ui import task_def_manage as tdm
    qp: dict = {"td_view": "A1"}
    with patch("streamlit.query_params", qp), \
         patch("streamlit.session_state", {}):
        tdm._consume_td_nav_pending()
    assert qp == {"td_view": "A1"}  # 딥링크 쿼리는 그대로


def test_consume_nav_pending_ignores_non_dict_and_pops():
    from ui import task_def_manage as tdm
    state: dict = {"_td_nav_pending": "td_view=A1"}
    qp: dict = {}
    with patch("streamlit.query_params", qp), \
         patch("streamlit.session_state", state):
        tdm._consume_td_nav_pending()
    assert qp == {}
    assert "_td_nav_pending" not in state


def test_consume_nav_pending_resets_delete_confirm():
    """내비가 발생하면 무장된 삭제 confirm 은 해제 (다음 진입 시 오발사 방지)."""
    from ui import task_def_manage as tdm
    state: dict = {"_td_nav_pending": {"td_q": ""}, "_td_del_confirm": "A1"}
    with patch("streamlit.query_params", {}), \
         patch("streamlit.session_state", state):
        tdm._consume_td_nav_pending()
    assert "_td_del_confirm" not in state


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


def test_empty_html_with_query():
    from ui.task_def_manage import _empty_html
    html = _empty_html("비전")
    assert "검색 결과가 없어요" in html


def test_empty_html_without_query():
    from ui.task_def_manage import _empty_html
    html = _empty_html()
    assert "등록된 작업 정의가 없어요" in html


def test_row_card_html_renders_pid_and_name_without_anchor():
    """카드 클릭은 오버레이 st.button — 시각 html 엔 앵커(full reload)가 없다."""
    from ui.task_def_manage import _row_card_html
    from store import task_defs_db
    task_defs_db.upsert("A1", _sample_json("A1"))
    html = _row_card_html(task_defs_db.get("A1"))
    assert "A1" in html
    assert "이름 A1" in html
    assert "<a" not in html
    assert "td_view=" not in html


# ── 상세 ────────────────────────────────────────────────

def test_detail_html_renders_all_sections():
    from ui.task_def_manage import _detail_html
    from store import task_defs_db
    task_defs_db.upsert("A1", _sample_json("A1"))
    row = task_defs_db.get("A1")
    html = _detail_html(row)
    assert "이름 A1" in html
    assert "설명" in html
    assert "목표1" in html
    assert "R" in html and "C" in html  # risk
    assert "AR" in html and "E" in html  # automation
    # 액션은 _render_detail_actions 의 st.button — 시각 html 엔 앵커 없음
    assert 'href="?' not in html


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
    html = _detail_html(task_defs_db.get("EVIL"))
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


def test_delete_via_nav_pending_round_trip():
    """[🗑️ 삭제 확정] 버튼 경로 — pending(td_action=delete) 이 같은 run 안에서
    번역→소비돼 행 삭제 + 토스트, 쿼리에 td_action/td_pid 잔류 없음."""
    from ui import task_def_manage as tdm
    from store import task_defs_db
    task_defs_db.upsert("A1", _sample_json("A1"))

    state: dict = {
        "_td_nav_pending": {"td_action": "delete", "td_pid": "A1", "td_q": "비전"},
    }
    qp: dict = {"td_view": "A1", "td_q": "비전"}
    with patch("streamlit.query_params", qp), \
         patch("streamlit.session_state", state):
        tdm.consume_td_action_if_any()

    assert task_defs_db.get("A1") is None
    kind, msg = state["_td_toast"]
    assert kind == "ok" and "A1" in msg
    assert "td_action" not in qp and "td_pid" not in qp
    assert "td_view" not in qp           # 전체 교체 — 상세에서 목록으로
    assert qp.get("td_q") == "비전"      # 검색어는 유지


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


def test_row_card_html_escapes_injection():
    """카드 시각 html — 작업명에 마크업이 들어와도 escape."""
    from ui.task_def_manage import _row_card_html
    from store import task_defs_db
    evil = "<img src=x onerror=alert(1)>"
    js = json.dumps({
        "process_id": "EV2", "process_name": evil,
        "org_meta": {"team": "T", "dept": "D"},
    }, ensure_ascii=False)
    task_defs_db.upsert("EV2", js)
    html = _row_card_html(task_defs_db.get("EV2"))
    assert "<img" not in html
    assert "&lt;img" in html


def test_consume_save_keeps_nav_pending_for_render():
    """저장 버튼은 `_do_td_save` + `_td_nav_pending`(detail 행선지)을 함께 설정.
    consume_save 는 nav pending 을 건드리지 않는다 (번역은 nav consumer 몫)."""
    from ui import task_def_manage as tdm
    from roadmap.task_def_form import TaskDefForm
    from store import task_defs_db

    f = TaskDefForm(
        process_id="X1", process_name="x",
        org_meta={"team": "T", "dept": "D"},
    )
    state: dict = {"_do_td_save": {"mode": "create", "form": f},
                   "_td_nav_pending": {"td_view": "X1", "td_q": ""}}
    with patch("streamlit.session_state", state):
        tdm.consume_td_save_if_any()

    assert state.get("_td_nav_pending") == {"td_view": "X1", "td_q": ""}
    assert task_defs_db.get("X1") is not None


# ═══════════════════════════════════════════════════════
# e2e — AppTest 로 app.py 구동 (버튼 내비 소켓 rerun)
# ═══════════════════════════════════════════════════════

def _taskdef_app():
    from streamlit.testing.v1 import AppTest
    from persona import store as ps
    from persona.schema import Persona
    ps.reset(); ps.clear_onboarding_dismiss()
    ps.save(Persona(name="홍길동", dept="도장1팀", team="자동화1팀"))
    at = AppTest.from_file("app.py", default_timeout=30)
    at.session_state["app_area"] = "📋 작업 정의"
    return at


def test_apptest_nav_pending_opens_detail():
    """세션 pending(`_td_nav_pending={"td_view": pid}`) → run 1회로 상세 렌더."""
    from store import task_defs_db
    task_defs_db.upsert("A1", _sample_json("A1"))
    at = _taskdef_app()
    at.session_state["_td_nav_pending"] = {"td_view": "A1"}
    at.run()
    assert not at.exception
    htmls = "\n".join(h.proto.body for h in at.get("html"))
    assert "td-detail" in htmls
    assert "이름 A1" in htmls


def test_apptest_list_renders_overlay_buttons_not_anchors():
    """목록 — 카드 시각 html(td-card) + 오버레이 버튼(td_open_*), 앵커 카드 없음."""
    from store import task_defs_db
    task_defs_db.upsert("A1", _sample_json("A1"))
    at = _taskdef_app()
    at.run()
    assert not at.exception
    htmls = "\n".join(h.proto.body for h in at.get("html"))
    assert "td-card" in htmls
    assert '<a class="td-card"' not in htmls
    keys = {(b.key or "") for b in at.get("button")}
    assert "td_open_0" in keys      # 카드 오버레이
    assert "td_add_btn" in keys     # ＋ 새 작업 추가


def test_apptest_card_button_click_navigates_to_detail():
    """카드 오버레이 버튼 클릭 → 소켓 rerun 으로 상세 진입 (예외 없음)."""
    from store import task_defs_db
    task_defs_db.upsert("A1", _sample_json("A1"))
    at = _taskdef_app()
    at.run()
    btns = [b for b in at.get("button") if (b.key or "") == "td_open_0"]
    assert btns
    btns[0].click()
    at.run()
    assert not at.exception
    htmls = "\n".join(h.proto.body for h in at.get("html"))
    assert "td-detail" in htmls
    assert "이름 A1" in htmls
