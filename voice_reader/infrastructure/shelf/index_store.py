"""Where the shelf keeps what it scanned and what the reader stated.

One SQLite file holding three tables, which are not three of the same thing:

- `roots` and `stated` are the reader's. They survive a rescan, an index
  rebuild and a deleted thumbnail cache (DATA-BS-002).
- `entries` is derived wholly from disk. Deleting it costs a rescan and
  nothing else (DATA-BS-001).

That is why `rebuild_entries` exists and why it empties one table rather than
the file: a rebuild must never be able to take the reader's work with it.

The file lives in the application's own storage, never inside a shelf root
(DATA-BS-003, C-2).
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from voice_reader.domain.shelf.identity import ShelfEntry, ShelfKey

_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS roots (
        position INTEGER PRIMARY KEY,
        path TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS entries (
        path TEXT PRIMARY KEY,
        size_bytes INTEGER NOT NULL,
        modified_ns INTEGER NOT NULL,
        title TEXT NOT NULL,
        author TEXT NOT NULL,
        subjects TEXT NOT NULL,
        book_id TEXT,
        total_chars INTEGER,
        has_cover INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS stated (
        token TEXT PRIMARY KEY,
        genres TEXT NOT NULL
    )
    """,
)

INDEX_FILE_NAME = "shelf.sqlite3"


@dataclass(frozen=True, slots=True)
class SqliteShelfIndex:
    """The shelf index, in one file beside the application's other data."""

    directory: Path

    @property
    def path(self) -> Path:
        return self.directory / INDEX_FILE_NAME

    def _connect(self) -> sqlite3.Connection:
        self.directory.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        for statement in _SCHEMA:
            connection.execute(statement)
        return connection

    # Roots -----------------------------------------------------------------

    def load_roots(self) -> tuple[Path, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT path FROM roots ORDER BY position"
            ).fetchall()
        return tuple(Path(row[0]) for row in rows)

    def save_roots(self, roots: tuple[Path, ...]) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM roots")
            connection.executemany(
                "INSERT INTO roots (position, path) VALUES (?, ?)",
                [(index, str(root)) for index, root in enumerate(roots)],
            )

    # Entries ---------------------------------------------------------------

    def load_entries(self) -> tuple[ShelfEntry, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT path, size_bytes, modified_ns, title, author, subjects, "
                "book_id, total_chars, has_cover FROM entries ORDER BY path"
            ).fetchall()
        return tuple(_entry_from(row) for row in rows)

    def save_entries(self, entries: tuple[ShelfEntry, ...]) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM entries")
            connection.executemany(
                "INSERT INTO entries (path, size_bytes, modified_ns, title, author, "
                "subjects, book_id, total_chars, has_cover) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [_row_from(entry) for entry in entries],
            )

    def rebuild_entries(self) -> None:
        """Empty the derived half, leaving the reader's half untouched."""

        with self._connect() as connection:
            connection.execute("DELETE FROM entries")

    # What the reader stated ------------------------------------------------

    def load_stated_genres(self) -> dict[str, tuple[str, ...]]:
        with self._connect() as connection:
            rows = connection.execute("SELECT token, genres FROM stated").fetchall()
        return {token: tuple(json.loads(genres)) for token, genres in rows}

    def save_stated_genres(self, stated: dict[str, tuple[str, ...]]) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM stated")
            connection.executemany(
                "INSERT INTO stated (token, genres) VALUES (?, ?)",
                [(token, json.dumps(list(genres))) for token, genres in stated.items()],
            )


def _row_from(entry: ShelfEntry) -> tuple:
    return (
        str(entry.key.path),
        entry.key.size_bytes,
        entry.key.modified_ns,
        entry.title,
        entry.author,
        json.dumps(list(entry.subjects)),
        entry.book_id,
        entry.total_chars,
        int(entry.has_cover),
    )


def _entry_from(row: tuple) -> ShelfEntry:
    (
        path,
        size_bytes,
        modified_ns,
        title,
        author,
        subjects,
        book_id,
        total_chars,
        has_cover,
    ) = row
    return ShelfEntry(
        key=ShelfKey(path=Path(path), size_bytes=size_bytes, modified_ns=modified_ns),
        title=title,
        author=author,
        subjects=tuple(json.loads(subjects)),
        book_id=book_id,
        total_chars=total_chars,
        has_cover=bool(has_cover),
    )
