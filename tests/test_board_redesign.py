"""보드 재설계 — 적응형 트렌드(일별/신규 배지) · 키워드 설정 모달 저장 · 한눈요약 구조화."""
from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest
import streamlit as st

from ui import board_v2


# ── 트렌드: 적응형 granularity + '신규' 배지 ─────────────────

def _weekly_spike(name="AI", total=12):
    """주별 8칸 중 금주에만 데이터 — 짧은 누적 시나리오."""
    return [{"name": name, "counts": [0] * 7 + [total]}]


def test_trend_switches_to_daily_mode_when_accumulation_short(monkeypatch):
    """데이터가 1주에만 있으면 주별 8칸 대신 일별 14칸으로 전환."""
    daily = [{"name": "AI", "counts": [0, 0, 1, 2, 0, 1, 3, 2, 1, 0, 2, 4, 3, 5]}]
    monkeypatch.setattr(board_v2, "_weekly_keyword_series",
                        lambda weeks=8: (["W1"] * 8, _weekly_spike()))
    monkeypatch.setattr(board_v2, "_daily_keyword_series",
                        lambda days=14: ([f"6/{d}" for d in range(1, 14)] + ["오늘"], daily))
    board_v2._board_trend.clear()
    t = board_v2._board_trend()
    assert "오늘" in t["xticks"]                       # 일별 라벨 사용
    assert "일별 추이" in t["anno_sub"]                # 모드 안내
    assert "+100%" not in t["kw_list"]                # 무의미한 +100% 없음


def test_trend_stays_weekly_with_long_accumulation(monkeypatch):
    series = [{"name": "AI", "counts": [5, 7, 6, 8, 9, 12, 11, 15]}]
    monkeypatch.setattr(board_v2, "_weekly_keyword_series",
                        lambda weeks=8: ([f"W{i}" for i in range(7)] + ["금주"], series))
    board_v2._board_trend.clear()
    t = board_v2._board_trend()
    assert "금주" in t["xticks"]
    assert "8주간" in t["anno_sub"]


def test_trend_new_keyword_shows_badge_not_100pct(monkeypatch):
    """비교 기준(첫 1/3)이 0 인 키워드는 +100% 대신 '신규 N건' 배지."""
    monkeypatch.setattr(board_v2, "_weekly_keyword_series",
                        lambda weeks=8: (["W1"] * 8, _weekly_spike(total=12)))
    monkeypatch.setattr(board_v2, "_daily_keyword_series", lambda days=14: ([], []))
    board_v2._board_trend.clear()
    t = board_v2._board_trend()                       # 일별 폴백 실패 → 주별 유지
    assert "신규 12건" in t["kw_list"]
    assert "+100%" not in t["kw_list"]
    assert "첫 등장" in t["anno_sub"]


def test_delta_info_flags_new():
    assert board_v2._delta_info([0, 0, 0, 0, 0, 0, 0, 9]) == (100, True)
    assert board_v2._delta_info([3, 3, 3, 3, 3, 3, 3, 6])[1] is False


def test_delta_info_trims_leading_empty_buckets():
    """수집 시작이 윈도보다 늦어도(앞 버킷 전부 0) 실제 데이터 구간으로 % 계산."""
    pct, is_new = board_v2._delta_info([0, 0, 0, 0, 2, 3, 4, 6])
    assert is_new is False
    assert pct == 200                                  # head=2 → tail=6


# ── 키워드 관리: × 버튼 제거 + 설정 모달 저장 ─────────────────

def test_kw_x_buttons_removed():
    assert not hasattr(board_v2, "_render_kw_x_buttons")


def test_kw_mgr_html_has_no_inline_add_chip(monkeypatch):
    from persona.schema import Persona
    news = pd.DataFrame({
        "title": ["용접 자동화"], "link": ["l1"], "keywords": ["용접"],
        "collected_at": ["2026-06-11T00:00:00+00:00"], "source": ["naver"],
    })
    monkeypatch.setattr(board_v2._news_db, "load_news_for_days", lambda days=30: news)
    html = board_v2._board_kw_mgr_html(Persona(interest_keywords=["용접"]))
    assert "db-kw-add-inline" not in html             # ＋ 추가 칩 제거
    assert "키워드 추가 + 즉시 수집" not in html


