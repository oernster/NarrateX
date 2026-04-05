from __future__ import annotations


from voice_reader.application.services.structural_bookmark_service import (
    StructuralBookmarkService,
)


def test_front_matter_marker_allows_parenthetical_variants() -> None:
    # Some books render e.g. "Essay Index (overview)".
    text = "Contents\n\nEssay Index (overview)\n\nPrologue\n\nHello\n"
    svc = StructuralBookmarkService()
    out = svc.build_for_loaded_book(book_id="b1", normalized_text=text)
    # Ensure markers don't create spurious sections.
    assert any(b.kind == "prologue" for b in out)
    assert all("essay index" not in b.label.casefold() for b in out)

