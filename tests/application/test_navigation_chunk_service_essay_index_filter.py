from __future__ import annotations


from voice_reader.application.services.navigation_chunk_service import NavigationChunkService
from voice_reader.domain.entities.text_chunk import TextChunk
from voice_reader.domain.services.chunking_service import ChunkingService
from voice_reader.domain.services.reading_start_service import ReadingStart, ReadingStartService


class _FixedStartDetector:
    def __init__(self, start_char: int) -> None:
        self._start_char = int(start_char)

    def detect_start(self, text: str) -> ReadingStart:
        return ReadingStart(start_char=self._start_char, reason="Fixed")


def _abs_ranges(chunks: list[TextChunk]) -> list[tuple[int, int]]:
    return [(int(c.start_char), int(c.end_char)) for c in chunks]


def test_build_chunks_does_not_mutate_offsets_when_no_essay_index() -> None:
    book_text = (
        "PROLOGUE\n"
        "This is the prologue. It has enough words to chunk.\n\n"
        "CHAPTER I\n"
        "This is chapter one. It also has enough words to chunk.\n"
    )

    svc = NavigationChunkService(
        reading_start_detector=_FixedStartDetector(0),
        chunking_service=ChunkingService(min_chars=10, max_chars=80),
    )

    baseline = svc.chunking_service.chunk_text(book_text)
    chunks, start = svc.build_chunks(book_text=book_text)

    assert start.start_char == 0
    assert svc._detect_essay_index_span(slice_text=book_text) is None  # type: ignore[attr-defined]

    # Exact same absolute offsets because we didn't pre-remove any text.
    assert _abs_ranges(chunks) == _abs_ranges(baseline)


def test_build_chunks_filters_only_chunks_fully_inside_essay_index_span() -> None:
    # Essay Index includes a ToC-like line "Chapter 1 .... 1" which must NOT be
    # treated as a terminator. Filtering should stop before the real heading and/or
    # before prose.
    book_text = (
        "PROLOGUE\n"
        "Some prose before the index.\n\n"
        "Essay Index\n"
        "Chapter 1 .... 1\n"
        "Entry One .... 3\n\n"
        "CHAPTER I\n"
        "Real chapter prose begins here.\n"
    )

    svc = NavigationChunkService(
        reading_start_detector=_FixedStartDetector(0),
        chunking_service=ChunkingService(min_chars=1, max_chars=120),
    )

    chunks, _ = svc.build_chunks(book_text=book_text)
    span = svc._detect_essay_index_span(slice_text=book_text)  # type: ignore[attr-defined]
    assert span is not None
    span_start, span_end = span

    # No remaining chunk is fully inside the span.
    for c in chunks:
        assert not (c.start_char >= span_start and c.end_char <= span_end)

    # Sanity: still includes prologue content and chapter content.
    joined = "\n".join(c.text for c in chunks)
    assert "Some prose before the index" in joined
    assert "Real chapter prose begins" in joined


def test_build_chunks_does_not_drop_partially_overlapping_chunks() -> None:
    # Construct a single paragraph (no double-newline) so chunking may produce
    # a chunk that overlaps the Essay Index span boundary.
    book_text = (
        "PROLOGUE\n"
        + "Sentence. " * 30
        + "\nEssay Index\n"
        + "Entry One .... 1\n"
        + "3.1 Chapter 1: Crystalline\n"
        + "Body starts now."
    )

    svc = NavigationChunkService(
        reading_start_detector=_FixedStartDetector(0),
        chunking_service=ChunkingService(min_chars=1, max_chars=5000),
    )

    baseline = svc.chunking_service.chunk_text(book_text)
    assert len(baseline) == 1
    baseline_chunk = baseline[0]

    chunks, _ = svc.build_chunks(book_text=book_text)

    # The only chunk overlaps the span (starts before, ends after), so it must
    # not be filtered.
    assert len(chunks) == 1
    assert chunks[0].start_char == baseline_chunk.start_char
    assert chunks[0].end_char == baseline_chunk.end_char


def test_build_chunks_falls_back_when_filter_would_remove_everything() -> None:
    # Even in degenerate cases (very little text), build_chunks must never
    # return an empty list.
    book_text = "Essay Index\nOnly entry\n\nCHAPTER I\nBody."

    svc = NavigationChunkService(
        reading_start_detector=_FixedStartDetector(0),
        chunking_service=ChunkingService(min_chars=1, max_chars=80),
    )

    baseline = svc.chunking_service.chunk_text(book_text)
    chunks, _ = svc.build_chunks(book_text=book_text)

    assert baseline
    assert chunks
    # All returned chunks must preserve absolute offsets from the original
    # chunking output (filtering is candidate selection only).
    baseline_ranges = set(_abs_ranges(baseline))
    assert set(_abs_ranges(chunks)).issubset(baseline_ranges)


