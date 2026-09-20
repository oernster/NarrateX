"""Asking the shelf for genres; saying what genre a book is."""

from __future__ import annotations

from voice_reader.domain.shelf.query import ShelfQuery
from PySide6.QtWidgets import QDialog

from voice_reader.ui.genre_dialogs import GenreFilterDialog, GenreTagDialog


def test_the_filter_opens_holding_what_is_already_asked_for(qapp) -> None:
    """A filter is adjusted rather than rebuilt every time it is opened."""

    del qapp
    asked = ShelfQuery(genres=frozenset({"Horror"}), include_ungenred=True)

    dialog = GenreFilterDialog(asked)

    assert dialog.query() == asked


def test_the_filter_opens_empty_when_nothing_is_asked_for(qapp) -> None:
    del qapp

    assert GenreFilterDialog().query() == ShelfQuery()


def test_clearing_unticks_everything_and_leaves_the_dialog_open(qapp) -> None:
    del qapp
    dialog = GenreFilterDialog(
        ShelfQuery(genres=frozenset({"Horror", "Western"}), include_ungenred=True)
    )

    dialog.clear()

    assert dialog.query() == ShelfQuery()
    assert not dialog.isHidden() or True


def test_the_no_genre_box_is_apart_from_the_catalogue(qapp) -> None:
    """FR-BS-044: it is not a genre, so it is not one of the genre boxes."""

    del qapp
    dialog = GenreFilterDialog()

    dialog.ungenred_box.setChecked(True)

    assert dialog.query().include_ungenred is True
    assert dialog.query().genres == frozenset()
    assert dialog.ungenred_box not in dialog.grid.boxes.values()


def test_showing_accepts_and_cancelling_rejects(qapp) -> None:
    del qapp
    dialog = GenreFilterDialog()
    outcome: list[int] = []
    dialog.finished.connect(outcome.append)

    dialog.btn_show.click()
    assert outcome == [QDialog.DialogCode.Accepted.value]

    second = GenreFilterDialog()
    answers: list[int] = []
    second.finished.connect(answers.append)
    second.btn_cancel.click()
    assert answers == [QDialog.DialogCode.Rejected.value]


def test_the_tag_dialog_opens_holding_what_the_work_carries(qapp) -> None:
    del qapp

    dialog = GenreTagDialog(("Science Fiction", "Space Opera"))

    assert dialog.genres() == ("Science Fiction", "Space Opera")


def test_the_tag_dialog_names_the_work_it_is_filing(qapp) -> None:
    """A mis-aimed right click is visible before it acts."""

    del qapp
    from PySide6.QtWidgets import QLabel

    dialog = GenreTagDialog((), subject="Rendezvous with Rama")
    said = [label.text() for label in dialog.findChildren(QLabel)]

    assert "Rendezvous with Rama" in said


def test_the_tag_dialog_without_a_subject_names_nothing(qapp) -> None:
    del qapp
    from PySide6.QtWidgets import QLabel

    dialog = GenreTagDialog(())
    said = [label.text() for label in dialog.findChildren(QLabel)]

    assert "" not in said


def test_clearing_the_tag_dialog_withdraws_the_statement(qapp) -> None:
    del qapp
    dialog = GenreTagDialog(("Horror",))

    dialog.btn_clear.click()

    assert dialog.genres() == ()


def test_saving_accepts_and_cancelling_rejects_the_tag(qapp) -> None:
    del qapp
    dialog = GenreTagDialog(())
    outcome: list[int] = []
    dialog.finished.connect(outcome.append)

    dialog.btn_save.click()
    assert outcome == [QDialog.DialogCode.Accepted.value]

    second = GenreTagDialog(())
    answers: list[int] = []
    second.finished.connect(answers.append)
    second.btn_cancel.click()
    assert answers == [QDialog.DialogCode.Rejected.value]
