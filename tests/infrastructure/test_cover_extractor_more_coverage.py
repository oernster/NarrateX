from __future__ import annotations

import io
import zipfile
from pathlib import Path
from types import SimpleNamespace

from voice_reader.infrastructure.books.cover_extractor import CoverExtractor


def test_cover_extractor_txt_returns_none(tmp_path: Path) -> None:
    p = tmp_path / "a.txt"
    p.write_text("x", encoding="utf-8")
    assert CoverExtractor().extract_cover_bytes(p) is None


def test_cover_extractor_epub_finds_image_from_cover_doc(tmp_path: Path) -> None:
    epub = tmp_path / "b.epub"
    img_bytes = b"\x89PNG\r\n\x1a\n..."
    with zipfile.ZipFile(epub, "w") as z:
        z.writestr(
            "OEBPS/cover.xhtml",
            '<html><body><img src="../Images/cover.jpg"/></body></html>',
        )
        z.writestr("Images/cover.jpg", b"JPGDATA")
    assert CoverExtractor().extract_cover_bytes(epub) == b"JPGDATA"


def test_cover_extractor_epub_suffix_match_when_nested_folder(tmp_path: Path) -> None:
    epub = tmp_path / "c.epub"
    with zipfile.ZipFile(epub, "w") as z:
        z.writestr(
            "nested/cover.html",
            '<html><body><img src="cover.png"/></body></html>',
        )
        z.writestr("top/nested/cover.png", b"PNGDATA")
    assert CoverExtractor().extract_cover_bytes(epub) == b"PNGDATA"


def test_cover_extractor_epub_fallback_first_image_asset(tmp_path: Path) -> None:
    epub = tmp_path / "d.epub"
    with zipfile.ZipFile(epub, "w") as z:
        z.writestr("images/001.png", b"A")
        z.writestr("images/cover.png", b"COVER")
        z.writestr("text/ch1.xhtml", "<html>no cover here</html>")
    assert CoverExtractor().extract_cover_bytes(epub) == b"COVER"


def test_cover_extractor_epub_errors_return_none(monkeypatch, tmp_path: Path) -> None:
    epub = tmp_path / "e.epub"
    epub.write_bytes(b"not-a-zip")
    assert CoverExtractor().extract_cover_bytes(epub) is None


def test_cover_extractor_pdf_uses_fitz_stub(monkeypatch, tmp_path: Path) -> None:
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"%PDF")

    class _FakePix:
        def tobytes(self, fmt: str) -> bytes:
            assert fmt == "png"
            return b"PNG"

    class _FakePage:
        def get_pixmap(self, matrix, alpha: bool):
            assert alpha is False
            return _FakePix()

    class _FakeDoc:
        page_count = 1

        def load_page(self, idx: int):
            assert idx == 0
            return _FakePage()

    fake_fitz = SimpleNamespace(open=lambda path: _FakeDoc(), Matrix=lambda a, b: (a, b))
    monkeypatch.setitem(__import__("sys").modules, "fitz", fake_fitz)
    assert CoverExtractor().extract_cover_bytes(pdf) == b"PNG"


def test_cover_extractor_pdf_failure_returns_none(monkeypatch, tmp_path: Path) -> None:
    pdf = tmp_path / "b.pdf"
    pdf.write_bytes(b"%PDF")

    fake_fitz = SimpleNamespace(open=lambda path: (_ for _ in ()).throw(RuntimeError("x")))
    monkeypatch.setitem(__import__("sys").modules, "fitz", fake_fitz)
    assert CoverExtractor().extract_cover_bytes(pdf) is None

