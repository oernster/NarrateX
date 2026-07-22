"""Which occurrence of a repeated heading becomes the bookmark.

A label like "Chapter 1" appears twice in a typical book: once in the contents
and once where the chapter actually starts. Sending a reader to the contents
entry would be worse than having no bookmark, so these cover the choice between
the two, and the front-matter boundary that informs it.
"""

from __future__ import annotations


from voice_reader.application.services.structural_bookmark_service import (
    RawHeadingCandidate,
    StructuralBookmarkService,
    classify_heading,
    dedupe_candidates,
    scan_structural_headings,
)

from voice_reader.domain.services.chunking_service import ChunkingService
from voice_reader.application.services.navigation_chunk_service import (
    NavigationChunkService,
)
from voice_reader.domain.document import plain_text
from voice_reader.domain.document.reading_start import body_opening_offset


def _document(text: str):
    """The structure a plain-text book load would produce."""

    return plain_text.build_document(source=text)


def _build(nav: NavigationChunkService, text: str):
    """Chunk `text` through the document model, as a real book load would."""

    return nav.build_chunks(book_text=text, document=_document(text))


def test_chapter_label_duplicated_toc_and_body_prefers_body_occurrence() -> None:
    text = (
        "Title Page\n\n"
        "Table of Contents\n"
        "\n"
        "Chapter 1\n"
        "Chapter 2\n"
        "Chapter 3\n"
        "\n\n"
        "Prologue\n\n"
        "Chapter 1\nBody 1\n\n"
        "Chapter 2\nBody 2\n\n"
        "Chapter 3\nBody 3\n\n"
    )

    svc = StructuralBookmarkService()
    out = svc.build_for_loaded_book(
        book_id="b1", normalized_text=text, document=_document(text)
    )
    labels = [b.label for b in out]
    assert "Chapter 3" in labels

    b3 = [b for b in out if b.label == "Chapter 3"][0]
    assert b3.kind == "chapter"
    assert b3.char_offset == text.index("\nChapter 3\nBody 3") + 1


def test_chapter_label_duplicated_pdf_spaced_dot_toc_and_body_prefers_body_occurrence() -> (
    None
):
    # PDF-style TOCs often use spaced-dot leaders.
    text = (
        "Contents\n\n"
        "Chapter 1: Crystalline . . . . . . 31\n"
        "Chapter 2: Decision Architecture in code . . . . . . 33\n\n"
        "CHAPTER 1\n"
        "Body 1\n\n"
        "CHAPTER 2\n"
        "Body 2\n\n"
    )

    svc = StructuralBookmarkService()
    out = svc.build_for_loaded_book(
        book_id="b1", normalized_text=text, document=_document(text)
    )

    # We expect Chapter 2 bookmark to anchor to the body occurrence (CHAPTER 2).
    b2 = [b for b in out if "chapter" in b.kind and "2" in b.label][0]
    assert b2.char_offset == text.index("CHAPTER 2")


def test_part_label_duplicated_toc_and_body_prefers_body_occurrence() -> None:
    text = (
        "Table of Contents\n\n"
        "Part I\n"
        "Chapter 1\n"
        "\n\n"
        "Part I\n"
        "Chapter 1\n\n"
        "Hello\n"
    )

    svc = StructuralBookmarkService()
    out = svc.build_for_loaded_book(
        book_id="b1", normalized_text=text, document=_document(text)
    )
    part = [b for b in out if b.kind == "part"][0]
    assert part.label == "Part I"
    # Prefer the later (body) occurrence, not the TOC copy.
    assert part.char_offset == text.rindex("\nPart I\nChapter 1") + 1


def test_exact_full_line_matching_only_inline_mention_is_not_a_heading() -> None:
    text = (
        "Table of Contents\n\n"
        "Chapter 3\n\n"
        "Prologue\n\n"
        "In this chapter we will discuss Chapter 3 as a concept.\n\n"
    )

    svc = StructuralBookmarkService()
    out = svc.build_for_loaded_book(
        book_id="b1", normalized_text=text, document=_document(text)
    )

    # We should *not* create a Chapter 3 bookmark anchored to the inline mention.
    # Since there's no body occurrence of Chapter 3 after the body start, and
    # front matter exists, Chapter 3 should be omitted.
    assert all(b.label != "Chapter 3" for b in out)


def test_body_start_cutoff_prefers_first_real_body_heading_after_front_matter() -> None:
    text = (
        "Table of Contents\n\n"
        "Essay Index\n\n"
        "Index\n\n"
        "Prologue\n\n"
        "Once upon a time.\n"
    )

    assert body_opening_offset(_document(text)) == text.index("Prologue")


def test_metadata_candidate_before_body_start_is_corrected_to_body_occurrence() -> None:
    text = "Table of Contents\n\n" "Chapter 3\n\n" "Prologue\n\n" "Chapter 3\nBody\n"

    # Simulate metadata pointing at the TOC occurrence.
    md = type(
        "Ch",
        (),
        {
            "title": "Chapter 3",
            "char_offset": text.index("Chapter 3"),
            "chunk_index": None,
        },
    )()

    svc = StructuralBookmarkService()
    out = svc.build_for_loaded_book(
        book_id="b1",
        normalized_text=text,
        document=_document(text),
        chapter_candidates=[md],
    )
    b3 = [b for b in out if b.label == "Chapter 3"][0]
    assert b3.char_offset == text.index("\nChapter 3\nBody") + 1


