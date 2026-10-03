"""The book id is the book's text, not its filename (audit round 3, N-1, N-3).

Bookmarks, the resume position and the shelf's progress are all keyed by the
book id, so an id that changes when a file is renamed loses them; an id
two different books share hands one book's place to the other.
"""

from __future__ import annotations

from pathlib import Path

from voice_reader.infrastructure.books.converter import CalibreConverter
from voice_reader.infrastructure.books.parser import BookParser
from voice_reader.infrastructure.books.repository import LocalBookRepository

# Long enough that two books can share every character the old id looked at.
_SHARED_FRONT_MATTER = ("Front matter shared by two editions. " * 70).strip()


def _repository(tmp_path: Path) -> LocalBookRepository:
    return LocalBookRepository(
        converter=CalibreConverter(temp_books_dir=tmp_path / "converted"),
        parser=BookParser(),
    )


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_renaming_a_book_keeps_its_id(tmp_path: Path) -> None:
    text = "Chapter 1\n\nThe same book, word for word.\n"
    original = _write(tmp_path / "Notes.txt", text)
    renamed = _write(tmp_path / "Notes (renamed).txt", text)

    repository = _repository(tmp_path)

    assert repository.load(original).id == repository.load(renamed).id


def test_two_books_sharing_a_name_and_an_opening_have_different_ids(
    tmp_path: Path,
) -> None:
    first = _write(
        tmp_path / "a" / "Notes.txt",
        _SHARED_FRONT_MATTER + "\n\nA book about the sea.\n",
    )
    second = _write(
        tmp_path / "b" / "Notes.txt",
        _SHARED_FRONT_MATTER + "\n\nA quite different book about gardens.\n",
    )

    repository = _repository(tmp_path)

    assert repository.load(first).id != repository.load(second).id


def test_an_edit_late_in_a_book_changes_its_id(tmp_path: Path) -> None:
    """A resume offset into the old text must not land in the new one."""

    path = _write(tmp_path / "Notes.txt", _SHARED_FRONT_MATTER + "\n\nThe end.\n")
    repository = _repository(tmp_path)
    before = repository.load(path).id

    _write(path, _SHARED_FRONT_MATTER + "\n\nAn added preface.\n\nThe end.\n")

    assert repository.load(path).id != before


def test_a_loaded_book_names_the_id_earlier_versions_gave_it(tmp_path: Path) -> None:
    """The old id is how an existing reader's bookmarks are found again."""

    import hashlib

    path = _write(tmp_path / "Notes.txt", "Chapter 1\n\nSome prose.\n")
    book = _repository(tmp_path).load(path)

    old_id = hashlib.sha256(
        ("Notes" + book.normalized_text[:2000]).encode("utf-8")
    ).hexdigest()[:16]
    assert book.legacy_ids == (old_id,)
    assert book.id != old_id
