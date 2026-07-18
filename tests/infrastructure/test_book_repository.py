from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from voice_reader.domain.document.anchoring import BlockDraft
from voice_reader.domain.document.block_kind import BlockKind
from voice_reader.domain.entities.book import Book
from voice_reader.infrastructure.books.parser import ParsedBook
from voice_reader.infrastructure.books.repository import LocalBookRepository

STRUCTURED_TEXT = (
    "Chapter One\n"
    "\n"
    "The opening paragraph of the book.\n"
    "\n"
    "Chapter Two\n"
    "\n"
    "The closing paragraph of the book.\n"
)

STRUCTURED_DRAFTS = (
    BlockDraft(kind=BlockKind.HEADING, text="Chapter One", level=1),
    BlockDraft(kind=BlockKind.PARAGRAPH, text="The opening paragraph of the book."),
    BlockDraft(kind=BlockKind.HEADING, text="Chapter Two", level=1),
    BlockDraft(kind=BlockKind.PARAGRAPH, text="The closing paragraph of the book."),
)


@dataclass(frozen=True, slots=True)
class FakeConverter:
    def convert_to_epub_if_needed(self, source_path: Path) -> Path:
        return source_path


@dataclass(frozen=True, slots=True)
class FakeParser:
    raw_text: str = "RAW"
    normalized_text: str = "NORM"
    drafts: tuple[BlockDraft, ...] = field(default=())

    def parse(self, path: Path) -> ParsedBook:
        return ParsedBook(
            raw_text=self.raw_text,
            normalized_text=self.normalized_text,
            drafts=self.drafts,
        )


def _load(tmp_path: Path, parser: FakeParser) -> Book:
    p = tmp_path / "x.txt"
    p.write_text("hello", encoding="utf-8")
    repo = LocalBookRepository(converter=FakeConverter(), parser=parser)
    return repo.load(p)


def test_local_book_repository_loads_book(tmp_path: Path) -> None:
    book = _load(tmp_path, FakeParser())

    assert isinstance(book, Book)
    assert book.title == "x"
    assert book.normalized_text == "NORM"


def test_a_book_always_carries_a_document(tmp_path: Path) -> None:
    book = _load(tmp_path, FakeParser())

    assert book.document is not None


def test_drafts_are_assembled_into_a_structured_document(tmp_path: Path) -> None:
    book = _load(
        tmp_path,
        FakeParser(
            normalized_text=STRUCTURED_TEXT,
            drafts=STRUCTURED_DRAFTS,
        ),
    )

    assert book.document is not None
    assert [s.title for s in book.document.sections] == ["Chapter One", "Chapter Two"]
    assert [e.title for e in book.document.toc] == ["Chapter One", "Chapter Two"]


def test_document_spans_index_the_normalized_text(tmp_path: Path) -> None:
    book = _load(
        tmp_path,
        FakeParser(
            normalized_text=STRUCTURED_TEXT,
            drafts=STRUCTURED_DRAFTS,
        ),
    )

    assert book.document is not None
    for block in book.document.blocks:
        slice_ = book.normalized_text[block.source_start : block.source_end]
        # Whitespace may differ: the source wraps, the block text is flattened.
        assert "".join(slice_.split()) == "".join(block.text.split())


def test_no_drafts_falls_back_to_an_unstructured_document(tmp_path: Path) -> None:
    book = _load(tmp_path, FakeParser(normalized_text=STRUCTURED_TEXT))

    assert book.document is not None
    assert len(book.document.sections) == 1
    assert len(book.document.blocks) == 1
    assert book.document.blocks[0].kind is BlockKind.PARAGRAPH
    assert book.document.blocks[0].text == STRUCTURED_TEXT


def test_poorly_covered_extraction_falls_back_rather_than_shipping_gaps(
    tmp_path: Path,
) -> None:
    # Only a sliver of the text is accounted for, so the model is not trusted.
    sparse = (BlockDraft(kind=BlockKind.PARAGRAPH, text="Chapter One"),)
    book = _load(
        tmp_path,
        FakeParser(normalized_text=STRUCTURED_TEXT, drafts=sparse),
    )

    assert book.document is not None
    # The fallback is one paragraph spanning everything, not the sparse model.
    assert len(book.document.blocks) == 1
    assert book.document.blocks[0].text == STRUCTURED_TEXT


def test_the_book_id_is_unaffected_by_the_document_model(tmp_path: Path) -> None:
    # Existing bookmarks and resume positions are keyed by book id, so adding
    # structure must not change it.
    without = _load(tmp_path, FakeParser(normalized_text=STRUCTURED_TEXT))
    with_structure = _load(
        tmp_path,
        FakeParser(normalized_text=STRUCTURED_TEXT, drafts=STRUCTURED_DRAFTS),
    )

    assert without.id == with_structure.id


def test_the_normalized_text_is_unaffected_by_the_document_model(
    tmp_path: Path,
) -> None:
    without = _load(tmp_path, FakeParser(normalized_text=STRUCTURED_TEXT))
    with_structure = _load(
        tmp_path,
        FakeParser(normalized_text=STRUCTURED_TEXT, drafts=STRUCTURED_DRAFTS),
    )

    assert without.normalized_text == with_structure.normalized_text
