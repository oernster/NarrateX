from __future__ import annotations

from pathlib import Path

import pytest

from voice_reader.infrastructure.books.converter import CalibreConverter
from voice_reader.shared.errors import BookConversionError


def test_converter_raises_when_ebook_convert_missing(monkeypatch, tmp_path: Path) -> None:
    src = tmp_path / "a.mobi"
    src.write_text("x", encoding="utf-8")

    def fake_run(*args, **kwargs):
        raise FileNotFoundError("no")

    monkeypatch.setattr(__import__("subprocess"), "run", fake_run)
    c = CalibreConverter(temp_books_dir=tmp_path)
    with pytest.raises(BookConversionError):
        c.convert_to_epub_if_needed(src)


def test_converter_raises_when_ebook_convert_fails(monkeypatch, tmp_path: Path) -> None:
    src = tmp_path / "a.mobi"
    src.write_text("x", encoding="utf-8")

    class _R:
        returncode = 1
        stderr = "bad"
        stdout = ""

    monkeypatch.setattr(__import__("subprocess"), "run", lambda *a, **k: _R())
    c = CalibreConverter(temp_books_dir=tmp_path)
    with pytest.raises(BookConversionError):
        c.convert_to_epub_if_needed(src)


def test_converter_raises_when_output_missing(monkeypatch, tmp_path: Path) -> None:
    src = tmp_path / "a.mobi"
    src.write_text("x", encoding="utf-8")

    class _R:
        returncode = 0
        stderr = ""
        stdout = ""

    monkeypatch.setattr(__import__("subprocess"), "run", lambda *a, **k: _R())
    c = CalibreConverter(temp_books_dir=tmp_path)
    with pytest.raises(BookConversionError):
        c.convert_to_epub_if_needed(src)

