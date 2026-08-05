"""`find_exact_heading_occurrences`: which body line a heading label binds to.

The function has one hard requirement: never bind a structural bookmark to a
Table-of-Contents copy of the heading. Everything else is about recovering the
heading when a PDF has broken it across two lines.
"""

from __future__ import annotations

import pytest

from voice_reader.application.services.structural_bookmarks import occurrences
from voice_reader.application.services.structural_bookmarks.occurrences import (
    find_exact_heading_occurrences,
)


def _find(text: str, label: str, **kwargs) -> list:
    return find_exact_heading_occurrences(normalized_text=text, label=label, **kwargs)


class TestNothingToMatch:
    def test_empty_text_returns_no_occurrences(self) -> None:
        assert _find("", "Chapter 1") == []

    def test_empty_label_returns_no_occurrences(self) -> None:
        assert _find("Chapter 1\n", "") == []

    def test_label_that_cleans_away_returns_no_occurrences(self) -> None:
        assert _find("Chapter 1\n", "   ") == []


class TestExactLineMatch:
    def test_a_heading_between_blanks_is_found_with_its_offset(self) -> None:
        found = _find("Chapter 1\n\nSome prose here.\n", "Chapter 1")

        assert len(found) == 1
        assert found[0].char_offset == 0
        assert found[0].label == "Chapter 1"
        assert found[0].prev_blank is True
        assert found[0].next_blank is True

    def test_a_heading_on_the_final_line_reports_the_end_as_blank(self) -> None:
        found = _find("prose\n\nChapter 6", "Chapter 6")

        assert len(found) == 1
        assert found[0].next_blank is True

    def test_a_heading_surrounded_by_prose_reports_neither_side_blank(self) -> None:
        found = _find("prose before\nChapter 5\nprose after\n", "Chapter 5")

        assert len(found) == 1
        assert found[0].prev_blank is False
        assert found[0].next_blank is False

    def test_every_occurrence_is_returned_in_document_order(self) -> None:
        text = "Chapter 1\n\nfoo\n\nChapter 1\n\nbar\n"

        offsets = [o.char_offset for o in _find(text, "Chapter 1")]

        assert offsets == sorted(offsets)
        assert len(offsets) == 2


class TestMinimumOffset:
    def test_occurrences_before_the_minimum_are_skipped(self) -> None:
        text = "Chapter 1\n\nfoo\n\nChapter 1\n\nbar\n"
        first, second = [o.char_offset for o in _find(text, "Chapter 1")]

        found = _find(text, "Chapter 1", min_char_offset=first + 1)

        assert [o.char_offset for o in found] == [second]

    def test_a_negative_minimum_is_treated_as_zero(self) -> None:
        found = _find("Chapter 1\n\nprose\n", "Chapter 1", min_char_offset=-500)

        assert [o.char_offset for o in found] == [0]


class TestTableOfContentsRejection:
    def test_a_line_carrying_a_dotted_leader_is_never_bound(self) -> None:
        text = "Chapter 1 . . . . 12\n\nChapter 1\n\nprose\n"

        found = _find(text, "Chapter 1")

        assert len(found) == 1
        assert found[0].char_offset > 0

    def test_an_outline_number_above_a_leader_below_marks_a_toc_entry(self) -> None:
        text = "1.2\nChapter 3\n. . . .\n"

        assert _find(text, "Chapter 3") == []

    def test_an_outline_number_without_leader_evidence_is_not_enough(self) -> None:
        text = "1.2\nChapter 3\nordinary prose follows\n"

        found = _find(text, "Chapter 3")

        assert len(found) == 1

    def test_a_leader_only_line_below_marks_a_toc_entry(self) -> None:
        text = "Chapter 4\n. . . .\nbody\n"

        assert _find(text, "Chapter 4") == []

    def test_a_page_number_alone_below_is_not_enough(self) -> None:
        text = "Chapter 7\n12\nbody text continues here\n"

        found = _find(text, "Chapter 7")

        assert len(found) == 1


