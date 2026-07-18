"""Extract layout-aware lines from a PDF.

PyMuPDF's `dict` extraction mode reports font size, weight and position for
every span, and groups lines into blocks. Plain `text` mode discards all of it.
This adapter reads the richer form and hands it to the pure classifier.

The extracted *text* used elsewhere still comes from `text` mode, unchanged, so
`normalized_text` and every offset anchored to it stay exactly as they were.
"""

from __future__ import annotations

import logging

from voice_reader.domain.document.anchoring import BlockDraft
from voice_reader.domain.document.pdf_lines import PdfLine, drafts_from_lines

log = logging.getLogger(__name__)

# PyMuPDF block types: 0 is text, 1 is an image.
_TEXT_BLOCK_TYPE = 0

# PyMuPDF span flag bits. Bit 4 marks bold.
_BOLD_FLAG = 1 << 4

_EMPTY_BBOX = (0.0, 0.0, 0.0, 0.0)
_BBOX_TOP = 1
_BBOX_BOTTOM = 3


def _line_from(line: dict, *, page_index: int, page_height: float, block_index: int):
    spans = line.get("spans") or ()
    text = "".join(str(span.get("text", "")) for span in spans)
    if not text.strip():
        return None

    sizes = [float(span.get("size", 0.0)) for span in spans]
    bbox = line.get("bbox") or _EMPTY_BBOX

    return PdfLine(
        text=text,
        size=max(sizes, default=0.0),
        bold=any(int(span.get("flags", 0)) & _BOLD_FLAG for span in spans),
        top=float(bbox[_BBOX_TOP]),
        bottom=float(bbox[_BBOX_BOTTOM]),
        page_index=page_index,
        page_height=page_height,
        block_index=block_index,
    )


def lines_from_document(document) -> tuple[PdfLine, ...]:
    """Walk every page, returning one entry per non-empty text line."""

    lines: list[PdfLine] = []

    for page_index, page in enumerate(document):
        page_height = float(page.rect.height)
        content = page.get_text("dict") or {}

        for block_index, block in enumerate(content.get("blocks") or ()):
            if int(block.get("type", _TEXT_BLOCK_TYPE)) != _TEXT_BLOCK_TYPE:
                continue
            for line in block.get("lines") or ():
                built = _line_from(
                    line,
                    page_index=page_index,
                    page_height=page_height,
                    block_index=block_index,
                )
                if built is not None:
                    lines.append(built)

    return tuple(lines)


def drafts_from_document(document) -> tuple[BlockDraft, ...]:
    """Return structural drafts for a PDF, or none if layout is unavailable.

    Failure here is not fatal. Returning no drafts means the book falls back to
    the unstructured model and behaves exactly as it always has, which is
    preferable to failing the load over a layout quirk.
    """

    try:
        return drafts_from_lines(lines_from_document(document))
    except Exception:
        log.warning("PDF layout extraction failed; continuing without structure")
        return ()
