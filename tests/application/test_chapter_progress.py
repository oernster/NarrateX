"""Tests for naming the chapter a listener is in.

The status line used to count text fragments, which answers no question a
listener has. These cover the replacement: the chapter, and how far into it.
"""

from __future__ import annotations

from voice_reader.application.services.chapter_progress import chapter_progress_label
from voice_reader.domain.entities.chapter import Chapter

BOOK_LENGTH = 1000


def _chapters() -> list[Chapter]:
    return [
        Chapter(title="Prologue", char_offset=0, chunk_index=0),
        Chapter(title="Chapter 1", char_offset=200, chunk_index=5),
        Chapter(title="Chapter 2", char_offset=600, chunk_index=20),
    ]


def _label(char_offset: int | None, *, chapters=None, book_length=BOOK_LENGTH):
    return chapter_progress_label(
        _chapters() if chapters is None else chapters,
        char_offset=char_offset,
        book_length=book_length,
    )


class TestNamingTheChapter:
    def test_names_the_chapter_the_offset_falls_in(self) -> None:
        assert _label(300).startswith("Chapter 1")

    def test_the_last_chapter_runs_to_the_end_of_the_book(self) -> None:
        # 600 to 1000, so 800 is halfway.
        assert _label(800) == "Chapter 2 - 50%"

    def test_an_offset_inside_the_first_chapter_names_it(self) -> None:
        assert _label(50) == "Prologue - 25%"

    def test_the_boundary_offset_belongs_to_the_chapter_it_opens(self) -> None:
        assert _label(200).startswith("Chapter 1")


class TestHowFarThrough:
    def test_the_percentage_is_of_the_chapter_not_the_book(self) -> None:
        # 400 is 20% through a 1000-char book, but halfway through a chapter
        # running 200 to 600.
        assert _label(400) == "Chapter 1 - 50%"

    def test_a_just_started_chapter_never_reads_as_zero(self) -> None:
        # Sitting at 0% reads as "nothing is happening".
        assert _label(200) == "Chapter 1 - 1%"

    def test_a_nearly_finished_chapter_never_reads_as_complete(self) -> None:
        # Sitting at 100% while still reading reads as "this is over".
        assert _label(599) == "Chapter 1 - 99%"

    def test_an_offset_past_the_end_is_still_bounded(self) -> None:
        assert _label(5000) == "Chapter 2 - 99%"


class TestWhenThereIsNothingToSay:
    def test_no_chapters_yields_no_label(self) -> None:
        assert _label(100, chapters=[]) is None

    def test_no_position_yields_no_label(self) -> None:
        assert _label(None) is None

    def test_an_offset_before_the_first_chapter_yields_no_label(self) -> None:
        chapters = [Chapter(title="Chapter 1", char_offset=500, chunk_index=0)]
        assert _label(100, chapters=chapters) is None

    def test_a_chapter_of_no_length_still_names_itself(self) -> None:
        # A book whose length is unknown, or two chapters at one offset.
        chapters = [Chapter(title="Prologue", char_offset=100, chunk_index=0)]
        assert _label(100, chapters=chapters, book_length=0) == "Prologue"
