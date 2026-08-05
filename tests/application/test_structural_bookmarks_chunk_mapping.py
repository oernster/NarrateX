"""Mapping between character offsets and chunk indices.

Both directions are deliberately total: every failure returns ``None`` rather
than raising, because a structural bookmark that cannot be placed should be
dropped quietly instead of stopping playback.
"""

from __future__ import annotations

from dataclasses import dataclass

from voice_reader.application.services.structural_bookmarks.chunk_mapping import (
    resolve_char_offset_for_chunk_index,
    resolve_chunk_index_for_offset,
)


@dataclass(frozen=True, slots=True)
class FakeChunk:
    """Stands in for a TextChunk; only the two boundaries are read."""

    start_char: object
    end_char: object


def _chunks() -> list[FakeChunk]:
    return [FakeChunk(0, 100), FakeChunk(100, 250), FakeChunk(250, 400)]


class TestOffsetForChunkIndex:
    def test_a_valid_index_gives_the_chunk_start(self) -> None:
        assert (
            resolve_char_offset_for_chunk_index(chunk_index=1, chunks=_chunks()) == 100
        )

    def test_no_chunks_gives_nothing(self) -> None:
        assert resolve_char_offset_for_chunk_index(chunk_index=0, chunks=None) is None

    def test_an_empty_sequence_gives_nothing(self) -> None:
        assert resolve_char_offset_for_chunk_index(chunk_index=0, chunks=[]) is None

    def test_an_unusable_index_gives_nothing(self) -> None:
        assert (
            resolve_char_offset_for_chunk_index(chunk_index="two", chunks=_chunks())
            is None
        )

    def test_a_negative_index_gives_nothing(self) -> None:
        assert (
            resolve_char_offset_for_chunk_index(chunk_index=-1, chunks=_chunks())
            is None
        )

    def test_an_index_past_the_end_gives_nothing(self) -> None:
        assert (
            resolve_char_offset_for_chunk_index(chunk_index=3, chunks=_chunks()) is None
        )

    def test_an_unusable_chunk_boundary_gives_nothing(self) -> None:
        chunks = [FakeChunk("not a number", 100)]

        assert resolve_char_offset_for_chunk_index(chunk_index=0, chunks=chunks) is None


class TestChunkIndexForOffset:
    def test_an_offset_inside_a_chunk_gives_that_chunk(self) -> None:
        assert resolve_chunk_index_for_offset(char_offset=150, chunks=_chunks()) == 1

    def test_an_offset_on_a_boundary_gives_the_chunk_it_starts(self) -> None:
        assert resolve_chunk_index_for_offset(char_offset=250, chunks=_chunks()) == 2

    def test_no_chunks_gives_nothing(self) -> None:
        assert resolve_chunk_index_for_offset(char_offset=0, chunks=None) is None

    def test_an_unusable_offset_gives_nothing(self) -> None:
        assert (
            resolve_chunk_index_for_offset(char_offset="start", chunks=_chunks())
            is None
        )

    def test_an_offset_in_a_gap_gives_the_next_chunk_that_starts_after_it(self) -> None:
        chunks = [FakeChunk(0, 50), FakeChunk(200, 300)]

        assert resolve_chunk_index_for_offset(char_offset=100, chunks=chunks) == 1

    def test_an_offset_past_every_chunk_gives_nothing(self) -> None:
        assert (
            resolve_chunk_index_for_offset(char_offset=9999, chunks=_chunks()) is None
        )

    def test_an_unusable_chunk_is_skipped_rather_than_fatal(self) -> None:
        chunks = [FakeChunk("bad", "worse"), FakeChunk(100, 250)]

        assert resolve_chunk_index_for_offset(char_offset=150, chunks=chunks) == 1
