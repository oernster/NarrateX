from __future__ import annotations


from voice_reader.application.services.structural_bookmark_service import (
    RawHeadingCandidate,
    StructuralBookmarkService,
    classify_heading,
    dedupe_candidates,
    detect_body_start_offset,
    scan_structural_headings,
)


def test_includes_chapter_headings() -> None:
    text = "\n\nChapter 1: Start\n\nA real paragraph.\n"
    svc = StructuralBookmarkService()
    out = svc.build_for_loaded_book(book_id="b1", normalized_text=text)
    assert [b.kind for b in out] == ["chapter"]
    assert out[0].label.startswith("Chapter 1")
    assert out[0].char_offset >= 0


def test_includes_part_headings() -> None:
    text = "\n\nPart I - Foundations\n\nChapter 1: Start\n\n"
    svc = StructuralBookmarkService()
    out = svc.build_for_loaded_book(book_id="b1", normalized_text=text)
    kinds = [b.kind for b in out]
    assert "part" in kinds


def test_includes_prologue_and_conclusion() -> None:
    text = "\n\nPrologue\n\nOnce upon a time.\n\nConclusion\n\nThe end.\n"
    svc = StructuralBookmarkService()
    out = svc.build_for_loaded_book(book_id="b1", normalized_text=text)
    assert [b.kind for b in out] == ["prologue", "conclusion"]


def test_excludes_table_of_contents_and_essay_index() -> None:
    for label in ["Table of Contents", "Contents", "Essay Index", "Pattern Index"]:
        kind, include, _prio = classify_heading(label)
        assert include is False
        assert kind is None

    text = "\n\nTable of Contents\n\n1 Something\n\nChapter 1: Start\n\n"
    svc = StructuralBookmarkService()
    out = svc.build_for_loaded_book(book_id="b1", normalized_text=text)
    assert [b.kind for b in out] == ["chapter"]


def test_prefers_metadata_candidate_over_text_scan_duplicate() -> None:
    text = "\n\nChapter 1: Start\n\nA para.\n"
    # Create both a metadata and text_scan candidate at a nearby offset.
    md = RawHeadingCandidate(
        label="Chapter 1: Start",
        char_offset=2,
        chunk_index=7,
        source="nav",
    )
    scan = RawHeadingCandidate(
        label="Chapter 1: Start",
        char_offset=10,
        chunk_index=None,
        source="text_scan",
    )

    deduped = dedupe_candidates(candidates=[scan, md])
    assert len(deduped) == 1
    assert deduped[0].source == "nav"

    svc = StructuralBookmarkService()
    out = svc.build_for_loaded_book(
        book_id="b1",
        normalized_text=text,
        chapter_candidates=[
            type(
                "Ch",
                (),
                {"title": "Chapter 1: Start", "char_offset": 2, "chunk_index": 7},
            )()
        ],
    )
    assert len(out) == 1
    assert out[0].kind == "chapter"
    assert out[0].char_offset == 2


def test_sorts_by_char_offset() -> None:
    text = "\n\nChapter 2: Two\n\nX\n\nChapter 1: One\n\n"
    svc = StructuralBookmarkService()
    out = svc.build_for_loaded_book(book_id="b1", normalized_text=text)
    # Output should be ordered by appearance, not chapter number.
    assert [b.label for b in out] == ["Chapter 2: Two", "Chapter 1: One"]
    assert out[0].char_offset < out[1].char_offset


def test_uses_char_offset_as_primary_navigation_anchor() -> None:
    text = "\n\nPart I - Foundations\n\n"
    cand = scan_structural_headings(normalized_text=text)
    assert cand
    assert cand[0].char_offset is not None
    svc = StructuralBookmarkService()
    out = svc.build_for_loaded_book(book_id="b1", normalized_text=text)
    assert out
    assert isinstance(out[0].char_offset, int)


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
    out = svc.build_for_loaded_book(book_id="b1", normalized_text=text)
    labels = [b.label for b in out]
    assert "Chapter 3" in labels

    b3 = [b for b in out if b.label == "Chapter 3"][0]
    assert b3.kind == "chapter"
    assert b3.char_offset == text.index("\nChapter 3\nBody 3") + 1


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
    out = svc.build_for_loaded_book(book_id="b1", normalized_text=text)
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
    out = svc.build_for_loaded_book(book_id="b1", normalized_text=text)

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

    off = detect_body_start_offset(text)
    assert off == text.index("Prologue")


def test_metadata_candidate_before_body_start_is_corrected_to_body_occurrence() -> None:
    text = (
        "Table of Contents\n\n"
        "Chapter 3\n\n"
        "Prologue\n\n"
        "Chapter 3\nBody\n"
    )

    # Simulate metadata pointing at the TOC occurrence.
    md = type(
        "Ch",
        (),
        {"title": "Chapter 3", "char_offset": text.index("Chapter 3"), "chunk_index": None},
    )()

    svc = StructuralBookmarkService()
    out = svc.build_for_loaded_book(book_id="b1", normalized_text=text, chapter_candidates=[md])
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
    out = svc.build_for_loaded_book(book_id="b1", normalized_text=text)
    assert all(b.label != "Chapter 7" for b in out)

