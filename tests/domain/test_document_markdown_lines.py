"""Tests for line-level markdown classification."""

from __future__ import annotations

import pytest

from voice_reader.domain.document import markdown_lines as lines_module


class TestSplitLines:
    def test_empty_source_yields_no_lines(self) -> None:
        assert lines_module.split_lines("") == ()

    def test_none_source_yields_no_lines(self) -> None:
        assert lines_module.split_lines(None) == ()  # type: ignore[arg-type]

    def test_offsets_index_the_source_exactly(self) -> None:
        source = "alpha\nbeta\ngamma"
        for line in lines_module.split_lines(source):
            assert source[line.start : line.end] == line.text

    def test_blank_lines_are_preserved_with_their_offsets(self) -> None:
        source = "alpha\n\nbeta"
        result = lines_module.split_lines(source)

        assert [line.text for line in result] == ["alpha", "", "beta"]
        assert source[result[2].start : result[2].end] == "beta"


class TestBlank:
    @pytest.mark.parametrize("text", ["", "   ", "\t"])
    def test_whitespace_only_lines_are_blank(self, text: str) -> None:
        assert lines_module.is_blank(text) is True

    def test_prose_is_not_blank(self) -> None:
        assert lines_module.is_blank("prose") is False


class TestAtxHeading:
    @pytest.mark.parametrize(
        ("text", "level", "title"),
        [
            ("# One", 1, "One"),
            ("## Two", 2, "Two"),
            ("###### Six", 6, "Six"),
            ("   ### Indented", 3, "Indented"),
            ("## Closed ##", 2, "Closed"),
        ],
    )
    def test_recognises_headings(self, text: str, level: int, title: str) -> None:
        assert lines_module.atx_heading(text) == (level, title)

    @pytest.mark.parametrize(
        "text",
        [
            "prose",
            "#no space",
            "####### seven hashes",
            "    # four spaces is code indent",
        ],
    )
    def test_rejects_non_headings(self, text: str) -> None:
        assert lines_module.atx_heading(text) is None


class TestSetext:
    def test_equals_underline_is_level_one(self) -> None:
        assert lines_module.setext_level("===") == 1

    def test_dash_underline_is_level_two(self) -> None:
        assert lines_module.setext_level("---") == 2

    def test_prose_is_not_an_underline(self) -> None:
        assert lines_module.setext_level("prose") is None


class TestThematicBreak:
    @pytest.mark.parametrize("text", ["---", "***", "___", "- - -", "  ***"])
    def test_recognises_breaks(self, text: str) -> None:
        assert lines_module.is_thematic_break(text) is True

    @pytest.mark.parametrize("text", ["--", "prose", "-* -"])
    def test_rejects_non_breaks(self, text: str) -> None:
        assert lines_module.is_thematic_break(text) is False


class TestBlockQuote:
    def test_returns_the_quoted_content(self) -> None:
        assert lines_module.block_quote_content("> quoted") == "quoted"

    def test_handles_a_marker_with_no_space(self) -> None:
        assert lines_module.block_quote_content(">quoted") == "quoted"

    def test_returns_empty_for_a_bare_marker(self) -> None:
        assert lines_module.block_quote_content(">") == ""

    def test_returns_none_for_prose(self) -> None:
        assert lines_module.block_quote_content("prose") is None


class TestListItem:
    @pytest.mark.parametrize("marker", ["-", "*", "+", "1.", "2)"])
    def test_recognises_markers(self, marker: str) -> None:
        assert lines_module.list_item(f"{marker} item") == (1, "item")

    def test_indent_increases_the_level(self) -> None:
        assert lines_module.list_item("  - nested") == (2, "nested")
        assert lines_module.list_item("    - deeper") == (3, "deeper")

    def test_returns_none_for_prose(self) -> None:
        assert lines_module.list_item("prose") is None


class TestFences:
    @pytest.mark.parametrize("text", ["```", "~~~", "```python", "  ```"])
    def test_recognises_fence_openings(self, text: str) -> None:
        assert lines_module.fence_marker(text) is not None

    def test_returns_none_for_prose(self) -> None:
        assert lines_module.fence_marker("prose") is None

    def test_a_matching_marker_closes_the_fence(self) -> None:
        assert lines_module.closes_fence("```", marker="```") is True

    def test_a_longer_marker_closes_the_fence(self) -> None:
        assert lines_module.closes_fence("````", marker="```") is True

    def test_a_shorter_marker_does_not_close_the_fence(self) -> None:
        assert lines_module.closes_fence("```", marker="````") is False

    def test_a_different_marker_does_not_close_the_fence(self) -> None:
        assert lines_module.closes_fence("~~~", marker="```") is False

    def test_prose_does_not_close_the_fence(self) -> None:
        assert lines_module.closes_fence("prose", marker="```") is False
