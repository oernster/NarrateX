"""The shelf's cover reader and the reducer beside it, over real files.

The reader is checked on the precedence it promises and on the one thing it must
never do, which is start a process (FR-BS-031). The reducer is checked on real
encoded images, because an image library that cannot be trusted to decode is not
worth a fake that always can.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from PySide6.QtCore import QBuffer
from PySide6.QtGui import QImage

from voice_reader.domain.shelf.identity import ShelfKey
from voice_reader.infrastructure.shelf import cover_reader as reader_module
from voice_reader.infrastructure.shelf.cover_reader import ShelfCoverReader
from voice_reader.infrastructure.shelf.thumbnailer import QtThumbnailMaker


def _png(width: int, height: int, colour: int = 0x224466) -> bytes:
    picture = QImage(width, height, QImage.Format.Format_RGB32)
    picture.fill(colour)
    buffer = QBuffer()
    buffer.open(QBuffer.OpenModeFlag.WriteOnly)
    assert picture.save(buffer, "PNG")
    return bytes(buffer.data())


def _key(path: Path) -> ShelfKey:
    return ShelfKey(path=path, size_bytes=path.stat().st_size, modified_ns=1)


# The reader --------------------------------------------------------------


def test_a_sibling_cover_image_wins(tmp_path: Path) -> None:
    """FR-BS-030: the sidecar image comes before anything inside the file."""

    book = tmp_path / "Dune - Frank Herbert.epub"
    book.write_bytes(b"not a real epub")
    (tmp_path / "cover.jpg").write_bytes(_png(40, 60))

    found = ShelfCoverReader().cover_bytes(_key(book))

    assert found == (tmp_path / "cover.jpg").read_bytes()


def test_a_text_file_is_never_opened_for_a_picture(tmp_path: Path) -> None:
    book = tmp_path / "Notes - Someone.txt"
    book.write_text("words", encoding="utf-8")

    assert ShelfCoverReader().cover_bytes(_key(book)) is None


def test_an_unreadable_epub_is_no_picture_rather_than_a_raise(tmp_path: Path) -> None:
    book = tmp_path / "Broken - Someone.epub"
    book.write_bytes(b"certainly not a zip")

    assert ShelfCoverReader().cover_bytes(_key(book)) is None


def test_a_kindle_file_with_no_header_is_no_picture(tmp_path: Path) -> None:
    book = tmp_path / "Broken - Someone.azw3"
    book.write_bytes(b"not a palm database")

    assert ShelfCoverReader().cover_bytes(_key(book)) is None


def test_an_extractor_that_explodes_leaves_the_tile_blank(
    tmp_path: Path, monkeypatch
) -> None:
    book = tmp_path / "Dune - Frank Herbert.pdf"
    book.write_bytes(b"not a real pdf")

    def _boom(_path):
        raise RuntimeError("the reader gave up")

    monkeypatch.setattr(reader_module, "extract_pdf_cover", _boom)

    assert ShelfCoverReader().cover_bytes(_key(book)) is None


def test_a_pdf_cover_is_read_through_its_own_extractor(
    tmp_path: Path, monkeypatch
) -> None:
    book = tmp_path / "Dune - Frank Herbert.pdf"
    book.write_bytes(b"not a real pdf")
    monkeypatch.setattr(reader_module, "extract_pdf_cover", lambda _p: b"rastered")

    assert ShelfCoverReader().cover_bytes(_key(book)) == b"rastered"


def test_an_epub_cover_is_read_through_its_own_extractor(
    tmp_path: Path, monkeypatch
) -> None:
    book = tmp_path / "Dune - Frank Herbert.epub"
    book.write_bytes(b"not a real epub")
    monkeypatch.setattr(reader_module, "extract_epub_cover", lambda _p: b"embedded")

    assert ShelfCoverReader().cover_bytes(_key(book)) == b"embedded"


def test_no_process_is_started_for_any_format(tmp_path: Path, monkeypatch) -> None:
    """FR-BS-031, proved by making a process fail the test rather than cost 2.3 s."""

    def _forbidden(*args, **kwargs):
        raise AssertionError("the shelf's cover reader started a process")

    for name in ("run", "Popen", "check_output", "call", "check_call"):
        monkeypatch.setattr(subprocess, name, _forbidden)

    books = []
    for suffix in (".epub", ".pdf", ".azw3", ".mobi", ".txt", ".kfx"):
        book = tmp_path / f"Dune - Frank Herbert{suffix}"
        book.write_bytes(b"content that is not really this format")
        books.append(book)

    for book in books:
        ShelfCoverReader().cover_bytes(_key(book))


def test_a_huge_sidecar_is_not_read_for_a_thumbnail(tmp_path: Path) -> None:
    book = tmp_path / "Dune - Frank Herbert.epub"
    book.write_bytes(b"not a real epub")
    oversized = tmp_path / "cover.png"
    oversized.write_bytes(_png(1, 1) + b"\x00" * (13 * 1024 * 1024))

    assert ShelfCoverReader().cover_bytes(_key(book)) is None


# The reducer -------------------------------------------------------------


def test_a_large_cover_is_reduced_to_fit() -> None:
    small = QtThumbnailMaker().downscale(_png(1000, 1500), width=320, height=480)

    assert small is not None
    picture = QImage.fromData(small)
    assert picture.width() <= 320
    assert picture.height() <= 480
    assert picture.width() > 0


def test_proportions_are_kept() -> None:
    small = QtThumbnailMaker().downscale(_png(1000, 500), width=320, height=480)

    picture = QImage.fromData(small)
    assert picture.width() == 320
    assert picture.height() == 160


def test_a_small_cover_is_left_at_its_own_size() -> None:
    """Enlarging trades a sharp little picture for a soft big one."""

    small = QtThumbnailMaker().downscale(_png(80, 120), width=320, height=480)

    picture = QImage.fromData(small)
    assert (picture.width(), picture.height()) == (80, 120)


def test_something_that_is_not_an_image_reduces_to_nothing() -> None:
    assert (
        QtThumbnailMaker().downscale(b"certainly not an image", width=10, height=10)
        is None
    )


def test_a_box_with_no_room_in_it_reduces_to_nothing() -> None:
    """Scaling into nothing leaves an image that cannot be encoded.

    Not a size any caller asks for; exactly the shape of failure a caller
    must survive: an answer of None rather than a half-written thumbnail.
    """

    assert QtThumbnailMaker().downscale(_png(40, 60), width=0, height=0) is None


def test_the_reducer_needs_no_application(tmp_path: Path) -> None:
    """Measured on 2026-09-20; the reason this class sits in infrastructure.

    The suite already has an application, so this runs the reduce in a bare
    interpreter to show it does not need one.
    """

    script = tmp_path / "reduce.py"
    script.write_text(
        "from PySide6.QtCore import QBuffer\n"
        "from PySide6.QtGui import QImage\n"
        "from voice_reader.infrastructure.shelf.thumbnailer import QtThumbnailMaker\n"
        "picture = QImage(600, 900, QImage.Format.Format_RGB32)\n"
        "picture.fill(0)\n"
        "buffer = QBuffer()\n"
        "buffer.open(QBuffer.OpenModeFlag.WriteOnly)\n"
        "picture.save(buffer, 'PNG')\n"
        "small = QtThumbnailMaker().downscale(\n"
        "    bytes(buffer.data()), width=320, height=480\n"
        ")\n"
        "print(len(small))\n",
        encoding="utf-8",
    )
    import os
    import sys

    root = Path(__file__).resolve().parents[3]
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(root)
    done = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        env=environment,
        timeout=120,
    )

    assert done.returncode == 0, done.stderr
    assert int(done.stdout.strip()) > 0


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
