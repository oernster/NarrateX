"""`StructuralBookmarkService` input handling.

The service is the seam between a loaded book and the resolution pipeline. It
has to survive whatever the parsers hand it, because a malformed chapter
candidate should cost one heading rather than the whole section list.
"""

from __future__ import annotations

from dataclasses import dataclass

from voice_reader.application.services.structural_bookmark_service import (
    StructuralBookmarkService,
)
from voice_reader.domain.document import plain_text

TEXT = "\n\nChapter 9: Ninth\n\nA real paragraph follows here.\n"


@dataclass(frozen=True, slots=True)
class FakeChapter:
    """Stands in for the parser's Chapter entity, read by duck typing."""

    title: object = None
    char_offset: object = None
    chunk_index: object = None


def _build(text: str = TEXT, **kwargs):
    return StructuralBookmarkService().build_for_loaded_book(
        book_id="b1",
        normalized_text=text,
        document=plain_text.build_document(source=text),
        **kwargs,
    )


class TestEmptyInput:
    def test_no_text_yields_no_bookmarks(self) -> None:
        assert _build(text="") == []


class TestMinimumOffset:
    def test_a_usable_minimum_is_honoured_without_losing_the_heading(self) -> None:
        out = _build(min_char_offset=0)

        assert [b.kind for b in out] == ["chapter"]

    def test_an_unusable_minimum_is_treated_as_unset(self) -> None:
        assert _build(min_char_offset="later") == _build(min_char_offset=None)


class TestChapterCandidates:
    def test_a_candidate_with_a_title_contributes_a_heading(self) -> None:
        out = _build(
            chapter_candidates=[
                FakeChapter(title="Chapter 9: Ninth", char_offset=2, chunk_index=0)
            ]
        )

        assert [b.kind for b in out] == ["chapter"]

    def test_a_candidate_with_no_title_is_skipped(self) -> None:
        with_none = _build(chapter_candidates=[FakeChapter()])

        assert with_none == _build()

    def test_an_unusable_char_offset_falls_back_to_the_text_anchor(self) -> None:
        out = _build(
            chapter_candidates=[
                FakeChapter(title="Chapter 9: Ninth", char_offset="oops")
            ]
        )

        assert [b.kind for b in out] == ["chapter"]
        assert out[0].char_offset == TEXT.index("Chapter 9")

    def test_an_unusable_chunk_index_is_dropped_rather_than_fatal(self) -> None:
        out = _build(
            chapter_candidates=[
                FakeChapter(title="Chapter 9: Ninth", char_offset=2, chunk_index="oops")
            ]
        )

        assert [b.kind for b in out] == ["chapter"]
