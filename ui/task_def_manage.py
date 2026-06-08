"""작업 정의 관리 UI (PR-6) — 검색 / 1건 보기 / 추가·수정·삭제 / history.

`docs/TASK_DEF_PLAN.md` M3 — 1차 완성. `📋 작업 데이터` 그룹의 `manage` sub-탭.

URL 파라미터 (stateless):
  ?dm_grp=tasks&dm_tab=manage
    &td_q=<검색어>
    &td_view=<process_id>           1건 상세
    &td_edit=<process_id>           수정 폼
    &td_add=1                       새 작업 추가 폼
    &td_hist=<process_id>           history 패널
    &td_action=delete&td_pid=<pid>  삭제 액션 (consume → toast)
"""
from __future__ import annotations

import html as _html
import json
from typing import Any
from urllib.parse import quote

import streamlit as st

from roadmap.task_def_form import TaskDefForm
from roadmap.task_def_json import TaskDefJsonError
from store import task_defs_db


# ── inline style 상수 ──────────────────────────────────
# 이 화면의 동적 st.html 은 screen CSS(.td-*) 가 안정적으로 적용되지 않아
# (전역 CSS 만 주입됨) inline style 을 함께 박는다. PR-5 diff 미리보기/토스트
# 와 동일한 코드베이스 관행. 클래스도 유지해 screen CSS 동작 시 호환.
_S_LIST = "margin:8px 24px 24px;display:grid;gap:8px;"
_S_CARD = (
    "display:grid;gap:4px;padding:12px 14px;background:var(--surface-card);"
    "border:1px solid var(--surface-divider);border-radius:10px;text-decoration:none;"
    "color:var(--text-primary);"
)
_S_CARD_NAME = "font-size:15px;font-weight:700;color:var(--text-primary);"
_S_CARD_META = "font-size:12.5px;color:var(--text-secondary);"
_S_CARD_PID = "font-size:12px;color:var(--text-muted);font-family:ui-monospace,monospace;"
_S_DETAIL = (
    "margin:8px 24px 24px;padding:18px 22px;background:var(--surface-card);"
    "border:1px solid var(--surface-divider);border-radius:12px;"
)
_S_DETAIL_NAME = "font-size:22px;font-weight:800;color:var(--text-primary);letter-spacing:-0.01em;"
_S_DETAIL_PID = "font-size:13px;color:var(--text-secondary);font-family:ui-monospace,monospace;"
_S_TAG = (
    "display:inline-block;padding:2px 8px;margin-right:6px;background:var(--surface-soft);"
    "border-radius:999px;font-size:12px;color:var(--text-secondary);font-weight:600;"
)
_S_SECTION_H = "margin:14px 0 6px;font-size:14px;color:var(--text-primary);font-weight:700;"
_S_UL = "margin:0;padding-left:20px;color:var(--text-secondary);line-height:1.6;"
_S_ACTIONS = (
    "display:flex;gap:8px;margin-top:18px;padding-top:14px;"
    "border-top:1px solid var(--surface-divider);"
)
_S_BTN = "padding:7px 14px;border-radius:8px;text-decoration:none;font-size:13px;font-weight:700;"
_S_BTN_PRIMARY = _S_BTN + "background:var(--accent-primary);color:#fff;"
_S_BTN_SECONDARY = _S_BTN + "background:var(--surface-soft);color:var(--text-primary);"
_S_BTN_DANGER = _S_BTN + "background:rgba(185,28,28,0.12);color:var(--semantic-danger);border:1px solid rgba(185,28,28,0.30);"
_S_HISTORY = (
    "margin:18px 24px 24px;padding:14px 18px;background:var(--surface-card);"
    "border:1px solid var(--surface-divider);border-radius:12px;"
)


# ── URL 빌더 ────────────────────────────────────────────

def _manage_href(**params: Any) -> str:
    """`?app_area=📋 작업 정의&...` URL 빌더(작업 정의 화면 액션). 빈 값은 자동 생략.

    구 `?dm_grp=tasks&dm_tab=manage` 탭 핸드오프는 화면 분리(뉴스 수집/작업 정의)로
    불필요 — manage 는 작업 정의 화면에 탭 없이 단독 렌더된다.
    """
    parts = [f"app_area={quote('📋 작업 정의')}"]
    for k, v in params.items():
        if v in (None, "", False):
            continue
        parts.append(f"{k}={quote(str(v))}")
    return "?" + "&".join(parts)


