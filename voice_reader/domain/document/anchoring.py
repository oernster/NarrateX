"""Anchor discovered blocks onto the canonical source text.

Structure and text arrive from different places. A format reader discovers
structure while walking its own representation (EPUB tags, PDF font sizes),
whereas `normalized_text` is produced separately and must not change: it is the
coordinate system for chunking, bookmarks, the resume position, the ideas index,
the audio cache key and the derived `book_id`. Changing it would silently orphan
every bookmark a reader already has.

So the reader emits drafts (what a block *is* and what it *says*) and this
module finds where each one sits in the canonical text.

Matching ignores whitespace entirely. The two representations carry the same
characters in the same order and differ only in how they are wrapped and
spaced, so comparing with whitespace removed makes the match exact rather than
approximate. Scanning is forward-only, which keeps repeated text (a running
header appearing on every page) anchored to the right occurrence.

A draft that cannot be found is dropped rather than guessed at. That is
deliberate: dropped drafts lower `Document.covered_ratio`, and a low enough
ratio is what tips a caller over to the unstructured fallback. Uncertainty
degrades the confidence signal instead of corrupting the offsets.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from voice_reader.domain.document.block_kind import BlockKind
from voice_reader.domain.document.model import Block

_NON_SPACE = re.compile(r"\S")


@dataclass(frozen=True, slots=True)
class BlockDraft:
    """A block a format reader has identified, before it has been located."""

    kind: BlockKind
    text: str
    level: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.kind, BlockKind):
            raise TypeError("BlockDraft kind must be a BlockKind")
        if self.level < 0:
            raise ValueError("BlockDraft level must not be negative")


def _condense(text: str) -> tuple[str, tuple[int, ...]]:
    """Return `text` without whitespace, plus each kept character's offset."""

    matches = list(_NON_SPACE.finditer(text))
    condensed = "".join(match.group() for match in matches)
    offsets = tuple(match.start() for match in matches)
    return condensed, offsets


def _strip_whitespace(text: str) -> str:
    return "".join(text.split())


def anchor_blocks(
    *,
    source: str,
    drafts: tuple[BlockDraft, ...],
) -> tuple[Block, ...]:
    """Locate each draft in `source`, in order, returning anchored blocks.

    Drafts that cannot be located are omitted. The returned blocks are ordered
    and non-overlapping by construction.
    """

    body = str(source or "")
    if not body or not drafts:
        return ()

    condensed, offsets = _condense(body)
    if not condensed:
        return ()

    blocks: list[Block] = []
    cursor = 0

    for draft in drafts:
        needle = _strip_whitespace(draft.text)
        if not needle:
            continue

        found = condensed.find(needle, cursor)
        if found < 0:
            continue

        last = found + len(needle) - 1
        blocks.append(
            Block(
                kind=draft.kind,
                source_start=offsets[found],
                source_end=offsets[last] + 1,
                text=draft.text,
                level=draft.level,
            )
        )
        cursor = found + len(needle)

    return tuple(blocks)
