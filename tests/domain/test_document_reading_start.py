"""Tests for deciding where the body of a book begins."""

from __future__ import annotations

from voice_reader.domain.document.block_kind import BlockKind
from voice_reader.domain.document.model import Block, Document, Section
from voice_reader.domain.document.plain_text import build_document
from voice_reader.domain.document.reading_start import (
    contents_end_offset,
    reading_start_offset,
)


def _block(kind: BlockKind, start: int, end: int, text: str = "x") -> Block:
    return Block(kind=kind, source_start=start, source_end=end, text=text)


def _section(title: str, start: int, end: int, blocks: tuple[Block, ...]) -> Section:
    return Section(title=title, source_start=start, source_end=end, blocks=blocks)


class TestContentsEnd:
    def test_a_document_with_no_contents_ends_at_zero(self) -> None:
        doc = build_document(source="Chapter 1\n\nSome prose here.\n")

        assert contents_end_offset(doc) == 0

    def test_dotted_leader_entries_mark_the_end(self) -> None:
        # The PDF shape: a contents page leaves leader entries behind.
        source = (
            "Prologue . . . . . . . . . . 2\n"
            "\n"
            "Chapter 1 . . . . . . . . . . 7\n"
            "\n"
            "Chapter 1\n"
            "\n"
            "The prose begins here.\n"
        )
        doc = build_document(source=source)
        end = contents_end_offset(doc)

        assert end > 0
        assert source.index("Chapter 1\n\nThe prose") >= end

    def test_a_section_titled_contents_marks_the_end(self) -> None:
        # The EPUB shape: a contents list with no leaders at all.
        entry = _block(BlockKind.PARAGRAPH, 10, 40, "Some listed item")
        heading = _block(BlockKind.HEADING, 0, 8, "Contents")
        doc = Document(
            source_length=100,
            sections=(_section("Contents", 0, 40, (heading, entry)),),
        )

        assert contents_end_offset(doc) == 40

    def test_the_latest_piece_of_evidence_wins(self) -> None:
        toc = _block(BlockKind.TOC_ENTRY, 50, 80, "Prologue ..... 2")
        heading = _block(BlockKind.HEADING, 0, 8, "Contents")
        doc = Document(
            source_length=200,
            sections=(
                _section("Contents", 0, 30, (heading,)),
                _section("", 50, 80, (toc,)),
            ),
        )

        assert contents_end_offset(doc) == 80


class TestReadingStart:
    def test_narration_starts_at_a_named_body_opening(self) -> None:
        source = (
            "THE BOOK\n"
            "\n"
            "Contents\n"
            "\n"
            "Prologue\n"
            "\n"
            "The story truly begins here.\n"
        )
        doc = build_document(source=source)

        assert reading_start_offset(doc) == source.index("Prologue\n\nThe story")

    def test_the_title_page_is_skipped(self) -> None:
        source = "THE BOOK\n\nChapter 1\n\nThe story begins.\n"
        doc = build_document(source=source)

        assert reading_start_offset(doc) != 0

    def test_a_body_opening_named_inside_the_contents_is_not_used(self) -> None:
        # The trap this module exists for: a contents page lists the very
        # heading names being searched for, so a naive scan from the top finds
        # "Prologue" inside the table rather than the real one.
        source = (
            "Contents\n"
            "\n"
            "Prologue . . . . . . . . . . 2\n"
            "\n"
            "Prologue\n"
            "\n"
            "The real prologue text.\n"
        )
        doc = build_document(source=source)
        start = reading_start_offset(doc)

        assert start is not None
        assert start > source.index("Prologue . . .")
        assert source[start:].startswith("Prologue\n\nThe real")

    def test_a_numbered_division_opens_the_body(self) -> None:
        source = "Contents\n\nChapter 4\n\nThe fourth chapter.\n"
        doc = build_document(source=source)
        start = reading_start_offset(doc)

        assert start is not None
        assert source[start:].startswith("Chapter 4")

    def test_falls_back_to_the_first_spoken_block_past_the_contents(self) -> None:
        # No recognisable body opening, so the first real content past the
        # contents is the best available answer.
        heading = _block(BlockKind.HEADING, 0, 8, "Contents")
        body = _block(BlockKind.PARAGRAPH, 60, 90, "Unnamed body text")
        doc = Document(
            source_length=100,
            sections=(
                _section("Contents", 0, 40, (heading,)),
                _section("", 60, 90, (body,)),
            ),
        )

        assert reading_start_offset(doc) == 60

    def test_a_body_opening_with_nothing_spoken_is_passed_over(self) -> None:
        folio = _block(BlockKind.PAGE_NUMBER, 10, 12, "2")
        body = _block(BlockKind.PARAGRAPH, 60, 90, "Real text")
        doc = Document(
            source_length=100,
            sections=(
                _section("Prologue", 10, 12, (folio,)),
                _section("", 60, 90, (body,)),
            ),
        )

        assert reading_start_offset(doc) == 60

    def test_falls_back_to_the_body_start_when_nothing_follows_the_contents(
        self,
    ) -> None:
        body = _block(BlockKind.PARAGRAPH, 0, 20, "Everything is before it")
        toc = _block(BlockKind.TOC_ENTRY, 50, 80, "Prologue ..... 2")
        doc = Document(
            source_length=100,
            sections=(_section("", 0, 80, (body, toc)),),
        )

        assert reading_start_offset(doc) == 0

    def test_a_document_with_nothing_spoken_has_no_start(self) -> None:
        folio = _block(BlockKind.PAGE_NUMBER, 0, 2, "2")
        doc = Document(source_length=10, sections=(_section("", 0, 2, (folio,)),))

        assert reading_start_offset(doc) is None

    def test_an_empty_document_has_no_start(self) -> None:
        assert reading_start_offset(Document(source_length=0)) is None

    def test_a_prose_section_after_the_contents_is_narrated(self) -> None:
        # The combined hardback shape: "About This Edition" carries real
        # prose between the contents and Book 1. It is shown in the pane,
        # so narration must start there, not at the first recognised
        # opening name after it.
        source = (
            "Contents\n"
            "\n"
            "About This Edition . . . . . . 2\n"
            "\n"
            "Book 1: Decision Architecture . . . . . . 5\n"
            "\n"
            "About This Edition\n"
            "\n"
            "This is the second edition of the combined series.\n"
            "\n"
            "Book 1: Decision Architecture\n"
            "\n"
            "Organisations fail slowly, then suddenly.\n"
        )
        doc = build_document(source=source)
        start = reading_start_offset(doc)

        assert start is not None
        assert source[start:].startswith("About This Edition\n\nThis is the second")

    def test_a_leftover_contents_line_is_still_passed_over(self) -> None:
        # A boundary landing slightly short leaves a bare heading with no
        # prose under it; the prose requirement keeps skipping it.
        stray = _block(BlockKind.HEADING, 45, 53, "Prologue")
        body = _block(BlockKind.PARAGRAPH, 60, 90, "The real prologue text")
        heading = _block(BlockKind.HEADING, 0, 8, "Contents")
        doc = Document(
            source_length=100,
            sections=(
                _section("Contents", 0, 40, (heading,)),
                _section("Prologue", 45, 53, (stray,)),
                _section("Prologue", 60, 90, (body,)),
            ),
        )

        assert reading_start_offset(doc) == 60

    def test_an_untitled_section_is_not_a_body_opening(self) -> None:
        source = "Contents\n\nsome lowercase prose that carries on and on here.\n"
        doc = build_document(source=source)

        # Falls through to the first spoken block past the contents rather than
        # treating the untitled run as a named opening.
        assert reading_start_offset(doc) is not None
