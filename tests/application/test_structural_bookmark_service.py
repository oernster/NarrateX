from __future__ import annotations


from voice_reader.application.services.structural_bookmark_service import (
    RawHeadingCandidate,
    StructuralBookmarkService,
    classify_heading,
    dedupe_candidates,
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

