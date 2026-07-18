"""Plan what the reading pane shows, and map between the two coordinate spaces.

The pane displays only body blocks, so its text is not the book's text: the
contents, folios and running heads are gone, and each block reads as its
cleaned form rather than its raw slice. That gives two coordinate spaces.

- *source* offsets index `normalized_text`. Everything persisted or shared uses
  these: chunk spans, bookmarks, the resume position, the ideas index.
- *render* offsets index what the pane actually shows.

This module builds the rendered text and keeps the correspondence between the
two, so highlighting can go source to render and a click can go render to
source. Nothing outside the pane ever needs to know the render space exists.

Blocks are joined with a single newline because that is exactly how a
`QTextDocument` counts positions: one per block separator. Render offsets are
therefore already valid `QTextCursor` positions, with no second translation.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass

from voice_reader.domain.document.block_kind import BlockKind
from voice_reader.domain.document.model import Document

_BLOCK_SEPARATOR = "\n"


@dataclass(frozen=True, slots=True)
class RenderedBlock:
    """One displayed block, in both coordinate spaces."""

    kind: BlockKind
    level: int
    text: str
    render_start: int
    render_end: int
    source_start: int
    source_end: int


@dataclass(frozen=True, slots=True)
class RenderPlan:
    """The pane's text, plus the mapping back to the book's own offsets."""

    text: str
    blocks: tuple[RenderedBlock, ...]
    # Sorted lookup keys, precomputed so translation stays cheap enough to run
    # on every playback tick.
    render_starts: tuple[int, ...]
    source_starts: tuple[int, ...]

    def _index_for(self, starts: tuple[int, ...], offset: int) -> int | None:
        if not self.blocks:
            return None
        return max(0, bisect_right(starts, offset) - 1)

    def to_render(self, source_offset: int) -> int:
        """Translate a book offset into a pane position.

        An offset inside skipped content (a folio, the contents) has no
        position of its own, so it resolves to the start of the next visible
        block. Highlighting then moves to the next thing the reader can see
        rather than vanishing.
        """

        index = self._index_for(self.source_starts, source_offset)
        if index is None:
            return 0

        block = self.blocks[index]
        if source_offset < block.source_start:
            return block.render_start
        if source_offset >= block.source_end:
            following = index + 1
            if following < len(self.blocks):
                return self.blocks[following].render_start
            return block.render_end
        return min(
            block.render_start + (source_offset - block.source_start), block.render_end
        )

    def to_source(self, render_offset: int) -> int:
        """Translate a pane position into a book offset."""

        index = self._index_for(self.render_starts, render_offset)
        if index is None:
            return 0

        block = self.blocks[index]
        if render_offset < block.render_start:
            return block.source_start
        if render_offset >= block.render_end:
            following = index + 1
            if following < len(self.blocks):
                return self.blocks[following].source_start
            return block.source_end
        return min(
            block.source_start + (render_offset - block.render_start), block.source_end
        )


def build_render_plan(document: Document, *, body_start: int = 0) -> RenderPlan:
    """Lay out a document's displayed blocks into pane text.

    `body_start` drops everything before it. That is how the front matter stops
    being shown: a contents page's own titles are classified as headings, since
    that is exactly what they look like, so excluding them by kind is not
    possible. Excluding them by *position* is, because the contents has a known
    extent. The contents does not disappear, it becomes navigation instead of
    body text.
    """

    blocks: list[RenderedBlock] = []
    parts: list[str] = []
    cursor = 0

    for block in document.displayed_blocks:
        if block.source_start < body_start:
            continue

        text = block.text
        if not text:
            continue

        parts.append(text)
        blocks.append(
            RenderedBlock(
                kind=block.kind,
                level=block.level,
                text=text,
                render_start=cursor,
                render_end=cursor + len(text),
                source_start=block.source_start,
                source_end=block.source_end,
            )
        )
        cursor += len(text) + len(_BLOCK_SEPARATOR)

    return RenderPlan(
        text=_BLOCK_SEPARATOR.join(parts),
        blocks=tuple(blocks),
        render_starts=tuple(b.render_start for b in blocks),
        source_starts=tuple(b.source_start for b in blocks),
    )