def test_no_safe_occurrence_means_no_bookmark() -> None:
    text = (
        "Table of Contents\n\n"
        "Chapter 7\n"
        "\n"
        "Essay Index\n\n"
        "Index\n\n"
        "Prologue\n\n"
        "Body starts here.\n"
    )

    svc = StructuralBookmarkService()
    out = svc.build_for_loaded_book(
        book_id="b1", normalized_text=text, document=_document(text)
    )
    assert all(b.label != "Chapter 7" for b in out)


def test_excludes_chapter_like_toc_entries_before_reading_start() -> None:
    # TOC has clean "Chapter N" lines; body has the real chapter.
    text = (
        "Table of Contents\n\n"
        "Chapter 1\n"
        "Chapter 2\n\n"
        "Chapter 1\n\n"
        "Body starts here.\n"
    )
    nav = NavigationChunkService(
        chunking_service=ChunkingService(min_chars=10, max_chars=200),
    )
    chunks, start = _build(nav, text)
    min_off = int(start.start_char)

    svc = StructuralBookmarkService()
    out = svc.build_for_loaded_book(
        book_id="b1",
        normalized_text=text,
        document=_document(text),
        chunks=chunks,
        min_char_offset=min_off,
    )

    # Chapter 2 exists only in TOC: should be excluded.
    assert all(b.label != "Chapter 2" for b in out)
    # Chapter 1 should exist.
    c1 = [b for b in out if b.label == "Chapter 1"][0]
    assert c1.char_offset >= 0


def test_prefers_post_boundary_duplicate_over_early_toc_duplicate() -> None:
    text = (
        "Table of Contents\n\n"
        "Chapter 3\n\n"
        "Prologue\n\n"
        "Prologue body.\n\n"
        "Chapter 3\n\n"
        "Body 3.\n"
    )

    nav = NavigationChunkService(
        chunking_service=ChunkingService(min_chars=10, max_chars=200),
    )
    chunks, _start = _build(nav, text)

    # Set boundary between the TOC occurrence and the real body occurrence.
    min_off = text.rindex("\nChapter 3\n\nBody 3") + 1

    svc = StructuralBookmarkService()
    out = svc.build_for_loaded_book(
        book_id="b1",
        normalized_text=text,
        document=_document(text),
        chunks=chunks,
        min_char_offset=min_off,
    )
    b3 = [b for b in out if b.label == "Chapter 3"][0]
    assert b3.char_offset >= min_off


def test_keeps_real_preface_or_prologue_when_it_is_after_boundary_or_is_the_boundary() -> (
    None
):
    text = "Preface\n\nReal preface paragraph.\n\nChapter 1\n\nBody.\n"
    nav = NavigationChunkService(
        chunking_service=ChunkingService(min_chars=10, max_chars=200),
    )
    chunks, start = _build(nav, text)

    # Boundary is the narration start (first narratable paragraph).
    # Sections now land on the heading line, so allow the heading to be pre-boundary.
    min_off = None

    svc = StructuralBookmarkService()
    out = svc.build_for_loaded_book(
        book_id="b1",
        normalized_text=text,
        document=_document(text),
        chunks=chunks,
        min_char_offset=min_off,
    )
    labels = [b.label for b in out]
    assert "Preface" in labels
    pre = [b for b in out if b.label == "Preface"][0]
    assert pre.char_offset == 0


def test_sections_include_intro_when_essay_index_is_inside_body_after_prologue() -> (
    None
):
    # Regression: an "Essay Index" marker can appear after body has begun
    # (e.g. after Prologue). That must not cause later headings like
    # Introduction to be treated as "front matter" and excluded.
    text = (
        "PROLOGUE\n\n"
        "Prologue prose begins here. It has enough words to count as prose.\n\n"
        "Essay Index\n"
        "Entry One .... 1\n\n"
        "INTRODUCTION\n\n"
        "Introduction prose begins here. It also has enough words to count.\n\n"
        "CHAPTER 1\n\n"
        "Chapter one prose begins here. It is real content.\n"
    )

    nav = NavigationChunkService(
        chunking_service=ChunkingService(min_chars=10, max_chars=200),
    )
    chunks, start = _build(nav, text)
    min_off = int(start.start_char)

    svc = StructuralBookmarkService()
    out = svc.build_for_loaded_book(
        book_id="b1",
        normalized_text=text,
        document=_document(text),
        chunks=chunks,
        min_char_offset=min_off,
    )
    kinds = [b.kind for b in out]
    assert "prologue" in kinds
    assert "introduction" in kinds
    assert "chapter" in kinds


def test_filters_resolved_chunk_index_candidates_before_boundary() -> None:
    # Synthetic case: a chapter candidate comes via chunk_index pointing at a
    # pre-boundary chunk (e.g. front matter). If the resolved jump target ends
    # before the boundary, the bookmark must be dropped.
    text = "Chapter 1\n\nPara one.\n\n"
    chunks = ChunkingService(min_chars=5, max_chars=50).chunk_text(text)
    assert len(chunks) >= 2

    # Candidate points to the heading chunk.
    md = type("Ch", (), {"title": "Chapter 1", "char_offset": None, "chunk_index": 0})()
    # Boundary is at the start of the paragraph chunk.
    min_off = int(chunks[1].start_char)

    svc = StructuralBookmarkService()
    out = svc.build_for_loaded_book(
        book_id="b1",
        normalized_text=text,
        document=_document(text),
        chapter_candidates=[md],
        chunks=chunks,
        min_char_offset=min_off,
    )
    assert all(b.label != "Chapter 1" for b in out)
