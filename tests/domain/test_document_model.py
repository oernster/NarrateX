"""Tests for the structured document model."""

from __future__ import annotations

import pytest

from voice_reader.domain.document import Block, BlockKind, Document, Section, TocEntry


def _para(start: int, end: int, text: str = "body") -> Block:
    return Block(
        kind=BlockKind.PARAGRAPH,
        source_start=start,
        source_end=end,
        text=text,
    )


class TestBlock:
    def test_rejects_a_kind_that_is_not_a_block_kind(self) -> None:
        with pytest.raises(TypeError):
            Block(
                kind="paragraph",  # type: ignore[arg-type]
                source_start=0,
                source_end=1,
                text="x",
            )

    def test_rejects_a_negative_start(self) -> None:
        with pytest.raises(ValueError):
            _para(-1, 5)

    def test_rejects_an_end_before_the_start(self) -> None:
        with pytest.raises(ValueError):
            _para(10, 4)

    def test_rejects_a_negative_level(self) -> None:
        with pytest.raises(ValueError):
            Block(
                kind=BlockKind.HEADING,
                source_start=0,
                source_end=4,
                text="Six",
                level=-1,
            )

    def test_allows_an_empty_span(self) -> None:
        assert _para(7, 7).source_length == 0

    def test_source_length_is_the_span_width(self) -> None:
        assert _para(10, 25).source_length == 15

    def test_delegates_display_and_narration_policy_to_its_kind(self) -> None:
        code = Block(
            kind=BlockKind.CODE,
            source_start=0,
            source_end=3,
            text="x=1",
        )
        assert code.is_displayed is True
        assert code.is_spoken is False


class TestTocEntry:
    def test_rejects_a_negative_level(self) -> None:
        with pytest.raises(ValueError):
            TocEntry(title="Prologue", level=-1)

    def test_rejects_a_negative_target_offset(self) -> None:
        with pytest.raises(ValueError):
            TocEntry(title="Prologue", target_source_offset=-2)

    def test_is_unresolved_without_a_target(self) -> None:
        assert TocEntry(title="Prologue").is_resolved is False

    def test_is_resolved_with_a_target(self) -> None:
        entry = TocEntry(title="Prologue", target_source_offset=0)
        assert entry.is_resolved is True


class TestSection:
    def test_rejects_an_end_before_the_start(self) -> None:
        with pytest.raises(ValueError):
            Section(title="One", source_start=9, source_end=2)

    def test_rejects_a_negative_start(self) -> None:
        with pytest.raises(ValueError):
            Section(title="One", source_start=-1, source_end=2)

    def test_rejects_blocks_that_are_not_a_tuple(self) -> None:
        with pytest.raises(TypeError):
            Section(
                title="One",
                source_start=0,
                source_end=2,
                blocks=[_para(0, 2)],  # type: ignore[arg-type]
            )

    def test_partitions_its_blocks_by_policy(self) -> None:
        heading = Block(
            kind=BlockKind.HEADING,
            source_start=0,
            source_end=5,
            text="One",
            level=1,
        )
        body = _para(6, 20)
        folio = Block(
            kind=BlockKind.PAGE_NUMBER,
            source_start=21,
            source_end=23,
            text="12",
        )
        code = Block(
            kind=BlockKind.CODE,
            source_start=24,
            source_end=30,
            text="x=1",
        )
        section = Section(
            title="One",
            source_start=0,
            source_end=30,
            blocks=(heading, body, folio, code),
        )

        assert section.displayed_blocks == (heading, body, code)
        assert section.spoken_blocks == (heading, body)


