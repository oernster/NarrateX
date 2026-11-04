"""Rebuild the mathematics a PDF set in two dimensions as lines of text.

`pdf_mathematics` reads one row and `pdf_mathematics_rows` decides what the
rows are. This module decides what is rebuilt together. On the page a
display equation is not a row: a summation sign carries its limits above
and below, a fraction stacks its numerator over its denominator; PyMuPDF
reports each of those stacks as lines of its own, often in blocks of their
own, so "N = sum from k = 0 to m" comes back as five lines in three blocks.

A block with no maths font in it is passed through untouched, line for line,
so a book with no mathematics reads exactly as it did. Only blocks that set
mathematics are rebuilt; blocks that overlap one of them vertically are
rebuilt together with it, because that is how a split equation arrives.

Pure: every rule here is testable without opening a PDF.
"""

from __future__ import annotations

from dataclasses import dataclass

from voice_reader.domain.document.pdf_mathematics import (
    SCRIPT_SIZE_RATIO,
    PdfSpan,
    fold_text,
    is_script,
    piece_from_span,
    render_level,
    tidy_spacing,
)
from voice_reader.domain.document.pdf_mathematics_rows import (
    attach_fractions,
    place_scripts,
    rows_of,
)

# How far, in fractions of the larger size, a script-sized fragment block may
# stand clear of a block and still be read with it.
_FRAGMENT_SLACK_RATIO = 0.5


@dataclass(frozen=True, slots=True)
class PdfRawLine:
    """One line as the extractor reported it: its spans and its box."""

    spans: tuple[PdfSpan, ...]
    block_index: int
    top: float
    bottom: float


@dataclass(frozen=True, slots=True)
class AssembledLine:
    """One line of text with the evidence the classifier reads off it."""

    text: str
    size: float
    bold: bool
    top: float
    bottom: float
    block_index: int


@dataclass(frozen=True, slots=True)
class _Extent:
    top: float
    bottom: float
    size: float

    def meets(self, other: _Extent) -> bool:
        """Whether two blocks share any height, a fragment allowed a little slack.

        A limit set over an integral sign is a block of its own a few points
        clear of the sign's block. It is script-sized where the sign is not;
        only a block that small is reached for across a gap: two prose
        paragraphs are never joined by their paragraph space.
        """

        slack = 0.0
        if min(self.size, other.size) < SCRIPT_SIZE_RATIO * max(self.size, other.size):
            slack = _FRAGMENT_SLACK_RATIO * max(self.size, other.size)
        return self.top - slack < other.bottom and self.bottom + slack > other.top


def _plain_line(line: PdfRawLine) -> AssembledLine:
    return AssembledLine(
        text="".join(fold_text(span.text, maths=False) for span in line.spans),
        size=max((span.size for span in line.spans), default=0.0),
        bold=any(span.bold for span in line.spans),
        top=line.top,
        bottom=line.bottom,
        block_index=line.block_index,
    )


def _blocks_in_order(
    lines: tuple[PdfRawLine, ...],
) -> list[tuple[int, list[PdfRawLine]]]:
    blocks: dict[int, list[PdfRawLine]] = {}
    for line in lines:
        blocks.setdefault(line.block_index, []).append(line)
    return list(blocks.items())


def _sets_mathematics(block: list[PdfRawLine]) -> bool:
    return any(span.in_maths_font for line in block for span in line.spans)


def _extent(block: list[PdfRawLine]) -> _Extent:
    return _Extent(
        top=min(line.top for line in block),
        bottom=max(line.bottom for line in block),
        size=max(span.size for line in block for span in line.spans),
    )


def _groups(
    blocks: list[tuple[int, list[PdfRawLine]]],
) -> dict[int, list[int]]:
    """Maths blocks that overlap vertically, keyed by the first of each group."""

    groups: list[list[int]] = []
    extents: dict[int, _Extent] = {}
    for index, block in blocks:
        if not _sets_mathematics(block):
            continue
        extent = extents[index] = _extent(block)
        joined = None
        for group in groups:
            if any(extent.meets(extents[member]) for member in group):
                joined = group
                break
        if joined is None:
            groups.append([index])
        else:
            joined.append(index)
    return {group[0]: group for group in groups}


def _row_size(pieces: list[PdfSpan]) -> float:
    """The size carrying the most ink: characters weighted by their size.

    Counting characters alone lets a display equation's limits outvote its
    body, since "k = 0" and "m" are five characters against "N =" and a
    sign. Weighted by size the body wins, while a stray larger fragment of a
    character or two cannot outvote a line of body text.
    """

    ink: dict[float, float] = {}
    for piece in pieces:
        key = round(piece.size, 1)
        ink[key] = ink.get(key, 0.0) + key * len(piece.text.strip())
    return max(ink.items(), key=lambda item: (item[1], item[0]))[0]


def _assemble_group(
    lines: list[PdfRawLine], *, block_index: int
) -> list[AssembledLine]:
    pieces = [
        piece
        for line in lines
        for span in line.spans
        if (piece := piece_from_span(span)) is not None
    ]
    content = [p for p in pieces if not p.text.isspace()]
    if not content:
        return []
    size = _row_size(content)
    rows = rows_of([p for p in content if not is_script(p, size=size)], size=size)
    place_scripts(
        rows,
        [p for p in content if is_script(p, size=size)],
        [p for p in pieces if p.text.isspace()],
        size=size,
    )
    attach_fractions(rows, size=size)

    assembled: list[AssembledLine] = []
    for row in rows:
        held = row.all_pieces
        if not held:
            continue
        baseline = row.baseline if row.pieces else held[0].baseline
        text = tidy_spacing(render_level(held, baseline=baseline, size=size))
        if not text:
            continue
        assembled.append(
            AssembledLine(
                text=text,
                size=size,
                bold=any(p.bold for p in row.pieces),
                top=min(p.top for p in held),
                bottom=max(p.bottom for p in held),
                block_index=block_index,
            )
        )
    return assembled


def assemble_lines(lines: tuple[PdfRawLine, ...]) -> tuple[AssembledLine, ...]:
    """The page's lines of text, its mathematics rebuilt, the rest untouched.

    Blocks keep their order. A group of maths blocks is emitted where its
    first block stood and its other blocks are consumed into it.
    """

    blocks = _blocks_in_order(lines)
    groups = _groups(blocks)
    consumed = {member for group in groups.values() for member in group[1:]}
    by_index = dict(blocks)

    assembled: list[AssembledLine] = []
    for index, block in blocks:
        if index in consumed:
            continue
        if index in groups:
            members = [line for member in groups[index] for line in by_index[member]]
            assembled.extend(_assemble_group(members, block_index=index))
        else:
            assembled.extend(_plain_line(line) for line in block)
    return tuple(assembled)
