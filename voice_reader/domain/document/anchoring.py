"""Anchor discovered blocks onto the canonical source text.

Structure and text arrive from different places. A format reader discovers
structure while walking its own representation (EPUB tags, PDF font sizes),
whereas `normalized_text` is produced separately and must not change: it is the
coordinate system for chunking, bookmarks, the resume position, the ideas index,
the audio cache key and the derived `book_id`. Changing it would silently orphan
every bookmark a reader already has.

So the reader emits drafts (what a block *is* and what it *says*) and this
module finds where each one sits in the canonical text.

Matching ignores whitespace entirely, and folds the few characters the text
extraction rewrites on its way to `normalized_text`. The two representations
carry the same characters in the same order and differ only in how they are
wrapped, spaced and hyphenated, so comparing on that footing makes the match
exact rather than approximate. Scanning is forward-only, which keeps repeated
text (a running header appearing on every page) anchored to the right
occurrence.

Folding is not cosmetic. A draft is a whole paragraph of joined lines, so one
unfolded character anywhere in it loses the entire paragraph, not just the word
it sits in. Every fold here is the mirror of a rewrite `_dehyphenate` applies to
the source, and each is one character wide or dropped outright, so the offsets
recorded alongside stay true to the original text.

A draft that cannot be found is dropped rather than guessed at. That is
deliberate: dropped drafts lower `Document.covered_ratio`, and a low enough
ratio is what tips a caller over to the unstructured fallback. Uncertainty
degrades the confidence signal instead of corrupting the offsets.
"""

from __future__ import annotations

from dataclasses import dataclass

from voice_reader.domain.document.block_kind import BlockKind
from voice_reader.domain.document.model import Block

# Characters the extraction removes outright, so a draft still carrying one
# would never be found. The soft hyphen is invisible typesetting advice.
_DROPPED_IN_SOURCE = frozenset({"­"})

# Characters the extraction rewrites, mapped to what it rewrites them to. The
# non-breaking hyphen becomes a plain one, which is what a hyphenated term in a
# typeset PDF hinges on.
_FOLDED_IN_SOURCE = {"‑": "-"}


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


def _match_char(char: str) -> str | None:
    """Fold one character for matching, or None when it carries no meaning."""

    if char.isspace() or char in _DROPPED_IN_SOURCE:
        return None
    return _FOLDED_IN_SOURCE.get(char, char)


def _condense(text: str) -> tuple[str, tuple[int, ...]]:
    """Return `text` folded for matching, plus each kept character's offset."""

    condensed: list[str] = []
    offsets: list[int] = []
    for index, char in enumerate(text):
        folded = _match_char(char)
        if folded is None:
            continue
        condensed.append(folded)
        offsets.append(index)
    return "".join(condensed), tuple(offsets)


def _match_key(text: str) -> str:
    """Fold a draft's text the same way, so the two can be compared."""

    return "".join(
        folded for folded in (_match_char(char) for char in text) if folded is not None
    )


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
        needle = _match_key(draft.text)
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