# ── action consumer (URL 액션 → pending → toast) ──────

def consume_td_action_if_any() -> None:
    """`?td_action=delete&td_pid=<pid>` 1회 소비. 삭제 토스트 설정."""
    action = (st.query_params.get("td_action") or "").strip()
    pid = (st.query_params.get("td_pid") or "").strip()
    if not action or not pid:
        return
    # URL 에서 1회 제거
    for k in ("td_action", "td_pid"):
        try:
            del st.query_params[k]
        except Exception:  # noqa: BLE001
            pass

    if action == "delete":
        try:
            ok = task_defs_db.delete(pid, source="ui_edit")
            if ok:
                st.session_state["_td_toast"] = (
                    "ok", f"🗑️ `{pid}` 작업 정의를 삭제했어요."
                )
            else:
                st.session_state["_td_toast"] = (
                    "warn", f"⚠️ `{pid}` 작업이 이미 없어요."
                )
        except Exception as exc:
            st.session_state["_td_toast"] = (
                "error", f"⚠️ 삭제 실패: {type(exc).__name__}: {exc}"
            )


def consume_td_save_if_any() -> None:
    """`_do_td_save` pending (mode + form-data) 소비 → upsert → 토스트."""
    payload = st.session_state.pop("_do_td_save", None)
    if not payload:
        return
    mode = payload.get("mode")  # "create" | "update"
    form: TaskDefForm = payload.get("form")
    if not form:
        return
    try:
        json_str = form.to_json()
        existed = task_defs_db.get(form.process_id) is not None
        task_defs_db.upsert(
            form.process_id, json_str,
            task_def_text=(form.task_def_text or None),
            source="ui_edit",
        )
        verb = "수정" if (mode == "update" or existed) else "추가"
        st.session_state["_td_toast"] = (
            "ok", f"✅ `{form.process_id}` 작업 정의를 {verb}했어요."
        )
    except TaskDefJsonError as exc:
        st.session_state["_td_toast"] = ("error", f"⚠️ 검증 실패: {exc}")
    except ValueError as exc:
        st.session_state["_td_toast"] = ("error", f"⚠️ 저장 실패: {exc}")


def render_td_toast_if_needed() -> None:
    payload = st.session_state.pop("_td_toast", None)
    if not payload:
        return
    kind, message = payload
    bg, border, color = {
        "ok":    ("#ECFDF5", "#A7F3D0", "#064E3B"),
        "warn":  ("#FFFBEB", "#FDE68A", "#92400E"),
        "error": ("#FEF2F2", "#FECACA", "#991B1B"),
    }.get(kind, ("#F1F5F9", "#CBD5E1", "var(--text-primary)"))
    safe = _html.escape(message)
    st.html(
        f'<div style="margin:0 24px 14px;padding:10px 14px;background:{bg};'
        f'border:1px solid {border};border-radius:8px;font-size:13px;'
        f'color:{color};font-weight:600;">{safe}</div>'
    )


# ── 검색 + 매칭 리스트 ───────────────────────────────

def _search_rows(query: str, limit: int = 50) -> list[dict]:
    """질의어가 있으면 search, 없으면 list_all 최신."""
    q = (query or "").strip()
    if q:
        return task_defs_db.search(q, limit=limit)
    return task_defs_db.list_all(limit=limit)


def _row_card_html(row: dict, query: str = "") -> str:
    """검색 결과 1건 카드 — 작업명 · 부서/공정 · pid."""
    pid = row.get("process_id") or ""
    obj = row.get("json_obj") or {}
    if not isinstance(obj, dict):
        obj = {}
    name = obj.get("process_name") or pid
    dept = row.get("dept") or ""
    process = row.get("process") or ""
    task = row.get("task") or ""
    chain = " · ".join(p for p in (dept, process, task) if p)

    view_href = _manage_href(td_view=pid, td_q=query)
    return (
        f'<a class="td-card" style="{_S_CARD}" href="' + _html.escape(view_href)
        + '" target="_self">'
        f'<div class="td-card-name" style="{_S_CARD_NAME}">{_html.escape(str(name))}</div>'
        f'<div class="td-card-meta" style="{_S_CARD_META}">{_html.escape(chain)}</div>'
        f'<div class="td-card-pid" style="{_S_CARD_PID}"><code>{_html.escape(str(pid))}</code></div>'
        '</a>'
    )


