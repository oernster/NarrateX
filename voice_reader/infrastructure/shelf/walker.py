"""Walking a shelf root for the book files NarrateX can open.

FR-BS-002, FR-BS-006 and FR-BS-007. Three outcomes are told apart, because a
reader acts differently on each: a root that is not there; a folder inside it
that cannot be read; a folder that simply holds no books.

Nothing here decides what a book is; `domain.shelf.formats` owns that, so the
scanner and the file dialog cannot disagree with this walk.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

from voice_reader.domain.shelf import formats
from voice_reader.domain.shelf.discovery import WalkResult
from voice_reader.domain.shelf.identity import ShelfKey

WalkFn = Callable[..., Iterator[tuple[str, list[str], list[str]]]]


@dataclass(frozen=True, slots=True)
class FileSystemWalker:
    """Finds book files beneath a root, reporting what it could not read.

    The walk itself is injected. It is `os.walk` in the application; a test
    supplies its own, so the two paths a real filesystem reaches only by
    accident (a folder that refuses to open, a file that disappears between
    the listing and the stat) can both be driven on purpose.
    """

    walk_fn: WalkFn = field(default=os.walk)

    def walk(self, root: Path) -> WalkResult:
        if not root.is_dir():
            return WalkResult(root_reachable=False)

        keys: list[ShelfKey] = []
        unreadable: list[Path] = []

        def note(error: OSError) -> None:
            """A folder that refused to open is recorded, never raised."""

            filename = getattr(error, "filename", None)
            unreadable.append(Path(filename) if filename else root)

        for dirpath, _dirnames, filenames in self.walk_fn(root, onerror=note):
            for name in filenames:
                path = Path(dirpath) / name
                if not formats.is_book(path.suffix):
                    continue
                key = _key_for(path)
                if key is not None:
                    keys.append(key)

        return WalkResult(keys=tuple(keys), unreadable=tuple(unreadable))


def _key_for(path: Path) -> ShelfKey | None:
    """The cheap identity of one file; None when it vanished mid-walk.

    A file can be deleted between the listing and the stat, which is a fact
    about a live filesystem rather than a fault in the scan.
    """

    try:
        stat = path.stat()
    except OSError:
        return None
    return ShelfKey(path=path, size_bytes=stat.st_size, modified_ns=stat.st_mtime_ns)
