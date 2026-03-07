from __future__ import annotations

from pathlib import Path

import pytest

from voice_reader.infrastructure.books.converter import CalibreConverter
from voice_reader.shared.errors import BookConversionError


def test_converter_passes_through_supported_formats(tmp_path: Path) -> None:
    c = CalibreConverter(temp_books_dir=tmp_path)
    for name in ["a.epub", "b.pdf", "c.txt"]:
        p = tmp_path / name
        p.write_text("x", encoding="utf-8")
        assert c.convert_to_epub_if_needed(p) == p


def test_converter_rejects_unknown_extension(tmp_path: Path) -> None:
    c = CalibreConverter(temp_books_dir=tmp_path)
    p = tmp_path / "a.docx"
    p.write_text("x", encoding="utf-8")
    with pytest.raises(BookConversionError):
        c.convert_to_epub_if_needed(p)


def test_converter_runs_ebook_convert(monkeypatch, tmp_path: Path) -> None:
    src = tmp_path / "a.mobi"
    src.write_text("x", encoding="utf-8")
    c = CalibreConverter(temp_books_dir=tmp_path)

    def fake_run(cmd, capture_output, text, check):
        # create output file
        out = Path(cmd[-1])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"epub")

        class R:
            returncode = 0
            stderr = ""
            stdout = ""

        return R()

    monkeypatch.setattr(__import__("subprocess"), "run", fake_run)
    out = c.convert_to_epub_if_needed(src)
    assert out.suffix.lower() == ".epub"
    assert out.exists()