def _list_html(rows: list[dict], query: str = "") -> str:
    if not rows:
        msg = "검색 결과가 없어요." if query else "등록된 작업 정의가 없어요."
        return (
            '<div class="td-empty" style="padding:32px;text-align:center;'
            'color:var(--text-secondary);font-size:14px;">'
            f'{_html.escape(msg)}</div>'
        )
    parts = [f'<div class="td-list" style="{_S_LIST}">']
    for r in rows:
        parts.append(_row_card_html(r, query=query))
    parts.append("</div>")
    return "".join(parts)


# ── 1건 상세 (read-only) ───────────────────────────────

def _detail_html(row: dict, query: str = "") -> str:
    pid = row.get("process_id") or ""
    obj = row.get("json_obj") or {}
    if not isinstance(obj, dict):
        obj = {}

    name = obj.get("process_name") or pid
    desc = obj.get("process_description") or ""
    domain = obj.get("process_domain") or ""
    category = obj.get("process_category") or ""

    meta = obj.get("org_meta") or {}
    if not isinstance(meta, dict):
        meta = {}

    parts = [f'<div class="td-detail" style="{_S_DETAIL}">']
    # 헤더
    parts.append(
        '<div class="td-detail-head" style="display:flex;align-items:baseline;'
        'gap:12px;margin-bottom:12px;">'
        f'<div class="td-detail-name" style="{_S_DETAIL_NAME}">{_html.escape(str(name))}</div>'
        f'<div class="td-detail-pid" style="{_S_DETAIL_PID}"><code>{_html.escape(str(pid))}</code></div>'
        '</div>'
    )
    # 조직 메타
    if meta:
        rows = [
            ("팀", meta.get("team")), ("부서", meta.get("dept")),
            ("분과", meta.get("division")), ("공정", meta.get("process")),
            ("작업", meta.get("task")), ("세부작업", meta.get("sub_task")),
        ]
        items = [
            '<div class="td-meta-row" style="font-size:13px;">'
            f'<span class="td-meta-k" style="color:var(--text-secondary);font-weight:600;">{k}: </span>'
            f'<span class="td-meta-v" style="color:var(--text-primary);">{_html.escape(str(v))}</span></div>'
            for k, v in rows if v
        ]
        if items:
            parts.append(
                '<div class="td-meta" style="display:grid;'
                'grid-template-columns:repeat(3,1fr);gap:6px 18px;margin:8px 0 12px;">'
                + "".join(items) + '</div>'
            )
    # 도메인/카테고리/설명
    if domain or category:
        parts.append(
            '<div class="td-tags" style="margin:4px 0 10px;">'
            + (f'<span class="td-tag" style="{_S_TAG}">{_html.escape(str(domain))}</span>' if domain else "")
            + (f'<span class="td-tag" style="{_S_TAG}">{_html.escape(str(category))}</span>' if category else "")
            + '</div>'
        )
    if desc:
        parts.append(
            f'<div class="td-desc" style="margin:6px 0 12px;color:var(--text-secondary);'
            f'line-height:1.6;">{_html.escape(str(desc))}</div>'
        )

    # objectives
    objs = obj.get("objectives") or []
    if isinstance(objs, list) and objs:
        items = "".join(f"<li>{_html.escape(str(o))}</li>" for o in objs if o)
        parts.append(
            f'<div class="td-section"><h4 style="{_S_SECTION_H}">🎯 목표</h4>'
            f'<ul style="{_S_UL}">{items}</ul></div>'
        )
    # risks
    risks = obj.get("overall_quality_risks") or []
    if isinstance(risks, list) and risks:
        items = []
        for r in risks:
            if isinstance(r, dict):
                rk = r.get("risk") or ""
                rc = r.get("consequence") or ""
                items.append(
                    f"<li><b>{_html.escape(str(rk))}</b>"
                    + (f" — {_html.escape(str(rc))}" if rc else "")
                    + "</li>"
                )
        if items:
            parts.append(
                f'<div class="td-section"><h4 style="{_S_SECTION_H}">⚠️ 품질 리스크</h4>'
                f'<ul style="{_S_UL}">{"".join(items)}</ul></div>'
            )
    # automation
    autos = obj.get("automation_potential_areas") or []
    if isinstance(autos, list) and autos:
        items = []
        for a in autos:
            if isinstance(a, dict):
                ar = a.get("area") or ""
                tc = a.get("technology") or ""
                eff = a.get("expected_effect") or ""
                line = f"<b>{_html.escape(str(ar))}</b>"
                if tc:
                    line += f" — {_html.escape(str(tc))}"
                if eff:
                    line += f" → {_html.escape(str(eff))}"
                items.append(f"<li>{line}</li>")
        if items:
            parts.append(
                f'<div class="td-section"><h4 style="{_S_SECTION_H}">🤖 자동화 가능 영역</h4>'
                f'<ul style="{_S_UL}">{"".join(items)}</ul></div>'
            )
    # 액션 링크
    edit_href = _manage_href(td_edit=pid, td_q=query)
    hist_href = _manage_href(td_view=pid, td_hist=pid, td_q=query)
    delete_href = _manage_href(td_action="delete", td_pid=pid, td_q=query)
    back_href = _manage_href(td_q=query)
    parts.append(
        f'<div class="td-actions" style="{_S_ACTIONS}">'
        f'<a class="td-btn td-btn-secondary" style="{_S_BTN_SECONDARY}" '
        f'href="{_html.escape(back_href)}" target="_self">← 목록</a>'
        f'<a class="td-btn td-btn-primary" style="{_S_BTN_PRIMARY}" '
        f'href="{_html.escape(edit_href)}" target="_self">✏️ 수정</a>'
        f'<a class="td-btn td-btn-secondary" style="{_S_BTN_SECONDARY}" '
        f'href="{_html.escape(hist_href)}" target="_self">🕒 history</a>'
        f'<a class="td-btn td-btn-danger" style="{_S_BTN_DANGER}" '
        f'href="{_html.escape(delete_href)}" target="_self" '
        f'onclick="return confirm(\'정말 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.\');">'
        f'🗑️ 삭제</a>'
        '</div>'
    )

    # history (선택)
    parts.append("</div>")
    return "".join(parts)


