"""B.5 데이터관리 4 탭 wire — jobs / kw / task / src."""
from __future__ import annotations

from unittest.mock import patch
from urllib.parse import quote

import pandas as pd


# ── URL 빌더 ────────────────────────────────────────────────

def test_dm_tab_href_jobs_omits_dm_tab_param():
    from ui import data_management_v2 as dm
    href = dm._dm_tab_href("jobs")
    assert "app_area=" + quote("🧱 데이터 관리") in href
    assert "dm_tab=" not in href  # 기본 탭은 깨끗한 URL


def test_dm_tab_href_with_specific_tab():
    from ui import data_management_v2 as dm
    href = dm._dm_tab_href("kw")
    assert "dm_tab=kw" in href
    href2 = dm._dm_tab_href("src")
    assert "dm_tab=src" in href2


# ── _dm_tabs_html — <a> + 활성 마킹 ────────────────────────

def test_dm_tabs_html_renders_anchors_not_disabled_buttons():
    from ui import data_management_v2 as dm
    # PR-A 이후 news 그룹은 jobs/kw/src 3개만 sub-탭으로 노출 (task 는 tasks 그룹).
    html = dm._dm_tabs_html("jobs", {"active_sources": 4, "today_count": 32})
    assert html.count('class="dm-tab"') + html.count('class="dm-tab dm-tab-active"') == 3
    # disabled 자취 없음
    assert "disabled" not in html
    # B.5 PR 안내 텍스트 사라짐
    assert "B.5 PR" not in html


def test_dm_tabs_html_marks_selected_tab():
    from ui import data_management_v2 as dm
    html = dm._dm_tabs_html("kw", {"active_sources": 1, "today_count": 1})
    # kw 만 active
    assert html.count("dm-tab-active") == 1
    assert html.count('aria-current="true"') == 1
    assert 'aria-current="true"' in html
    # 키워드 라벨에 활성
    assert "키워드" in html


def test_dm_tabs_html_invalid_falls_back_to_jobs():
    from ui import data_management_v2 as dm
    html = dm._dm_tabs_html("nuke", {"active_sources": 0, "today_count": 0})
    # jobs 만 활성
    assert html.count("dm-tab-active") == 1
    assert "수집잡" in html


# ── _dm_kw_body_html ────────────────────────────────────────

def test_dm_kw_body_shows_user_terms_and_muted():
    from ui import data_management_v2 as dm
    from persona.schema import Persona
    persona = Persona(
        dept="도장",
        interest_tasks=["비전 검사", "막두께 측정"],
        interest_lv3=["도장 검사"],
        muted_keywords=["AI"],
    )
    with patch.object(dm._news_db, "load_news_for_days", return_value=pd.DataFrame()):
        html = dm._dm_kw_body_html(persona)
    assert "비전 검사" in html
    assert "막두께 측정" in html
    assert "도장 검사" in html
    assert "AI" in html
    # 자동 추출 / 내가 추가 / 숨김 세 섹션 헤더
    assert "SOLA 자동 추출" in html
    assert "내가 추가" in html
    assert "숨김 키워드" in html
    # 보드 ⑦ 인계 링크
    assert "?app_area=" + quote("📊 오늘의 보드") in html
    # 페르소나 편집 진입
    assert "?persona_editor=1" in html


def test_dm_kw_body_filters_muted_from_auto():
    """자동 추출 그룹에서 muted 키워드 제외."""
    from ui import data_management_v2 as dm
    from persona.schema import Persona
    persona = Persona(dept="도장", muted_keywords=["AI"])
    news = pd.DataFrame([{"keywords": "AI, 로봇"} for _ in range(5)])
    fake_top = pd.DataFrame({"keyword": ["AI", "로봇", "비전"], "count": [20, 10, 5]})
    with patch.object(dm._news_db, "load_news_for_days", return_value=news), \
         patch("store.trends.top_keywords", return_value=fake_top):
        html = dm._dm_kw_body_html(persona)
    # 자동 추출 chip 에 로봇/비전 보이고 AI 는 자동에 없음(숨김 섹션에는 있음)
    # 자동 추출 섹션의 chip 카운트로 확인
    assert "로봇" in html
    # AI 는 muted 섹션에만 등장 (line-through 처리)
    assert "dm-kw-chip-muted" in html