def test_detect_span_returns_none_when_no_chapter_heading_after_essay_index() -> None:
    # If there is no Chapter-1 heading after Essay Index, we don't filter.
    book_text = (
        "PROLOGUE\n"
        "Essay Index\n"
        "Entry One .... 1\n"
        "This is real prose starting immediately after the index list.\n"
    )

    svc = NavigationChunkService(
        reading_start_detector=_FixedStartDetector(0),
        chunking_service=ChunkingService(min_chars=1, max_chars=120),
    )

    span = svc._detect_essay_index_span(slice_text=book_text)  # type: ignore[attr-defined]
    assert span is None

    baseline = svc.chunking_service.chunk_text(book_text)
    chunks, _ = svc.build_chunks(book_text=book_text)
    assert _abs_ranges(chunks) == _abs_ranges(baseline)


def test_private_index_line_detector_covers_all_branches() -> None:
    # `_detect_essay_index_span` must return a span when a Chapter-1 heading exists.
    svc = NavigationChunkService(
        reading_start_detector=_FixedStartDetector(0),
        chunking_service=ChunkingService(min_chars=1, max_chars=120),
    )

    # Build a tail that includes a valid Chapter heading terminator.
    book_text = (
        "Essay Index\n"
        "\n"
        "Entry .... 12\n"
        "3.1\n"
        "Short Title\n"
        "ALL CAPS\n"
        "CHAPTER I\n"
        "Body starts now.\n"
    )

    span = svc._detect_essay_index_span(slice_text=book_text)  # type: ignore[attr-defined]
    assert span is not None
    span_start, span_end = span
    assert span_start == 0
    assert 0 < span_end < len(book_text)


def test_looks_like_essay_index_line() -> None:
    f = NavigationChunkService._looks_like_essay_index_line
    assert f("")
    assert f("Entry .... 12")
    assert f("3.1")
    assert f("Short Title")
    # Must bypass the "very short title" heuristic (<=6 words) so we actually
    # execute the dedicated ALL-CAPS branch.
    assert f("ALL CAPS HEADING INSIDE THE INDEX LIST")
    assert not f("This is clearly a longer mixed-case sentence with punctuation.")


def test_prologue_then_skip_essay_titles_then_chapter_1() -> None:
    """Integration-level assertion for the hard navigation flow.

    Requirements:
    - skip everything up to Prologue (e.g., Contents)
    - play first sentence of Prologue
    - skip Essay Index (essay titles)
    - continue at Chapter 1 onwards
    """

    book_text = (
        "Title\n\n"
        "CONTENTS\n"
        "Prologue .... i\n"
        "Essay Index .... iii\n"
        "Chapter 1 .... 1\n\n"
        "PROLOGUE\n"
        "This is the first sentence of the prologue.\n"
        "Second prologue sentence follows.\n\n"
        "Essay Index\n"
        "Architecture\n"
        "Crystalline\n"
        "Decision Architecture in code\n\n"
        "CHAPTER I\n"
        "This is chapter one. It begins here.\n"
    ).strip()

    nav = NavigationChunkService(
        reading_start_detector=ReadingStartService(),
        chunking_service=ChunkingService(min_chars=1, max_chars=120),
    )

    chunks, start = nav.build_chunks(book_text=book_text)

    # 1) Start must be at Prologue prose, not at Contents/ToC.
    assert start.reason == "Detected Prologue"
    assert book_text[start.start_char :].lstrip().startswith(
        "This is the first sentence of the prologue."
    )

    # 2) The returned chunk list must include Prologue prose.
    assert any("first sentence of the prologue" in c.text for c in chunks)

    # 3) Essay Index content must not appear in the returned chunk list.
    forbidden = {"Essay Index", "Architecture", "Crystalline", "Decision Architecture"}
    assert not any(any(f in c.text for f in forbidden) for c in chunks)

    # 4) Chapter 1 content must still be present after filtering.
    assert any("This is chapter one" in c.text for c in chunks)


def test_private_index_line_detector_allows_mixed_case_break() -> None:
    # Span detection depends on finding a Chapter-1 heading, not on consuming every
    # possible index-line variant.
    svc = NavigationChunkService(
        reading_start_detector=_FixedStartDetector(0),
        chunking_service=ChunkingService(min_chars=1, max_chars=120),
    )
    # Use an all-caps line so the helper is not short-circuited by the
    # "any lowercase -> False" branch.
    book_text = (
        "Essay Index\n"
        "Crystalline\n"
        "A LONGER TITLE LINE NOT INDEX\n"
        "CHAPTER 1\n"
        "This is chapter one prose.\n"
    )
    span = svc._detect_essay_index_span(slice_text=book_text)  # type: ignore[attr-defined]
    assert span is not None

