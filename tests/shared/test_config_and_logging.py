from __future__ import annotations

import logging
from pathlib import Path

from voice_reader.shared.config import Config
from voice_reader.shared.logging_utils import configure_logging


def test_config_creates_directories(tmp_path: Path) -> None:
    cfg = Config.from_project_root(tmp_path)
    cfg.ensure_directories()
    assert cfg.paths.voices_dir.exists()
    assert cfg.paths.cache_dir.exists()
    assert cfg.paths.temp_books_dir.exists()
    assert cfg.paths.bookmarks_dir.exists()


def test_configure_logging_does_not_crash() -> None:
    configure_logging(logging.INFO)