# ── _dm_src_body_html ──────────────────────────────────────

def test_dm_src_body_shows_per_source_counts():
    from ui import data_management_v2 as dm
    news = pd.DataFrame([
        {"source": "naver", "collected_at": "2026-05-31T06:00:00+00:00"},
        {"source": "naver", "collected_at": "2026-05-30T06:00:00+00:00"},
        {"source": "google", "collected_at": "2026-05-31T06:00:00+00:00"},
    ])
    with patch.object(dm._news_db, "load_news_for_days", return_value=news):
        html = dm._dm_src_body_html({"active_sources": 2})
    # 출처별 카운트
    assert "naver" in html
    assert "google" in html
    assert "2건/7일" in html  # naver
    assert "1건/7일" in html  # google
    # 기대 출처(0건) 도 회색으로 노출
    assert "AI Times" in html
    assert "7일 무수집" in html


def test_dm_src_body_empty_news():
    from ui import data_management_v2 as dm
    with patch.object(dm._news_db, "load_news_for_days", return_value=pd.DataFrame()):
        html = dm._dm_src_body_html({"active_sources": 0})
    # 기대 출처 4개 모두 노출 (cnt 0)
    assert "AI Times" in html
    assert "Google RSS" in html
    assert "네이버 기술" in html
    assert "오토메이션월드" in html
    assert html.count("7일 무수집") >= 4


# ── _dm_task_body_html ─────────────────────────────────────

def test_dm_task_body_renders_section_card():
    from ui import data_management_v2 as dm
    with patch.object(dm, "_load_tasks", return_value=pd.DataFrame()):
        html = dm._dm_task_body_html()
    assert "작업 정의 데이터" in html
    assert "엑셀" in html
    assert "아직 없음" in html


def test_dm_task_body_shows_current_count():
    from ui import data_management_v2 as dm
    fake_df = pd.DataFrame([{"a": i} for i in range(42)])
    with patch.object(dm, "_load_tasks", return_value=fake_df):
        html = dm._dm_task_body_html()
    assert "42건" in html


# ── 디스패치 ────────────────────────────────────────────────

def test_dm_tab_body_html_dispatches_by_tab():
    from ui import data_management_v2 as dm
    from persona.schema import Persona
    stats = {"active_sources": 4, "today_count": 1}
    with patch.object(dm._news_db, "load_news_for_days", return_value=pd.DataFrame()), \
         patch.object(dm, "_load_tasks", return_value=pd.DataFrame()):
        kw_html = dm._dm_tab_body_html("kw", persona=Persona(), dm_stats=stats)
        task_html = dm._dm_tab_body_html("task", persona=Persona(), dm_stats=stats)
        src_html = dm._dm_tab_body_html("src", persona=Persona(), dm_stats=stats)
        jobs_html = dm._dm_tab_body_html("jobs", persona=Persona(), dm_stats=stats)

    assert "키워드 관리" in kw_html
    assert "작업 정의 데이터" in task_html
    assert "출처 설정" in src_html
    # jobs 는 본문 없음 (split 자체가 본문)
    assert jobs_html == ""


# ── render() — st.tabs(네이티브) 헤더/본문 분리 ─────────────

def test_render_dm_header_has_kpis_and_no_tab_bar():
    """헤더는 KPI 4종만(1회 고정). 탭 전환은 st.tabs 클라이언트사이드라 헤더에
    앵커 탭(<a dm-tab>)·`?dm_tab=` 앵커·{{DM_TABS}} placeholder 가 남지 않는다."""
    from ui import data_management_v2 as dm
    stats = {"active_sources": 4, "today_count": 1, "total_chunks": 100, "last_update": "06:00"}
    captured = []
    with patch("streamlit.html", side_effect=lambda s: captured.append(s)):
        dm._render_dm_header(stats)
    assert captured
    html = captured[0]
    # KPI 값이 헤더에 박힘
    assert "100" in html        # total_chunks
    assert "06:00" in html      # last_update
    # 앵커 탭 바·핸드오프 앵커·placeholder 잔재 없음
    assert 'class="dm-tab"' not in html
    assert 'href="?dm_tab=' not in html
    assert "{{DM_TABS}}" not in html


