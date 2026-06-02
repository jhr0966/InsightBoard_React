"""Phase C — 인사이트 화면 정리: 가짜 ia-sola 패널 + 죽은 필터 제거, PoC 중복집계 수정."""
from __future__ import annotations

from ui import insights_v2


def test_strip_removes_fake_sola_and_filters_keeps_main():
    html = (
        '<div class="ia-shell"><header>h</header>'
        '<div class="ia-filters"><div class="ia-seg"><button>7일</button></div></div>'
        '<div class="ia-grid"><main class="ia-main">{{IA_HEATMAP}}</main>'
        '<aside class="ia-sola"><div>가짜 인용</div></aside></div></div>'
    )
    out = insights_v2._strip_mockup_blocks(html)
    assert "ia-sola" not in out
    assert "가짜 인용" not in out
    assert "ia-filters" not in out
    assert "7일" not in out
    # 본문/그리드/placeholder 보존
    assert '<main class="ia-main">' in out
    assert '<div class="ia-grid">' in out
    assert "{{IA_HEATMAP}}" in out


def test_strip_is_noop_when_blocks_absent():
    html = '<div class="ia-shell"><main>{{X}}</main></div>'
    assert insights_v2._strip_mockup_blocks(html) == html


def test_real_template_stripped_of_mockup_keeps_placeholders():
    raw = insights_v2._IA_TEMPLATE.read_text(encoding="utf-8")
    out = insights_v2._strip_mockup_blocks(raw)
    # 가짜 SOLA 패널·필터 잔재 제거
    assert "ia-sola" not in out
    assert "ia-filters" not in out
    assert "도장 부스 #3 비전 PoC" not in out      # 가짜 추천 카드
    assert "저장한 뷰" not in out                    # 죽은 필터 버튼
    # 실데이터 placeholder 는 보존
    for ph in ("{{IA_HEATMAP}}", "{{IA_MATRIX_SVG}}", "{{IA_TKW_LIST}}", "{{IA_PROCESS_MAP}}"):
        assert ph in out


def test_poc_candidates_excludes_pending_proposals(monkeypatch):
    """PoC 후보 = 자동화 기회 셀만. 채택 대기(pending) 제안서를 더하지 않는다."""
    import pandas as pd
    # pending 이 5건 있어도 poc_candidates 에 합산되면 안 됨
    monkeypatch.setattr(
        insights_v2.bookmarks_store, "summary_counts",
        lambda: {"total": 5, "by_type": {}, "proposal_status": {"pending": 5}},
    )
    monkeypatch.setattr(insights_v2._news_db, "load_news_for_days", lambda days: pd.DataFrame())
    monkeypatch.setattr(insights_v2, "_load_tasks", lambda: pd.DataFrame())
    stats = insights_v2._ia_stats()
    # 데이터 없음 → 기회 셀 0 → pending 합산 안 하므로 0 이어야 (이전 버그면 5)
    assert stats["poc_candidates"] == "0"
