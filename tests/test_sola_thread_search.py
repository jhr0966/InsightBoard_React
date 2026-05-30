"""SOLA thread 검색 — 필터 로직 + 렌더된 list HTML 검증."""
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


# ── 렌더 — 검색 모드 ────────────────────────────────────────

def test_render_search_mode_emits_flat_result_group():
    threads = [_t("도장 비전 PoC"), _t("VOC 예측"), _t("도료 자동 공급")]
    out = sw._render_thread_list_html(threads, threads[0].id, search_query="도")
    # 단일 평탄 그룹
    assert out.count("검색 결과 2건") == 1
    # 일반 그룹 (오늘/어제/이번 주/이전/★ 고정) 미노출
    assert "ws-th-grp\">오늘" not in out
    assert "ws-th-grp\">★ 고정" not in out
    # 매칭된 thread 만 노출
    assert "도장 비전 PoC" in out
    assert "도료 자동 공급" in out
    assert "VOC 예측" not in out


def test_render_search_empty_match_shows_friendly_card_with_query():
    threads = [_t("도장 비전")]
    out = sw._render_thread_list_html(threads, threads[0].id, search_query="없는키워드")
    assert "일치하는 대화가 없어요" in out
    assert "없는키워드" in out
    assert "검색을 지우면" in out


def test_render_search_escapes_query_in_empty_card():
    """검색어가 HTML 특수문자여도 escape 되어야 (XSS 방어)."""
    threads = [_t("도장")]
    out = sw._render_thread_list_html(threads, threads[0].id, search_query="<script>")
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


def test_render_no_query_keeps_normal_grouping():
    threads = [
        _t("오늘1", updated_at="2026-05-29T08:00:00+00:00"),
        _t("핀1", updated_at="2026-05-29T07:00:00+00:00", pinned=True),
    ]
    out = sw._render_thread_list_html(threads, threads[0].id, search_query="")
    assert "검색 결과" not in out
    # ★ 고정 그룹은 노출
    assert "★ 고정" in out


def test_render_truncates_very_long_query_in_empty_card():
    """40자 초과 검색어는 cap 되어 안내 카드 정상 표시."""
    long_q = "a" * 200
    out = sw._render_thread_list_html([], "x", search_query=long_q)
    # 안내 카드 노출되고 (총 검색어 길이가 200자라도 cap 으로 노출)
    assert "일치하는 대화가 없어요" in out
