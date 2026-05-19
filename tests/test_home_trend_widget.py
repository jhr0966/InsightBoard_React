"""홈 트렌드 위젯 — payload 계산, 칩 HTML, page_context 합산."""
from __future__ import annotations

import pandas as pd
import pytest

from store import news_db
from ui import home_tab


def _save_at(date_str: str, source: str, articles: list[dict]) -> None:
    from store.paths import news_dir_for

    day_dir = news_dir_for(date_str)
    df = pd.DataFrame(articles)
    for col in news_db._ARTICLE_COLS:
        if col not in df.columns:
            df[col] = ""
    df = df[list(news_db._ARTICLE_COLS)].astype(str)
    df.to_parquet(day_dir / f"{source}_test.parquet", index=False)


# ── _compute_home_trend_payload ───────────────────────────────────

def test_compute_payload_days1_uses_today_df():
    today = pd.DataFrame(
        [{"title": "t1", "link": "u1", "date": "2026-05-13", "keywords_llm": "용접 자동화"}]
    )
    out = home_tab._compute_home_trend_payload(today, days=1)
    assert len(out["period_df"]) == 1
    assert "vol_df" in out and "emergence" in out
    # days=1 이면 emergence 는 비어 있어야 (오늘만)
    assert out["emergence"]["new"].empty
    assert out["emergence"]["rising"].empty
    assert out["emergence"]["gone"].empty


def test_compute_payload_days7_aggregates_and_classifies_emergence():
    from datetime import datetime, timezone

    fixed_now = datetime(2026, 5, 13, 12, 0, 0, tzinfo=timezone.utc)

    _save_at("2026-05-13", "naver", [
        {"title": "오늘 a", "link": "u1", "date": "2026-05-13",
         "keywords_llm": "디지털트윈, 용접 자동화"},
    ])
    _save_at("2026-05-12", "naver", [
        {"title": "어제 b", "link": "u2", "date": "2026-05-12",
         "keywords_llm": "용접 자동화, 그라인딩"},
    ])
    _save_at("2026-05-11", "naver", [
        {"title": "그제 c", "link": "u3", "date": "2026-05-11",
         "keywords_llm": "그라인딩"},
    ])

    today_df = news_db.load_news_for_days(days=1, now=fixed_now)
    out = home_tab._compute_home_trend_payload(today_df, days=7, now=fixed_now)

    # period_df 누적
    assert len(out["period_df"]) == 3
    # vol_df 일자별 zero-fill 포함 7 행
    assert len(out["vol_df"]) == 7
    em = out["emergence"]
    # 디지털트윈은 오늘만 → new
    assert "디지털트윈" in set(em["new"]["keyword"].astype(str))
    # 그라인딩은 기준에만 → gone
    assert "그라인딩" in set(em["gone"]["keyword"].astype(str))


def test_compute_payload_empty_today_returns_empty_emergence():
    empty = pd.DataFrame(columns=["title", "link", "date", "keywords_llm"])
    out = home_tab._compute_home_trend_payload(empty, days=7)
    assert out["emergence"]["new"].empty
    assert out["emergence"]["rising"].empty
    assert out["emergence"]["gone"].empty


def test_compute_payload_uses_published_at_when_date_is_display_text():
    """실데이터 회귀: 네이버 '1시간 전', 구글 RFC pubDate, tech '최신 동향' 처럼
    date 가 표시 텍스트여도 published_at 으로 today 분류가 동작해야."""
    from datetime import datetime, timezone

    fixed_now = datetime(2026, 5, 13, 12, 0, 0, tzinfo=timezone.utc)

    _save_at("2026-05-13", "naver", [
        {"title": "오늘 a", "link": "u1",
         "date": "1시간 전", "published_at": "2026-05-13T03:00:00+00:00",
         "keywords_llm": "디지털트윈"},
    ])
    _save_at("2026-05-12", "naver", [
        {"title": "어제 b", "link": "u2",
         "date": "Tue, 12 May 2026 09:00:00 GMT", "published_at": "2026-05-12T09:00:00+00:00",
         "keywords_llm": "그라인딩"},
    ])

    today_df = news_db.load_news_for_days(days=1, now=fixed_now)
    out = home_tab._compute_home_trend_payload(today_df, days=7, now=fixed_now)
    em = out["emergence"]
    # 디지털트윈은 published_at 기준 오늘만 → new
    assert "디지털트윈" in set(em["new"]["keyword"].astype(str))
    # 그라인딩은 어제만 → gone
    assert "그라인딩" in set(em["gone"]["keyword"].astype(str))


