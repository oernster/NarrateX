"""How the shelf identifies a book; why that is not how narration does.

FR-BS-010, FR-BS-011 and C-5. There are two identities in play and confusing
them is the mistake this module exists to prevent.

**The book id** that bookmarks, the resume position and the audio cache are all
keyed by is a SHA-256 over the book's normalised text. It survives a file being
moved or renamed, which is exactly what those stores need. It also costs a full
parse, so computing it for the 2818 files of the reference library is not
something a scan can do.

**The shelf key** is the cheap one: where the file is, how big it is and when it
last changed. It is enough to notice a new file, a deleted file and a changed
file, which is all a scan needs. It does NOT survive a move, so it is never used
to hold anything the reader stated.

The join between them happens once, lazily, when a book is actually opened: the
narration layer answers a book id and the shelf records it against the entry.
Until then an entry has no book id and its tile shows no progress.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from voice_reader.domain.shelf import formats, text


@dataclass(frozen=True, slots=True)
class ShelfKey:
    """Where a file is, how big it is, when it last changed."""

    path: Path
    size_bytes: int
    modified_ns: int

    def __post_init__(self) -> None:
        if self.size_bytes < 0:
            raise ValueError("ShelfKey size cannot be negative")
        if self.modified_ns < 0:
            raise ValueError("ShelfKey modification time cannot be negative")

    @property
    def token(self) -> str:
        """A stable string for a store's primary key."""

        return f"{self.path.as_posix()}|{self.size_bytes}|{self.modified_ns}"

    def unchanged_from(self, other: "ShelfKey") -> bool:
        """True when both keys describe the same file in the same state."""

        return (
            self.path == other.path
            and self.size_bytes == other.size_bytes
            and self.modified_ns == other.modified_ns
        )


@dataclass(frozen=True, slots=True)
class ShelfEntry:
    """One book file on disk, as the shelf knows it.

    `book_id` is None until the book has been opened once (FR-BS-011).
    `subjects` holds the raw strings the sources stated, kept so a later change
    to the alias table re-files an entry without another scan.
    """

    key: ShelfKey
    title: str
    author: str
    subjects: tuple[str, ...] = ()
    book_id: str | None = None
    has_cover: bool = False

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValueError("ShelfEntry needs a title")

    @property
    def suffix(self) -> str:
        return self.key.path.suffix.lower()

    @property
    def needs_conversion(self) -> bool:
        return formats.needs_conversion(self.suffix)

    @property
    def preference_rank(self) -> int:
        return formats.preference_rank(self.suffix)

    @property
    def work_key(self) -> tuple[str, str]:
        """The identity two files must share to be one work (FR-BS-012).

        The author half compares on the name rather than on its punctuation,
        so "Robert A Heinlein" and "Robert A. Heinlein" are one man and his
        book is one tile.
        """

        return (text.title_key(self.title), text.name_core(self.author))

    def with_book_id(self, book_id: str) -> "ShelfEntry":
        """The same entry, now knowing its narration identity."""

        if not book_id.strip():
            raise ValueError("book id cannot be empty")
        return replace(self, book_id=book_id)

    def with_metadata(
        self,
        *,
        title: str | None = None,
        author: str | None = None,
        subjects: tuple[str, ...] | None = None,
    ) -> "ShelfEntry":
        """The same entry carrying metadata from a better source."""

        return replace(
            self,
            title=self.title if title is None else title,
            author=self.author if author is None else author,
            subjects=self.subjects if subjects is None else subjects,
        )


def entry_from_filename(key: ShelfKey) -> ShelfEntry:
    """The entry a file yields when nothing but its name is known.

    FR-BS-021 and FR-BS-022: the last source in the precedence, used when
    neither a sidecar nor the file's own metadata states a title.
    """

    title, author = text.split_filename(key.path.stem)
    return ShelfEntry(key=key, title=title, author=author)
