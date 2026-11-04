"""Extract layout-aware lines from a PDF.

PyMuPDF's `dict` extraction mode reports font, size, weight and position for
every span; it groups lines into blocks. Plain `text` mode discards all of it.
This adapter reads the richer form and hands it to the pure assembly and
classification.

The canonical text comes from the same pass. Measured over six books and
1,312 pages, the lines of `dict` mode joined with a newline each are byte for
byte what `text` mode returns, so reading the text off the lines loses
nothing and gains the one thing `text` mode cannot give: the mathematics a
maths font set in two dimensions, rebuilt by `pdf_mathematics_layout` from
the spans' boxes. The classifier's furniture verdicts feed back into that
text: the parser strips running heads and margin folios from each page,
guided by `furniture_texts_by_page`, so the canonical text and the drafts
anchored onto it describe the same book.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from voice_reader.domain.document.anchoring import BlockDraft
from voice_reader.domain.document.pdf_lines import (
    PdfLine,
    drafts_from_lines,
    furniture_texts_by_page,
)
from voice_reader.domain.document.pdf_mathematics import PdfSpan
from voice_reader.domain.document.pdf_mathematics_layout import (
    PdfRawLine,
    assemble_lines,
)

log = logging.getLogger(__name__)

# PyMuPDF block types: 0 is text, 1 is an image.
_TEXT_BLOCK_TYPE = 0

# PyMuPDF span flag bits. Bit 4 marks bold.
_BOLD_FLAG = 1 << 4

_EMPTY_BBOX = (0.0, 0.0, 0.0, 0.0)
_EMPTY_ORIGIN = (0.0, 0.0)
_BBOX_LEFT = 0
_BBOX_TOP = 1
_BBOX_RIGHT = 2
_BBOX_BOTTOM = 3
_ORIGIN_Y = 1


@dataclass(frozen=True, slots=True)
class PdfExtraction:
    """Every non-empty line plus each page's text as the lines spell it."""

    lines: tuple[PdfLine, ...]
    page_texts: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PdfLayout:
    """What one layout pass tells the parser.

    `page_texts` is None when the pass failed, in which case the parser reads
    each page's text the plain way and the book carries no structure.
    """

    furniture: dict[int, tuple[str, ...]]
    drafts: tuple[BlockDraft, ...]
    page_texts: tuple[str, ...] | None


def _span_from(span: dict) -> PdfSpan:
    bbox = span.get("bbox") or _EMPTY_BBOX
    origin = span.get("origin") or _EMPTY_ORIGIN
    return PdfSpan(
        text=str(span.get("text", "")),
        font=str(span.get("font", "")),
        size=float(span.get("size", 0.0)),
        bold=bool(int(span.get("flags", 0)) & _BOLD_FLAG),
        left=float(bbox[_BBOX_LEFT]),
        top=float(bbox[_BBOX_TOP]),
        right=float(bbox[_BBOX_RIGHT]),
        bottom=float(bbox[_BBOX_BOTTOM]),
        baseline=float(origin[_ORIGIN_Y]),
    )


def _raw_line(line: dict, *, block_index: int) -> PdfRawLine:
    bbox = line.get("bbox") or _EMPTY_BBOX
    return PdfRawLine(
        spans=tuple(_span_from(span) for span in line.get("spans") or ()),
        block_index=block_index,
        top=float(bbox[_BBOX_TOP]),
        bottom=float(bbox[_BBOX_BOTTOM]),
    )


def _raw_lines(page) -> tuple[PdfRawLine, ...]:
    content = page.get_text("dict") or {}
    lines: list[PdfRawLine] = []
    for block_index, block in enumerate(content.get("blocks") or ()):
        if int(block.get("type", _TEXT_BLOCK_TYPE)) != _TEXT_BLOCK_TYPE:
            continue
        for line in block.get("lines") or ():
            lines.append(_raw_line(line, block_index=block_index))
    return tuple(lines)


def extract_document(document) -> PdfExtraction:
    """Walk every page: one entry per non-empty text line plus each page's text."""

    lines: list[PdfLine] = []
    page_texts: list[str] = []

    for page_index, page in enumerate(document):
        page_height = float(page.rect.height)
        assembled = assemble_lines(_raw_lines(page))
        page_texts.append("".join(line.text + "\n" for line in assembled))
        for line in assembled:
            if not line.text.strip():
                continue
            lines.append(
                PdfLine(
                    text=line.text,
                    size=line.size,
                    bold=line.bold,
                    top=line.top,
                    bottom=line.bottom,
                    page_index=page_index,
                    page_height=page_height,
                    block_index=line.block_index,
                )
            )

    return PdfExtraction(lines=tuple(lines), page_texts=tuple(page_texts))


def lines_from_document(document) -> tuple[PdfLine, ...]:
    """Walk every page, returning one entry per non-empty text line."""

    return extract_document(document).lines


def layout_from_document(document) -> PdfLayout:
    """Furniture texts to strip per page, structural drafts and page texts.

    Failure here is not fatal. Returning nothing means the text keeps every
    line it was extracted with and the book falls back to the unstructured
    model, exactly as it always has, which is preferable to failing the load
    over a layout quirk.
    """

    try:
        extraction = extract_document(document)
        return PdfLayout(
            furniture=furniture_texts_by_page(extraction.lines),
            drafts=drafts_from_lines(extraction.lines),
            page_texts=extraction.page_texts,
        )
    except Exception:
        log.warning("PDF layout extraction failed; continuing without structure")
        return PdfLayout(furniture={}, drafts=(), page_texts=None)
