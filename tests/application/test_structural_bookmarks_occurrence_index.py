"""The one-pass heading occurrence index.

Scanning the whole document once per label is fast enough on a novel and slow
enough on a 100-label omnibus PDF to read as a hang. The index does one pass
for a whole set of labels and has to reach the same answers as the per-label
scan it replaces.
"""

from __future__ import annotations

import pytest

from voice_reader.application.services.structural_bookmarks import occurrence_index
from voice_reader.application.services.structural_bookmarks.occurrence_index import (
    HeadingOccurrenceIndex,
)


def _index(text: str, *labels: str, min_char_offset: int = 0) -> HeadingOccurrenceIndex:
    return HeadingOccurrenceIndex.build(
        normalized_text=text,
        wanted_norm_labels=list(labels),
        min_char_offset=min_char_offset,
    )


class TestNothingToIndex:
    def test_empty_text_gives_an_empty_index(self) -> None:
        built = _index("", "chapter 1")

        assert (built.exact, built.wrapped, built.prefix) == ({}, {}, {})

    def test_no_wanted_labels_gives_an_empty_index(self) -> None:
        built = _index("Chapter 1\n")

        assert (built.exact, built.wrapped, built.prefix) == ({}, {}, {})


class TestExactMatches:
    def test_a_heading_line_is_indexed_with_its_offset(self) -> None:
        text = "prose\n\nChapter 1\n\nmore prose\n"

        found = _index(text, "chapter 1").occurrences_for_label(label="Chapter 1")

        assert [o.char_offset for o in found] == [text.index("Chapter 1")]

    def test_lines_before_the_minimum_offset_are_not_indexed(self) -> None:
        text = "Chapter 1\n\nprose\n\nChapter 1\n\nmore\n"
        second = text.index("Chapter 1", 1)

        found = _index(text, "chapter 1", min_char_offset=second).occurrences_for_label(
            label="Chapter 1"
        )

        assert [o.char_offset for o in found] == [second]


class TestTableOfContentsRejection:
    def test_a_dotted_leader_line_is_not_indexed(self) -> None:
        text = "Chapter 1 . . . . 12\n"

        assert _index(text, "chapter 1").occurrences_for_label(label="Chapter 1") == []

    def test_an_outline_number_above_a_leader_below_marks_a_toc_entry(self) -> None:
        text = "1.2\nChapter 3\n. . . .\n"

        assert _index(text, "chapter 3").occurrences_for_label(label="Chapter 3") == []

    def test_an_outline_number_without_leader_evidence_is_not_enough(self) -> None:
        text = "1.2\nChapter 3\nordinary prose follows\n"

        found = _index(text, "chapter 3").occurrences_for_label(label="Chapter 3")

        assert len(found) == 1

    def test_a_leader_only_line_below_marks_a_toc_entry(self) -> None:
        text = "Chapter 4\n. . . .\nbody\n"

        assert _index(text, "chapter 4").occurrences_for_label(label="Chapter 4") == []


class TestPrecedence:
    def test_a_wrapped_heading_is_used_when_there_is_no_exact_line(self) -> None:
        text = "Chapter 1:\nThe Beginning\n\nprose\n"

        found = _index(text, "chapter 1: the beginning").occurrences_for_label(
            label="Chapter 1: The Beginning"
        )

        assert [o.label for o in found] == ["Chapter 1: The Beginning"]

    def test_a_marker_line_is_used_when_nothing_else_matches(self) -> None:
        text = "Chapter 2\n\nprose here\n"

        found = _index(text, "chapter 2").occurrences_for_label(
            label="Chapter 2: Something Else"
        )

        assert [o.label for o in found] == ["Chapter 2"]

    def test_a_hyphenated_wrap_is_joined_without_a_space(self) -> None:
        text = "Introduc-\ntion\n\nprose\n"

        found = _index(text, "introduction").occurrences_for_label(label="Introduction")

        assert [o.label for o in found] == ["Introduction"]

    def test_a_blank_label_matches_nothing(self) -> None:
        built = _index("Chapter 1\n", "chapter 1")

        assert built.occurrences_for(cleaned_label="   ", prefix_norm=None) == []

    def test_an_unknown_label_matches_nothing(self) -> None:
        built = _index("Chapter 1\n", "chapter 1")

        assert built.occurrences_for(cleaned_label="Chapter 9", prefix_norm=None) == []


class TestDegradedInput:
    def test_a_failure_cleaning_the_marker_prefix_leaves_the_lookup_working(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The handler exists so a cleaning failure cannot lose an exact match.

        It is not reachable from real input, since every call inside it is pure
        string work, so forcing the failure is the only way to show it holds.
        """

        built = _index("Chapter 2: Something\n\nprose\n", "chapter 2: something")
        real = occurrence_index.clean_heading_label

        def exploding(label: str) -> str:
            if str(label).strip() == "Chapter 2":
                raise RuntimeError("cleaning failed")
            return real(label)

        monkeypatch.setattr(occurrence_index, "clean_heading_label", exploding)

        found = built.occurrences_for_label(label="Chapter 2: Something")

        assert [o.char_offset for o in found] == [0]
