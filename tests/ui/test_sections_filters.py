from __future__ import annotations


def test_compute_structural_bookmarks_filters_book_title_heading() -> None:
    """Regression: book titles should never appear as Sections entries."""

    import logging
    from types import SimpleNamespace

    from voice_reader.domain.entities.structural_bookmark import StructuralBookmark
    from voice_reader.ui.structural_bookmarks_helpers import compute_structural_bookmarks

    class _Svc:
        def build_for_loaded_book(self, **_):
            return [
                StructuralBookmark(
                    label="Prologue",
                    char_offset=0,
                    chunk_index=None,
                    kind="prologue",
                    level=0,
                ),
                # This is the false-positive we want to suppress.
                StructuralBookmark(
                    label="Decision Architecture",
                    char_offset=10,
                    chunk_index=None,
                    kind="section",
                    level=0,
                ),
                StructuralBookmark(
                    label="Chapter 1: Start",
                    char_offset=20,
                    chunk_index=None,
                    kind="chapter",
                    level=0,
                ),
            ]

    class _Narr:
        def __init__(self):
            self._book = type(
                "B",
                (),
                {
                    "normalized_text": "\n\nPrologue\n\nHello\n",
                    "title": "Decision Architecture",
                },
            )()

        def loaded_book_id(self):
            return "b1"

    controller = SimpleNamespace(
        narration_service=_Narr(),
        structural_bookmark_service=_Svc(),
        _chapters=[],
        _log=logging.getLogger(__name__),
    )

    comp = compute_structural_bookmarks(controller)
    assert comp is not None

    labels = [b.label for b in comp.bookmarks]
    assert "Decision Architecture" not in labels

