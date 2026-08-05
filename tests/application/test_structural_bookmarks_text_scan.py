"""Scanning raw book text for lines that look like structural headings.

The scanner runs over every line of a book, so it is deliberately cheap and
deliberately permissive: any short line with blank space on both sides is
offered as a candidate, and classification decides later whether to keep it.
The interesting behaviour is what happens to a line that is NOT blank-bounded,
because that line is only promoted when it matches a strong marker pattern or
reads as a title-case heading.
"""

from __future__ import annotations

from voice_reader.application.services.structural_bookmarks.text_scan import (
    looks_like_paragraph_line,
    scan_structural_headings,
)


def _labels(text: str) -> list[str]:
    return [c.label for c in scan_structural_headings(normalized_text=text)]


def _one_blank_above(line: str) -> str:
    """A line with whitespace above and prose below, so only the line matters."""

    return f"\n\n{line}\nprose below\n"


class TestEmptyInput:
    def test_no_text_yields_no_candidates(self) -> None:
        assert scan_structural_headings(normalized_text="") == []


class TestStrongMarkers:
    def test_a_chapter_line_is_promoted_without_surrounding_blanks(self) -> None:
        assert _labels("Chapter 1: Start\nprose follows\n") == ["Chapter 1: Start"]

    def test_a_marker_word_on_its_own_is_promoted(self) -> None:
        assert _labels("Prologue\nprose follows\n") == ["Prologue"]

    def test_the_candidate_records_the_line_offset(self) -> None:
        text = "prose first\n\nChapter 1: Start\n\nmore prose\n"

        found = scan_structural_headings(normalized_text=text)
        chapter = next(c for c in found if c.label == "Chapter 1: Start")

        assert chapter.char_offset == text.index("Chapter 1")
        assert chapter.source == "text_scan"
        assert chapter.chunk_index is None


class TestLineRejection:
    def test_a_very_long_line_is_never_a_heading(self) -> None:
        long_line = "Word " * 40

        assert _labels(f"\n\n{long_line.strip()}\n\n") == []

    def test_a_comma_heavy_line_is_treated_as_prose(self) -> None:
        assert _labels("\n\napples, pears, plums, figs\n\n") == []

    def test_a_line_ending_in_a_full_stop_is_treated_as_prose(self) -> None:
        assert _labels("\n\nsomething happened here.\n\n") == []

    def test_an_unbounded_plain_line_is_not_a_heading(self) -> None:
        assert _labels("prose above\nsomething plain\nprose below\n") == []


class TestTitleCaseHeadings:
    def test_a_title_case_line_beside_whitespace_is_promoted(self) -> None:
        assert "Decision Attractor Diagrams" in _labels(
            _one_blank_above("Decision Attractor Diagrams")
        )

    def test_an_acronym_counts_as_title_case(self) -> None:
        assert "API Design Notes" in _labels(_one_blank_above("API Design Notes"))

    def test_a_numeral_counts_as_title_case(self) -> None:
        assert "Decision Attractor Diagrams 2" in _labels(
            _one_blank_above("Decision Attractor Diagrams 2")
        )

    def test_a_micro_structure_label_is_refused(self) -> None:
        assert "Implication" not in _labels(_one_blank_above("Implication"))

    def test_a_line_carrying_a_relation_character_is_refused(self) -> None:
        line = "Curvature: incentive gradient"

        assert line not in _labels(_one_blank_above(line))

    def test_an_equation_like_line_is_refused(self) -> None:
        line = "Speed Is Distance > Time Taken"

        assert line not in _labels(_one_blank_above(line))

    def test_a_line_of_mostly_lowercase_words_is_refused(self) -> None:
        line = "some plain words here"

        assert line not in _labels(_one_blank_above(line))


class TestWrappedHeadings:
    def test_a_heading_continued_on_the_next_line_is_joined(self) -> None:
        text = "Chapter 1: Advanced Decision\nMaking Systems Today\n\nprose\n"

        assert "Chapter 1: Advanced Decision Making Systems Today" in _labels(text)

    def test_a_hyphenated_break_is_joined_without_a_space(self) -> None:
        text = "Chapter 1: Advanced Deci-\nSion Making Systems\n\nprose\n"

        assert "Chapter 1: Advanced DeciSion Making Systems" in _labels(text)

    def test_a_bare_marker_does_not_swallow_the_line_below(self) -> None:
        assert _labels("Chapter 3\nBody text starts here now\n") == ["Chapter 3"]

    def test_a_marker_line_whose_title_wrapped_is_not_itself_a_candidate(self) -> None:
        # "Chapter 3:" is not a complete marker and has prose below it, so the
        # title line beneath is what gets promoted.
        labels = _labels("Chapter 3:\nThe Long Title Here\n\nprose\n")

        assert "Chapter 3:" not in labels
        assert "The Long Title Here" in labels

    def test_joining_stops_at_the_next_structural_marker(self) -> None:
        text = "Chapter 1: First Title\nChapter 2: Second Title\n"

        assert _labels(text) == ["Chapter 1: First Title", "Chapter 2: Second Title"]

    def test_joining_stops_at_a_page_number(self) -> None:
        assert _labels("Chapter 1: First Title\n12\n") == ["Chapter 1: First Title"]

    def test_joining_stops_at_a_leader_run(self) -> None:
        assert _labels("Chapter 1: First Title\n. . . .\n") == [
            "Chapter 1: First Title"
        ]

    def test_joining_stops_at_prose(self) -> None:
        text = "Chapter 1: First Title\nthis is a proper sentence.\n"

        assert _labels(text) == ["Chapter 1: First Title"]

    def test_joining_stops_at_a_dotted_leader_tail(self) -> None:
        # The tail is still offered on its own; what matters is that it was not
        # absorbed into the chapter label.
        text = "Chapter 1: First Title\nSomething Here .. 12\n"

        assert "Chapter 1: First Title" in _labels(text)

    def test_joining_stops_at_an_over_long_line(self) -> None:
        long_line = ("Continued " * 20).strip()

        assert _labels(f"Chapter 1: First Title\n{long_line}\n") == [
            "Chapter 1: First Title"
        ]

    def test_a_heading_on_the_final_line_has_nothing_to_join(self) -> None:
        assert _labels("Chapter 1: First Title") == ["Chapter 1: First Title"]


class TestParagraphDetection:
    def test_a_blank_line_is_not_a_paragraph(self) -> None:
        assert looks_like_paragraph_line("") is False

    def test_a_very_short_line_is_not_a_paragraph(self) -> None:
        assert looks_like_paragraph_line("Two words") is False

    def test_an_all_capitals_line_is_not_a_paragraph(self) -> None:
        assert looks_like_paragraph_line("THIS IS SHOUTING") is False

    def test_a_sentence_ending_in_a_full_stop_is_a_paragraph(self) -> None:
        assert looks_like_paragraph_line("this ends properly.") is True

    def test_a_long_line_is_a_paragraph(self) -> None:
        assert looks_like_paragraph_line("word " * 20) is True

    def test_a_short_unpunctuated_line_is_not_a_paragraph(self) -> None:
        assert looks_like_paragraph_line("some short line here") is False
