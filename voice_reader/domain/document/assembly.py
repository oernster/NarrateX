"""Build a document from drafts discovered by a format reader.

The shared tail of every inferred format: anchor the drafts onto the canonical
text, group the resulting blocks into sections, then derive the contents. Only
the discovery of drafts differs between EPUB, PDF and plain text.
"""

from __future__ import annotations

from voice_reader.domain.document.anchoring import BlockDraft, anchor_blocks
from voice_reader.domain.document.model import Document
from voice_reader.domain.document.sectioning import build_toc, group_into_sections


def build_from_drafts(
    *,
    source: str,
    drafts: tuple[BlockDraft, ...],
) -> Document:
    """Anchor `drafts` onto `source` and return the assembled document."""

    body = str(source or "")
    blocks = anchor_blocks(source=body, drafts=drafts)
    sections = group_into_sections(blocks=blocks)
    return Document(
        source_length=len(body),
        sections=sections,
        toc=build_toc(sections=sections),
    )
