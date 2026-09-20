"""What a walk of the disk answers; what one file's metadata says.

These are the values that cross the boundary between the shelf's rules and the
code that touches the filesystem. They live in the domain so the ports can be
stated without the domain learning what a directory is.

**An absence and a fault are different answers.** A walk that found nothing is
a fact about the folder; a folder that could not be read is a fault. The reader is
told about each in different words (FR-BS-006, FR-BS-058).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from voice_reader.domain.shelf.identity import ShelfKey


@dataclass(frozen=True, slots=True)
class WalkResult:
    """Every book file found under one root, plus what could not be read."""

    keys: tuple[ShelfKey, ...] = ()
    unreadable: tuple[Path, ...] = ()
    root_reachable: bool = True

    @property
    def found(self) -> int:
        return len(self.keys)

    @property
    def faults(self) -> int:
        return len(self.unreadable)

    def joined_with(self, other: "WalkResult") -> "WalkResult":
        """Two walks read as one, for a shelf holding several roots."""

        return WalkResult(
            keys=self.keys + other.keys,
            unreadable=self.unreadable + other.unreadable,
            root_reachable=self.root_reachable and other.root_reachable,
        )


@dataclass(frozen=True, slots=True)
class FileMetadata:
    """What a file says about itself, whether from inside it or from a sidecar.

    Every field is optional because most files state nothing: measured over the
    reference library, 1251 of 2784 state no subject and a plain text file
    states nothing at all. A field left empty means the source was silent, so
    the next source in the precedence is asked (FR-BS-020).
    """

    title: str = ""
    author: str = ""
    subjects: tuple[str, ...] = field(default_factory=tuple)
    has_cover: bool = False

    @property
    def states_a_title(self) -> bool:
        return bool(self.title.strip())

    @property
    def states_an_author(self) -> bool:
        return bool(self.author.strip())
