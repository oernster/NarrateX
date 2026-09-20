"""One file's cover artwork, in the order FR-BS-030 asks for.

A sibling cover image, then the picture the file itself carries, then nothing.
Each source is cheap enough to pay for while a tile is being made ready; the one
source that is not is deliberately absent.

**No conversion, ever (FR-BS-031).** The existing `cover_extractor` falls back to
`ebook-convert` for a Kindle file, measured at 2.3 seconds a book, which is about
54 minutes over the reference library. A Kindle cover is read straight out of the
EXTH header instead (FR-BS-032), measured at 1.3 ms to 7 ms.

The per-format helpers are the ones the reader already uses, so a cover shown on
a tile and a cover shown beside the open book come from the same code.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from voice_reader.domain.shelf import formats
from voice_reader.domain.shelf.identity import ShelfKey
from voice_reader.infrastructure.books.cover._io_utils import safe_read_image_bytes
from voice_reader.infrastructure.books.cover.epub import extract_epub_cover
from voice_reader.infrastructure.books.cover.pdf import extract_pdf_cover
from voice_reader.infrastructure.books.cover.sidecar import (
    resolve_calibre_sidecar_cover_path,
)
from voice_reader.infrastructure.shelf import kindle_header

# A sidecar image past this size is not a cover for a tile. The reader's own
# extractor reads a deterministic sidecar with no limit, because a full-size
# scan beside the open book is worth having; a thumbnail is not.
_MAX_SIDECAR_BYTES = 12 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class ShelfCoverReader:
    """Reads the picture for one shelf entry, spawning nothing."""

    def cover_bytes(self, key: ShelfKey) -> bytes | None:
        path = key.path
        sidecar = _from_sidecar(path)
        if sidecar:
            return sidecar
        return _from_file(path)


def _from_sidecar(path: Path) -> bytes | None:
    """The Calibre cover image sitting beside the book."""

    candidate = resolve_calibre_sidecar_cover_path(path)
    if candidate is None:
        return None
    return safe_read_image_bytes(candidate, max_bytes=_MAX_SIDECAR_BYTES)


def _from_file(path: Path) -> bytes | None:
    """What the file itself carries, for the formats that carry anything.

    A plain-text format carries no picture by definition, so it is not opened at
    all rather than opened and found wanting.
    """

    suffix = path.suffix.lower()
    if formats.reads_palm_container(suffix):
        return kindle_header.read(path).cover
    if suffix == _EPUB:
        return _guarded(extract_epub_cover, path)
    if suffix == _PDF:
        return _guarded(extract_pdf_cover, path)
    return None


_EPUB = ".epub"
_PDF = ".pdf"


def _guarded(extract, path: Path) -> bytes | None:
    """Run an extractor, treating any refusal as no picture.

    Both helpers reach third-party readers over files the reader nominated, so
    the ways they can fail are not enumerable. A tile with no picture is a fair
    outcome; a shelf that stops drawing is not.
    """

    try:
        return extract(path)
    except Exception:  # noqa: BLE001
        return None
