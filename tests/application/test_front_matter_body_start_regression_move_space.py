from __future__ import annotations


from voice_reader.application.services.structural_bookmark_service import (
    StructuralBookmarkService,
    detect_body_start_offset,
)


def test_body_start_ignores_toc_like_entries_and_handles_running_contents_header() -> None:
    # Regression fixture modeled on `decision-architecture-the-move-space.pdf`.
    #
    # PDF extracts can contain:
    # - a TOC where entries include dotted leaders + page numbers
    # - a repeated running header "Contents" (page header) immediately before the
    #   real body begins
    #
    # The body start must be the *body* Prologue, not the TOC entry.
    text = (
        "Decision Architecture: The Move\n"
        "Space\n\n"
        "Contents\n"
        "Prologue . . . . . . . . . . 1\n"
        "Chapter 1: These Are Not Examples2\n\n"
        "Contents\n"
        "Prologue\n\n"
        "Most organisational change fails.\n"
    )

    off = detect_body_start_offset(text)
    assert off == text.index("\nPrologue\n\n") + 1

    svc = StructuralBookmarkService()
    out = svc.build_for_loaded_book(book_id="b1", normalized_text=text)
    kinds = [b.kind for b in out]
    assert "prologue" in kinds

    # Prologue should be the first bookmark and anchored to the body occurrence.
    assert out[0].kind == "prologue"
    assert out[0].char_offset == text.index("\nPrologue\n\n") + 1


def test_epub_style_toc_does_not_leak_last_entry_as_first_section() -> None:
    # Some EPUBs include a plain list of headings as a "Table of Contents"
    # without dotted leaders or page numbers. The end of that block should be
    # detected at the first *body* heading, not at the last TOC entry.
    text = (
        "Table of Contents\n"
        "Prologue\n"
        "Chapter 1 - Start\n"
        "Chapter 51 - Tail Entry\n\n"
        "Prologue\n\n"
        "Body prose begins here with enough words to count as prose.\n"
    )

    svc = StructuralBookmarkService()
    out = svc.build_for_loaded_book(book_id="b1", normalized_text=text)
    assert out
    assert out[0].kind == "prologue"
    assert out[0].char_offset == text.index("\nPrologue\n\n") + 1