class TestWrappedHeadings:
    def test_a_heading_split_across_two_lines_anchors_to_the_first(self) -> None:
        text = "Chapter 1:\nThe Beginning\n\nprose\n"

        found = _find(text, "Chapter 1: The Beginning")

        assert len(found) == 1
        assert found[0].char_offset == 0
        assert found[0].label == "Chapter 1: The Beginning"

    def test_a_hyphenated_split_is_joined_without_a_space(self) -> None:
        text = "Introduc-\ntion\n\nprose\n"

        found = _find(text, "Introduction")

        assert len(found) == 1
        assert found[0].char_offset == 0
        assert found[0].label == "Introduction"

    def test_an_exact_match_wins_over_a_wrapped_one(self) -> None:
        text = "Chapter 1:\nThe Beginning\n\nChapter 1: The Beginning\n\nprose\n"

        found = _find(text, "Chapter 1: The Beginning")

        assert len(found) == 1
        assert found[0].char_offset > 0


class TestMarkerLineFallback:
    def test_a_bare_chapter_marker_is_used_when_nothing_else_matches(self) -> None:
        text = "Chapter 2\n\nprose here\n"

        found = _find(text, "Chapter 2: Something Else")

        assert len(found) == 1
        assert found[0].char_offset == 0
        assert found[0].label == "Chapter 2"

    def test_a_missing_separator_is_supplied_before_the_marker_is_taken(self) -> None:
        # Cleaning rewrites "Chapter 2 Something Else" to "Chapter 2: Something
        # Else", so the marker fallback still applies.
        text = "Chapter 2\n\nprose here\n"

        found = _find(text, "Chapter 2 Something Else")

        assert [o.label for o in found] == ["Chapter 2"]

    def test_a_label_that_is_not_a_chapter_gets_no_marker_fallback(self) -> None:
        text = "Prologue\n\nprose here\n"

        assert _find(text, "Prologue Extra Words") == []

    def test_a_marker_line_that_is_a_toc_entry_is_rejected(self) -> None:
        text = "Chapter 2\n. . . .\n"

        assert _find(text, "Chapter 2: Something Else") == []

    def test_a_marker_that_does_not_classify_as_a_chapter_is_ignored(self) -> None:
        text = "Contents\n\nprose here\n"

        assert _find(text, "Contents: Something Else") == []


class TestDegradedInput:
    """The two broad handlers exist so a cleaning failure cannot lose a match.

    Neither path is reachable from real input, since every call inside them is
    pure string work. Forcing the failure is the only way to show the handler
    does what it claims.
    """

    def test_a_failure_cleaning_the_marker_prefix_leaves_the_scan_running(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        real = occurrences.clean_heading_label

        def exploding(label: str) -> str:
            if str(label).strip() == "Chapter 2":
                raise RuntimeError("cleaning failed")
            return real(label)

        monkeypatch.setattr(occurrences, "clean_heading_label", exploding)

        # The marker fallback is abandoned, and the exact match is still found.
        found = _find("Chapter 2: Something\n\nprose\n", "Chapter 2: Something")

        assert [o.char_offset for o in found] == [0]

    def test_a_failure_joining_a_wrapped_heading_leaves_the_scan_running(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        real = occurrences.clean_heading_label
        seen = {"joins": 0}

        def exploding(label: str) -> str:
            # The label and the joined pair are the same string, so the first
            # call (cleaning the label itself) has to be let through.
            if str(label).strip() == "Alpha Beta":
                seen["joins"] += 1
                if seen["joins"] > 1:
                    raise RuntimeError("cleaning failed")
            return real(label)

        monkeypatch.setattr(occurrences, "clean_heading_label", exploding)

        assert _find("Alpha\nBeta\n\nprose\n", "Alpha Beta") == []
        assert seen["joins"] > 1
