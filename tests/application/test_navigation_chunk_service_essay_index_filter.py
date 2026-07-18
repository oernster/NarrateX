from __future__ import annotations


from voice_reader.application.services.navigation_chunk_service import (
    NavigationChunkService,
)
from voice_reader.domain.document import plain_text
from voice_reader.domain.document.model import Document
from voice_reader.domain.entities.text_chunk import TextChunk
from voice_reader.domain.services.chunking_service import ChunkingService


def _svc(*, min_chars: int = 1, max_chars: int = 120) -> NavigationChunkService:
    return NavigationChunkService(
        chunking_service=ChunkingService(min_chars=min_chars, max_chars=max_chars),
    )


def _flat(book_text: str) -> Document:
    """A book the model could not structure: one unbroken run of prose."""

    return Document.unstructured(text=book_text)


def _abs_ranges(chunks: list[TextChunk]) -> list[tuple[int, int]]:
    return [(int(c.start_char), int(c.end_char)) for c in chunks]


def _squash(text: str) -> str:
    return " ".join(text.split())


def _assert_spans_say_what_they_claim(chunks, book_text: str) -> None:
    """Every chunk's span must hold the text that chunk speaks."""

    for chunk in chunks:
        claimed = book_text[chunk.start_char : chunk.end_char]
        assert _squash(claimed) == _squash(chunk.text)


def test_build_chunks_clamps_a_negative_forced_start_to_zero() -> None:
    book_text = "Hello world.\n"
    svc = _svc(max_chars=120)

    chunks, start = svc.build_chunks(
        book_text=book_text,
        document=_flat(book_text),
        force_start_char=-5,
    )

    assert start.start_char == 0
    assert chunks
    assert chunks[0].start_char == 0


def test_build_chunks_does_not_mutate_offsets_when_no_essay_index() -> None:
    book_text = (
        "PROLOGUE\n"
        "This is the prologue. It has enough words to chunk.\n\n"
        "CHAPTER I\n"
        "This is chapter one. It also has enough words to chunk.\n"
    )

    svc = _svc(min_chars=10, max_chars=80)
    chunks, start = svc.build_chunks(book_text=book_text, document=_flat(book_text))

    assert start.start_char == 0
    assert svc._detect_essay_index_span(slice_text=book_text) is None  # type: ignore[attr-defined]

    # Offsets index the book itself, because no text was removed before chunking.
    _assert_spans_say_what_they_claim(chunks, book_text)
    assert chunks[0].start_char == 0
    assert chunks[-1].end_char <= len(book_text)


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

    svc = _svc()
    chunks, _ = svc.build_chunks(book_text=book_text, document=_flat(book_text))
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

    svc = _svc(max_chars=5000)
    baseline = svc.chunking_service.chunk_text(book_text)
    assert len(baseline) == 1

    chunks, _ = svc.build_chunks(book_text=book_text, document=_flat(book_text))

    # The only chunk overlaps the span (starts before, ends after), so it must
    # not be filtered.
    assert len(chunks) == 1
    _assert_spans_say_what_they_claim(chunks, book_text)


def test_build_chunks_falls_back_when_filter_would_remove_everything() -> None:
    # Even in degenerate cases (very little text), build_chunks must never
    # return an empty list.
    book_text = "Essay Index\nOnly entry\n\nCHAPTER I\nBody."

    svc = _svc(max_chars=80)
    baseline = svc.chunking_service.chunk_text(book_text)
    chunks, _ = svc.build_chunks(book_text=book_text, document=_flat(book_text))

    assert baseline
    assert chunks
    _assert_spans_say_what_they_claim(chunks, book_text)


def test_detect_span_returns_none_when_no_chapter_heading_after_essay_index() -> None:
    # If there is no Chapter-1 heading after Essay Index, we don't filter.
    book_text = (
        "PROLOGUE\n"
        "Essay Index\n"
        "Entry One .... 1\n"
        "This is real prose starting immediately after the index list.\n"
    )

    svc = _svc()
    span = svc._detect_essay_index_span(slice_text=book_text)  # type: ignore[attr-defined]
    assert span is None

    chunks, _ = svc.build_chunks(book_text=book_text, document=_flat(book_text))
    _assert_spans_say_what_they_claim(chunks, book_text)
    assert any("real prose starting immediately" in c.text for c in chunks)


