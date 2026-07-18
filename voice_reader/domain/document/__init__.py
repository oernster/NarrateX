"""Structured document model.

The one canonical structure produced from an extracted book, consumed
independently by the reading pane and by the narrator.
"""

from voice_reader.domain.document.block_kind import BlockKind
from voice_reader.domain.document.model import Block, Document, Section, TocEntry

__all__ = [
    "Block",
    "BlockKind",
    "Document",
    "Section",
    "TocEntry",
]
