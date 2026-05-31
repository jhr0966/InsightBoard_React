"""커스텀 RSS 실 수집 wire — store.sources.custom_sources → collect_batch."""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest


# ── scraping/rss.py 단위 ────────────────────────────────────

_SAMPLE_RSS = """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0">
  <channel>
    <title>Sample Feed</title>
    <item>
      <title>첫 번째 기사</title>
      <link>https://example.com/1</link>
      <pubDate>Sun, 31 May 2026 06:00:00 +0000</pubDate>
      <description>&lt;img src="https://example.com/img.png"/&gt;본문 내용</description>
    </item>
    <item>
      <title>두 번째 기사</title>
      <link>https://example.com/2</link>
      <pubDate>Sat, 30 May 2026 06:00:00 +0000</pubDate>
      <description>두 번째 본문</description>
    </item>
  </channel>
</rss>
"""

_SAMPLE_ATOM = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Atom Feed</title>
  <entry>
    <title>Atom 첫 기사</title>
    <link href="https://atom.example.com/1"/>
    <published>2026-05-31T06:00:00Z</published>
    <summary>요약 텍스트</summary>
  </entry>
</feed>
"""


def _mock_response(text: str, status: int = 200):
    resp = MagicMock()
    resp.text = text
    resp.status_code = status
    resp.raise_for_status = MagicMock()
    return resp


def test_rss_fetch_parses_rss2_items():
    from scraping import rss
    session = MagicMock()
    session.get.return_value = _mock_response(_SAMPLE_RSS)
    with patch("scraping.rss.build_session", return_value=session):
        articles = rss.fetch("https://example.com/rss", "TestFeed", max_results=5)

    assert len(articles) == 2
    assert articles[0]["title"] == "첫 번째 기사"
    assert articles[0]["link"] == "https://example.com/1"
    assert articles[0]["source"] == "TestFeed"
    assert articles[0]["published_at"]  # ISO 변환됨
    assert "본문" in articles[0]["summary"]
    # 이미지 추출
    assert articles[0]["image_url"] == "https://example.com/img.png"


def test_rss_fetch_parses_atom_entries():
    from scraping import rss
    session = MagicMock()
    session.get.return_value = _mock_response(_SAMPLE_ATOM)
    with patch("scraping.rss.build_session", return_value=session):
        articles = rss.fetch("https://atom.example.com/rss", "AtomFeed")

    assert len(articles) == 1
    assert articles[0]["title"] == "Atom 첫 기사"
    assert articles[0]["link"] == "https://atom.example.com/1"
    assert articles[0]["source"] == "AtomFeed"
    assert articles[0]["published_at"]


def test_rss_fetch_respects_max_results():
    from scraping import rss
    # 5 items, max_results=2
    items_xml = "".join(
        f"<item><title>T{i}</title><link>https://e.com/{i}</link>"
        f"<pubDate>Sun, 31 May 2026 06:00:00 +0000</pubDate></item>"
        for i in range(5)
    )
    feed = f'<?xml version="1.0"?><rss><channel>{items_xml}</channel></rss>'
    session = MagicMock()
    session.get.return_value = _mock_response(feed)
    with patch("scraping.rss.build_session", return_value=session):
        articles = rss.fetch("https://e.com/rss", "F", max_results=2)
    assert len(articles) == 2


def test_rss_fetch_dedupes_links():
    from scraping import rss
    feed = (
        '<?xml version="1.0"?><rss><channel>'
        '<item><title>A</title><link>https://e.com/x</link></item>'
        '<item><title>A duplicate</title><link>https://e.com/x</link></item>'
        '<item><title>B</title><link>https://e.com/y</link></item>'
        '</channel></rss>'
    )
    session = MagicMock()
    session.get.return_value = _mock_response(feed)
    with patch("scraping.rss.build_session", return_value=session):
        articles = rss.fetch("https://e.com/rss", "F")
    assert len(articles) == 2  # 중복 링크 1개 제거


def test_rss_fetch_rejects_invalid_url():
    from scraping import rss
    with pytest.raises(RuntimeError, match="잘못된 RSS URL"):
        rss.fetch("ftp://nope", "F")
    with pytest.raises(RuntimeError, match="잘못된 RSS URL"):
        rss.fetch("", "F")


def test_rss_fetch_raises_on_parse_error():
    from scraping import rss
    session = MagicMock()
    session.get.return_value = _mock_response("<not xml")
    with patch("scraping.rss.build_session", return_value=session), \
         pytest.raises(RuntimeError, match="파싱 실패"):
        rss.fetch("https://e.com/rss", "F")


def test_rss_fetch_raises_on_http_error():
    from scraping import rss
    import requests as _req
    session = MagicMock()
    err_resp = MagicMock()
    err_resp.raise_for_status.side_effect = _req.HTTPError("503")
    session.get.return_value = err_resp
    with patch("scraping.rss.build_session", return_value=session), \
         pytest.raises(RuntimeError, match="요청 실패"):
        rss.fetch("https://e.com/rss", "F")


# ── collect_batch 의 extra_feeds 통합 ───────────────────────

def test_collect_batch_extra_feeds_appends_saved(tmp_path, monkeypatch):
    """extra_feeds 가 주어지면 RSS 도 fetch 하여 saved 에 추가."""
    from scraping import run_daily
    # save_articles 가 실제 파일 안 쓰도록 mock
    fake_path = tmp_path / "out.parquet"
    monkeypatch.setattr(run_daily, "save_articles", lambda articles, source: fake_path)

    fake_articles = [
        {"title": "X", "link": "https://e.com/1", "source": "MyFeed"},
        {"title": "Y", "link": "https://e.com/2", "source": "MyFeed"},
    ]
    with patch("scraping.rss.fetch", return_value=fake_articles) as mock_rss:
        report = run_daily.collect_batch(
            [],  # 키워드 없음
            sources=(),  # 기본 출처 모두 스킵
            extra_feeds=[("MyFeed", "https://e.com/rss")],
        )

    mock_rss.assert_called_once()
    args, kwargs = mock_rss.call_args
    # url 과 source_name 전달
    assert args[0] == "https://e.com/rss"
    assert kwargs["source_name"] == "MyFeed"

    assert len(report.saved) == 1
    assert report.saved[0]["source"] == "MyFeed"
    assert report.saved[0]["count"] == 2


def test_collect_batch_extra_feeds_failure_goes_to_errors(tmp_path, monkeypatch):
    from scraping import run_daily
    monkeypatch.setattr(run_daily, "save_articles", lambda articles, source: tmp_path / "x")

    with patch("scraping.rss.fetch", side_effect=RuntimeError("net down")):
        report = run_daily.collect_batch(
            [],
            sources=(),
            extra_feeds=[("BadFeed", "https://bad/rss")],
        )

    assert len(report.saved) == 0
    assert len(report.errors) == 1
    assert report.errors[0]["source"] == "BadFeed"
    assert "net down" in report.errors[0]["error"]


def test_collect_batch_extra_feeds_default_none_no_rss_calls():
    """extra_feeds 미지정 시 rss.fetch 호출 안 됨."""
    from scraping import run_daily
    with patch("scraping.rss.fetch") as mock_rss:
        run_daily.collect_batch([], sources=())
    mock_rss.assert_not_called()


# ── UI 통합 — _collect_extra_feeds + dm refresh ─────────────

@pytest.fixture
def isolated_sources(tmp_path, monkeypatch):
    cfg_dir = tmp_path / "sources"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    from store import sources as src_store
    monkeypatch.setattr(src_store, "_config_path",
                        lambda: cfg_dir / "config.json")
    yield src_store


def test_collect_extra_feeds_returns_tuples_from_custom_sources(isolated_sources):
    from ui import board_v2
    isolated_sources.add_custom("Feed1", "https://f1.com/rss")
    isolated_sources.add_custom("Feed2", "https://f2.com/rss")
    feeds = board_v2._collect_extra_feeds()
    assert sorted(feeds) == [
        ("Feed1", "https://f1.com/rss"),
        ("Feed2", "https://f2.com/rss"),
    ]


def test_collect_extra_feeds_empty_when_no_custom(isolated_sources):
    from ui import board_v2
    assert board_v2._collect_extra_feeds() == []


def test_dm_refresh_passes_extra_feeds_to_collect_batch(isolated_sources):
    """데이터관리 새로고침이 등록된 커스텀 RSS 도 함께 전달."""
    from ui import data_management_v2 as dm
    from scraping.run_daily import CollectionReport
    import streamlit as st

    isolated_sources.add_custom("RSSx", "https://rss.x/feed")
    st.query_params.clear()
    st.query_params["refresh"] = "now"
    fake = CollectionReport(saved=[], errors=[])

    with patch("ui.board_v2._collect_keywords_for_persona", return_value=["AI"]), \
         patch("scraping.run_daily.collect_batch", return_value=fake) as mock_cb:
        dm._consume_refresh_if_any()

    mock_cb.assert_called_once()
    _, kwargs = mock_cb.call_args
    assert "extra_feeds" in kwargs
    assert kwargs["extra_feeds"] == [("RSSx", "https://rss.x/feed")]


def test_dm_refresh_toast_mentions_rss_count(isolated_sources):
    """ok 토스트에 등록된 RSS 출처 수가 표시된다."""
    from ui import data_management_v2 as dm
    from scraping.run_daily import CollectionReport
    import streamlit as st

    isolated_sources.add_custom("A", "https://a.com/rss")
    isolated_sources.add_custom("B", "https://b.com/rss")
    st.query_params.clear()
    st.query_params["refresh"] = "now"
    fake = CollectionReport(
        saved=[{"source": "A", "keywords": [], "count": 3, "path": "x"}],
        errors=[],
    )

    with patch("ui.board_v2._collect_keywords_for_persona", return_value=["X"]), \
         patch("scraping.run_daily.collect_batch", return_value=fake):
        dm._consume_refresh_if_any()

    toast = st.session_state.get("_dm_refresh_toast")
    assert toast[0] == "ok"
    assert "RSS 2건" in toast[1]
