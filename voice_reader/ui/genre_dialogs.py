"""Asking the shelf for genres; saying what genre a book is.

Two dialogs over the one grid of boxes, because they are two acts rather than
one: FR-BS-042 narrows what is shown, FR-BS-046 states what a book is. The
difference between them lives in `genre_grid.Manner` and nowhere else.

**Not stated is a box of its own, apart from the catalogue** (FR-BS-044). It is
not a genre, so it does not sit among them. Measured over the reference
library, only 1533 of 2784 files state any subject at all, so without this box
most of the shelf would be hidden behind a field nobody filled in.

**Clearing is a button rather than a chore** (FR-BS-045). Undoing a filter by
hunting for every ticked box is the kind of tidying a dialog should do for
somebody.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from voice_reader.domain.shelf.query import ShelfQuery
from voice_reader.ui.first_stop_dialog import FirstStopDialog
from voice_reader.ui.genre_grid import ASKING, STATING, GenreGrid
from voice_reader.ui.pane_focus import as_pane
from voice_reader.ui.ringed_check import RingedCheckBox

FILTER_TITLE = "Filter by genre"
TAG_TITLE = "File under a genre"
SHOW_TEXT = "Show"
SAVE_TEXT = "Save"
CLEAR_TEXT = "Clear"
CANCEL_TEXT = "Cancel"
UNGENRED_TEXT = "Books that state no genre"

# Wide enough for the catalogue's three columns without the longest name
# wrapping; tall enough that the scroll area is the exception.
DIALOG_WIDTH_PX = 760
DIALOG_HEIGHT_PX = 620

# The gap that rules the ungenred box apart from the catalogue above it.
# Without it the box sits under the last column and reads as one more genre,
# which is exactly what it is not.
APART_PX = 12

_TITLE_STYLE = "font-size: 14px; font-weight: 600;"


def _titled(dialog: FirstStopDialog, words: str) -> QVBoxLayout:
    """The frameless shell every dialog here wears, with its own heading.

    Frameless for the same reason the Bookmarks dialog is: Ubuntu's Yaru theme
    draws the title bar's minimise control as an em dash.
    """

    dialog.setWindowTitle(words)
    dialog.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
    dialog.setModal(True)
    dialog.resize(DIALOG_WIDTH_PX, DIALOG_HEIGHT_PX)
    root = QVBoxLayout(dialog)
    root.setContentsMargins(12, 12, 12, 12)
    root.setSpacing(10)
    heading = QLabel(words, dialog)
    heading.setStyleSheet(_TITLE_STYLE)
    root.addWidget(heading)
    return root


def _scrolled(grid: GenreGrid, parent: QWidget) -> QScrollArea:
    """The grid in a scroller, so a small screen still reaches every genre.

    A pane holds content rather than being something to act on, so it takes no
    keyboard stop and paints no ring; the boxes inside it do both.
    """

    area = as_pane(QScrollArea(parent))
    area.setWidgetResizable(True)
    area.setFrameShape(QScrollArea.Shape.NoFrame)
    area.setWidget(grid)
    return area


class GenreFilterDialog(FirstStopDialog):
    """Collects the genres to narrow the shelf to; nothing else."""

    def __init__(self, query: ShelfQuery | None = None, parent=None) -> None:
        super().__init__(parent)
        asked = query or ShelfQuery()
        self._asked = asked
        root = _titled(self, FILTER_TITLE)

        # Opened holding what is already being asked for, so a filter is
        # adjusted rather than rebuilt every time the dialog is opened.
        self.grid = GenreGrid(asked.genres, self, manner=ASKING)
        root.addWidget(_scrolled(self.grid, self), stretch=1)
        root.addSpacing(APART_PX)

        self.ungenred_box = RingedCheckBox(UNGENRED_TEXT, self)
        self.ungenred_box.setChecked(asked.include_ungenred)
        root.addWidget(self.ungenred_box)

        self.btn_clear = QPushButton(CLEAR_TEXT, self)
        self.btn_cancel = QPushButton(CANCEL_TEXT, self)
        self.btn_show = QPushButton(SHOW_TEXT, self)
        row = QHBoxLayout()
        row.addWidget(self.btn_clear)
        row.addStretch(1)
        row.addWidget(self.btn_cancel)
        row.addWidget(self.btn_show)
        root.addLayout(row)

        self.btn_clear.clicked.connect(self.clear)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_show.clicked.connect(self.accept)

    def clear(self) -> None:
        """Untick everything, leaving the dialog open to be asked again.

        It does not close: clearing and then showing the whole shelf is two
        presses, while somebody who cleared by accident has lost nothing.
        """

        self.grid.set_all(False)
        self.ungenred_box.setChecked(False)

    def query(self) -> ShelfQuery:
        """What has been asked for, as the shelf takes it.

        Built onto the query the dialog opened with rather than from nothing,
        so what this dialog does not ask about survives it: the words in the
        search field and the order the shelf is shown in.
        """

        return replace(
            self._asked,
            genres=frozenset(self.grid.chosen()),
            include_ungenred=self.ungenred_box.isChecked(),
        )


class GenreTagDialog(FirstStopDialog):
    """States what a book is: FR-BS-046, with FR-BS-046a for several."""

    def __init__(
        self,
        carried: Iterable[str] = (),
        parent=None,
        *,
        subject: str = "",
    ) -> None:
        super().__init__(parent)
        root = _titled(self, TAG_TITLE)
        if subject:
            named = QLabel(subject, self)
            named.setWordWrap(True)
            root.addWidget(named)

        self.grid = GenreGrid(carried, self, manner=STATING)
        root.addWidget(_scrolled(self.grid, self), stretch=1)

        self.btn_clear = QPushButton(CLEAR_TEXT, self)
        self.btn_cancel = QPushButton(CANCEL_TEXT, self)
        self.btn_save = QPushButton(SAVE_TEXT, self)
        row = QHBoxLayout()
        row.addWidget(self.btn_clear)
        row.addStretch(1)
        row.addWidget(self.btn_cancel)
        row.addWidget(self.btn_save)
        root.addLayout(row)

        self.btn_clear.clicked.connect(lambda: self.grid.set_all(False))
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_save.clicked.connect(self.accept)

    def genres(self) -> tuple[str, ...]:
        """The genres ticked; empty meaning the reader's statement is withdrawn."""

        return self.grid.chosen()
