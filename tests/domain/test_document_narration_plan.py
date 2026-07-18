"""Tests for planning what the narrator speaks from the document model."""

from __future__ import annotations

from voice_reader.domain.document.block_kind import BlockKind
from voice_reader.domain.document.model import Block, Document, Section
from voice_reader.domain.document.narration_plan import build_narration_chunks
from voice_reader.domain.entities.text_chunk import TextChunk
from voice_reader.domain.services.chunking_service import ChunkingService


def _chunker(*, min_chars: int = 1, max_chars: int = 400) -> ChunkingService:
    return ChunkingService(min_chars=min_chars, max_chars=max_chars)


def _document(source: str, spans: list[tuple[BlockKind, int, int]]) -> Document:
    blocks = tuple(
        Block(kind=kind, source_start=start, source_end=end, text=source[start:end])
        for kind, start, end in spans
    )
    section = Section(
        title="",
        source_start=0,
        source_end=len(source),
        blocks=blocks,
    )
    return Document(source_length=len(source), sections=(section,))


def _spoken(chunks: tuple[TextChunk, ...]) -> str:
    return " ".join(chunk.text for chunk in chunks)


class TestWhatGetsSpoken:
    def test_only_spoken_blocks_are_narrated(self) -> None:
        source = "The heading\n42\nThe body sentence.\n"
        document = _document(
            source,
            [
                (BlockKind.HEADING, 0, 11),
                (BlockKind.PAGE_NUMBER, 12, 14),
                (BlockKind.PARAGRAPH, 15, 33),
            ],
        )

        chunks = build_narration_chunks(
            document,
            source_text=source,
            chunking_service=_chunker(),
        )

        assert "42" not in _spoken(chunks)
        assert "The heading" in _spoken(chunks)
        assert "The body sentence." in _spoken(chunks)

    def test_a_document_with_nothing_spoken_yields_no_chunks(self) -> None:
        source = "1\n"
        document = _document(source, [(BlockKind.PAGE_NUMBER, 0, 1)])

        assert (
            build_narration_chunks(
                document,
                source_text=source,
                chunking_service=_chunker(),
            )
            == ()
        )

    def test_no_source_yields_no_chunks(self) -> None:
        assert (
            build_narration_chunks(
                Document(source_length=0),
                source_text=None,  # type: ignore[arg-type]
                chunking_service=_chunker(),
            )
            == ()
        )


class TestSpansSayWhatTheyClaim:
    def test_every_chunk_span_holds_that_chunk_s_text(self) -> None:
        # Two paragraphs whose gap collapses under the chunker's normalisation,
        # which is exactly where naive offset arithmetic drifts.
        source = "First sentence here.\n\n\nSecond sentence here.\n"
        document = _document(
            source,
            [
                (BlockKind.PARAGRAPH, 0, 20),
                (BlockKind.PARAGRAPH, 23, 44),
            ],
        )

        chunks = build_narration_chunks(
            document,
            source_text=source,
            chunking_service=_chunker(max_chars=30),
        )

        assert chunks
        for chunk in chunks:
            claimed = source[chunk.start_char : chunk.end_char]
            assert " ".join(claimed.split()) == " ".join(chunk.text.split())

    def test_chunk_ids_run_in_sequence_across_the_document(self) -> None:
        source = "One. Two. Three. Four. Five. Six."
        document = _document(source, [(BlockKind.PARAGRAPH, 0, len(source))])

        chunks = build_narration_chunks(
            document,
            source_text=source,
            chunking_service=_chunker(max_chars=12),
        )

        assert len(chunks) > 1
        assert [c.chunk_id for c in chunks] == list(range(len(chunks)))


