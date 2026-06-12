"""SOLA workshop 우측 ws-ctx 패널 실데이터 wire — 페르소나/보관함/빈 상태 정직화."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from persona.schema import Persona
from store.bookmarks import Bookmark
from ui import sola_workshop_v2 as sw


@pytest.fixture
def isolated_bookmarks(tmp_path, monkeypatch):
    """bookmarks 가 임시 디렉토리를 쓰도록 격리 — _path() 가 임시 dir 반환."""
    import config
    monkeypatch.setattr(config, "DATA_ROOT", tmp_path)
    bookmarks_dir = tmp_path / "bookmarks"
    bookmarks_dir.mkdir(parents=True, exist_ok=True)
    from store import bookmarks as bm
    monkeypatch.setattr(bm, "_path", lambda: bookmarks_dir / "items.jsonl")
    yield bm


# ── _ctx_archive_summary — 카운트 + 미리보기 ─────────────────

def test_ctx_archive_summary_empty_returns_zero_and_friendly_card(isolated_bookmarks):
    cnt, html = sw._ctx_archive_summary()
    assert cnt == 0
    assert "아직 제안서가 없어요" in html
    assert "보드의 자동화 제안 카드" in html  # 진입 경로 안내


def test_ctx_archive_summary_with_pending_shows_count_and_preview(isolated_bookmarks):
    isolated_bookmarks.add(Bookmark(
        id="bm_a", type="proposal", title="도장 비전 검사 PoC 제안서",
        content="4개월 PoC 일정", tags=["PoC"],
        created_at="2026-05-30T00:00:00+00:00",
    ))
    isolated_bookmarks.add(Bookmark(
        id="bm_b", type="proposal", title="용접 자동화 검토",
        content="용접 로봇 도입 검토", tags=[],
        created_at="2026-05-29T00:00:00+00:00",
    ))
    cnt, html = sw._ctx_archive_summary()
    assert cnt == 2
    # 가장 최근(2026-05-30) 이 노출
    assert "도장 비전 검사 PoC 제안서" in html
    assert "용접 자동화 검토" not in html  # 두번째는 미노출, 카운트만
    # 보관함 area 링크 (?app_area=📦)
    assert "app_area=" in html and "%F0%9F%93%A6" in html
    # 카운트가 본문에 노출
    assert "2건 대기" in html


def test_ctx_archive_summary_excludes_adopted_and_rejected(isolated_bookmarks):
    isolated_bookmarks.add(Bookmark(
        id="bm_ok", type="proposal", title="채택됨", content="", tags=[],
        created_at="2026-05-30T00:00:00+00:00", status="adopted",
    ))
    isolated_bookmarks.add(Bookmark(
        id="bm_no", type="proposal", title="기각됨", content="", tags=[],
        created_at="2026-05-30T00:00:00+00:00", status="rejected",
    ))
    cnt, html = sw._ctx_archive_summary()
    assert cnt == 0
    assert "채택됨" not in html
    assert "기각됨" not in html


def test_ctx_archive_summary_escapes_title_for_xss(isolated_bookmarks):
    isolated_bookmarks.add(Bookmark(
        id="bm_xss", type="proposal", title="<script>alert(1)</script>",
        content="", tags=[], created_at="2026-05-30T00:00:00+00:00",
    ))
    _cnt, html = sw._ctx_archive_summary()
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_ctx_archive_summary_handles_store_exception_gracefully(isolated_bookmarks):
    with patch.object(sw.bookmarks_store, "list_all", side_effect=RuntimeError("disk full")):
        cnt, html = sw._ctx_archive_summary()
    assert cnt == 0
    assert "아직 제안서가 없어요" in html  # 폴백 빈 카드


# ── _ctx_age_label — 친화 시간 표시 ──────────────────────────

def test_ctx_age_label_today_yesterday_days_and_month():
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    assert sw._ctx_age_label(now.isoformat()) == "오늘"
    assert sw._ctx_age_label((now - timedelta(days=1)).isoformat()) == "어제"
    assert sw._ctx_age_label((now - timedelta(days=3)).isoformat()) == "3일 전"
    older = (now - timedelta(days=30)).isoformat()
    label = sw._ctx_age_label(older)
    assert "월" in label and "일" in label  # "5월 17일" 형식


def test_ctx_age_label_empty_or_invalid_returns_empty():
    assert sw._ctx_age_label("") == ""
    assert sw._ctx_age_label("not-a-date") == ""
