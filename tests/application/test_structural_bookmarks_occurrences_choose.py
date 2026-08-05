"""`choose_best_occurrence`: which of several matches a bookmark should use.

Reading-start detectors return the first prose offset, which is usually just
after the heading line rather than on it. The chooser therefore allows a
heading to sit slightly before the preferred cut, and only falls back to a
much earlier candidate when there is nothing else.
"""

from __future__ import annotations

from voice_reader.application.services.structural_bookmarks.occurrences import (
    choose_best_occurrence,
)
from voice_reader.application.services.structural_bookmarks.types import (
    HeadingOccurrence,
)

# The chooser tolerates a heading this far before the preferred cut.
SOFT_ALLOWANCE = 250


def _occurrence(
    offset: int, *, prev_blank: bool = False, next_blank: bool = False
) -> HeadingOccurrence:
    return HeadingOccurrence(
        char_offset=offset,
        label="Heading",
        prev_blank=prev_blank,
        next_blank=next_blank,
    )


def _choose(occurrences, *, kind: str, cut: int):
    return choose_best_occurrence(
        label="Heading", kind=kind, occurrences=occurrences, prefer_min_offset=cut
    )


class TestNothingToChoose:
    def test_no_occurrences_yields_nothing(self) -> None:
        assert _choose([], kind="chapter", cut=1000) is None


class TestChapterAndPart:
    def test_a_heading_just_before_the_cut_beats_a_later_duplicate(self) -> None:
        near = _occurrence(900)
        later = _occurrence(5000)

        chosen = _choose([later, near], kind="chapter", cut=1000)

        assert chosen is near

    def test_the_earliest_near_candidate_wins(self) -> None:
        first = _occurrence(800)
        second = _occurrence(950)

        chosen = _choose([second, first], kind="part", cut=1000)

        assert chosen is first

    def test_the_earliest_candidate_after_the_cut_wins_when_none_is_near(
        self,
    ) -> None:
        early = _occurrence(10)
        first_after = _occurrence(2000)
        later = _occurrence(9000)

        chosen = _choose([later, first_after, early], kind="chapter", cut=1000)

        assert chosen is first_after

    def test_a_far_earlier_candidate_is_the_last_resort(self) -> None:
        only = _occurrence(10)

        chosen = _choose([only], kind="chapter", cut=1000)

        assert chosen is only

    def test_the_last_resort_prefers_a_heading_framed_by_blank_lines(self) -> None:
        plain = _occurrence(10)
        one_side = _occurrence(20, prev_blank=True)
        framed = _occurrence(30, prev_blank=True, next_blank=True)

        chosen = _choose([plain, one_side, framed], kind="chapter", cut=1000)

        assert chosen is framed

    def test_the_last_resort_breaks_a_tie_on_the_later_offset(self) -> None:
        earlier = _occurrence(10, prev_blank=True)
        later = _occurrence(20, prev_blank=True)

        chosen = _choose([earlier, later], kind="chapter", cut=1000)

        assert chosen is later


class TestOtherKinds:
    def test_a_heading_just_before_the_cut_beats_a_later_duplicate(self) -> None:
        near = _occurrence(900)
        in_the_index = _occurrence(50000)

        chosen = _choose([in_the_index, near], kind="prologue", cut=1000)

        assert chosen is near

    def test_the_earliest_candidate_after_the_cut_wins_when_none_is_near(
        self,
    ) -> None:
        early = _occurrence(10)
        first_after = _occurrence(1500)

        chosen = _choose([first_after, early], kind="introduction", cut=1000)

        assert chosen is first_after

    def test_a_far_earlier_candidate_is_the_last_resort(self) -> None:
        plain = _occurrence(10)
        framed = _occurrence(20, prev_blank=True, next_blank=True)

        chosen = _choose([plain, framed], kind="appendix", cut=1000)

        assert chosen is framed


class TestTheSoftBoundary:
    def test_a_candidate_exactly_at_the_allowance_still_counts_as_near(self) -> None:
        cut = 1000
        at_edge = _occurrence(cut - SOFT_ALLOWANCE)
        later = _occurrence(5000)

        chosen = _choose([later, at_edge], kind="chapter", cut=cut)

        assert chosen is at_edge

    def test_a_candidate_one_character_beyond_the_allowance_does_not(self) -> None:
        cut = 1000
        beyond = _occurrence(cut - SOFT_ALLOWANCE - 1)
        later = _occurrence(5000)

        chosen = _choose([later, beyond], kind="chapter", cut=cut)

        assert chosen is later

    def test_a_negative_cut_is_treated_as_zero(self) -> None:
        first = _occurrence(0)
        second = _occurrence(100)

        chosen = _choose([second, first], kind="chapter", cut=-500)

        assert chosen is first
