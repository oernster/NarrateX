"""Tidying of the section list after the headings have been resolved.

Three passes: drop a section that merely repeats the chapter title above it,
drop title-case subheadings sitting between two chapters, and give each book in
an omnibus its own prologue rather than letting deduplication collapse them.
"""

from __future__ import annotations

from voice_reader.application.services.structural_bookmarks.postprocess import (
    inject_prologue_after_each_book,
    suppress_redundant_title_sections,
    suppress_sections_between_chapters,
)
from voice_reader.domain.entities.structural_bookmark import StructuralBookmark


def _bookmark(
    label: str, *, offset: object = 0, kind: str = "section"
) -> StructuralBookmark:
    return StructuralBookmark(
        label=label,
        char_offset=offset,  # type: ignore[arg-type]
        chunk_index=None,
        kind=kind,
        level=0,
    )


class TestRedundantTitleSections:
    def test_a_section_repeating_the_chapter_title_is_dropped(self) -> None:
        chapter = _bookmark("Chapter 1: These Are Not Examples", kind="chapter")
        echo = _bookmark("These Are Not Examples", offset=40)

        assert suppress_redundant_title_sections(bookmarks=[chapter, echo]) == [chapter]

    def test_the_same_echo_far_below_is_kept(self) -> None:
        chapter = _bookmark("Chapter 1: These Are Not Examples", kind="chapter")
        later = _bookmark("These Are Not Examples", offset=5_000)

        kept = suppress_redundant_title_sections(bookmarks=[chapter, later])

        assert kept == [chapter, later]

    def test_a_section_with_different_text_is_kept(self) -> None:
        chapter = _bookmark("Chapter 1: These Are Not Examples", kind="chapter")
        other = _bookmark("Something Entirely Else", offset=40)

        kept = suppress_redundant_title_sections(bookmarks=[chapter, other])

        assert kept == [chapter, other]

    def test_a_chapter_with_no_title_after_the_number_suppresses_nothing(self) -> None:
        chapter = _bookmark("Chapter 1", kind="chapter")
        section = _bookmark("Some Heading Here", offset=40)

        kept = suppress_redundant_title_sections(bookmarks=[chapter, section])

        assert kept == [chapter, section]

    def test_an_unusable_offset_is_treated_as_not_close(self) -> None:
        chapter = _bookmark("Chapter 1: These Are Not Examples", kind="chapter")
        broken = _bookmark("These Are Not Examples", offset="not a number")

        kept = suppress_redundant_title_sections(bookmarks=[chapter, broken])

        assert kept == [chapter, broken]

    def test_a_leading_section_has_nothing_above_it_to_repeat(self) -> None:
        section = _bookmark("These Are Not Examples")

        assert suppress_redundant_title_sections(bookmarks=[section]) == [section]

    def test_a_section_below_a_prologue_is_left_alone(self) -> None:
        prologue = _bookmark("Prologue", kind="prologue")
        section = _bookmark("Prologue", offset=40)

        kept = suppress_redundant_title_sections(bookmarks=[prologue, section])

        assert kept == [prologue, section]


class TestSectionsBetweenChapters:
    def test_a_section_between_two_chapters_is_dropped(self) -> None:
        first = _bookmark("Chapter 1", offset=0, kind="chapter")
        middle = _bookmark("A Subheading", offset=100)
        second = _bookmark("Chapter 2", offset=200, kind="chapter")

        kept = suppress_sections_between_chapters(bookmarks=[first, middle, second])

        assert kept == [first, second]

    def test_a_book_with_one_chapter_keeps_its_sections(self) -> None:
        chapter = _bookmark("Chapter 1", offset=0, kind="chapter")
        section = _bookmark("A Subheading", offset=100)

        kept = suppress_sections_between_chapters(bookmarks=[chapter, section])

        assert kept == [chapter, section]

    def test_a_section_before_the_first_chapter_is_kept(self) -> None:
        section = _bookmark("A Subheading", offset=0)
        first = _bookmark("Chapter 1", offset=100, kind="chapter")
        second = _bookmark("Chapter 2", offset=200, kind="chapter")

        kept = suppress_sections_between_chapters(bookmarks=[section, first, second])

        assert kept == [section, first, second]

    def test_a_section_after_the_last_chapter_is_kept(self) -> None:
        first = _bookmark("Chapter 1", offset=0, kind="chapter")
        second = _bookmark("Chapter 2", offset=100, kind="chapter")
        trailing = _bookmark("A Subheading", offset=200)

        kept = suppress_sections_between_chapters(bookmarks=[first, second, trailing])

        assert kept == [first, second, trailing]


class TestProloguePerBook:
    TEXT = "Book One\n\nPrologue\n\nbody one\n\nBook Two\n\nPrologue\n\nbody two\n"

    def _books(self) -> list[StructuralBookmark]:
        return [
            _bookmark("Book One", offset=0, kind="book"),
            _bookmark("Book Two", offset=self.TEXT.index("Book Two"), kind="book"),
        ]

    def test_each_book_gains_its_own_prologue(self) -> None:
        out = inject_prologue_after_each_book(
            bookmarks=self._books(), normalized_text=self.TEXT
        )

        prologues = [b for b in out if b.kind == "prologue"]
        assert len(prologues) == 2
        assert [b.label for b in prologues] == ["Prologue", "Prologue"]
        assert [b.char_offset for b in out] == sorted(b.char_offset for b in out)

    def test_a_book_that_already_has_a_prologue_is_left_alone(self) -> None:
        existing = _bookmark(
            "Prologue", offset=self.TEXT.index("Prologue"), kind="prologue"
        )
        bookmarks = [self._books()[0], existing]

        out = inject_prologue_after_each_book(
            bookmarks=bookmarks, normalized_text=self.TEXT
        )

        assert len([b for b in out if b.kind == "prologue"]) == 1

    def test_a_prologue_too_far_below_its_book_is_not_claimed(self) -> None:
        out = inject_prologue_after_each_book(
            bookmarks=self._books(), normalized_text=self.TEXT, max_distance=1
        )

        assert [b for b in out if b.kind == "prologue"] == []

    def test_a_book_with_no_prologue_of_its_own_gains_nothing(self) -> None:
        text = "Book One\n\nPrologue\n\nbody one\n\nBook Two\n\nbody two\n"
        bookmarks = [
            _bookmark("Book One", offset=0, kind="book"),
            _bookmark("Book Two", offset=text.index("Book Two"), kind="book"),
        ]

        out = inject_prologue_after_each_book(bookmarks=bookmarks, normalized_text=text)

        assert len([b for b in out if b.kind == "prologue"]) == 1

    def test_a_document_with_no_books_is_untouched(self) -> None:
        bookmarks = [_bookmark("Chapter 1", kind="chapter")]

        out = inject_prologue_after_each_book(
            bookmarks=bookmarks, normalized_text=self.TEXT
        )

        assert out == bookmarks

    def test_empty_text_is_untouched(self) -> None:
        bookmarks = self._books()

        out = inject_prologue_after_each_book(bookmarks=bookmarks, normalized_text="")

        assert out == bookmarks

    def test_text_without_a_prologue_line_is_untouched(self) -> None:
        bookmarks = [_bookmark("Book One", offset=0, kind="book")]

        out = inject_prologue_after_each_book(
            bookmarks=bookmarks, normalized_text="Book One\n\nbody only\n"
        )

        assert out == bookmarks
