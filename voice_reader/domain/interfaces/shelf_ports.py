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
