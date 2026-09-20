"""The ports the shelf needs from the world outside it.

Four seams, stated as Protocols so the shelf's services can be exercised with
hand-written stand-ins and the real implementations can live in infrastructure
without the domain or the application ever importing them.

They are gathered in one module rather than scattered across four because they
are one boundary: everything the shelf needs from the disk. Splitting them
would put four two-line files beside each other and hide that fact.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from voice_reader.domain.shelf.discovery import FileMetadata, WalkResult
from voice_reader.domain.shelf.identity import ShelfEntry, ShelfKey


class BookFileWalker(Protocol):
    """Finds the book files under a root."""

    def walk(self, root: Path) -> WalkResult:
        """Every book file below `root`, with whatever could not be read.

        Never raises for a folder it cannot open: that is an answer, not a
        fault to throw (FR-BS-006).
        """


class BookMetadataReader(Protocol):
    """Reads what one file says about itself, without converting it."""

    def read(self, key: ShelfKey) -> FileMetadata:
        """The best metadata available for this file, cheaply.

        Spawns no process (FR-BS-031). A format it cannot read answers an empty
        `FileMetadata` rather than raising.
        """


class BookCoverSource(Protocol):
    """Reads one file's cover artwork, through the precedence in FR-BS-030."""

    def cover_bytes(self, key: ShelfKey) -> bytes | None:
        """The encoded cover image this file yields; None when it yields none.

        Spawns no process, ever (FR-BS-031): a Calibre conversion costs 2.3
        seconds a book, which is not a cost a tile may impose.
        """


class ThumbnailMaker(Protocol):
    """Turns a cover image into the small copy the grid draws (FR-BS-034)."""

    def downscale(self, image: bytes, *, width: int, height: int) -> bytes | None:
        """The image reduced to fit `width` by `height`; None when unreadable.

        Unreadable is an answer: a file claiming to be an image and failing to
        decode leaves the work with a placeholder rather than no shelf.
        """


class ThumbnailStore(Protocol):
    """Holds the downscaled cover art the grid draws (FR-BS-034)."""

    def has(self, token: str) -> bool: ...

    def put(self, token: str, image: bytes) -> None: ...

    def get(self, token: str) -> bytes | None: ...

    def forget(self, token: str) -> None: ...

    def clear(self) -> None:
        """Empty the cache. Everything in it is derived (FR-BS-035)."""


class ShelfIndexRepository(Protocol):
    """Holds the scanned index and everything the reader has stated.

    The index is derived and may be rebuilt at any time (DATA-BS-001). Reader
    statements are NOT derived and survive a rescan and a rebuild alike
    (DATA-BS-002), which is why they are loaded and saved separately.
    """

    def load_roots(self) -> tuple[Path, ...]: ...

    def save_roots(self, roots: tuple[Path, ...]) -> None: ...

    def load_entries(self) -> tuple[ShelfEntry, ...]: ...

    def save_entries(self, entries: tuple[ShelfEntry, ...]) -> None: ...

    def load_stated_genres(self) -> dict[str, tuple[str, ...]]: ...

    def save_stated_genres(self, stated: dict[str, tuple[str, ...]]) -> None: ...