class TestDocument:
    def test_rejects_a_negative_source_length(self) -> None:
        with pytest.raises(ValueError):
            Document(source_length=-1)

    def test_rejects_sections_that_are_not_a_tuple(self) -> None:
        with pytest.raises(TypeError):
            Document(
                source_length=0,
                sections=[],  # type: ignore[arg-type]
            )

    def test_rejects_a_toc_that_is_not_a_tuple(self) -> None:
        with pytest.raises(TypeError):
            Document(
                source_length=0,
                toc=[],  # type: ignore[arg-type]
            )

    def test_flattens_blocks_across_sections_in_reading_order(self) -> None:
        first = Section(
            title="One",
            source_start=0,
            source_end=10,
            blocks=(_para(0, 10, "first"),),
        )
        second = Section(
            title="Two",
            source_start=10,
            source_end=20,
            blocks=(_para(10, 20, "second"),),
        )
        doc = Document(source_length=20, sections=(first, second))

        assert [b.text for b in doc.blocks] == ["first", "second"]

    def test_partitions_blocks_by_policy(self) -> None:
        body = _para(0, 10)
        toc = Block(
            kind=BlockKind.TOC_ENTRY,
            source_start=10,
            source_end=20,
            text="Prologue 2",
        )
        section = Section(
            title="",
            source_start=0,
            source_end=20,
            blocks=(toc, body),
        )
        doc = Document(source_length=20, sections=(section,))

        assert doc.displayed_blocks == (body,)
        assert doc.spoken_blocks == (body,)

    def test_body_start_is_the_first_spoken_block(self) -> None:
        toc = Block(
            kind=BlockKind.TOC_ENTRY,
            source_start=0,
            source_end=40,
            text="Prologue . . . 2",
        )
        body = _para(40, 90)
        section = Section(
            title="",
            source_start=0,
            source_end=90,
            blocks=(toc, body),
        )
        doc = Document(source_length=90, sections=(section,))

        assert doc.body_start_offset == 40

    def test_body_start_is_none_when_nothing_is_spoken(self) -> None:
        toc = Block(
            kind=BlockKind.TOC_ENTRY,
            source_start=0,
            source_end=40,
            text="Prologue . . . 2",
        )
        section = Section(
            title="",
            source_start=0,
            source_end=40,
            blocks=(toc,),
        )
        doc = Document(source_length=40, sections=(section,))

        assert doc.body_start_offset is None

    def test_displayed_ratio_is_zero_for_an_empty_document(self) -> None:
        assert Document(source_length=0).displayed_ratio == 0.0

    def test_covered_ratio_is_zero_for_an_empty_document(self) -> None:
        assert Document(source_length=0).covered_ratio == 0.0

    def test_recognised_artefacts_count_towards_coverage_but_not_display(
        self,
    ) -> None:
        # Understanding that something is a page number is understanding the
        # text. A contents-heavy book must not be mistaken for an unparsed one.
        body = _para(0, 25)
        folio = Block(
            kind=BlockKind.PAGE_NUMBER,
            source_start=25,
            source_end=100,
            text="12",
        )
        section = Section(
            title="",
            source_start=0,
            source_end=100,
            blocks=(body, folio),
        )
        doc = Document(source_length=100, sections=(section,))

        assert doc.covered_ratio == pytest.approx(1.0)
        assert doc.displayed_ratio == pytest.approx(0.25)

    def test_unaccounted_text_lowers_coverage(self) -> None:
        body = _para(0, 20)
        section = Section(title="", source_start=0, source_end=20, blocks=(body,))
        doc = Document(source_length=100, sections=(section,))

        assert doc.covered_ratio == pytest.approx(0.2)

    def test_displayed_ratio_measures_displayed_coverage(self) -> None:
        body = _para(0, 25)
        folio = Block(
            kind=BlockKind.PAGE_NUMBER,
            source_start=25,
            source_end=100,
            text="12",
        )
        section = Section(
            title="",
            source_start=0,
            source_end=100,
            blocks=(body, folio),
        )
        doc = Document(source_length=100, sections=(section,))

        assert doc.displayed_ratio == pytest.approx(0.25)


class TestUnstructuredFallback:
    def test_empty_text_yields_an_empty_document(self) -> None:
        doc = Document.unstructured(text="")

        assert doc.source_length == 0
        assert doc.sections == ()
        assert doc.blocks == ()
        assert doc.body_start_offset is None

    def test_none_text_is_treated_as_empty(self) -> None:
        doc = Document.unstructured(text=None)  # type: ignore[arg-type]

        assert doc.source_length == 0

    def test_text_becomes_one_section_holding_one_paragraph(self) -> None:
        text = "Some prose that we could not confidently structure."
        doc = Document.unstructured(text=text)

        assert len(doc.sections) == 1
        assert len(doc.blocks) == 1

        block = doc.blocks[0]
        assert block.kind is BlockKind.PARAGRAPH
        assert block.text == text
        assert block.source_start == 0
        assert block.source_end == len(text)

    def test_fallback_spans_the_whole_source_so_nothing_is_lost(self) -> None:
        text = "A" * 500
        doc = Document.unstructured(text=text)

        assert doc.source_length == len(text)
        assert doc.body_start_offset == 0
        assert doc.displayed_ratio == pytest.approx(1.0)
