"""Hand-written stand-ins for the shelf's four ports.

No mock library: each of these is a small real object that records what it was
asked and answers what the test set up. A fake that can be read is a fake whose
behaviour a reader can check against the port it stands for.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from voice_reader.domain.entities.bookmark import Bookmark, ResumePosition
from voice_reader.domain.shelf.discovery import FileMetadata, WalkResult
from voice_reader.domain.shelf.identity import ShelfEntry, ShelfKey


def key(path: str, *, size: int = 1, modified: int = 1) -> ShelfKey:
    return ShelfKey(path=Path(path), size_bytes=size, modified_ns=modified)


class FakeIndex:
    """The shelf index, in memory, counting every save."""

    def __init__(
        self,
        *,
        roots: tuple[Path, ...] = (),
        entries: tuple[ShelfEntry, ...] = (),
        stated: dict[str, tuple[str, ...]] | None = None,
    ) -> None:
        self._roots = roots
        self._entries = entries
        self._stated = dict(stated or {})
        self.saves = 0

    def load_roots(self) -> tuple[Path, ...]:
        return self._roots

    def save_roots(self, roots: tuple[Path, ...]) -> None:
        self._roots = roots

    def load_entries(self) -> tuple[ShelfEntry, ...]:
        return self._entries

    def save_entries(self, entries: tuple[ShelfEntry, ...]) -> None:
        self._entries = entries
        self.saves += 1

    def load_stated_genres(self) -> dict[str, tuple[str, ...]]:
        return dict(self._stated)

    def save_stated_genres(self, stated: dict[str, tuple[str, ...]]) -> None:
        self._stated = dict(stated)


class FakeWalker:
    """Answers a prepared result per root, recording which roots were asked."""

    def __init__(self, results: dict[Path, WalkResult] | None = None) -> None:
        self._results = results or {}
        self.walked: list[Path] = []

    def walk(self, root: Path) -> WalkResult:
        self.walked.append(root)
        return self._results.get(root, WalkResult())


class FakeMetadataReader:
    """Answers prepared metadata; raises for paths told to fail."""

    def __init__(
        self,
        stated: dict[Path, FileMetadata] | None = None,
        *,
        unreadable: set[Path] | None = None,
    ) -> None:
        self._stated = stated or {}
        self._unreadable = unreadable or set()
        self.read_paths: list[Path] = []

    def read(self, key: ShelfKey) -> FileMetadata:
        self.read_paths.append(key.path)
        if key.path in self._unreadable:
            raise OSError("permission denied")
        return self._stated.get(key.path, FileMetadata())


class FakeBookmarks:
    """Only the two parts of the bookmark port the shelf uses."""

    def __init__(self, positions: dict[str, ResumePosition] | None = None) -> None:
        self._positions = dict(positions or {})
        self.deleted: list[str] = []

    def list_bookmarks(self, *, book_id: str) -> list[Bookmark]:
        del book_id
        return []

    def add_bookmark(
        self, *, book_id: str, char_offset: int, chunk_index: int
    ) -> Bookmark:  # pragma: no cover - the shelf never adds one
        raise NotImplementedError

    def delete_bookmark(
        self, *, book_id: str, bookmark_id: int
    ) -> None:  # pragma: no cover - the shelf never deletes one
        raise NotImplementedError

    def load_resume_position(self, *, book_id: str) -> ResumePosition | None:
        return self._positions.get(book_id)

    def save_resume_position(
        self, *, book_id: str, char_offset: int, chunk_index: int
    ) -> None:  # pragma: no cover - the shelf never writes one
        raise NotImplementedError

    def delete_book(self, *, book_id: str) -> None:
        self.deleted.append(book_id)
        self._positions.pop(book_id, None)


def resume_at(char_offset: int, *, when: datetime | None = None) -> ResumePosition:
    return ResumePosition(
        char_offset=char_offset,
        chunk_index=0,
        updated_at=when or datetime(2026, 9, 20, tzinfo=timezone.utc),
    )
