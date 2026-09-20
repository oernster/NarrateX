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


def test_converter_runs_ebook_convert(tmp_path: Path) -> None:
    """The runner is injected rather than patched onto subprocess.

    The converter holds the runner it was built with, so patching the module
    would change nothing; handing one in is also what lets a test read the
    environment Calibre would be given.
    """

    src = tmp_path / "a.mobi"
    src.write_text("x", encoding="utf-8")
    seen: dict = {}

    def fake_run(cmd, **kwargs):
        seen.update(kwargs)
        out = Path(cmd[-1])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"epub")

        class R:
            returncode = 0
            stderr = ""
            stdout = ""

        return R()

    c = CalibreConverter(temp_books_dir=tmp_path, runner=fake_run)
    out = c.convert_to_epub_if_needed(src)
    assert out.suffix.lower() == ".epub"
    assert out.exists()
    assert "env" in seen, "Calibre is always given an environment of its own"


def test_markdown_needs_no_conversion(tmp_path) -> None:
    from pathlib import Path as _Path

    from voice_reader.infrastructure.books.converter import CalibreConverter

    src = tmp_path / "book.md"
    src.write_text("# Title\n", encoding="utf-8")
    converter = CalibreConverter(temp_books_dir=_Path(tmp_path))

    assert converter.convert_to_epub_if_needed(src) == src