def _history_html(pid: str, limit: int = 20) -> str:
    rows = task_defs_db.history(pid, limit=limit)
    if not rows:
        return ""
    parts = [
        f'<div class="td-history" style="{_S_HISTORY}">'
        f'<h4 style="{_S_SECTION_H}">🕒 변경 이력 ({len(rows)})</h4>'
        '<ul style="margin:0;padding-left:0;list-style:none;">'
    ]
    for h in rows:
        when = (h.get("changed_at") or "")[:19].replace("T", " ")
        action = h.get("action") or ""
        src = h.get("source") or ""
        who = h.get("changed_by") or ""
        parts.append(
            '<li style="display:flex;gap:10px;padding:4px 0;font-size:13px;'
            'color:var(--text-secondary);border-bottom:1px dashed var(--surface-divider);">'
            f'<span class="td-h-action" style="font-weight:700;min-width:60px;'
            f'color:#2563EB;">{_html.escape(action)}</span>'
            f'<span class="td-h-when" style="color:var(--text-secondary);font-family:ui-monospace,monospace;'
            f'min-width:140px;">{_html.escape(when)}</span>'
            + (f'<span class="td-h-src" style="color:var(--text-secondary);">{_html.escape(src)}</span>' if src else "")
            + (f'<span class="td-h-who" style="color:var(--text-secondary);">{_html.escape(who)}</span>' if who else "")
            + '</li>'
        )
    parts.append("</ul></div>")
    return "".join(parts)


# ── 폼 (추가/수정 공용 Streamlit 위젯) ─────────────────