# ── _chip_row ─────────────────────────────────────────────────────

def test_chip_row_renders_keywords_with_count():
    df = pd.DataFrame([{"keyword": "용접 자동화", "count": 3}])
    out = home_tab._chip_row("🆕 새", df, color="#2563eb")
    assert "용접 자동화" in out
    assert "3" in out
    assert "🆕 새" in out


def test_chip_row_uses_delta_when_present():
    df = pd.DataFrame([{"keyword": "디지털트윈", "today": 5, "base": 1, "delta": 4}])
    out = home_tab._chip_row("📈", df, color="#16a34a")
    assert "+4" in out


def test_chip_row_empty_says_no_data():
    out = home_tab._chip_row("📉", pd.DataFrame(columns=["keyword", "count"]), color="#9ca3af")
    assert "없음" in out


def test_chip_row_escapes_html():
    df = pd.DataFrame([{"keyword": "<script>x</script>", "count": 1}])
    out = home_tab._chip_row("🆕", df, color="#000")
    assert "<script>" not in out  # 이스케이프 됐음
    assert "&lt;script&gt;" in out


# ── _trend_widget_html ────────────────────────────────────────────

def test_trend_widget_html_includes_brief_and_period_label():
    em = home_tab._empty_emergence()
    out = home_tab._trend_widget_html("최근 7일 핫이슈는 **용접 자동화**.", em)
    assert "최근 7일" in out
    assert "용접 자동화" in out
    assert "🧠 SOLA 한 줄" in out


def test_trend_widget_html_empty_brief_shows_placeholder():
    em = home_tab._empty_emergence()
    out = home_tab._trend_widget_html("", em)
    assert "갱신" in out or "버튼을 눌러" in out


# ── _build_trend_context ──────────────────────────────────────────

def test_build_trend_context_includes_volume_and_keywords_and_brief():
    payload = {
        "vol_df": pd.DataFrame([
            {"date": "2026-05-12", "count": 5},
            {"date": "2026-05-13", "count": 8},
        ]),
        "emergence": {
            "new": pd.DataFrame([{"keyword": "디지털트윈", "count": 2}]),
            "gone": pd.DataFrame(columns=["keyword", "count"]),
            "rising": pd.DataFrame([{"keyword": "용접 자동화", "today": 4, "base": 1, "delta": 3}]),
        },
    }
    ctx = home_tab._build_trend_context("최근 7일 **용접 자동화** 가 두드러집니다.", payload)
    assert "2026-05-13=8" in ctx
    assert "디지털트윈" in ctx
    assert "용접 자동화(+3)" in ctx
    assert "SOLA 한 줄 해석" in ctx


def test_build_trend_context_empty_returns_empty_string():
    payload = {
        "vol_df": pd.DataFrame(columns=["date", "count"]),
        "emergence": home_tab._empty_emergence(),
    }
    ctx = home_tab._build_trend_context("", payload)
    assert ctx == ""


# ── _build_page_context with trend_ctx ────────────────────────────

