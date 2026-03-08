from __future__ import annotations

import io
import subprocess
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


def test_cover_extractor_epub_single_quotes_are_supported(tmp_path: Path) -> None:
    epub = tmp_path / "b2.epub"
    with zipfile.ZipFile(epub, "w") as z:
        z.writestr(
            "OEBPS/cover.xhtml",
            "<html><body><img src='../Images/cover.png'/></body></html>",
        )
        z.writestr("Images/cover.png", b"PNGDATA")
    assert CoverExtractor().extract_cover_bytes(epub) == b"PNGDATA"


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


def test_cover_extractor_prefers_calibre_sidecar_cover(tmp_path: Path) -> None:
    # Calibre commonly stores a cover.jpg adjacent to the ebook file.
    book = tmp_path / "Book.azw3"
    book.write_bytes(b"dummy")
    (tmp_path / "cover.jpg").write_bytes(b"JPG")
    assert CoverExtractor().extract_cover_bytes(book) == b"JPG"


def test_cover_extractor_calibrebooks_shape_uses_adjacent_cover_jpg(tmp_path: Path) -> None:
    # Real CalibreBooks shape:
    #   Author/Title (ID)/Title - Author.azw3
    #   Author/Title (ID)/cover.jpg
    book_dir = tmp_path / "Some Author" / "Some Title (123)"
    book_dir.mkdir(parents=True)
    book = book_dir / "Some Title - Some Author.azw3"
    book.write_bytes(b"dummy")
    (book_dir / "cover.jpg").write_bytes(b"REALCOVER")
    assert CoverExtractor().extract_cover_bytes(book) == b"REALCOVER"


def test_cover_extractor_exact_cover_jpg_wins_over_heuristic_named_images(tmp_path: Path) -> None:
    book = tmp_path / "Book.azw3"
    book.write_bytes(b"dummy")
    (tmp_path / "my_cover.png").write_bytes(b"PNG")
    (tmp_path / "cover.jpg").write_bytes(b"JPG")
    assert CoverExtractor().extract_cover_bytes(book) == b"JPG"


def test_cover_extractor_no_cover_jpg_falls_back_to_other_sidecar(tmp_path: Path) -> None:
    book = tmp_path / "Book.azw3"
    book.write_bytes(b"dummy")
    (tmp_path / "my_cover.png").write_bytes(b"PNG")
    assert CoverExtractor().extract_cover_bytes(book) == b"PNG"


def test_cover_extractor_exact_sidecar_prevents_kindle_conversion(monkeypatch, tmp_path: Path) -> None:
    # If an exact sidecar cover exists, we must not invoke ebook-convert.
    book = tmp_path / "Book.azw3"
    book.write_bytes(b"dummy")
    (tmp_path / "cover.jpg").write_bytes(b"JPG")

    called = {"run": 0}

    def fake_run(*a, **k):
        called["run"] += 1
        raise AssertionError("ebook-convert should not be called when cover.jpg exists")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert CoverExtractor().extract_cover_bytes(book) == b"JPG"
    assert called["run"] == 0


def test_cover_extractor_sidecar_heuristic_scan_finds_cover_named_file(tmp_path: Path) -> None:
    book = tmp_path / "Book.azw3"
    book.write_bytes(b"dummy")
    (tmp_path / "my_cover.png").write_bytes(b"PNG")
    assert CoverExtractor().extract_cover_bytes(book) == b"PNG"


def test_cover_extractor_kindle_convert_to_epub_fallback(monkeypatch, tmp_path: Path) -> None:
    # No sidecar. Ensure we fall back to ebook-convert and then parse the produced EPUB.
    book = tmp_path / "Book.azw3"
    book.write_bytes(b"dummy")

    def fake_run(cmd, capture_output: bool, text: bool, check: bool):
        assert cmd[0] == "ebook-convert"
        out_path = Path(cmd[2])
        # Produce a minimal EPUB with a cover doc pointing at an image.
        with zipfile.ZipFile(out_path, "w") as z:
            z.writestr(
                "cover.xhtml",
                '<html><body><img src="images/cover.jpg"/></body></html>',
            )
            z.writestr("images/cover.jpg", b"COVER")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert CoverExtractor().extract_cover_bytes(book) == b"COVER"


def test_cover_extractor_kindle_convert_missing_ebook_convert_returns_none(
    monkeypatch, tmp_path: Path
) -> None:
    book = tmp_path / "Book.azw3"
    book.write_bytes(b"dummy")

    def fake_run(*a, **k):
        raise FileNotFoundError("ebook-convert")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert CoverExtractor().extract_cover_bytes(book) is None