def _render_form(form: TaskDefForm, *, mode: str, query: str = "") -> None:
    """Streamlit 위젯으로 폼 렌더. [💾 저장] / [← 취소] 버튼."""
    is_create = (mode == "create")
    title = "+ 새 작업 추가" if is_create else f"✏️ 수정 — {form.process_id}"
    st.html(
        f'<div style="margin:18px 24px 8px;font-size:18px;font-weight:800;'
        f'color:var(--text-primary);letter-spacing:-0.01em;">{_html.escape(title)}</div>'
    )

    # process_id (수정 시엔 readonly)
    pid_kw = {"value": form.process_id, "key": f"_td_pid_{mode}"}
    if not is_create:
        pid_kw["disabled"] = True
    form.process_id = st.text_input("공정 ID (PK) — 예: PNL-SEL-001", **pid_kw)

    # 조직 메타
    st.caption("📂 조직 메타 (team / dept 는 필수)")
    c1, c2, c3 = st.columns(3)
    with c1:
        form.org_meta["team"] = st.text_input(
            "팀", value=form.org_meta.get("team", ""), key=f"_td_team_{mode}",
        ).strip()
    with c2:
        form.org_meta["dept"] = st.text_input(
            "부서", value=form.org_meta.get("dept", ""), key=f"_td_dept_{mode}",
        ).strip()
    with c3:
        form.org_meta["division"] = st.text_input(
            "분과", value=form.org_meta.get("division", ""), key=f"_td_div_{mode}",
        ).strip()
    c4, c5, c6 = st.columns(3)
    with c4:
        form.org_meta["process"] = st.text_input(
            "공정", value=form.org_meta.get("process", ""), key=f"_td_proc_{mode}",
        ).strip()
    with c5:
        form.org_meta["task"] = st.text_input(
            "작업", value=form.org_meta.get("task", ""), key=f"_td_task_{mode}",
        ).strip()
    with c6:
        form.org_meta["sub_task"] = st.text_input(
            "세부작업", value=form.org_meta.get("sub_task", ""), key=f"_td_sub_{mode}",
        ).strip()

    # 본문
    st.caption("📝 본문")
    form.process_name = st.text_input(
        "공정명", value=form.process_name, key=f"_td_pname_{mode}",
    )
    form.process_description = st.text_area(
        "공정 설명", value=form.process_description,
        key=f"_td_desc_{mode}", height=100,
    )

    c7, c8 = st.columns(2)
    with c7:
        form.process_domain = st.text_input(
            "도메인", value=form.process_domain, key=f"_td_domain_{mode}",
        )
    with c8:
        form.process_category = st.text_input(
            "카테고리", value=form.process_category, key=f"_td_cat_{mode}",
        )

    # objectives — 텍스트 1줄당 1 objective
    st.caption("🎯 목표 (1줄에 1건)")
    objs_text = st.text_area(
        "목표", value="\n".join(form.objectives),
        key=f"_td_objs_{mode}", height=120,
        label_visibility="collapsed",
    )
    form.objectives = [o.strip() for o in objs_text.split("\n") if o.strip()]

    # quality risks — risk; consequence
    st.caption("⚠️ 품질 리스크 (`리스크; 결과` 한 줄에 한 쌍)")
    risks_text = st.text_area(
        "리스크",
        value="\n".join(
            f"{r.get('risk','').strip()}; {r.get('consequence','').strip()}".strip("; ").strip()
            for r in form.overall_quality_risks
        ),
        key=f"_td_risks_{mode}", height=120,
        label_visibility="collapsed",
    )
    form.overall_quality_risks = []
    for line in risks_text.split("\n"):
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split(";", 1)]
        risk = parts[0]
        cons = parts[1] if len(parts) > 1 else ""
        form.overall_quality_risks.append({"risk": risk, "consequence": cons})

    # automation — area; technology; expected_effect
    st.caption("🤖 자동화 영역 (`영역; 기술; 기대 효과` 한 줄에 한 항목)")
    autos_text = st.text_area(
        "자동화",
        value="\n".join(
            "; ".join(
                a.get(k, "").strip() for k in ("area", "technology", "expected_effect")
            ).rstrip("; ")
            for a in form.automation_potential_areas
        ),
        key=f"_td_autos_{mode}", height=120,
        label_visibility="collapsed",
    )
    form.automation_potential_areas = []
    for line in autos_text.split("\n"):
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split(";", 2)]
        d = {"area": parts[0] if len(parts) > 0 else "",
             "technology": parts[1] if len(parts) > 1 else "",
             "expected_effect": parts[2] if len(parts) > 2 else ""}
        form.automation_potential_areas.append(d)

    # 줄글 정의서
    st.caption("📄 공정 정의서 (줄글, 선택)")
    form.task_def_text = st.text_area(
        "줄글", value=form.task_def_text,
        key=f"_td_txt_{mode}", height=140,
        label_visibility="collapsed",
    )

    # 액션
    col_a, col_b = st.columns([1, 2])
    with col_a:
        cancel_target = (
            _manage_href(td_view=form.process_id, td_q=query)
            if not is_create else _manage_href(td_q=query)
        )
        # 취소는 단순 링크 — 일관성 위해 [← 취소] 버튼도 제공
        if st.button("← 취소", key=f"_td_cancel_{mode}"):
            st.session_state["_td_redirect"] = cancel_target
            st.rerun()
    with col_b:
        if st.button("💾 저장", type="primary", key=f"_td_save_{mode}"):
            # 검증을 먼저 시도해 UX 즉시성 확보
            try:
                form.to_json()
            except TaskDefJsonError as exc:
                st.error(f"⚠️ 검증 실패: {exc}")
                return
            st.session_state["_do_td_save"] = {"mode": mode, "form": form}
            st.session_state["_td_redirect"] = _manage_href(
                td_view=form.process_id, td_q=query,
            )
            st.rerun()


