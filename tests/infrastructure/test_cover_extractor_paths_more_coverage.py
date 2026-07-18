"""Cover the extractor's path reporting and its debug dump.

Two things here resist a plain directory. Absolute paths are only resolved for
the log, so the failure of `resolve()` must not change the outcome, and that
needs a path that refuses to resolve. The dump is opt-in through an environment
variable, so it needs turning on deliberately.
"""

from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path

from voice_reader.infrastructure.books.cover_extractor import CoverExtractor

_DUMP_FLAG = "NARRATEX_DUMP_COVER_BYTES"
_DUMP_DIR = "NARRATEX_COVER_DUMP_DIR"


class UnresolvablePath(type(Path())):
    """A path that cannot state its absolute form."""

    def resolve(self, strict: bool = False):
        del strict
        raise OSError("resolution unavailable")


def _epub_with_cover(path: Path) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("cover.xhtml", '<html><img src="images/cover.png"/></html>')
        archive.writestr("images/cover.png", b"EMBEDDED")
    return path


def test_an_unresolvable_path_still_finds_the_calibre_cover(tmp_path: Path) -> None:
    (tmp_path / "cover.jpg").write_bytes(b"JPG")
    book = UnresolvablePath(tmp_path) / "Book.epub"

    assert CoverExtractor().extract_cover_bytes(book) == b"JPG"


def test_an_unresolvable_path_still_finds_the_generic_sidecar(tmp_path: Path) -> None:
    (tmp_path / "my_cover.png").write_bytes(b"PNG")
    book = UnresolvablePath(tmp_path) / "Book.epub"

    assert CoverExtractor().extract_cover_bytes(book) == b"PNG"


def test_an_empty_calibre_cover_falls_through(tmp_path: Path) -> None:
    (tmp_path / "cover.jpg").write_bytes(b"")
    book = tmp_path / "Book.epub"
    book.write_bytes(b"not-a-zip")

    assert CoverExtractor().extract_cover_bytes(book) is None


def test_the_dump_names_the_file_after_the_sidecar_suffix(
    monkeypatch, tmp_path: Path
) -> None:
    dumps = tmp_path / "dumps"
    (tmp_path / "cover.jpg").write_bytes(b"JPG")
    monkeypatch.setenv(_DUMP_FLAG, "1")
    monkeypatch.setenv(_DUMP_DIR, str(dumps))

    assert CoverExtractor().extract_cover_bytes(tmp_path / "Book.epub") == b"JPG"

    (dumped,) = list(dumps.iterdir())
    assert dumped.name.startswith("Book__deterministic-sidecar__")
    assert dumped.suffix == ".jpg"
    assert dumped.read_bytes() == b"JPG"


def test_an_embedded_cover_dumps_to_the_default_directory(
    monkeypatch, tmp_path: Path
) -> None:
    library = tmp_path / "library"
    library.mkdir()
    book = _epub_with_cover(library / "Book.epub")
    dump_root = tmp_path / "temp"
    dump_root.mkdir()

    monkeypatch.setenv(_DUMP_FLAG, "yes")
    monkeypatch.delenv(_DUMP_DIR, raising=False)
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(dump_root))

    assert CoverExtractor().extract_cover_bytes(book) == b"EMBEDDED"

    (dumped,) = list((dump_root / "narratex-cover-dumps").iterdir())
    assert dumped.name.startswith("Book__epub__")
    # Embedded covers arrive without a filename, so the extension is generic.
    assert dumped.suffix == ".bin"


def test_a_failed_dump_does_not_lose_the_cover(monkeypatch, tmp_path: Path) -> None:
    blocked = tmp_path / "blocked"
    blocked.write_bytes(b"this is a file, not a directory")
    (tmp_path / "cover.jpg").write_bytes(b"JPG")

    monkeypatch.setenv(_DUMP_FLAG, "on")
    monkeypatch.setenv(_DUMP_DIR, str(blocked))

    assert CoverExtractor().extract_cover_bytes(tmp_path / "Book.epub") == b"JPG"
