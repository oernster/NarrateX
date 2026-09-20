"""Calibre is handed an environment that is not NarrateX's.

`ebook-convert` is a Qt program. A packaged NarrateX tells Qt where ITS plugins
live through the environment, and a child that inherits that reads our plugins
with Calibre's own Qt. Measured on 2026-09-20 against the installed build's
plugin directory: the same file and the same command convert in full with a clean
environment and die at Calibre's cover step with `QT_PLUGIN_PATH` set to ours, so
these tests plant that variable and read what the child would have been given.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from voice_reader.infrastructure.books.converter import (
    CalibreConverter,
    child_environment,
)
from voice_reader.shared.errors import BookConversionError


class _Runner:
    """Stands in for subprocess.run, recording what it was handed."""

    def __init__(self, *, returncode: int = 0, writes: bool = True) -> None:
        self.returncode = returncode
        self.writes = writes
        self.env: dict[str, str] | None = None
        self.cmd: list[str] | None = None

    def __call__(self, cmd, **kwargs):
        self.cmd = list(cmd)
        self.env = kwargs.get("env")
        if self.writes and self.returncode == 0:
            Path(cmd[-1]).write_bytes(b"an epub")
        return subprocess.CompletedProcess(
            args=cmd, returncode=self.returncode, stdout="", stderr="it went wrong"
        )


def _kindle(tmp_path: Path) -> Path:
    book = tmp_path / "Dune - Frank Herbert.azw3"
    book.write_bytes(b"not really a kindle file")
    return book


def test_our_qt_variables_do_not_reach_the_child(tmp_path, monkeypatch) -> None:
    """The planted variable is the one the frozen build sets."""

    monkeypatch.setenv("QT_PLUGIN_PATH", r"C:\NarrateX\_internal\PySide6\plugins")
    monkeypatch.setenv("QT_QPA_PLATFORM_PLUGIN_PATH", r"C:\NarrateX\platforms")
    monkeypatch.setenv("QML2_IMPORT_PATH", r"C:\NarrateX\qml")
    runner = _Runner()
    converter = CalibreConverter(temp_books_dir=tmp_path / "temp", runner=runner)

    converter.convert_to_epub_if_needed(_kindle(tmp_path))

    assert runner.env is not None
    assert "QT_PLUGIN_PATH" not in runner.env
    assert "QT_QPA_PLATFORM_PLUGIN_PATH" not in runner.env
    assert "QML2_IMPORT_PATH" not in runner.env


def test_everything_else_reaches_the_child(tmp_path, monkeypatch) -> None:
    """Calibre still needs a PATH, a home and whatever else it reads."""

    monkeypatch.setenv("PATH", r"C:\Program Files\Calibre2")
    monkeypatch.setenv("CALIBRE_CONFIG_DIRECTORY", r"C:\Users\Someone\calibre")
    runner = _Runner()
    converter = CalibreConverter(temp_books_dir=tmp_path / "temp", runner=runner)

    converter.convert_to_epub_if_needed(_kindle(tmp_path))

    assert runner.env["PATH"] == r"C:\Program Files\Calibre2"
    assert runner.env["CALIBRE_CONFIG_DIRECTORY"] == r"C:\Users\Someone\calibre"


def test_the_filter_is_read_off_a_mapping_rather_than_the_process() -> None:
    given = {
        "PATH": "somewhere",
        "QT_PLUGIN_PATH": "ours",
        "QTDIR": "ours too",
        "PYSIDE_DESIGNER_PLUGINS": "ours as well",
        "QUIET": "not a Qt variable",
    }

    kept = child_environment(given)

    assert kept == {"PATH": "somewhere", "QUIET": "not a Qt variable"}


def test_a_native_format_is_not_converted_at_all(tmp_path) -> None:
    runner = _Runner()
    converter = CalibreConverter(temp_books_dir=tmp_path / "temp", runner=runner)
    book = tmp_path / "Dune - Frank Herbert.epub"
    book.write_bytes(b"already an epub")

    assert converter.convert_to_epub_if_needed(book) == book
    assert runner.cmd is None


def test_a_format_nobody_opens_is_refused(tmp_path) -> None:
    converter = CalibreConverter(temp_books_dir=tmp_path / "temp", runner=_Runner())

    with pytest.raises(BookConversionError):
        converter.convert_to_epub_if_needed(tmp_path / "notes.rtf")


def test_a_failed_conversion_says_what_calibre_said(tmp_path) -> None:
    converter = CalibreConverter(
        temp_books_dir=tmp_path / "temp", runner=_Runner(returncode=1)
    )

    with pytest.raises(BookConversionError, match="it went wrong"):
        converter.convert_to_epub_if_needed(_kindle(tmp_path))


def test_a_conversion_that_writes_nothing_is_a_failure(tmp_path) -> None:
    """Calibre's Qt failure ends this way: a zero exit with no book."""

    converter = CalibreConverter(
        temp_books_dir=tmp_path / "temp", runner=_Runner(writes=False)
    )

    with pytest.raises(BookConversionError, match="did not produce"):
        converter.convert_to_epub_if_needed(_kindle(tmp_path))


def test_calibre_missing_is_said_plainly(tmp_path) -> None:
    def _absent(cmd, **kwargs):
        del cmd, kwargs
        raise FileNotFoundError("ebook-convert")

    converter = CalibreConverter(temp_books_dir=tmp_path / "temp", runner=_absent)

    with pytest.raises(BookConversionError, match="not found on PATH"):
        converter.convert_to_epub_if_needed(_kindle(tmp_path))