class TestRuns:
    def test_adjacent_blocks_of_one_kind_are_spoken_as_a_single_run(self) -> None:
        # Two sentence-sized blocks that a PDF extractor split apart. Left
        # alone they would be two short utterances with a breath between.
        source = "This is the first line. This is the second line."
        document = _document(
            source,
            [
                (BlockKind.PARAGRAPH, 0, 23),
                (BlockKind.PARAGRAPH, 24, 48),
            ],
        )

        chunks = build_narration_chunks(
            document,
            source_text=source,
            chunking_service=_chunker(min_chars=10, max_chars=400),
        )

        assert len(chunks) == 1
        assert chunks[0].text == source

    def test_a_heading_is_not_folded_into_the_paragraph_below_it(self) -> None:
        source = "Prologue\nThe opening sentence."
        document = _document(
            source,
            [
                (BlockKind.HEADING, 0, 8),
                (BlockKind.PARAGRAPH, 9, 30),
            ],
        )

        chunks = build_narration_chunks(
            document,
            source_text=source,
            chunking_service=_chunker(),
        )

        assert [c.text for c in chunks] == ["Prologue", "The opening sentence."]

    def test_skipped_text_between_blocks_breaks_the_run(self) -> None:
        # A running head sits between the two paragraphs. Joining across it
        # would give a chunk whose span covers text nobody asked to hear.
        source = "First paragraph. CHAPTER THREE Second paragraph."
        document = _document(
            source,
            [
                (BlockKind.PARAGRAPH, 0, 16),
                (BlockKind.RUNNING_HEAD, 17, 30),
                (BlockKind.PARAGRAPH, 31, 48),
            ],
        )

        chunks = build_narration_chunks(
            document,
            source_text=source,
            chunking_service=_chunker(min_chars=10, max_chars=400),
        )

        assert [c.text for c in chunks] == ["First paragraph.", "Second paragraph."]
        assert "CHAPTER THREE" not in _spoken(chunks)


class TestStartOffset:
    def test_blocks_before_the_start_offset_are_passed_over(self) -> None:
        source = "Front matter.\nThe body begins."
        document = _document(
            source,
            [
                (BlockKind.PARAGRAPH, 0, 13),
                (BlockKind.PARAGRAPH, 14, 30),
            ],
        )

        chunks = build_narration_chunks(
            document,
            source_text=source,
            chunking_service=_chunker(),
            start_offset=14,
        )

        assert [c.text for c in chunks] == ["The body begins."]

    def test_a_block_straddling_the_start_offset_is_entered_part_way(self) -> None:
        source = "Skip this. Keep this."
        document = _document(source, [(BlockKind.PARAGRAPH, 0, len(source))])

        chunks = build_narration_chunks(
            document,
            source_text=source,
            chunking_service=_chunker(),
            start_offset=11,
        )

        assert [c.text for c in chunks] == ["Keep this."]
        assert chunks[0].start_char == 11

    def test_a_negative_start_offset_is_clamped_to_the_beginning(self) -> None:
        source = "All of it."
        document = _document(source, [(BlockKind.PARAGRAPH, 0, len(source))])

        chunks = build_narration_chunks(
            document,
            source_text=source,
            chunking_service=_chunker(),
            start_offset=-5,
        )

        assert [c.text for c in chunks] == ["All of it."]


class TestUnplaceableChunks:
    def test_a_chunk_that_is_not_in_its_own_run_is_dropped(self) -> None:
        """A span is never guessed at, on the same reasoning as anchoring.

        No real chunker invents text, so this guards the contract rather than a
        known caller: a chunk whose span cannot be established is left out
        rather than given an offset that would mislead every consumer of it.
        """

        class _InventingChunker:
            def chunk_text(self, text: str) -> list[TextChunk]:
                del text
                return [
                    TextChunk(
                        chunk_id=0,
                        text="never appears in the source",
                        start_char=0,
                        end_char=27,
                    )
                ]

        source = "Real body text."
        document = _document(source, [(BlockKind.PARAGRAPH, 0, len(source))])

        chunks = build_narration_chunks(
            document,
            source_text=source,
            chunking_service=_InventingChunker(),  # type: ignore[arg-type]
        )

        assert chunks == ()
