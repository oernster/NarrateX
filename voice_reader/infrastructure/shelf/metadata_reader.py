"""What one book file says about itself, through the precedence in FR-BS-020.

The order is the sidecar, then the file's own metadata, then silence. The
filename is not consulted here: that is the domain's fallback, kept there so
this reader never has to know how a filename is spelled.

**Nothing here spawns a process** (FR-BS-031). A Kindle file is read through
its own header; an EPUB or a PDF is read only for the cover, only when
something asks for one, which the scan does not. The expensive paths stay
behind FR-BS-038 where the tile that needs them pays for them.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from voice_reader.domain.shelf import formats
from voice_reader.domain.shelf.discovery import FileMetadata
from voice_reader.domain.shelf.identity import ShelfKey
from voice_reader.infrastructure.books.cover.sidecar import (
    resolve_calibre_sidecar_cover_path,
)
from voice_reader.infrastructure.shelf import kindle_header, opf


@dataclass(frozen=True, slots=True)
class ShelfMetadataReader:
    """Reads a file's metadata cheaply, for the scan."""

    def read(self, key: ShelfKey) -> FileMetadata:
        path = key.path
        stated = _from_sidecar(path)
        embedded = _from_file(path)
        return FileMetadata(
            title=stated.title or embedded.title,
            author=stated.author or embedded.author,
            subjects=stated.subjects or embedded.subjects,
            has_cover=stated.has_cover or embedded.has_cover,
        )


def _from_sidecar(path: Path) -> FileMetadata:
    """The Calibre sidecar beside this book, when there is one."""

    has_cover = resolve_calibre_sidecar_cover_path(path) is not None
    sidecar = opf.sidecar_path(path)
    if sidecar is None:
        return FileMetadata(has_cover=has_cover)
    stated = opf.read(sidecar)
    return FileMetadata(
        title=stated.title,
        author=stated.author,
        subjects=stated.subjects,
        has_cover=has_cover,
    )


def _from_file(path: Path) -> FileMetadata:
    """What the file itself states, for the formats that state anything."""

    if not formats.reads_palm_container(path.suffix):
        return FileMetadata()
    header = kindle_header.read(path)
    return FileMetadata(
        title=header.title,
        author=header.author,
        subjects=header.subjects,
        has_cover=header.has_cover,
    )
