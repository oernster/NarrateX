"""Group a flat run of blocks into sections, and derive a table of contents.

Format independent. Markdown, EPUB, PDF and plain text all produce an ordered
run of blocks; how those blocks divide into sections and what the contents list
looks like is the same question in every case, so it is answered once here.
"""

from __future__ import annotations

from voice_reader.domain.document.block_kind import BlockKind
from voice_reader.domain.document.model import Block, Section, TocEntry


def _title_of(blocks: tuple[Block, ...]) -> str:
    for block in blocks:
        if block.kind is BlockKind.HEADING:
            return block.text
    return ""


def _heading_level_of(blocks: tuple[Block, ...]) -> int | None:
    for block in blocks:
        if block.kind is BlockKind.HEADING:
            return block.level
    return None


def _make_section(blocks: tuple[Block, ...]) -> Section:
    return Section(
        title=_title_of(blocks),
        source_start=blocks[0].source_start,
        source_end=blocks[-1].source_end,
        blocks=blocks,
    )


def group_into_sections(*, blocks: tuple[Block, ...]) -> tuple[Section, ...]:
    """Split `blocks` into sections, starting a new one at each heading.

    Blocks appearing before the first heading become a leading untitled section
    rather than being discarded, so no content is ever dropped by sectioning.
    """

    if not blocks:
        return ()

    sections: list[Section] = []
    current: list[Block] = []

    for block in blocks:
        if block.kind is BlockKind.HEADING and current:
            sections.append(_make_section(tuple(current)))
            current = []
        current.append(block)

    if current:
        sections.append(_make_section(tuple(current)))

    return tuple(sections)


def build_toc(*, sections: tuple[Section, ...]) -> tuple[TocEntry, ...]:
    """Derive contents entries from the headed sections.

    Only sections that actually carry a heading become entries. Every entry is
    resolved by construction, because it points at the section it came from.
    """

    entries: list[TocEntry] = []
    for section in sections:
        level = _heading_level_of(section.blocks)
        if level is None:
            continue
        entries.append(
            TocEntry(
                title=section.title,
                level=level,
                target_source_offset=section.source_start,
            )
        )
    return tuple(entries)