# ── 진입점: render() — 외부 호출용 ─────────────────────

def render(query_params_getter) -> None:
    """`manage` sub-탭 본문. query_params_getter 는 `st.query_params`.

    URL 파라미터에 따라 list / detail / form / history 모드 전환.
    """
    # redirect (저장/취소 후) 1회 소비
    redirect = st.session_state.pop("_td_redirect", None)
    if redirect:
        # streamlit 의 query_params 재할당으로 URL 갱신
        for kv in redirect.lstrip("?").split("&"):
            if "=" not in kv:
                continue
            k, v = kv.split("=", 1)
            from urllib.parse import unquote
            try:
                st.query_params[unquote(k)] = unquote(v)
            except Exception:  # noqa: BLE001
                pass

    render_td_toast_if_needed()

    q = (query_params_getter.get("td_q") or "").strip()
    view = (query_params_getter.get("td_view") or "").strip()
    edit = (query_params_getter.get("td_edit") or "").strip()
    add = (query_params_getter.get("td_add") or "").strip()
    hist = (query_params_getter.get("td_hist") or "").strip()

    # ── 추가 폼 ─────────────────────────────────────
    if add:
        form = TaskDefForm()
        _render_form(form, mode="create", query=q)
        return

    # ── 수정 폼 ─────────────────────────────────────
    if edit:
        row = task_defs_db.get(edit)
        if row is None:
            st.warning(f"⚠️ `{edit}` 작업을 찾을 수 없어요.")
            return
        form = TaskDefForm.from_db_row(row)
        _render_form(form, mode="update", query=q)
        return

    # ── 상세 ────────────────────────────────────────
    if view:
        row = task_defs_db.get(view)
        if row is None:
            st.warning(f"⚠️ `{view}` 작업을 찾을 수 없어요.")
            back_href = _manage_href(td_q=q)
            st.html(
                f'<a class="td-btn td-btn-secondary" style="{_S_BTN_SECONDARY}" '
                f'href="{_html.escape(back_href)}" target="_self">← 목록</a>'
            )
            return
        st.html(_detail_html(row, query=q))
        if hist:
            st.html(_history_html(hist))
        return

    # ── 목록 (검색) ────────────────────────────────
    # 검색창 + 새 작업 추가 버튼 — 둘 다 stateless URL
    add_href = _manage_href(td_add=1, td_q=q)
    head = (
        '<div class="td-head" style="display:flex;gap:12px;align-items:center;'
        'margin:18px 24px 8px;">'
        '<div class="td-head-title" style="flex:1;font-size:18px;font-weight:800;'
        'color:var(--text-primary);">📋 작업 정의 관리</div>'
        f'<a class="td-btn td-btn-primary" style="{_S_BTN_PRIMARY}" '
        f'href="{_html.escape(add_href)}" target="_self">+ 새 작업 추가</a>'
        '</div>'
    )
    st.html(head)

    # Streamlit 검색창은 폼-없이 URL 갱신 패턴
    typed = st.text_input(
        "검색 (작업명 / 공정 ID / JSON 본문)",
        value=q, key="_td_search_input",
        placeholder="예: 비전, 용접, PNL-SEL",
    )
    if typed != q:
        # 입력 변경 → URL 갱신 + rerun (stateless URL 유지)
        if typed.strip():
            st.query_params["td_q"] = typed.strip()
        else:
            try:
                del st.query_params["td_q"]
            except Exception:  # noqa: BLE001
                pass
        st.rerun()

    rows = _search_rows(q)
    total = task_defs_db.count()
    sub = f"검색 결과 {len(rows)}건" if q else f"전체 {total}건"
    st.caption(sub)
    st.html(_list_html(rows, query=q))
