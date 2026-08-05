"""Classifying a heading label into a kind, plus the two helpers around it.

Order matters here: the title-case heuristic runs before the single-word kinds,
so "Appendix" reaches the appendix rule only because one word is too few to
look like a title-case section.
"""

from __future__ import annotations

import pytest

from voice_reader.application.services.structural_bookmarks import candidate_scan
from voice_reader.application.services.structural_bookmarks.candidate_scan import (
    extract_heading_labels_from_text,
)
from voice_reader.application.services.structural_bookmarks.classification import (
    classify_heading,
)
from voice_reader.application.services.structural_bookmarks.normalization import (
    clean_heading_label,
)
from voice_reader.application.services.structural_bookmarks.types import (
    RawHeadingCandidate,
)


class TestUnusableLabels:
    @pytest.mark.parametrize("label", ["", "   ", "\n\t"])
    def test_a_blank_label_classifies_as_nothing(self, label: str) -> None:
        assert classify_heading(label) == (None, False, 0)


class TestSingleWordKinds:
    @pytest.mark.parametrize(
        "label,kind",
        [
            ("Prologue", "prologue"),
            ("Introduction", "introduction"),
            ("Preface", "preface"),
            ("Appendix", "appendix"),
            ("Epilogue", "epilogue"),
            ("Conclusion", "conclusion"),
            ("Afterword", "afterword"),
        ],
    )
    def test_the_kind_is_recognised_and_included(self, label: str, kind: str) -> None:
        found_kind, include, priority = classify_heading(label)

        assert (found_kind, include) == (kind, True)
        assert priority > 0

    @pytest.mark.parametrize(
        "label", ["Contents", "Table of Contents", "Index", "Summary", "Dedication"]
    )
    def test_front_matter_is_excluded(self, label: str) -> None:
        assert classify_heading(label) == (None, False, 0)


class TestTitleCaseSections:
    def test_a_title_case_line_becomes_a_section(self) -> None:
        assert classify_heading("Decision Attractor Diagrams")[:2] == ("section", True)

    def test_an_acronym_counts_as_a_title_word(self) -> None:
        assert classify_heading("API Design Notes")[:2] == ("section", True)

    def test_a_punctuation_only_word_is_ignored_when_scoring(self) -> None:
        assert classify_heading("Design & Systems")[:2] == ("section", True)

    def test_a_micro_structure_label_is_not_a_section(self) -> None:
        assert classify_heading("Implication") == (None, False, 0)

    def test_an_equation_like_line_is_not_a_section(self) -> None:
        assert classify_heading("Speed Is Distance > Time Taken") == (None, False, 0)

    def test_a_single_word_is_not_a_section(self) -> None:
        assert classify_heading("Notational") == (None, False, 0)


class TestOverlongLabels:
    def test_a_very_long_label_is_returned_with_only_whitespace_collapsed(
        self,
    ) -> None:
        long_label = "  " + ("word " * 200).strip() + "  "

        cleaned = clean_heading_label(long_label)

        assert len(cleaned) > 500
        assert cleaned == long_label.strip()


class TestLabelExtraction:
    def test_only_classifiable_headings_are_returned(self) -> None:
        text = "\n\nChapter 1: Start\n\nsome prose here\n\nContents\n\n"

        assert extract_heading_labels_from_text(normalized_text=text) == [
            "Chapter 1: Start"
        ]

    def test_the_same_heading_twice_is_returned_once(self) -> None:
        text = "Chapter 1: Start\nprose\n\nChapter 1: Start\nmore prose\n"

        assert extract_heading_labels_from_text(normalized_text=text) == [
            "Chapter 1: Start"
        ]

    def test_a_candidate_with_no_usable_label_is_skipped(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def only_blanks(*, normalized_text: str) -> list[RawHeadingCandidate]:
            del normalized_text
            return [
                RawHeadingCandidate(
                    label="   ", char_offset=0, chunk_index=None, source="text_scan"
                )
            ]

        monkeypatch.setattr(candidate_scan, "scan_structural_headings", only_blanks)

        assert extract_heading_labels_from_text(normalized_text="anything") == []
