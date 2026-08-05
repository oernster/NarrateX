"""Deduplication of heading candidates arriving from several sources.

The same heading is commonly reported by the EPUB nav, by the chapter parser
and by the raw text scan. They are merged per label, then clustered by
proximity so that a label which genuinely appears twice in a book stays twice.
"""

from __future__ import annotations

from voice_reader.application.services.structural_bookmarks.dedupe import (
    CLUSTER_DISTANCE_CHARS,
    UNKNOWN_OFFSET_SORT_KEY,
    dedupe_candidates,
)
from voice_reader.application.services.structural_bookmarks.types import (
    RawHeadingCandidate,
)


def _candidate(
    label: str,
    *,
    offset: int | None = 0,
    chunk: int | None = None,
    source: str = "text_scan",
) -> RawHeadingCandidate:
    return RawHeadingCandidate(
        label=label, char_offset=offset, chunk_index=chunk, source=source
    )


class TestSourcePreference:
    def test_the_navigation_source_beats_the_text_scan(self) -> None:
        scanned = _candidate("Chapter 1", offset=100, source="text_scan")
        from_nav = _candidate("Chapter 1", offset=120, source="nav")

        kept = dedupe_candidates(candidates=[scanned, from_nav])

        assert kept == [from_nav]

    def test_an_unrecognised_source_sits_between_the_two_known_ones(self) -> None:
        scanned = _candidate("Chapter 1", offset=100, source="text_scan")
        unknown = _candidate("Chapter 1", offset=120, source="somewhere_else")
        from_nav = _candidate("Chapter 1", offset=140, source="nav")

        assert dedupe_candidates(candidates=[scanned, unknown]) == [unknown]
        assert dedupe_candidates(candidates=[unknown, from_nav]) == [from_nav]

    def test_a_candidate_without_an_offset_is_never_merged_into_a_placed_one(
        self,
    ) -> None:
        # An offset-less candidate cannot be measured against anything, so it
        # forms its own cluster and survives alongside the placed one.
        placed = _candidate("Prologue", offset=500, source="text_scan")
        unplaced = _candidate("Prologue", offset=None, source="nav")

        kept = dedupe_candidates(candidates=[unplaced, placed])

        assert sorted(kept, key=lambda c: c.source) == sorted(
            [placed, unplaced], key=lambda c: c.source
        )

    def test_a_known_chunk_index_breaks_a_tie(self) -> None:
        without = _candidate("Prologue", offset=100, chunk=None)
        with_chunk = _candidate("Prologue", offset=100, chunk=7)

        assert dedupe_candidates(candidates=[without, with_chunk]) == [with_chunk]


class TestClustering:
    def test_two_nearby_reports_collapse_to_one(self) -> None:
        first = _candidate("Prologue", offset=1000)
        near = _candidate("Prologue", offset=1000 + CLUSTER_DISTANCE_CHARS)

        assert len(dedupe_candidates(candidates=[first, near])) == 1

    def test_two_distant_occurrences_are_both_kept(self) -> None:
        first = _candidate("Prologue", offset=1000)
        far = _candidate("Prologue", offset=1000 + CLUSTER_DISTANCE_CHARS + 1)

        kept = dedupe_candidates(candidates=[first, far])

        assert sorted(c.char_offset for c in kept) == [
            first.char_offset,
            far.char_offset,
        ]

    def test_each_offset_less_candidate_stands_alone(self) -> None:
        one = _candidate("Prologue", offset=None, source="nav")
        two = _candidate("Prologue", offset=None, source="chapter_parser")

        assert len(dedupe_candidates(candidates=[one, two])) == 2

    def test_an_offset_at_the_sort_sentinel_starts_its_own_cluster(self) -> None:
        # Offset-less candidates sort at the sentinel, so a real offset above it
        # lands after them and cannot be measured against the previous cluster.
        unplaced = _candidate("Prologue", offset=None)
        beyond = _candidate("Prologue", offset=UNKNOWN_OFFSET_SORT_KEY + 1)

        assert len(dedupe_candidates(candidates=[unplaced, beyond])) == 2

    def test_different_labels_are_never_merged(self) -> None:
        one = _candidate("Chapter 1", offset=100)
        two = _candidate("Chapter 2", offset=110)

        assert len(dedupe_candidates(candidates=[one, two])) == 2

    def test_a_candidate_with_no_usable_label_is_dropped(self) -> None:
        blank = _candidate("   ", offset=100)
        real = _candidate("Chapter 1", offset=200)

        assert dedupe_candidates(candidates=[blank, real]) == [real]

    def test_no_candidates_yields_nothing(self) -> None:
        assert dedupe_candidates(candidates=[]) == []