def test_render_jobs_split_emits_split_no_anchor_tabs():
    """jobs 탭 본문은 dm-split(수집잡+뉴스 라이브러리)만. 헤더는 _render_dm_header 가
    이미 그렸으므로 여기엔 KPI 가 없고, 앵커 탭/`?dm_tab=` 앵커도 없다."""
    from ui import data_management_v2 as dm
    stats = {"active_sources": 4, "today_count": 1, "total_chunks": 100, "last_update": "06:00"}
    captured = []
    with patch("streamlit.html", side_effect=lambda s: captured.append(s)), \
         patch.object(dm._news_db, "load_news_for_days", return_value=pd.DataFrame()), \
         patch.object(dm, "_news_cards_html", return_value=""), \
         patch.object(dm, "_ingest_jobs_html", return_value=""), \
         patch.object(dm, "_hist_html", return_value={"head": "", "svg": "", "foot": "", "runs": ""}):
        dm._render_jobs_split(stats)
    assert captured
    html = captured[0]
    # 기본 split 정상 노출
    assert "dm-split" in html
    # 앵커 탭/핸드오프 앵커 없음(전체 리로드 유발하던 `?dm_tab=` 제거)
    assert 'class="dm-tab"' not in html
    assert 'href="?dm_tab=' not in html
    assert "{{DM_TABS}}" not in html  # 본문 슬라이스라 placeholder 자체가 없음


# ── st.tabs(네이티브) — 모든 패널 eager 렌더, 전환은 클라이언트사이드 ──────

def _dm_app():
    from streamlit.testing.v1 import AppTest
    from persona import store as ps
    from persona.schema import Persona
    ps.reset(); ps.clear_onboarding_dismiss()
    ps.save(Persona(name="홍길동", dept="도장1팀", team="자동화1팀"))
    at = AppTest.from_file("app.py", default_timeout=60)
    at.session_state["app_area"] = "🧱 데이터 관리"
    return at


def test_dm_tabs_eager_render_all_panels_no_exception():
    """st.tabs 는 한 런에서 모든 패널을 eager 렌더 → jobs(dm-split)·kw(키워드 관리)
    본문이 동시에 출력되고 예외 없음. 탭 전환은 100% 클라이언트사이드(서버 rerun 0)라
    예전 앵커 탭 바(<a dm-tab>)는 더 이상 굽지 않는다."""
    at = _dm_app()
    at.run()
    assert not at.exception
    combined = "\n".join(h.proto.body for h in at.get("html"))
    assert "dm-split" in combined            # jobs 패널 (뉴스 라이브러리 split)
    assert "키워드 관리" in combined          # kw 패널 본문 — 동시에 렌더됨
    assert 'class="dm-tab"' not in combined  # 앵커 탭 바 제거됨(st.tabs 가 대체)


def test_dm_tabs_handoff_query_cleaned_and_panels_render():
    """레거시 핸드오프 `?dm_tab=src` 는 st.tabs 에선 탭을 못 고르므로 1회 정리된다.
    모든 패널은 여전히 eager 렌더되어 출처 본문이 출력된다."""
    at = _dm_app()
    at.query_params["dm_tab"] = "src"
    at.run()
    assert not at.exception
    combined = "\n".join(h.proto.body for h in at.get("html"))
    assert "출처" in combined                 # src 패널 본문
    assert "dm-split" in combined             # jobs 패널도 함께 eager 렌더
    # 핸드오프 query 는 정리됨(URL 만 지저분해지므로)
    assert "dm_tab" not in at.query_params
