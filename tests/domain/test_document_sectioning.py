"""Tests for grouping blocks into sections and deriving contents."""

from __future__ import annotations

from voice_reader.domain.document.block_kind import BlockKind
from voice_reader.domain.document.model import Block
from voice_reader.domain.document.sectioning import build_toc, group_into_sections


def _heading(start: int, end: int, text: str, level: int = 1) -> Block:
    return Block(
        kind=BlockKind.HEADING,
        source_start=start,
        source_end=end,
        text=text,
        level=level,
    )


def _para(start: int, end: int, text: str = "body") -> Block:
    return Block(
        kind=BlockKind.PARAGRAPH,
        source_start=start,
        source_end=end,
        text=text,
    )


class TestGroupIntoSections:
    def test_no_blocks_yields_no_sections(self) -> None:
        assert group_into_sections(blocks=()) == ()

    def test_a_heading_starts_a_new_section(self) -> None:
        blocks = (
            _heading(0, 10, "One"),
            _para(10, 20),
            _heading(20, 30, "Two"),
            _para(30, 40),
        )
        sections = group_into_sections(blocks=blocks)

        assert [s.title for s in sections] == ["One", "Two"]
        assert sections[0].source_start == 0
        assert sections[0].source_end == 20
        assert sections[1].source_start == 20
        assert sections[1].source_end == 40

    def test_blocks_before_the_first_heading_become_an_untitled_section(self) -> None:
        blocks = (_para(0, 10, "front matter"), _heading(10, 20, "One"))
        sections = group_into_sections(blocks=blocks)

        assert [s.title for s in sections] == ["", "One"]

    def test_no_content_is_dropped_by_sectioning(self) -> None:
        blocks = (
            _para(0, 10, "front matter"),
            _heading(10, 20, "One"),
            _para(20, 30),
        )
        sections = group_into_sections(blocks=blocks)
        regrouped = tuple(b for s in sections for b in s.blocks)

        assert regrouped == blocks

    def test_a_single_heading_with_no_body_still_forms_a_section(self) -> None:
        sections = group_into_sections(blocks=(_heading(0, 10, "Only"),))

        assert len(sections) == 1
        assert sections[0].title == "Only"

    def test_consecutive_headings_each_open_a_section(self) -> None:
        blocks = (_heading(0, 10, "One"), _heading(10, 20, "Two"))
        sections = group_into_sections(blocks=blocks)

        assert [s.title for s in sections] == ["One", "Two"]


class TestBuildToc:
    def test_no_sections_yields_no_entries(self) -> None:
        assert build_toc(sections=()) == ()

    def test_each_headed_section_becomes_a_resolved_entry(self) -> None:
        sections = group_into_sections(
            blocks=(
                _heading(0, 10, "One", level=1),
                _heading(10, 20, "One A", level=2),
            )
        )
        toc = build_toc(sections=sections)

        assert [(e.title, e.level, e.target_source_offset) for e in toc] == [
            ("One", 1, 0),
            ("One A", 2, 10),
        ]
        assert all(e.is_resolved for e in toc)

    def test_an_untitled_leading_section_is_not_an_entry(self) -> None:
        sections = group_into_sections(
            blocks=(_para(0, 10, "front matter"), _heading(10, 20, "One"))
        )
        toc = build_toc(sections=sections)

        assert [e.title for e in toc] == ["One"]
