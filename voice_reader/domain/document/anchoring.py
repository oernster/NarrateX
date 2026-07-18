"""Anchor discovered blocks onto the canonical source text.

Structure and text arrive from different places. A format reader discovers
structure while walking its own representation (EPUB tags, PDF font sizes),
whereas `normalized_text` is produced separately and must not change: it is the
coordinate system for chunking, bookmarks, the resume position, the ideas index,
the audio cache key and the derived `book_id`. Changing it would silently orphan
every bookmark a reader already has.

So the reader emits drafts (what a block *is* and what it *says*) and this
module finds where each one sits in the canonical text.

Matching is `text_index`'s job: it ignores whitespace and folds the characters
the extraction rewrites, while keeping each character's true offset. Scanning
is forward-only, which keeps repeated text (a running header appearing on every
page) anchored to the right occurrence.

That folding is not cosmetic here. A draft is a whole paragraph of joined
lines, so one unfolded character anywhere in it loses the entire paragraph, not
just the word it sits in.

A draft that cannot be found is dropped rather than guessed at. That is
deliberate: dropped drafts lower `Document.covered_ratio`, and a low enough
ratio is what tips a caller over to the unstructured fallback. Uncertainty
degrades the confidence signal instead of corrupting the offsets.
"""

from __future__ import annotations

from dataclasses import dataclass

from voice_reader.domain.document.block_kind import BlockKind
from voice_reader.domain.document.model import Block
from voice_reader.domain.document.text_index import condense, locate, match_key


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

    condensed, offsets = condense(body)
    if not condensed:
        return ()

    blocks: list[Block] = []
    cursor = 0

    for draft in drafts:
        placed = locate(
            condensed=condensed,
            offsets=offsets,
            needle=match_key(draft.text),
            cursor=cursor,
        )
        if placed is None:
            continue

        start, end, cursor = placed
        blocks.append(
            Block(
                kind=draft.kind,
                source_start=start,
                source_end=end,
                text=draft.text,
                level=draft.level,
            )
        )

    return tuple(blocks)