def test_build_page_context_includes_trend_ctx_when_provided():
    from persona.schema import Persona

    persona = Persona(dept="생산기술", job="자동화 엔지니어")
    ctx = home_tab._build_page_context(
        persona, news_items=[], insight_text="",
        trend_ctx="[최근 7일 트렌드] 일자별: 2026-05-13=8\nSOLA 한 줄 해석: 용접 자동화 상승",
    )
    assert "생산기술" in ctx
    assert "최근 7일 트렌드" in ctx
    assert "SOLA 한 줄 해석" in ctx


def test_build_page_context_omits_trend_when_empty():
    from persona.schema import Persona

    persona = Persona(dept="생산기술")
    ctx = home_tab._build_page_context(persona, news_items=[], insight_text="", trend_ctx="")
    assert "최근 7일 트렌드" not in ctx

# ── Phase 3 recommended actions and top opportunities ─────────────

def test_recommended_actions_prioritizes_missing_data_and_persona():
    from persona.schema import Persona

    actions = home_tab._recommended_actions(
        news_count=0,
        roadmap_count=0,
        enriched_count=0,
        persona=Persona(),
        top_opportunities=pd.DataFrame(),
    )

    titles = [a["title"] for a in actions]
    assert titles[:3] == ["뉴스를 먼저 수집하세요", "로드맵을 업로드하세요", "페르소나를 설정하세요"]
    assert actions[0]["target"] == "데이터 관리"


def test_recommended_actions_promotes_opportunity_and_sola_when_ready():
    from persona.schema import Persona

    cells = pd.DataFrame([
        {"dept": "생산기술", "lv3": "용접", "cell_score": 8.2, "sample_tasks": "용접 자동화", "sample_news": "로봇"}
    ])
    actions = home_tab._recommended_actions(
        news_count=5,
        roadmap_count=3,
        enriched_count=4,
        persona=Persona(dept="생산기술", job="자동화"),
        top_opportunities=cells,
    )

    assert actions[0]["target"] == "인사이트 분석"
    assert "생산기술 · 용접" in actions[0]["body"]
    assert actions[1]["target"] == "SOLA 작업실"


def test_recommended_actions_html_escapes_text_and_tone():
    html = home_tab._recommended_actions_html([
        {
            "icon": "<i>",
            "title": "<script>x</script>",
            "body": "body<script>",
            "target": "target",
            "tone": 'bad" onclick="x',
        }
    ])

    assert 'onclick' not in html
    assert "&lt;script&gt;x&lt;/script&gt;" in html
    assert "body&lt;script&gt;" in html
    assert "&lt;i&gt;" in html


def test_top_opportunities_html_marks_persona_dept_and_escapes():
    from persona.schema import Persona

    cells = pd.DataFrame([
        {
            "dept": "생산기술",
            "lv3": "<용접>",
            "cell_score": 9.25,
            "sample_tasks": "작업<script>",
            "sample_news": "뉴스<script>",
        }
    ])

    html = home_tab._top_opportunities_html(cells, persona=Persona(dept="생산기술"))
    assert 'class="opportunity-pulse-card mine"' in html
    assert "score 9.2" in html
    assert "&lt;용접&gt;" in html
    assert "작업&lt;script&gt;" in html
    assert "<script>" not in html


def test_build_page_context_includes_recommendations_and_top_opportunities():
    from persona.schema import Persona

    cells = pd.DataFrame([
        {
            "dept": "생산기술",
            "lv3": "용접",
            "cell_score": 9.0,
            "sample_tasks": "용접 자동화",
            "sample_news": "로봇",
        }
    ])
    ctx = home_tab._build_page_context(
        Persona(dept="생산기술"),
        news_items=[],
        insight_text="",
        recommended_actions=[{"target": "인사이트 분석", "title": "검토", "body": "기회 확인"}],
        top_opportunities=cells,
    )

    assert "추천 다음 행동" in ctx
    assert "인사이트 분석: 검토" in ctx
    assert "자동화 기회 Top" in ctx
    assert "생산기술 / 용접 score=9.0" in ctx
