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
    assert cfg.paths.ideas_work_dir.exists()
    assert cfg.paths.temp_books_dir.exists()
    assert cfg.paths.bookmarks_dir.exists()
    assert cfg.paths.shelf_index_dir.exists()
    assert cfg.paths.shelf_thumbnails_dir.exists()


def test_the_shelf_index_survives_a_cache_clear(tmp_path: Path) -> None:
    """DATA-BS-002: the index holds reader statements, so it is not cache.

    The entrypoint empties `cache_dir` on every launch. An index inside it
    would take the reader's corrected genres with it; the thumbnails would be
    redrawn every launch for nothing. Neither sits under that directory.
    """

    cfg = Config.from_project_root(tmp_path)

    assert cfg.paths.cache_dir not in cfg.paths.shelf_index_dir.parents
    assert cfg.paths.cache_dir not in cfg.paths.shelf_thumbnails_dir.parents
    assert cfg.paths.shelf_index_dir.parent == cfg.paths.bookmarks_dir.parent


def test_configure_logging_does_not_crash() -> None:
    configure_logging(logging.INFO)


def test_configure_logging_supports_optional_file_handler(
    monkeypatch, tmp_path: Path
) -> None:
    """Cover the packaged-build debug log handler path."""

    import sys
    import voice_reader.shared.logging_utils as lu

    monkeypatch.setenv("NARRATEX_LOG_FILE", "1")
    monkeypatch.setattr(sys, "argv", [str(tmp_path / "NarrateX.exe")])
    lu.configure_logging(logging.INFO)

    # Expect a debug log file to be created.
    assert (tmp_path / "NarrateX.debug.log.txt").exists()


def test_configure_logging_falls_back_to_cwd_when_argv_resolve_fails(
    monkeypatch, tmp_path: Path
) -> None:
    """Coverage: exercise argv[0].resolve() exception path."""

    import sys
    import voice_reader.shared.logging_utils as lu

    monkeypatch.setenv("NARRATEX_LOG_FILE", "1")
    monkeypatch.setattr(sys, "argv", [str(tmp_path / "NarrateX.exe")])

    # Force Path.resolve() to raise so we take the base=Path.cwd() fallback.
    def _bad_resolve(self) -> Path:  # noqa: ANN001
        raise RuntimeError("boom")

    monkeypatch.setattr(lu.Path, "resolve", _bad_resolve, raising=True)
    monkeypatch.setattr(lu.Path, "cwd", lambda: tmp_path, raising=True)

    lu.configure_logging(logging.INFO)
    assert (tmp_path / "NarrateX.debug.log.txt").exists()


def test_configure_logging_ignores_filehandler_failure(
    monkeypatch, tmp_path: Path
) -> None:
    """Coverage: exercise FileHandler exception swallow (never fail startup)."""

    import sys
    import voice_reader.shared.logging_utils as lu

    monkeypatch.setenv("NARRATEX_LOG_FILE", "1")
    monkeypatch.setattr(sys, "argv", [str(tmp_path / "NarrateX.exe")])

    def _bad_file_handler(*args, **kwargs):  # noqa: ANN001
        raise OSError("nope")

    monkeypatch.setattr(lu.logging, "FileHandler", _bad_file_handler, raising=True)

    # Should not crash even though file handler creation fails.
    lu.configure_logging(logging.INFO)
