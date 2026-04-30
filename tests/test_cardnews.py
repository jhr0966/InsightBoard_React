from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import cardnews


def test_render_png_returns_bytes() -> None:
    article = {
        "title": "자동용접 공정 최적화",
        "press": "테스트언론",
        "date": "2026-04-30",
        "summary": "요약",
        "keywords": "자동화,용접",
    }
    png = cardnews.render_png(article)
    assert isinstance(png, (bytes, bytearray))
    assert len(png) > 100


def test_render_deck_count_matches_input() -> None:
    articles = [
        {"title": "A", "press": "P1", "date": "2026-01-01"},
        {"title": "B", "press": "P2", "date": "2026-01-02"},
    ]
    deck = cardnews.render_deck(articles)
    assert len(deck) == 2
