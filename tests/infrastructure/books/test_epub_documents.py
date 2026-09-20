"""Reading an EPUB's documents; what gets left out of the book."""

from __future__ import annotations

from voice_reader.domain.document.anchoring import BlockDraft
from voice_reader.domain.document.block_kind import BlockKind
from voice_reader.infrastructure.books.epub_documents import (
    epub_title,
    item_html,
    navigation_names,
    without_page_furniture,
)

TITLE = "When the Wind Blows"


class _Item:
    """An EPUB item, as the readers in the wild present one."""

    def __init__(self, content=None, body=None) -> None:
        if content is not None:
            self.get_content = lambda: content
        if body is not None:
            self.get_body_content = lambda: body


class _Exploding:
    def get_content(self):
        raise RuntimeError("this item cannot be read")


class _Book:
    def __init__(self, stated) -> None:
        self._stated = stated

    def get_metadata(self, namespace, name):
        del namespace, name
        return self._stated


def _draft(text: str) -> BlockDraft:
    return BlockDraft(kind=BlockKind.PARAGRAPH, text=text)


# The bytes of a document -------------------------------------------------


def test_the_usual_getter_is_used_when_it_answers() -> None:
    assert item_html(_Item(content=b"<p>x</p>")) == b"<p>x</p>"


def test_the_body_getter_is_used_when_the_first_answers_nothing() -> None:
    assert item_html(_Item(content=b"", body=b"<p>y</p>")) == b"<p>y</p>"


def test_an_item_that_answers_nothing_at_all_is_absent_rather_than_a_fault() -> None:
    assert item_html(_Item()) is None


def test_a_getter_that_explodes_is_passed_over() -> None:
    assert item_html(_Exploding()) is None


# What the book says it is called -----------------------------------------


def test_the_stated_title_is_read_off_the_metadata() -> None:
    assert epub_title(_Book([(TITLE, {})])) == TITLE


def test_a_bare_string_is_accepted_as_well_as_a_pair() -> None:
    assert epub_title(_Book([TITLE])) == TITLE


def test_a_blank_or_absent_title_is_no_title() -> None:
    assert epub_title(_Book([("   ", {})])) is None
    assert epub_title(_Book([])) is None
    assert epub_title(_Book(None)) is None


def test_a_book_that_cannot_be_asked_states_no_title() -> None:
    class _Silent:
        def get_metadata(self, namespace, name):
            raise RuntimeError("no metadata here")

    assert epub_title(_Silent()) is None


# The running header ------------------------------------------------------


def test_the_running_header_leaves_the_text_and_the_blocks_together() -> None:
    """FR: what the narrator says and what the pane shows must agree."""

    documents = [
        (TITLE, (_draft(TITLE),)),
        (f"{TITLE}\nPrologue", (_draft(TITLE), _draft("Prologue"))),
        (f"{TITLE}\nThe wind rose.", (_draft(TITLE), _draft("The wind rose."))),
    ]

    texts, drafts = without_page_furniture(documents, title=TITLE)

    assert texts == ["Prologue", "The wind rose."]
    assert [d.text for d in drafts] == ["Prologue", "The wind rose."]


def test_a_book_with_no_running_header_keeps_every_word() -> None:
    documents = [
        (TITLE, (_draft(TITLE),)),
        ("Prologue", (_draft("Prologue"),)),
    ]

    texts, drafts = without_page_furniture(documents, title=TITLE)

    assert texts == [TITLE, "Prologue"]
    assert [d.text for d in drafts] == [TITLE, "Prologue"]


def test_a_document_with_no_blocks_still_offers_its_text() -> None:
    """The text-only fallback, for an EPUB no HTML parser would take."""

    documents = [("Prologue", ()), ("The wind rose.", ())]

    texts, drafts = without_page_furniture(documents, title=TITLE)

    assert texts == ["Prologue", "The wind rose."]
    assert drafts == []


# What the book's navigation states -----------------------------------------


class _Link:
    def __init__(self, title) -> None:
        self.title = title


class _Navigated:
    def __init__(self, toc) -> None:
        self.toc = toc


def test_the_navigation_names_are_read_in_reading_order() -> None:
    book = _Navigated([_Link("Prologue"), _Link("Chapter 1")])

    assert navigation_names(book) == ("Prologue", "Chapter 1")


def test_a_nested_navigation_is_flattened() -> None:
    """Depth expresses a part within a book; a list of names need not."""

    book = _Navigated([_Link("Book One"), [_Link("Chapter 1"), _Link("Chapter 2")]])

    assert navigation_names(book) == ("Book One", "Chapter 1", "Chapter 2")


def test_entries_with_no_usable_name_are_passed_over() -> None:
    book = _Navigated([_Link("Chapter 1"), _Link("  "), _Link(None), object()])

    assert navigation_names(book) == ("Chapter 1",)


def test_a_book_with_no_navigation_states_no_names() -> None:
    assert navigation_names(_Navigated(None)) == ()
    assert navigation_names(object()) == ()


def test_a_navigation_that_cannot_be_read_states_no_names() -> None:
    class _Broken:
        @property
        def toc(self):
            raise RuntimeError("no navigation here")

    assert navigation_names(_Broken()) == ()


def test_the_navigation_reaches_the_blocks_it_names() -> None:
    """The whole spine at once: the fallback needs every document first."""

    documents = [
        ("Chapter 1", (_draft("Chapter 1"),)),
        ("Chapter 2", (_draft("Chapter 2"),)),
    ]

    _texts, drafts = without_page_furniture(
        documents, title=TITLE, navigation=("Chapter 1", "Chapter 2")
    )

    assert [d.kind for d in drafts] == [BlockKind.HEADING, BlockKind.HEADING]
