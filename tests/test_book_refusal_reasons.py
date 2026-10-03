"""Refusing a book for the right reason (audit round 3, N-11).

A text of nothing but scene separators was adopted and then finished at once,
since narration drops separator lines; it now meets the no-text message. A
copy-protected EPUB parses to nothing too and was told its pages were probably
pictures; it is now told it is protected. Font obfuscation also uses
`encryption.xml` in books with no protection at all, so that alone changes
nothing.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from tests.infrastructure.test_book_repository import FakeConverter, FakeParser
from voice_reader.infrastructure.books.epub_protection import MAX_NOTES_BYTES
from voice_reader.infrastructure.books.repository import LocalBookRepository
from voice_reader.shared.errors import BookHasNoTextError, BookIsProtectedError

_DRM = "http://www.w3.org/2001/04/xmlenc#aes128-cbc"
_FONT_OBFUSCATION = "http://www.idpf.org/2008/embedding"


def _repository(normalized: str = "") -> LocalBookRepository:
    return LocalBookRepository(
        converter=FakeConverter(),
        parser=FakeParser(raw_text=normalized, normalized_text=normalized),
    )


def _encryption_xml(*references: tuple[str, str]) -> str:
    data = "".join(
        '<EncryptedData xmlns="http://www.w3.org/2001/04/xmlenc#">'
        f'<EncryptionMethod Algorithm="{algorithm}"/>'
        f'<CipherData><CipherReference URI="{uri}"/></CipherData>'
        "</EncryptedData>"
        for algorithm, uri in references
    )
    return (
        '<encryption xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
        f"{data}</encryption>"
    )


def _epub(path: Path, encryption: str | None) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip")
        if encryption is not None:
            archive.writestr("META-INF/encryption.xml", encryption)
    return path


def test_a_text_of_nothing_but_separators_is_refused(tmp_path: Path) -> None:
    with pytest.raises(BookHasNoTextError):
        _repository("---\n\n***\n\n___").load(tmp_path / "scenes.txt")


def test_a_separator_between_words_is_still_a_book(tmp_path: Path) -> None:
    book = _repository("One.\n\n---\n\nTwo.").load(tmp_path / "scenes.txt")

    assert book.normalized_text.startswith("One.")


def test_a_protected_epub_is_told_it_is_protected(tmp_path: Path) -> None:
    book = _epub(
        tmp_path / "locked.epub",
        _encryption_xml((_DRM, "OEBPS/chapter1.xhtml")),
    )

    with pytest.raises(BookIsProtectedError) as caught:
        _repository().load(book)

    assert str(caught.value) == BookIsProtectedError.READER_TEXT
    assert isinstance(caught.value, BookHasNoTextError)


def test_unreadable_encryption_notes_count_as_protection(tmp_path: Path) -> None:
    book = _epub(tmp_path / "locked.epub", "<encryption><not closed")

    with pytest.raises(BookIsProtectedError):
        _repository().load(book)


def test_encryption_notes_too_large_to_read_count_as_protection(
    tmp_path: Path,
) -> None:
    padding = " " * MAX_NOTES_BYTES
    book = _epub(tmp_path / "locked.epub", f"<encryption>{padding}</encryption>")

    with pytest.raises(BookIsProtectedError):
        _repository().load(book)


def test_obfuscated_fonts_alone_are_not_protection(tmp_path: Path) -> None:
    book = _epub(
        tmp_path / "fonts.epub",
        _encryption_xml((_FONT_OBFUSCATION, "OEBPS/fonts/serif.otf")),
    )

    with pytest.raises(BookHasNoTextError) as caught:
        _repository().load(book)

    assert not isinstance(caught.value, BookIsProtectedError)


def test_an_epub_with_no_encryption_notes_keeps_the_usual_reason(
    tmp_path: Path,
) -> None:
    book = _epub(tmp_path / "pictures.epub", None)

    with pytest.raises(BookHasNoTextError) as caught:
        _repository().load(book)

    assert not isinstance(caught.value, BookIsProtectedError)


def test_a_file_that_is_not_an_archive_keeps_the_usual_reason(tmp_path: Path) -> None:
    book = tmp_path / "odd.epub"
    book.write_bytes(b"not a zip")

    with pytest.raises(BookHasNoTextError) as caught:
        _repository().load(book)

    assert not isinstance(caught.value, BookIsProtectedError)
