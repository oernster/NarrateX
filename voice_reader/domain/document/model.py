"""Domain entities: the structured document model.

Central invariant: **the model never rewrites the book text.**

Every block records a span `(source_start, source_end)` into the book's
`normalized_text`. That string stays exactly as it is today, so every character
offset already in use keeps its meaning: chunk spans, the chapter index,
structural bookmarks, the ideas index, click-to-seek, persisted bookmarks, the
resume position, the audio cache key and the derived `book_id`.

Rendering and narration are *views* over those spans, never replacements for
them. A block additionally carries its own `text`, because normalisation can
rejoin hard-wrapped lines or drop hyphenation, so what is shown is not always
byte-identical to the source slice. The span remains the anchor.
"""

from __future__ import annotations

from dataclasses import dataclass

from voice_reader.domain.document.block_kind import BlockKind


def _validate_span(*, start: int, end: int, label: str) -> None:
    """Validate a half-open character span into the source text."""

    if start < 0:
        raise ValueError(f"{label} source_start must not be negative")
    if end < start:
        raise ValueError(f"{label} source_end must not precede source_start")


@dataclass(frozen=True, slots=True)
class Block:
    """One block of content, anchored to a span of the source text."""

    kind: BlockKind
    source_start: int
    source_end: int
    text: str
    # Heading depth, or list nesting depth. Zero for flat blocks.
    level: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.kind, BlockKind):
            raise TypeError("Block kind must be a BlockKind")
        _validate_span(
            start=self.source_start,
            end=self.source_end,
            label="Block",
        )
        if self.level < 0:
            raise ValueError("Block level must not be negative")

    @property
    def source_length(self) -> int:
        return self.source_end - self.source_start

    @property
    def is_displayed(self) -> bool:
        return self.kind.is_displayed

    @property
    def is_spoken(self) -> bool:
        return self.kind.is_spoken


@dataclass(frozen=True, slots=True)
class TocEntry:
    """One table-of-contents entry, resolved to a body offset where possible."""

    title: str
    level: int = 0
    target_source_offset: int | None = None

    def __post_init__(self) -> None:
        if self.level < 0:
            raise ValueError("TocEntry level must not be negative")
        if self.target_source_offset is not None and self.target_source_offset < 0:
            raise ValueError("TocEntry target_source_offset must not be negative")

    @property
    def is_resolved(self) -> bool:
        """Whether this entry points at a known offset in the body."""

        return self.target_source_offset is not None


@dataclass(frozen=True, slots=True)
class Section:
    """An ordered run of blocks under one heading.

    Named `Section` rather than `Chapter` for two reasons: the name `Chapter` is
    already taken by the navigation entity in `domain.entities`, and not every
    structural division of a book is a chapter (front matter, prologue and
    appendices are sections too). Navigation chapters are derived from sections.
    """

    title: str
    source_start: int
    source_end: int
    blocks: tuple[Block, ...] = ()

    def __post_init__(self) -> None:
        _validate_span(
            start=self.source_start,
            end=self.source_end,
            label="Section",
        )
        if not isinstance(self.blocks, tuple):
            raise TypeError("Section blocks must be a tuple")

    @property
    def displayed_blocks(self) -> tuple[Block, ...]:
        return tuple(b for b in self.blocks if b.is_displayed)

    @property
    def spoken_blocks(self) -> tuple[Block, ...]:
        return tuple(b for b in self.blocks if b.is_spoken)


@dataclass(frozen=True, slots=True)
class Document:
    """A whole book as ordered sections, plus its navigable contents."""

    source_length: int
    sections: tuple[Section, ...] = ()
    toc: tuple[TocEntry, ...] = ()

    def __post_init__(self) -> None:
        if self.source_length < 0:
            raise ValueError("Document source_length must not be negative")
        if not isinstance(self.sections, tuple):
            raise TypeError("Document sections must be a tuple")
        if not isinstance(self.toc, tuple):
            raise TypeError("Document toc must be a tuple")

    @classmethod
    def unstructured(cls, *, text: str) -> "Document":
        """Fallback model for text we cannot confidently structure.

        This is the guardrail path. Rather than a second code path that bypasses
        the model, extraction that fails its confidence check degrades to a
        single section holding one paragraph spanning everything. The renderer
        and the narrator then behave exactly as they do today, with no special
        case at either consumer.
        """

        body = str(text or "")
        length = len(body)
        if not body:
            return cls(source_length=0)

        block = Block(
            kind=BlockKind.PARAGRAPH,
            source_start=0,
            source_end=length,
            text=body,
        )
        section = Section(
            title="",
            source_start=0,
            source_end=length,
            blocks=(block,),
        )
        return cls(source_length=length, sections=(section,))

    @property
    def blocks(self) -> tuple[Block, ...]:
        """Every block, in reading order."""

        return tuple(b for section in self.sections for b in section.blocks)

    @property
    def displayed_blocks(self) -> tuple[Block, ...]:
        return tuple(b for b in self.blocks if b.is_displayed)

    @property
    def spoken_blocks(self) -> tuple[Block, ...]:
        return tuple(b for b in self.blocks if b.is_spoken)

    @property
    def body_start_offset(self) -> int | None:
        """Source offset of the first spoken block, or None when there is none.

        This is the model's answer to "where does the body begin", replacing the
        several detectors that answer it independently today.
        """

        for block in self.blocks:
            if block.is_spoken:
                return block.source_start
        return None

    @property
    def structured_ratio(self) -> float:
        """Proportion of the source text covered by displayed blocks.

        The extraction confidence signal. A caller compares this against its own
        configured threshold to decide whether to keep the model or fall back to
        `unstructured()`. The threshold is a policy decision and deliberately
        does not live here.
        """

        if self.source_length <= 0:
            return 0.0
        covered = sum(b.source_length for b in self.displayed_blocks)
        return covered / self.source_length
