"""daily_scrape CLI 의 custom RSS 통합 + workflow yml 정합성."""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture
def isolated_sources(tmp_path, monkeypatch):
    cfg_dir = tmp_path / "sources"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    from store import sources as src_store
    monkeypatch.setattr(src_store, "_config_path",
                        lambda: cfg_dir / "config.json")
    yield src_store


# ── _load_extra_feeds ──────────────────────────────────────

def test_load_extra_feeds_empty_when_no_custom(isolated_sources):
    from scripts.daily_scrape import _load_extra_feeds
    assert _load_extra_feeds() == []


def test_load_extra_feeds_returns_registered_tuples(isolated_sources):
    from scripts.daily_scrape import _load_extra_feeds
    isolated_sources.add_custom("A", "https://a.com/rss")
    isolated_sources.add_custom("B", "https://b.com/rss")
    feeds = _load_extra_feeds()
    assert sorted(feeds) == [
        ("A", "https://a.com/rss"),
        ("B", "https://b.com/rss"),
    ]


def test_load_extra_feeds_swallows_exception_and_warns(capsys):
    from scripts import daily_scrape
    with patch("store.sources.custom_sources", side_effect=RuntimeError("boom")):
        feeds = daily_scrape._load_extra_feeds()
    assert feeds == []
    err = capsys.readouterr().err
    assert "custom_sources 로드 실패" in err
    assert "boom" in err


# ── main() — extra_feeds 인자 흐름 ─────────────────────────

def test_main_passes_extra_feeds_to_collect_batch(isolated_sources, capsys):
    from scripts import daily_scrape
    from scraping.run_daily import CollectionReport

    isolated_sources.add_custom("MyRSS", "https://my.rss")
    fake = CollectionReport(saved=[], errors=[])

    with patch("scripts.daily_scrape.collect_batch", return_value=fake) as mock_cb:
        rc = daily_scrape.main(["--keywords", "X"])

    assert rc == 0
    mock_cb.assert_called_once()
    _, kwargs = mock_cb.call_args
    assert "extra_feeds" in kwargs
    assert kwargs["extra_feeds"] == [("MyRSS", "https://my.rss")]
    out = capsys.readouterr().out
    assert "커스텀 RSS 1건" in out


def test_main_skip_custom_rss_flag_passes_none(isolated_sources, capsys):
    from scripts import daily_scrape
    from scraping.run_daily import CollectionReport

    isolated_sources.add_custom("MyRSS", "https://my.rss")
    fake = CollectionReport(saved=[], errors=[])

    with patch("scripts.daily_scrape.collect_batch", return_value=fake) as mock_cb:
        daily_scrape.main(["--keywords", "X", "--skip-custom-rss"])

    _, kwargs = mock_cb.call_args
    assert kwargs.get("extra_feeds") is None
    out = capsys.readouterr().out
    assert "커스텀 RSS 0건" in out


def test_main_reports_errors(isolated_sources, capsys):
    from scripts import daily_scrape
    from scraping.run_daily import CollectionReport

    fake = CollectionReport(
        saved=[],
        errors=[{"source": "BadFeed", "keyword": "", "error": "rate limited"}],
    )
    with patch("scripts.daily_scrape.collect_batch", return_value=fake):
        daily_scrape.main(["--keywords", "X", "--skip-custom-rss"])

    out = capsys.readouterr().out
    assert "일부 오류 1건" in out
    assert "BadFeed" in out
    assert "rate limited" in out


def test_main_warns_when_zero_articles(isolated_sources, capsys):
    from scripts import daily_scrape
    from scraping.run_daily import CollectionReport
    fake = CollectionReport(saved=[], errors=[])
    with patch("scripts.daily_scrape.collect_batch", return_value=fake):
        rc = daily_scrape.main(["--keywords", "X", "--skip-custom-rss"])
    assert rc == 0
    cap = capsys.readouterr()
    assert "0건" in cap.err or "0건" in cap.out


# ── workflow yml 정합성 ────────────────────────────────────

def test_workflow_yaml_is_valid_and_uses_skip_flag():
    """scrape-daily.yml 가 skip_custom_rss 입력을 정의하고 스크립트에 전달한다."""
    from pathlib import Path
    yml_path = Path(__file__).parent.parent / ".github" / "workflows" / "scrape-daily.yml"
    text = yml_path.read_text(encoding="utf-8")
    # YAML 파싱 — yaml 의 boolean alias 로 `on:` 키는 True 로 파싱될 수 있음
    try:
        import yaml
        data = yaml.safe_load(text)
        on_key = data.get("on") if "on" in data else data.get(True)
        assert on_key is not None
        assert "skip_custom_rss" in on_key["workflow_dispatch"]["inputs"]
    except ImportError:
        assert "skip_custom_rss" in text
    # CLI flag 전달 코드 존재
    assert "--skip-custom-rss" in text


def test_workflow_cron_schedule_is_set():
    from pathlib import Path
    yml_path = Path(__file__).parent.parent / ".github" / "workflows" / "scrape-daily.yml"
    text = yml_path.read_text(encoding="utf-8")
    # cron 표현식 존재
    assert "cron:" in text
    # 명시적인 시간대 주석 (KST 09:00)
    assert "KST" in text


def test_main_fail_on_empty_returns_1_when_zero_articles(isolated_sources):
    from scripts import daily_scrape
    from scraping.run_daily import CollectionReport
    fake = CollectionReport(saved=[], errors=[])  # total_articles == 0
    with patch("scripts.daily_scrape.collect_batch", return_value=fake):
        assert daily_scrape.main(["--fail-on-empty", "--keywords", "X", "--skip-custom-rss"]) == 1
        assert daily_scrape.main(["--keywords", "X", "--skip-custom-rss"]) == 0   # 플래그 없으면 0


def test_main_fail_on_empty_returns_0_when_articles_saved(isolated_sources):
    from scripts import daily_scrape
    from scraping.run_daily import CollectionReport
    fake = CollectionReport(saved=[{"source": "naver", "keywords": ["X"], "count": 3, "path": "p"}], errors=[])
    with patch("scripts.daily_scrape.collect_batch", return_value=fake):
        assert daily_scrape.main(["--fail-on-empty", "--keywords", "X", "--skip-custom-rss"]) == 0
