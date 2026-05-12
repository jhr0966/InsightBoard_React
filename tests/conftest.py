"""테스트가 data/ 를 더럽히지 않도록 임시 디렉토리로 라우팅."""
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolated_data_dirs(monkeypatch, tmp_path):
    """config 의 데이터 경로를 tmp_path 로 교체. 테스트 간 격리."""
    import config

    root = tmp_path / "data"
    news = root / "news"
    roadmap = root / "roadmap"
    sola = root / "sola"
    for p in (news, roadmap, sola):
        p.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(config, "DATA_ROOT", root, raising=True)
    monkeypatch.setattr(config, "NEWS_DIR", news, raising=True)
    monkeypatch.setattr(config, "ROADMAP_DIR", roadmap, raising=True)
    monkeypatch.setattr(config, "SOLA_DIR", sola, raising=True)
    # store.paths 가 import 시 NEWS_DIR 를 가져갔을 수 있으므로 동기화
    import store.paths as paths_mod

    monkeypatch.setattr(paths_mod, "NEWS_DIR", news, raising=True)
    monkeypatch.setattr(paths_mod, "ROADMAP_DIR", roadmap, raising=True)

    # persona.store, store.bookmarks 도 동일하게 동기화
    try:
        import persona.store as persona_store_mod

        monkeypatch.setattr(persona_store_mod, "DATA_ROOT", root, raising=True)
    except ImportError:
        pass
    try:
        import store.bookmarks as bookmarks_mod

        monkeypatch.setattr(bookmarks_mod, "DATA_ROOT", root, raising=True)
    except ImportError:
        pass

    # store.cache / chat_log 는 import 시 SOLA_DIR 를 from-import 함
    try:
        import store.cache as cache_mod

        monkeypatch.setattr(cache_mod, "SOLA_DIR", sola, raising=True)
    except ImportError:
        pass
    try:
        import store.chat_log as chat_log_mod

        monkeypatch.setattr(chat_log_mod, "SOLA_DIR", sola, raising=True)
    except ImportError:
        pass
    yield Path(root)
