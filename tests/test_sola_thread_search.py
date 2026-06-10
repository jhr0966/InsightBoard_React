"""SOLA thread 검색 — 필터/그룹핑 로직 + 항목·빈 카드 html 검증.

위젯화(2026-06-10) 이후 단일 문자열 `_render_thread_list_html` 은 항목별
st.container + 투명 오버레이 st.button(`_render_thread_list`)으로 전환·삭제됐다.
순수 로직은 `_thread_groups`(그룹핑) / `_thread_item_html`(항목 시각, 앵커 없음) /
`_thread_search_empty_html`(검색 0건 카드)로 분리 — 여기서 검증한다.
"""
from __future__ import annotations

from store.sola_threads import Thread
from ui import sola_workshop_v2 as sw


def _t(title: str, **overrides) -> Thread:
    defaults = dict(
        id=f"th_{abs(hash(title)) % 10000:04x}",
        title=title,
        created_at="2026-05-29T00:00:00+00:00",
        updated_at="2026-05-29T10:00:00+00:00",
        message_count=1,
        pinned=False,
    )
    defaults.update(overrides)
    return Thread(**defaults)


# ── 필터 로직 ────────────────────────────────────────────────

def test_filter_threads_empty_query_returns_input_unchanged():
    threads = [_t("a"), _t("b")]
    assert sw._filter_threads_by_query(threads, "") == threads
    assert sw._filter_threads_by_query(threads, "   ") == threads


def test_filter_threads_substring_match():
    threads = [_t("도장 비전 PoC"), _t("VOC 예측"), _t("도료 자동 공급")]
    out = sw._filter_threads_by_query(threads, "도")
    titles = [t.title for t in out]
    assert "도장 비전 PoC" in titles
    assert "도료 자동 공급" in titles
    assert "VOC 예측" not in titles


def test_filter_threads_case_insensitive():
    threads = [_t("VOC Forecast"), _t("voc baseline")]
    assert len(sw._filter_threads_by_query(threads, "voc")) == 2
    assert len(sw._filter_threads_by_query(threads, "VOC")) == 2
    assert len(sw._filter_threads_by_query(threads, "Voc")) == 2


def test_filter_threads_no_match_returns_empty():
    threads = [_t("도장 비전")]
    assert sw._filter_threads_by_query(threads, "nope") == []


def test_filter_threads_handles_empty_title_safely():
    """title 이 빈 문자열이어도 예외 없이 빈 매칭."""
    threads = [_t("도장")]
    threads.append(Thread(
        id="th_empty", title="", created_at="2026-05-29T00:00:00+00:00",
        updated_at="2026-05-29T00:00:00+00:00", message_count=0, pinned=False,
    ))
    out = sw._filter_threads_by_query(threads, "도장")
    assert len(out) == 1
    assert out[0].title == "도장"


# ── 그룹핑 — 검색 모드 ──────────────────────────────────────

def test_groups_search_mode_emits_flat_result_group():
    threads = [_t("도장 비전 PoC"), _t("VOC 예측"), _t("도료 자동 공급")]
    groups = sw._thread_groups(threads, search_query="도")
    # 단일 평탄 그룹 — 일반 그룹(오늘/어제/이번 주/이전/★ 고정) 미노출
    assert len(groups) == 1
    label, items = groups[0]
    assert label == "검색 결과 2건"
    # 매칭된 thread 만 노출
    titles = [t.title for t in items]
    assert "도장 비전 PoC" in titles
    assert "도료 자동 공급" in titles
    assert "VOC 예측" not in titles


def test_groups_search_no_match_returns_empty():
    threads = [_t("도장 비전")]
    assert sw._thread_groups(threads, search_query="없는키워드") == []


def test_search_empty_card_shows_friendly_text_with_query():
    out = sw._thread_search_empty_html("없는키워드")
    assert "일치하는 대화가 없어요" in out
    assert "없는키워드" in out
    assert "검색을 지우면" in out


def test_search_empty_card_escapes_query():
    """검색어가 HTML 특수문자여도 escape 되어야 (XSS 방어)."""
    out = sw._thread_search_empty_html("<script>")
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


def test_groups_no_query_keeps_normal_grouping():
    threads = [
        _t("오늘1", updated_at="2026-05-29T08:00:00+00:00"),
        _t("핀1", updated_at="2026-05-29T07:00:00+00:00", pinned=True),
    ]
    labels = [label for label, _ in sw._thread_groups(threads, "")]
    assert not any("검색 결과" in lb for lb in labels)
    # ★ 고정 그룹은 노출
    assert "★ 고정" in labels


def test_search_empty_card_truncates_very_long_query():
    """40자 초과 검색어는 cap 되어 안내 카드 정상 표시."""
    long_q = "a" * 200
    out = sw._thread_search_empty_html(long_q)
    assert "일치하는 대화가 없어요" in out
    assert "a" * 40 in out
    assert "a" * 41 not in out


# ── 항목 시각 html — 앵커 없음 (클릭은 오버레이 st.button) ──

def test_thread_item_html_has_no_anchor_and_keeps_classes():
    """full-reload 앵커(?switch_thread=) 금지 — 시각 html 만, 클래스 호환 유지."""
    t = _t("도장 비전 PoC")
    out = sw._thread_item_html(t, active_id=t.id)
    assert "<a" not in out
    assert "switch_thread=" not in out
    assert "ws-th-item" in out
    assert "ws-th-active" in out          # 활성 항목 강조 클래스
    assert "도장 비전 PoC" in out


def test_thread_item_html_inactive_has_no_active_class():
    t = _t("일반 세션")
    out = sw._thread_item_html(t, active_id="th_other")
    assert "ws-th-item" in out
    assert "ws-th-active" not in out


def test_thread_item_html_escapes_title():
    t = _t("<script>alert(1)</script>")
    out = sw._thread_item_html(t, active_id="x")
    assert "<script>" not in out
    assert "&lt;script&gt;" in out
