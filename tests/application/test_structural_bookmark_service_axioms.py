from __future__ import annotations


from voice_reader.application.services.structural_bookmark_service import (
    StructuralBookmarkService,
)


def test_includes_axiom_headings() -> None:
    text = "\n\nPrologue\n\nX\n\nAxiom 1: Decision Events\n\nY\n\nAxiom 2: Authority\n\nZ\n"
    svc = StructuralBookmarkService()
    out = svc.build_for_loaded_book(book_id="b1", normalized_text=text)
    kinds = [b.kind for b in out]
    assert "prologue" in kinds
    assert "axiom" in kinds
    labels = [b.label for b in out]
    assert any(l.startswith("Axiom 1") for l in labels)
    assert any(l.startswith("Axiom 2") for l in labels)


def test_includes_title_case_section_headings_without_chapter_prefix() -> None:
    text = (
        "Prologue\n\n"
        "Decision Attractor Diagrams\n"
        "A paragraph follows immediately.\n\n"
        "Applied Decision Light Cones\n"
        "More text.\n"
    )
    out = StructuralBookmarkService().build_for_loaded_book(
        book_id="b1", normalized_text=text
    )
    labels = [b.label for b in out]
    assert "Prologue" in labels
    assert "Decision Attractor Diagrams" in labels
    assert "Applied Decision Light Cones" in labels


def test_does_not_treat_inline_book_title_list_as_sections() -> None:
    text = (
        "The books\n"
        "How Technical Organisations Fail and Recover\n"
        "Focuses on failure modes and recovery patterns\n"
        "Recurring Structural Patterns in Technical Organisations\n"
        "Identifies common structural patterns and their consequences\n"
        "The Move Space\n"
        "Introduces a positional model\n"
        "Relativistic Decision Architecture\n"
        "Explores how perspective\n"
    )
    out = StructuralBookmarkService().build_for_loaded_book(
        book_id="b1", normalized_text=text
    )
    labels = [b.label for b in out]
    assert "The Move Space" not in labels
    assert "Relativistic Decision Architecture" not in labels


def test_merges_wrapped_heading_lines_into_one_bookmark_label() -> None:
    # Simulate a PDF where a long heading wraps across lines.
    text = (
        "\n\nChapter 35: Structural Design for\n"
        "Technical Organisations\n\n"
        "Body text starts here.\n"
    )
    out = StructuralBookmarkService().build_for_loaded_book(
        book_id="b1", normalized_text=text
    )
    labels = [b.label for b in out]
    assert "Chapter 35: Structural Design for Technical Organisations" in labels


def test_drops_truncated_heading_when_full_joined_heading_is_adjacent() -> None:
    text = (
        "\n\n"
        "Chapter 1: What Is Decision\n"
        "Chapter 1: What Is Decision Architecture?\n\n"
        "Body.\n"
    )
    out = StructuralBookmarkService().build_for_loaded_book(
        book_id="b1", normalized_text=text
    )
    labels = [b.label for b in out]
    assert "Chapter 1: What Is Decision" not in labels
    assert "Chapter 1: What Is Decision Architecture?" in labels


def test_drops_title_case_section_heading_between_two_chapters() -> None:
    text = (
        "\n\n"
        "Chapter 13: Introducing KPIs to Improve Performance\n\n"
        "Aligning Incentives to System-Level Outcomes\n\n"
        "Chapter 14: Adding More Status Reporting to Improve Visibility\n\n"
        "Body.\n"
    )
    out = StructuralBookmarkService().build_for_loaded_book(
        book_id="b1", normalized_text=text
    )
    labels = [b.label for b in out]
    assert "Chapter 13: Introducing KPIs to Improve Performance" in labels
    assert "Chapter 14: Adding More Status Reporting to Improve Visibility" in labels
    assert "Aligning Incentives to System-Level Outcomes" not in labels


def test_includes_book_headings() -> None:
    text = (
        "Prologue\n\n"
        "Book 1: Decision Architecture\n\n"
        "Chapter 1: Start\n\n"
        "Book 2: Another\n\n"
        "Chapter 2: Next\n\n"
        "Body.\n"
    )
    out = StructuralBookmarkService().build_for_loaded_book(
        book_id="b1", normalized_text=text
    )
    labels = [b.label for b in out]
    kinds = [b.kind for b in out]
    assert "book" in kinds
    assert "Book 1: Decision Architecture" in labels
    assert "Book 2: Another" in labels

