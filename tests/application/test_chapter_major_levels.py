"""Next Chapter must reach the next chapter, not the next sub-heading.

Heading levels are ranks within one book rather than a shared scale: across the
reference books a chapter sits at level 3 in one and level 2 in three others,
because a PDF's levels come from sorting its own font sizes. So the rule works
on the ranks a book actually uses, and these tests pin that.
"""

from __future__ import annotations

from voice_reader.application.services.chapter_index_service import ChapterIndexService
from voice_reader.domain.document.block_kind import BlockKind
from voice_reader.domain.document.model import Block, Section
from voice_reader.domain.entities.text_chunk import TextChunk

SOURCE_LENGTH = 10_000


def _section(title: str, *, level: int, start: int) -> Section:
    heading = Block(
        kind=BlockKind.HEADING,
        source_start=start,
        source_end=start + len(title),
        text=title,
        level=level,
    )
    body = Block(
        kind=BlockKind.PARAGRAPH,
        source_start=start + len(title) + 1,
        source_end=start + len(title) + 40,
        text="Body prose for this section, long enough to speak.",
    )
    return Section(
        title=title,
        source_start=start,
        source_end=body.source_end,
        blocks=(heading, body),
    )


def _chunks() -> list[TextChunk]:
    return [
        TextChunk(
            chunk_id=index,
            text="Body prose for this section, long enough to speak.",
            start_char=index * 100,
            end_char=index * 100 + 50,
        )
        for i, index in enumerate(range(SOURCE_LENGTH // 100))
    ]


def _titles(sections) -> list[str]:
    service = ChapterIndexService()
    chapters = service.build_index_from_sections(
        sections=sections,
        chunks=_chunks(),
    )
    return [c.title for c in chapters]


class TestMajorDivisionsOnly:
    def test_the_deepest_rank_is_left_out(self) -> None:
        sections = [
            _section("Book One", level=1, start=0),
            _section("Chapter 1", level=3, start=1000),
            _section("A sub-heading", level=4, start=2000),
            _section("Chapter 2", level=3, start=3000),
            _section("Another sub-heading", level=4, start=4000),
        ]

        assert _titles(sections) == ["Book One", "Chapter 1", "Chapter 2"]

    def test_ranks_are_read_from_the_book_rather_than_fixed(self) -> None:
        # The same shape, one rank deeper throughout. A fixed threshold would
        # keep nothing here; the ranks present are what count.
        sections = [
            _section("Part One", level=2, start=0),
            _section("Chapter 1", level=4, start=1000),
            _section("A sub-heading", level=5, start=2000),
            _section("Chapter 2", level=4, start=3000),
        ]

        assert _titles(sections) == ["Part One", "Chapter 1", "Chapter 2"]

    def test_two_ranks_are_kept_so_chapters_survive_a_part_division(self) -> None:
        # Keeping only the shallowest would reduce a book to its parts.
        sections = [
            _section("Part One", level=1, start=0),
            _section("Chapter 1", level=2, start=1000),
            _section("Chapter 2", level=2, start=2000),
        ]

        assert _titles(sections) == ["Part One", "Chapter 1", "Chapter 2"]

    def test_a_flat_book_keeps_every_section(self) -> None:
        sections = [
            _section("One", level=1, start=0),
            _section("Two", level=1, start=1000),
        ]

        assert _titles(sections) == ["One", "Two"]


class TestFilteringOrder:
    def test_front_matter_headings_do_not_shift_the_ranks(self) -> None:
        """Position is filtered before ranking, not after.

        Front matter carries headings of its own. Ranking before excluding it
        let a shallow contents heading occupy a rank, pushing the chapters out
        of the two that are kept. On the combined hardback that turned two
        hundred chapters into nine parts.
        """

        sections = [
            _section("Contents", level=1, start=0),
            _section("Book One", level=2, start=1000),
            _section("Chapter 1", level=3, start=2000),
            _section("Chapter 2", level=3, start=3000),
            _section("A sub-heading", level=4, start=4000),
        ]

        service = ChapterIndexService()
        chapters = service.build_index_from_sections(
            sections=sections,
            chunks=_chunks(),
            min_char_offset=1000,
        )

        assert [c.title for c in chapters] == ["Book One", "Chapter 1", "Chapter 2"]


class TestUnclassifiableSections:
    def test_a_section_with_no_heading_is_kept_rather_than_guessed_at(self) -> None:
        body = Block(
            kind=BlockKind.PARAGRAPH,
            source_start=0,
            source_end=40,
            text="Body prose with no heading above it at all.",
        )
        untitled = Section(
            title="Untitled run", source_start=0, source_end=40, blocks=(body,)
        )
        sections = [
            untitled,
            _section("Chapter 1", level=1, start=1000),
            _section("A sub-heading", level=2, start=2000),
        ]

        assert "Untitled run" in _titles(sections)

    def test_a_book_with_no_levels_at_all_stays_fully_navigable(self) -> None:
        # No heading anywhere means no ranks to compare, so filtering by rank
        # would remove everything. Keeping the lot is the safe answer.
        def _headingless(title: str, start: int) -> Section:
            body = Block(
                kind=BlockKind.PARAGRAPH,
                source_start=start,
                source_end=start + 40,
                text="Body prose with no heading above it at all.",
            )
            return Section(
                title=title,
                source_start=start,
                source_end=start + 40,
                blocks=(body,),
            )

        sections = [_headingless("One", 0), _headingless("Two", 1000)]

        assert _titles(sections) == ["One", "Two"]
