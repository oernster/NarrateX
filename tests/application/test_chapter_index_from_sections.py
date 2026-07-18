"""Tests for building navigation anchors from the document model."""

from __future__ import annotations

from voice_reader.application.services.chapter_index_service import ChapterIndexService
from voice_reader.domain.document.block_kind import BlockKind
from voice_reader.domain.document.model import Block, Section
from voice_reader.domain.entities.text_chunk import TextChunk


def _chunk(chunk_id: int, start: int, end: int, text: str = "some prose") -> TextChunk:
    return TextChunk(chunk_id=chunk_id, text=text, start_char=start, end_char=end)


def _section(title: str, start: int, end: int, *, spoken: bool = True) -> Section:
    kind = BlockKind.HEADING if spoken else BlockKind.PAGE_NUMBER
    block = Block(kind=kind, source_start=start, source_end=end, text=title or "12")
    return Section(title=title, source_start=start, source_end=end, blocks=(block,))


CHUNKS = [
    _chunk(0, 0, 50),
    _chunk(1, 50, 100),
    _chunk(2, 100, 150),
]


class TestBuildIndexFromSections:
    def test_no_chunks_yields_no_chapters(self) -> None:
        service = ChapterIndexService()

        assert service.build_index_from_sections(sections=(), chunks=[]) == []

    def test_no_sections_yields_no_chapters(self) -> None:
        service = ChapterIndexService()

        assert service.build_index_from_sections(sections=(), chunks=CHUNKS) == []

    def test_each_titled_section_becomes_a_chapter(self) -> None:
        sections = (_section("Prologue", 0, 10), _section("Chapter 1", 60, 70))
        chapters = ChapterIndexService().build_index_from_sections(
            sections=sections, chunks=CHUNKS
        )

        assert [c.title for c in chapters] == ["Prologue", "Chapter 1"]

    def test_it_finds_sections_the_heading_regex_cannot(self) -> None:
        # "Prologue" contains no numbered "chapter", so detection misses it
        # entirely while the model knows exactly what it is.
        sections = (_section("Prologue", 0, 10),)
        service = ChapterIndexService()

        from_model = service.build_index_from_sections(sections=sections, chunks=CHUNKS)
        by_detection = service.build_index("Prologue\n\nSome prose.", chunks=CHUNKS)

        assert [c.title for c in from_model] == ["Prologue"]
        assert by_detection == []

    def test_an_untitled_section_is_skipped(self) -> None:
        sections = (_section("", 0, 10), _section("Chapter 1", 60, 70))
        chapters = ChapterIndexService().build_index_from_sections(
            sections=sections, chunks=CHUNKS
        )

        assert [c.title for c in chapters] == ["Chapter 1"]

    def test_a_section_with_nothing_spoken_is_skipped(self) -> None:
        sections = (_section("Front", 0, 10, spoken=False),)
        chapters = ChapterIndexService().build_index_from_sections(
            sections=sections, chunks=CHUNKS
        )

        assert chapters == []

    def test_a_section_maps_to_a_playback_chunk(self) -> None:
        sections = (_section("Chapter 2", 110, 120),)
        chapters = ChapterIndexService().build_index_from_sections(
            sections=sections, chunks=CHUNKS
        )

        assert chapters[0].chunk_index == 2

    def test_a_section_past_every_chunk_is_dropped(self) -> None:
        sections = (_section("Appendix", 9000, 9010),)
        chapters = ChapterIndexService().build_index_from_sections(
            sections=sections, chunks=CHUNKS
        )

        assert chapters == []

    def test_sections_before_the_body_start_are_dropped(self) -> None:
        # Filtering must use the section's own offset. Chunks begin at the
        # narration start, so a chunk-based filter keeps every front-matter
        # section and puts the title page and contents into the list.
        sections = (_section("Front", 0, 10), _section("Chapter 2", 110, 120))
        chapters = ChapterIndexService().build_index_from_sections(
            sections=sections, chunks=CHUNKS, min_char_offset=100
        )

        assert [c.title for c in chapters] == ["Chapter 2"]

    def test_a_section_starting_in_a_gap_uses_the_next_chunk(self) -> None:
        # Artefacts are skipped, so playback chunks need not be contiguous. A
        # section heading landing in one of those gaps must still resolve.
        gapped = [_chunk(0, 0, 50), _chunk(1, 100, 150)]
        sections = (_section("Chapter 2", 60, 70),)
        chapters = ChapterIndexService().build_index_from_sections(
            sections=sections, chunks=gapped
        )

        assert [c.chunk_index for c in chapters] == [1]

    def test_chapters_come_back_in_reading_order(self) -> None:
        sections = (_section("Second", 110, 120), _section("First", 10, 20))
        chapters = ChapterIndexService().build_index_from_sections(
            sections=sections, chunks=CHUNKS
        )

        assert [c.title for c in chapters] == ["First", "Second"]
