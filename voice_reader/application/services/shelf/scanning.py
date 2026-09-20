"""Walking the shelf roots and reconciling what was found with what was known.

FR-BS-002 to FR-BS-008. The service owns the order of the steps; every rule it
applies belongs to the domain and every touch of the disk belongs to a port.

**A scan is a reconciliation, not a rebuild.** An unchanged file keeps the
entry it already had, which keeps the book id the reader's earlier opening paid
for and keeps the scan off the file entirely. Only a new file or a changed one
costs a read.

**An unreachable root removes nothing.** A shelf root on a drive that is not
plugged in is not an empty folder, so its entries stay exactly where they were
and the reader is told the root could not be reached (FR-BS-007). Treating the
two alike would empty a shelf every time a drive was left at home.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from voice_reader.domain.interfaces.shelf_ports import (
    BookFileWalker,
    BookMetadataReader,
    ShelfIndexRepository,
)
from voice_reader.domain.shelf import corpus, roots as root_rules
from voice_reader.domain.shelf.discovery import FileMetadata, WalkResult
from voice_reader.domain.shelf.identity import ShelfEntry, ShelfKey, entry_from_filename


@dataclass(frozen=True, slots=True)
class ScanReport:
    """What one scan did, in the words the shelf tells the reader."""

    found: int = 0
    added: int = 0
    removed: int = 0
    rereads: int = 0
    kept: int = 0
    unreadable: tuple[Path, ...] = field(default_factory=tuple)
    unreachable_roots: tuple[Path, ...] = field(default_factory=tuple)

    @property
    def total(self) -> int:
        return self.added + self.rereads + self.kept

    @property
    def found_nothing(self) -> bool:
        """True when the walk succeeded and there was simply nothing to read."""

        return self.found == 0 and not self.unreachable_roots


@dataclass(frozen=True, slots=True)
class ShelfScanner:
    """Turns shelf roots into an index of entries."""

    walker: BookFileWalker
    metadata: BookMetadataReader
    index: ShelfIndexRepository

    def scan(
        self,
        *,
        roots: tuple[Path, ...] | None = None,
        on_entry: Callable[[ShelfEntry], None] | None = None,
    ) -> ScanReport:
        """Walk every root, reconcile, save and report.

        `on_entry` is called as each entry is settled, so the shelf can fill in
        front of the reader rather than waiting for the walk to end
        (FR-BS-036). It is called for kept entries too, because the shelf being
        drawn does not care which of them cost a read.
        """

        watched = self.index.load_roots() if roots is None else roots
        known = {entry.key.path: entry for entry in self.index.load_entries()}

        walk, unreachable = self._walk_all(watched)
        entries, added, rereads, kept = self._reconcile(walk.keys, known, on_entry)
        entries = self._retained(entries, known, unreachable)
        surviving = {entry.key.path for entry in entries}
        removed = sum(1 for path in known if path not in surviving)
        entries = corpus.resolve_author_first(entries)
        self.index.save_entries(entries)

        return ScanReport(
            found=walk.found,
            added=added,
            removed=removed,
            rereads=rereads,
            kept=kept,
            unreadable=walk.unreadable,
            unreachable_roots=unreachable,
        )

    def _walk_all(
        self, watched: tuple[Path, ...]
    ) -> tuple[WalkResult, tuple[Path, ...]]:
        walk = WalkResult()
        unreachable: list[Path] = []
        for root in watched:
            result = self.walker.walk(root)
            if not result.root_reachable:
                unreachable.append(root)
            walk = walk.joined_with(result)
        return walk, tuple(unreachable)

    def _reconcile(
        self,
        keys: tuple[ShelfKey, ...],
        known: dict[Path, ShelfEntry],
        on_entry: Callable[[ShelfEntry], None] | None,
    ) -> tuple[tuple[ShelfEntry, ...], int, int, int]:
        entries: list[ShelfEntry] = []
        seen: set[Path] = set()
        added = rereads = kept = 0
        for key in keys:
            if key.path in seen:
                continue
            seen.add(key.path)
            previous = known.get(key.path)
            if previous is not None and previous.key.unchanged_from(key):
                entry = previous
                kept += 1
            else:
                entry = self._read(key, previous)
                if previous is None:
                    added += 1
                else:
                    rereads += 1
            entries.append(entry)
            if on_entry is not None:
                on_entry(entry)
        return tuple(entries), added, rereads, kept

    def _read(self, key: ShelfKey, previous: ShelfEntry | None) -> ShelfEntry:
        """One file read through the precedence in FR-BS-020.

        A changed file keeps the book id and length it already had: the bytes
        moved while the book did not, so discarding them would lose the
        reader's progress over a touched modification time.
        """

        stated = self._stated(key)
        entry = entry_from_filename(key)
        if stated.states_a_title:
            entry = entry.with_metadata(title=stated.title)
        if stated.states_an_author:
            entry = entry.with_metadata(author=stated.author)
        entry = entry.with_metadata(subjects=stated.subjects)
        entry = ShelfEntry(
            key=entry.key,
            title=entry.title,
            author=entry.author,
            subjects=entry.subjects,
            book_id=previous.book_id if previous else None,
            total_chars=previous.total_chars if previous else None,
            has_cover=stated.has_cover,
        )
        return entry

    def _stated(self, key: ShelfKey) -> FileMetadata:
        """What the file says; nothing at all when it cannot be read.

        A file that refuses to be read is one entry short of its metadata, not
        a scan that stops (FR-BS-006).
        """

        try:
            return self.metadata.read(key)
        except OSError:
            return FileMetadata()

    @staticmethod
    def _retained(
        entries: tuple[ShelfEntry, ...],
        known: dict[Path, ShelfEntry],
        unreachable: tuple[Path, ...],
    ) -> tuple[ShelfEntry, ...]:
        """Entries under an unreachable root are kept as they were."""

        if not unreachable:
            return entries
        present = {entry.key.path for entry in entries}
        stranded = tuple(
            entry
            for path, entry in known.items()
            if path not in present
            and root_rules.covering(unreachable, path) is not None
        )
        return entries + stranded