def test_private_index_line_detector_covers_all_branches() -> None:
    # `_detect_essay_index_span` must return a span when a Chapter-1 heading exists.
    svc = _svc()

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
    - play the Prologue
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

    nav = _svc()
    document = plain_text.build_document(source=book_text)
    chunks, start = nav.build_chunks(book_text=book_text, document=document)

    # 1) Start must be at the Prologue, not at Contents/ToC. The model opens on
    #    the heading, which the pane shows and the narrator now reads.
    assert start.reason == "Detected body start"
    assert book_text[start.start_char :].lstrip().startswith("PROLOGUE")

    # 2) The returned chunk list must include Prologue prose.
    assert any("first sentence of the prologue" in c.text for c in chunks)

    # 3) Essay Index content must not appear in the returned chunk list.
    forbidden = {"Essay Index", "Architecture", "Crystalline"}
    assert not any(any(f in c.text for f in forbidden) for c in chunks)

    # 4) Chapter 1 content must still be present after filtering.
    assert any("This is chapter one" in c.text for c in chunks)

    # 5) Every chunk still says exactly what its span claims.
    _assert_spans_say_what_they_claim(chunks, book_text)


def test_prologue_then_skip_essay_index_but_keep_introduction_then_chapter_1() -> None:
    """Regression: Essay Index filtering must not skip a real Introduction.

    Scenario:
    - Start at the Prologue.
    - Essay Index appears after Prologue.
    - Introduction appears after Essay Index and before Chapter 1.

    Expected:
    - Essay Index content is filtered from chunk list.
    - Introduction prose is preserved.
    - Chapter 1 prose is preserved.
    """

    book_text = (
        "CONTENTS\n"
        "Prologue .... i\n"
        "Essay Index .... iii\n"
        "Introduction .... v\n"
        "Chapter 1 .... 1\n\n"
        "PROLOGUE\n"
        "This is the first sentence of the prologue.\n\n"
        "Essay Index\n"
        "Architecture\n"
        "Crystalline\n\n"
        "INTRODUCTION\n"
        "This is the first sentence of the introduction.\n\n"
        "CHAPTER 1\n"
        "This is chapter one. It begins here.\n"
    ).strip()

    nav = _svc()
    document = plain_text.build_document(source=book_text)
    chunks, start = nav.build_chunks(book_text=book_text, document=document)

    # 1) Start must be at the Prologue, not at Contents/ToC.
    assert start.reason == "Detected body start"
    assert book_text[start.start_char :].lstrip().startswith("PROLOGUE")

    # 2) Essay Index heading + titles must not appear.
    forbidden = {"Essay Index", "Architecture", "Crystalline"}
    assert not any(any(f in c.text for f in forbidden) for c in chunks)

    # 3) Introduction must still be present.
    assert any("first sentence of the introduction" in c.text for c in chunks)

    # 4) Chapter 1 content must still be present.
    assert any("This is chapter one" in c.text for c in chunks)


def test_private_index_line_detector_allows_mixed_case_break() -> None:
    # Span detection depends on finding a Chapter-1 heading, not on consuming every
    # possible index-line variant.
    svc = _svc()
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


def test_detect_span_ignores_toc_entries_without_dotted_leaders() -> None:
    # Some TOCs use trailing roman numerals without dotted leaders.
    # Those must not terminate the Essay Index span.
    svc = _svc()

    book_text = (
        "Essay Index\n"
        "Introduction v\n"
        "Entry One\n"
        "INTRODUCTION\n"
        "Real introduction prose begins here.\n"
    )

    span = svc._detect_essay_index_span(slice_text=book_text)  # type: ignore[attr-defined]
    assert span is not None
    start, end = span

    # Span must start at the Essay Index heading.
    assert start == 0
    # Span must end at the real INTRODUCTION heading (not at "Introduction v").
    assert book_text[end:].lstrip().startswith("INTRODUCTION")
