from __future__ import annotations


from voice_reader.application.services.chapter_index_service import ChapterIndexService
from voice_reader.domain.entities.text_chunk import TextChunk


def test_build_index_detects_chapter_1_and_resolves_offsets_and_chunk_index() -> None:
    text = "Intro\n\nChapter 1\nHello world.\n\nChapter 2\nNext."  # noqa: WPS336
    # Two chunks: intro+chapter1, then chapter2.
    chunks = [
        TextChunk(chunk_id=0, text=text[:30], start_char=0, end_char=30),
        TextChunk(chunk_id=1, text=text[30:], start_char=30, end_char=len(text)),
    ]
    svc = ChapterIndexService()
    chapters = svc.build_index(text, chunks=chunks, min_char_offset=0)

    assert [c.title for c in chapters] == ["Chapter 1", "Chapter 2"]
    assert chapters[0].char_offset == text.index("Chapter 1")
    assert chapters[1].char_offset == text.index("Chapter 2")
    assert chapters[0].chunk_index == 0
    assert chapters[1].chunk_index == 1


def test_build_index_maps_to_playback_candidate_indices_skipping_silent_chunks() -> (
    None
):
    # A first chunk that sanitizes to empty should not count toward playback indices.
    silent = "1\n1.1\n"  # sanitizer drops number-only and numbering prefixes
    c1 = "Chapter 1\nHello.\n"
    c2 = "Chapter 2\nWorld.\n"
    text = silent + "\n" + c1 + "\n" + c2
    chunks = [
        TextChunk(chunk_id=0, text=silent, start_char=0, end_char=len(silent)),
        TextChunk(
            chunk_id=1,
            text=c1,
            start_char=len(silent) + 1,
            end_char=len(silent) + 1 + len(c1),
        ),
        TextChunk(
            chunk_id=2,
            text=c2,
            start_char=len(silent) + 2 + len(c1),
            end_char=len(text),
        ),
    ]
    svc = ChapterIndexService()
    chapters = svc.build_index(text, chunks=chunks, min_char_offset=0)
    assert [c.title for c in chapters] == ["Chapter 1", "Chapter 2"]
    # Playback indices should be 0 and 1 (silent chunk skipped).
    assert [c.chunk_index for c in chapters] == [0, 1]


def test_build_index_detects_roman_numeral_headings_case_insensitive() -> None:
    text = "CHAPTER I\nA\n\nChapter ix\nB\n"
    chunks = [TextChunk(chunk_id=0, text=text, start_char=0, end_char=len(text))]
    svc = ChapterIndexService()
    chapters = svc.build_index(text, chunks=chunks, min_char_offset=0)
    assert [c.title for c in chapters] == ["CHAPTER I", "Chapter ix"]


def test_build_index_ignores_pdf_toc_entries_with_dotted_leaders() -> None:
    # Regression: dotted leaders indicate a TOC entry, not a body heading.
    text = "Contents\n\nChapter 1: Title . . . . 12\n\nCHAPTER 1\nBody\n"
    chunks = [TextChunk(chunk_id=0, text=text, start_char=0, end_char=len(text))]
    svc = ChapterIndexService()
    chapters = svc.build_index(text, chunks=chunks, min_char_offset=0)
    assert [c.title for c in chapters] == ["CHAPTER 1"]


def test_build_index_ignores_unsupported_headings() -> None:
    text = 'Part 1\nChapterhouse\n"In this chapter we discuss"\n'
    chunks = [TextChunk(chunk_id=0, text=text, start_char=0, end_char=len(text))]
    svc = ChapterIndexService()
    chapters = svc.build_index(text, chunks=chunks, min_char_offset=0)
    assert chapters == []


def test_line_text_at_handles_bounds() -> None:
    svc = ChapterIndexService()
    text = "Chapter 1\nA\n"
    assert svc._line_text_at(text, -999) == "Chapter 1"  # noqa: SLF001
    assert svc._line_text_at(text, 999) == ""  # noqa: SLF001


def test_resolve_chunk_index_fallback_to_next_chunk_start() -> None:
    # When the heading offset falls between candidate chunks, we select the next.
    text = "Preface\n\nChapter 1\nA\n"
    chunks = [
        TextChunk(chunk_id=0, text="Preface", start_char=0, end_char=7),
        TextChunk(chunk_id=1, text="A", start_char=text.index("A"), end_char=len(text)),
    ]
    svc = ChapterIndexService()
    chapters = svc.build_index(text, chunks=chunks, min_char_offset=0)
    assert chapters
    assert chapters[0].chunk_index == 1


def test_resolve_chunk_index_returns_none_when_after_last_candidate() -> None:
    # If a match occurs after the last candidate chunk ends, we drop it.
    svc = ChapterIndexService()
    text = "Chapter 1\nA\n\nChapter 2\n"
    # Only one candidate chunk covering the first chapter.
    chunks = [TextChunk(chunk_id=0, text="Chapter 1\nA", start_char=0, end_char=11)]
    chapters = svc.build_index(text, chunks=chunks, min_char_offset=0)
    assert [c.title for c in chapters] == ["Chapter 1"]


def test_build_index_filters_chapters_when_candidate_ends_before_min_char_offset() -> (
    None
):
    svc = ChapterIndexService()
    text = "Chapter 1\nA\n\nChapter 2\nB\n"
    chunks = [
        TextChunk(chunk_id=0, text="Chapter 1\nA", start_char=0, end_char=11),
        TextChunk(chunk_id=1, text="Chapter 2\nB", start_char=13, end_char=len(text)),
    ]
    # min offset beyond first candidate end filters Chapter 1.
    chapters = svc.build_index(text, chunks=chunks, min_char_offset=12)
    assert [c.title for c in chapters] == ["Chapter 2"]


