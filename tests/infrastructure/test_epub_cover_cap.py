"""An EPUB's cover is read only when its stated size is a cover's (round 3, N-5).

The shelf reads covers in the window's own process. A 2 MB EPUB holding a
2 GiB zero-filled `cover.jpg` once cost over 4 GiB there; the cap the sidecar
already had now applies to the size an archive entry states, checked before a
byte is decompressed.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

from voice_reader.infrastructure.books.cover._io_utils import MAX_COVER_BYTES
from voice_reader.infrastructure.books.cover.epub import extract_epub_cover

SMALL_COVER = b"\x89PNG small but real enough"


def _epub(path: Path, entries: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return path


def test_an_oversized_cover_entry_is_not_read(tmp_path: Path) -> None:
    book = _epub(
        tmp_path / "bomb.epub",
        {"OEBPS/cover.jpg": bytes(MAX_COVER_BYTES + 1)},
    )

    assert extract_epub_cover(book) is None


def test_an_oversized_entry_gives_way_to_the_next_picture(tmp_path: Path) -> None:
    book = _epub(
        tmp_path / "mixed.epub",
        {
            "OEBPS/cover.jpg": bytes(MAX_COVER_BYTES + 1),
            "OEBPS/plate.png": SMALL_COVER,
        },
    )

    assert extract_epub_cover(book) == SMALL_COVER


def test_a_cover_at_the_cap_is_read(tmp_path: Path) -> None:
    data = bytes(MAX_COVER_BYTES)
    book = _epub(tmp_path / "full.epub", {"OEBPS/cover.jpg": data})

    assert extract_epub_cover(book) == data
