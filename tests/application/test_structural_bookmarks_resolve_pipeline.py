"""Resolving heading candidates into placed structural bookmarks.

Candidates arrive from three sources with three different ideas of where a
heading is: the nav gives a label with no offset, the chapter parser gives an
offset that may predate the body, and the text scan gives a line. This is where
those are reconciled against the document's own body boundary.
"""

from __future__ import annotations

from dataclasses import dataclass

from voice_reader.application.services.structural_bookmarks.resolve_pipeline import (
    resolve_structural_bookmarks,
)
from voice_reader.application.services.structural_bookmarks.types import (
    RawHeadingCandidate,
)

FRONT = "Contents\n\nsome front matter\n\n"
BODY = "Chapter 1: The Beginning\n\nreal prose starts here and runs on.\n"
TEXT = FRONT + BODY
BODY_START = len(FRONT)


@dataclass(frozen=True, slots=True)
class FakeChunk:
    start_char: object
    end_char: object


def _candidate(
    label: str,
    *,
    offset: int | None = None,
    chunk: int | None = None,
    source: str = "nav",
) -> RawHeadingCandidate:
    return RawHeadingCandidate(
        label=label, char_offset=offset, chunk_index=chunk, source=source
    )


def _resolve(
    candidates,
    *,
    text: str = TEXT,
    chunks=None,
    min_char_offset=None,
    body_start_offset: int = 0,
    front_matter_present: bool = False,
    toc_end_offset=None,
    prefer_min_offset: int = 0,
    min_anchor_offset: int = 0,
):
    return resolve_structural_bookmarks(
        text=text,
        raw_candidates=list(candidates),
        chunks=chunks,
        min_char_offset=min_char_offset,
        body_start_offset=body_start_offset,
        front_matter_present=front_matter_present,
        toc_end_offset=toc_end_offset,
        prefer_min_offset=prefer_min_offset,
        min_anchor_offset=min_anchor_offset,
    )


class TestCandidateFiltering:
    def test_a_heading_found_in_the_text_is_placed(self) -> None:
        out = _resolve([_candidate("Chapter 1: The Beginning")])

        assert [(b.kind, b.char_offset) for b in out] == [
            ("chapter", TEXT.index("Chapter 1"))
        ]

    def test_a_blank_label_is_dropped(self) -> None:
        assert _resolve([_candidate("   ")]) == []

    def test_a_front_matter_label_is_dropped(self) -> None:
        assert _resolve([_candidate("Contents")]) == []

    def test_a_chapter_with_no_occurrence_in_the_text_is_dropped(self) -> None:
        assert _resolve([_candidate("Chapter 9: Missing", offset=0)]) == []


class TestOffsetSelection:
    def test_a_parser_offset_earlier_than_the_text_match_wins(self) -> None:
        text = "Prologue\n\nprose one.\n\nPrologue\n\nprose two.\n"
        second = text.index("Prologue", 1)

        out = _resolve(
            [_candidate("Prologue", offset=0)],
            text=text,
            prefer_min_offset=0,
        )

        assert [b.char_offset for b in out] == [0]
        assert second > 0

    def test_a_parser_offset_is_used_when_no_text_match_survives(self) -> None:
        # "Preface" never appears as a line, so only the parser offset places it.
        out = _resolve(
            [_candidate("Preface", offset=BODY_START)],
            prefer_min_offset=len(TEXT),
        )

        assert [b.char_offset for b in out] == [BODY_START]

    def test_an_offset_inside_the_contents_is_ignored(self) -> None:
        out = _resolve(
            [_candidate("Preface", offset=1)],
            toc_end_offset=BODY_START,
            prefer_min_offset=len(TEXT),
        )

        assert out == []

    def test_a_chapter_offset_before_the_body_is_ignored(self) -> None:
        out = _resolve(
            [_candidate("Chapter 1: The Beginning", offset=1)],
            body_start_offset=BODY_START,
        )

        assert [b.char_offset for b in out] == [TEXT.index("Chapter 1")]

    def test_a_heading_resolved_before_the_body_is_refused(self) -> None:
        text = "Prologue\n\nfront matter prose.\n\nlater body prose here.\n"

        out = _resolve(
            [_candidate("Prologue", offset=0)],
            text=text,
            body_start_offset=len(text) - 10,
            front_matter_present=True,
        )

        assert out == []


class TestPreferredBoundary:
    def test_a_parser_offset_before_the_text_line_is_preferred(self) -> None:
        text = "front\n\nPreface\n\nprose here.\n"

        out = _resolve([_candidate("Preface", offset=0)], text=text)

        assert [b.char_offset for b in out] == [0]
        assert text.index("Preface") > 0

    def test_a_text_line_before_the_boundary_is_used_as_a_last_resort(self) -> None:
        text = "Prologue\n\nprose here.\n"

        out = _resolve([_candidate("Prologue")], text=text, prefer_min_offset=1000)

        assert [b.char_offset for b in out] == [0]


class TestMergingNeighbours:
    TEXT = "Chapter 1\n\nChapter 1: The Beginning\n\nprose here.\n"

    def test_a_marker_and_its_full_title_collapse_into_one(self) -> None:
        out = _resolve(
            [
                _candidate("Chapter 1", offset=0),
                _candidate("Chapter 1: The Beginning"),
            ],
            text=self.TEXT,
        )

        assert [(b.label, b.char_offset) for b in out] == [
            ("Chapter 1: The Beginning", 0)
        ]

    def test_two_unrelated_headings_are_both_kept(self) -> None:
        text = "Prologue\n\nprose one.\n\nChapter 1: The Beginning\n\nprose two.\n"

        out = _resolve(
            [_candidate("Prologue"), _candidate("Chapter 1: The Beginning")],
            text=text,
        )

        assert [b.kind for b in out] == ["prologue", "chapter"]


class TestChunkResolution:
    def test_a_chunk_index_is_attached_when_chunks_are_known(self) -> None:
        chunks = [FakeChunk(0, len(TEXT))]

        out = _resolve([_candidate("Chapter 1: The Beginning")], chunks=chunks)

        assert [b.chunk_index for b in out] == [0]

    def test_a_chunk_less_candidate_is_placed_from_its_chunk_index(self) -> None:
        chunks = [FakeChunk(0, BODY_START), FakeChunk(BODY_START, len(TEXT))]

        out = _resolve(
            [_candidate("Preface", chunk=1)],
            chunks=chunks,
            prefer_min_offset=len(TEXT),
        )

        assert [b.char_offset for b in out] == [BODY_START]

    def test_a_chunk_ending_before_the_minimum_drops_the_bookmark(self) -> None:
        chunks = [FakeChunk(0, 10), FakeChunk(10, len(TEXT))]

        out = _resolve(
            [_candidate("Chapter 1: The Beginning")],
            chunks=chunks,
            min_char_offset=len(TEXT) + 1,
        )

        assert out == []

    def test_an_unusable_chunk_end_is_not_fatal(self) -> None:
        # The chunk starts after the offset, so the index resolves without ever
        # reading `end_char`; the minimum-offset check is what trips over it.
        chunks = [FakeChunk(len(TEXT), "bad")]

        out = _resolve(
            [_candidate("Chapter 1: The Beginning")],
            chunks=chunks,
            min_char_offset=0,
        )

        assert [(b.kind, b.chunk_index) for b in out] == [("chapter", 0)]