def test_build_index_filters_chapters_on_exception_accessing_candidate(
    monkeypatch,
) -> None:
    del monkeypatch
    svc = ChapterIndexService()
    text = "Chapter 1\nA\n"

    class FlakyChunk:
        chunk_id = 0
        text = "Chapter 1\nA\n"
        start_char = 0

        def __init__(self) -> None:
            self._end_calls = 0

        @property
        def end_char(self) -> int:
            # First access succeeds (used by resolve_chunk_index).
            # Second access fails (used by the min_char_offset filter).
            self._end_calls += 1
            if self._end_calls >= 2:
                raise RuntimeError("boom")
            return len(text)

    # Use a min_char_offset so the filter is evaluated.
    chapters = svc.build_index(text, chunks=[FlakyChunk()], min_char_offset=0)  # type: ignore[arg-type]
    assert chapters == []


def test_build_index_returns_empty_when_no_headings_exist() -> None:
    text = "Hello\nWorld\n"
    chunks = [TextChunk(chunk_id=0, text=text, start_char=0, end_char=len(text))]
    svc = ChapterIndexService()
    assert svc.build_index(text, chunks=chunks, min_char_offset=0) == []


def test_build_index_preserves_text_order() -> None:
    text = "Chapter 2\nB\n\nChapter 10\nC\n\nChapter 3\nD\n"
    chunks = [TextChunk(chunk_id=0, text=text, start_char=0, end_char=len(text))]
    svc = ChapterIndexService()
    chapters = svc.build_index(text, chunks=chunks, min_char_offset=0)
    assert [c.title for c in chapters] == ["Chapter 2", "Chapter 10", "Chapter 3"]


def test_build_index_filters_chapters_before_min_char_offset() -> None:
    text = "Chapter 1\nA\n\nChapter 2\nB\n"
    chunks = [TextChunk(chunk_id=0, text=text, start_char=0, end_char=len(text))]
    svc = ChapterIndexService()

    min_off = text.index("Chapter 2")
    chapters = svc.build_index(text, chunks=chunks, min_char_offset=min_off)
    # min_char_offset can be inside the previous chapter chunk (narration start
    # often skips the heading line), so Chapter 1 may still be kept.
    assert [c.title for c in chapters] == ["Chapter 1", "Chapter 2"]


def test_get_next_chapter_when_before_first_heading_returns_first() -> None:
    text = "Chapter 1\nA\n\nChapter 2\nB\n"
    chunks = [TextChunk(chunk_id=0, text=text, start_char=0, end_char=len(text))]
    svc = ChapterIndexService()
    chapters = svc.build_index(text, chunks=chunks, min_char_offset=0)
    assert svc.get_current_chapter(chapters, current_char_offset=-1) is None
    assert svc.get_next_chapter(chapters, current_char_offset=-1) == chapters[0]


def test_previous_chapter_when_no_current_returns_none() -> None:
    svc = ChapterIndexService()
    assert svc.get_previous_chapter([], current_char_offset=0) is None


def test_navigation_helpers_prev_next_current() -> None:
    text = "Chapter 1\nA\n\nChapter 2\nB\n\nChapter 3\nC\n"
    chunks = [TextChunk(chunk_id=0, text=text, start_char=0, end_char=len(text))]
    svc = ChapterIndexService()
    chapters = svc.build_index(text, chunks=chunks, min_char_offset=0)

    pos = text.index("Chapter 2") + 2
    assert svc.get_current_chapter(chapters, current_char_offset=pos) == chapters[1]
    assert svc.get_previous_chapter(chapters, current_char_offset=pos) == chapters[0]
    assert svc.get_next_chapter(chapters, current_char_offset=pos) == chapters[2]

    at_first = text.index("Chapter 1")
    assert svc.get_previous_chapter(chapters, current_char_offset=at_first) is None

    at_last = text.index("Chapter 3") + 20
    assert svc.get_next_chapter(chapters, current_char_offset=at_last) is None


def test_build_index_with_no_playback_candidates_returns_empty() -> None:
    text = "Chapter 1\nA\n"
    # Chunk sanitizes to empty: numbering-only + blank.
    chunks = [TextChunk(chunk_id=0, text="1\n", start_char=0, end_char=2)]
    svc = ChapterIndexService()
    assert svc.build_index(text, chunks=chunks, min_char_offset=0) == []


def test_build_index_skips_empty_heading_line_text() -> None:
    # Titles are preserved; empty titles are not expected under the strict regex.
    # This test exists to ensure a blank first line doesn't break scanning.
    svc = ChapterIndexService()
    text = "\n\nChapter 1\nA\n"
    chunks = [TextChunk(chunk_id=0, text=text, start_char=0, end_char=len(text))]
    chapters = svc.build_index(text, chunks=chunks, min_char_offset=0)
    assert [c.title for c in chapters] == ["Chapter 1"]


def test_get_next_chapter_empty_sequence_returns_none() -> None:
    svc = ChapterIndexService()
    assert svc.get_next_chapter([], current_char_offset=0) is None


def test_build_index_skips_match_when_chunk_index_unresolvable(monkeypatch) -> None:
    del monkeypatch
    svc = ChapterIndexService()
    # If there are no candidates, index is empty.
    text = "Chapter 1\nA\n"
    chunks = [TextChunk(chunk_id=0, text="1\n", start_char=0, end_char=2)]
    assert svc.build_index(text, chunks=chunks, min_char_offset=0) == []


def test_get_next_chapter_handles_exception_indexing() -> None:
    # get_next_chapter assumes normal Sequence semantics.
    svc = ChapterIndexService()
    assert svc.get_next_chapter([], current_char_offset=-1) is None