@pytest.fixture
def isolated_persona(tmp_path, monkeypatch):
    """페르소나 JSON 영구 저장소를 임시 디렉토리로 격리 (test_kw_actions 와 동형)."""
    monkeypatch.setenv("NEWS_DATA_ROOT", str(tmp_path / "data"))
    import config
    monkeypatch.setattr(config, "DATA_ROOT", tmp_path / "data")
    from persona import store as persona_store
    monkeypatch.setattr(
        persona_store, "_profile_path",
        lambda: tmp_path / "data" / "persona" / "profile.json",
    )
    (tmp_path / "data" / "persona").mkdir(parents=True, exist_ok=True)
    yield persona_store


def test_kw_settings_save_consumes_widget_values(isolated_persona):
    """모달 [저장] — 선택 유지/제거/신규 추가 + muted 교체가 persona 에 반영."""
    from persona.schema import Persona
    p = Persona(name="t", interest_tasks=["로봇 티칭"], interest_lv3=["도장"],
                interest_keywords=["AI"], muted_keywords=["업무"])
    isolated_persona.save(p)
    st.session_state["persona"] = p
    st.session_state["_do_kw_settings_save"] = True
    st.session_state["_kw_settings_open"] = True
    # '도장' 제거, '비전 검사' 신규 추가, 'AI'/'로봇 티칭' 유지
    st.session_state["kw_set_user"] = ["AI", "로봇 티칭", "비전 검사"]
    st.session_state["kw_set_muted"] = ["AX"]

    assert board_v2.consume_kw_settings_save_if_any() is True
    saved = isolated_persona.load()
    assert saved.interest_tasks == ["로봇 티칭"]
    assert saved.interest_lv3 == []                       # 선택 해제 → 제거
    assert saved.interest_keywords == ["AI", "비전 검사"]  # 유지 + 신규
    assert saved.muted_keywords == ["AX"]                 # 교체
    assert "_kw_settings_open" not in st.session_state    # 모달 닫힘
    assert "kw_set_user" not in st.session_state          # 위젯 상태 정리
    tone, msg = st.session_state.pop("_kw_action_toast")
    assert tone == "ok"


def test_kw_settings_save_noop_without_pending():
    st.session_state.pop("_do_kw_settings_save", None)
    assert board_v2.consume_kw_settings_save_if_any() is False


# ── 한눈요약: 헤드라인+불릿 구조화 + 절단 방어 ─────────────────

def test_sanitize_brief_drops_truncated_last_line():
    from sola.board_brief import _sanitize_brief
    raw = "Physical AI 가 화두입니다.\n- **검사**: 비전 검사 자동화가 확산되고 있습니다.\n- 생산자동화그룹은 이러한"
    out = _sanitize_brief(raw)
    assert "이러한" not in out
    assert out.endswith("확산되고 있습니다.")


def test_brief_html_renders_headline_and_points(monkeypatch):
    news = pd.DataFrame({
        "title": ["기사 A", "기사 B"], "link": ["a", "b"], "source": ["naver"] * 2,
        "press": ["", ""], "collected_at": ["2026-06-11T00:00:00+00:00"] * 2,
        "image_url": [""] * 2, "summary": ["요약"] * 2, "summary_llm": [""] * 2,
        "keywords": ["AI"] * 2,
    })
    monkeypatch.setattr(board_v2._news_db, "load_news_for_days", lambda days=3: news)
    monkeypatch.setattr(board_v2, "_load_tasks", lambda: pd.DataFrame())
    monkeypatch.setattr(
        "sola.board_brief.brief",
        lambda items, persona_label="", **kw:
            "AI 검사가 화두입니다.\n- **AI**: 비전 검사 적용이 늘었습니다.\n- **로봇**: 용접 티칭이 단축됐습니다.",
    )
    board_v2._brief_html.clear()
    out = board_v2._brief_html(persona_label="t")
    assert 'class="db-brief-greet-tx"' in out["summary"]   # 헤드라인 단일 래퍼(flex 조각 방지)
    assert out["summary"].count("<li>") == 2               # 불릿 2개
    assert "<b>AI</b>" in out["summary"]
