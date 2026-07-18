"""Infrastructure: BookRepository implementation."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from voice_reader.domain.document.anchoring import BlockDraft
from voice_reader.domain.document.assembly import build_from_drafts
from voice_reader.domain.document.model import Document
from voice_reader.domain.entities.book import Book
from voice_reader.domain.interfaces.book_repository import BookRepository
from voice_reader.infrastructure.books.converter import CalibreConverter
from voice_reader.infrastructure.books.parser import BookParser

# Least share of the book that must be accounted for by *some* block before the
# structured model is trusted.
#
# This is the guardrail: extraction that could not account for at least this
# much of the text is treated as too poor to structure, and the book falls back
# to being one unbroken run of prose, which reads and narrates exactly as it
# always has. Half is a deliberately forgiving bar. A well-formed book scores
# far above it, and a walk that has genuinely failed scores near zero, so the
# threshold separates those two cases without sitting near either.
_MIN_COVERED_RATIO = 0.5

# A model that recognised plenty of furniture but found no body text has not
# understood the book, whatever its coverage. Any real body content clears this.
_MIN_DISPLAYED_RATIO = 0.05


@dataclass(frozen=True, slots=True)
class LocalBookRepository(BookRepository):
    converter: CalibreConverter
    parser: BookParser

    def load(self, source_path: Path) -> Book:
        converted = self.converter.convert_to_epub_if_needed(source_path)
        parsed = self.parser.parse(converted)
        normalized = parsed.normalized_text
        title = source_path.stem
        book_id = hashlib.sha256(
            (title + normalized[:2000]).encode("utf-8", errors="ignore")
        ).hexdigest()[:16]
        return Book(
            id=book_id,
            title=title,
            raw_text=parsed.raw_text,
            normalized_text=normalized,
            document=self._build_document(
                normalized=normalized,
                drafts=parsed.drafts,
            ),
        )

    @staticmethod
    def _build_document(
        *,
        normalized: str,
        drafts: tuple[BlockDraft, ...],
    ) -> Document:
        """Assemble the document model, falling back when confidence is low.

        Always returns a document. The fallback is a real model rather than an
        absence of one, so the renderer and the narrator have a single code path
        regardless of how well extraction went.
        """

        if drafts:
            document = build_from_drafts(source=normalized, drafts=drafts)
            understood = document.covered_ratio >= _MIN_COVERED_RATIO
            has_body = document.displayed_ratio >= _MIN_DISPLAYED_RATIO
            if understood and has_body:
                return document
        return Document.unstructured(text=normalized)
