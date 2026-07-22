"""Infrastructure: BookRepository implementation."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from voice_reader.domain.document.assembly import build_from_drafts
from voice_reader.domain.document.model import Document
from voice_reader.domain.entities.book import Book
from voice_reader.domain.interfaces.book_repository import BookRepository
from voice_reader.infrastructure.books.converter import CalibreConverter
from voice_reader.infrastructure.books.parser import BookParser, ParsedBook

# Least share of the book that must be accounted for by *some* block before the
# structured model is trusted.
#
# This is the guardrail: extraction that could not account for at least this
# much of the text is treated as too poor to structure, and the book falls back
# to being one unbroken run of prose, which reads and narrates the whole text.
#
# The bar is high on purpose, because the model now decides what is *spoken*,
# not just what is displayed. Any block the structured model does not cover is
# text the narrator would silently skip, so a model that covers, say, 0.6 would
# read aloud only six-tenths of the book with no sign of the rest. The complete
# flat fallback is the lesser evil there. Real books cluster at 0.96 and above,
# and a genuinely failed walk scores near zero, so 0.90 sits in the wide gap
# between them: it keeps every well-formed book with margin, and rejects
# anything that would drop more than a tenth of the text from narration.
_MIN_COVERED_RATIO = 0.90

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
            document=self._build_document(normalized=normalized, parsed=parsed),
        )

    @staticmethod
    def _candidate_document(
        *,
        normalized: str,
        parsed: ParsedBook,
    ) -> Document | None:
        """The model the format produced, however it chose to report it."""

        if parsed.document is not None:
            return parsed.document
        if parsed.drafts:
            return build_from_drafts(source=normalized, drafts=parsed.drafts)
        return None

    @classmethod
    def _build_document(cls, *, normalized: str, parsed: ParsedBook) -> Document:
        """Assemble the document model, falling back when confidence is low.

        Always returns a document. The fallback is a real model rather than an
        absence of one, so the renderer and the narrator have a single code path
        regardless of how well extraction went.
        """

        candidate = cls._candidate_document(normalized=normalized, parsed=parsed)
        if candidate is not None:
            understood = candidate.covered_ratio >= _MIN_COVERED_RATIO
            has_body = candidate.displayed_ratio >= _MIN_DISPLAYED_RATIO
            if understood and has_body:
                return candidate
        return Document.unstructured(text=normalized)
