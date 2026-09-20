"""The shelf surface: what the main window shows instead of the reader.

FR-BS-050a makes the shelf a view of the existing window rather than a second
window, so this widget is one page of a stack whose other page is the reader
row. Nothing here reaches the disk or the index: the controller hands it works
and it draws them.

**Every container here is chrome.** A pane holds content rather than being
something to act on, so none of them takes a keyboard stop or paints a ring;
see the `noborderfocus` model. The controls inside them do both.

Three states are told apart because a reader acts differently on each: no
folder chosen yet (FR-BS-057), a folder that holds nothing readable
(FR-BS-058), a shelf with works on it.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from voice_reader.domain.shelf import formats
from voice_reader.ui.pane_focus import as_pane
from voice_reader.ui.sentence_case_label import SentenceCaseLabel

CHOOSE_ROOT_TEXT = "Choose a folder"
RESCAN_TEXT = "Rescan"

NO_ROOT_TEXT = "No folder has been chosen yet"
NO_BOOKS_TEXT = "That folder holds nothing NarrateX can read"
SCANNING_TEXT = "Reading your folders"
SCANNING_HINT = "This takes a few seconds the first time."

# The words under the empty states. The extensions are read from the one
# declaration of what a book is, so this sentence cannot name a format the
# scanner does not look for.
NO_ROOT_HINT = "Choose the folder holding your books and NarrateX will read it."
NO_BOOKS_HINT = f"It looks for {', '.join(sorted(formats.RECOGNISED))}."

_HEADING_POINT_SIZE = 14


class ShelfView(QWidget):
    """The shelf, as one page of the main window's stack."""

    choose_root_clicked = Signal()
    rescan_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        controls = QHBoxLayout()
        controls.setSpacing(8)
        self.btn_choose_root = QPushButton(CHOOSE_ROOT_TEXT)
        self.btn_rescan = QPushButton(RESCAN_TEXT)
        self.btn_rescan.setEnabled(False)
        controls.addWidget(self.btn_choose_root)
        controls.addWidget(self.btn_rescan)
        controls.addStretch(1)
        self.lbl_count = SentenceCaseLabel("")
        controls.addWidget(self.lbl_count)
        root.addLayout(controls)

        self.lbl_state = QLabel(NO_ROOT_TEXT)
        self.lbl_state.setAlignment(Qt.AlignCenter)
        heading = self.lbl_state.font()
        heading.setPointSize(_HEADING_POINT_SIZE)
        heading.setBold(True)
        self.lbl_state.setFont(heading)

        self.lbl_hint = QLabel(NO_ROOT_HINT)
        self.lbl_hint.setAlignment(Qt.AlignCenter)
        self.lbl_hint.setWordWrap(True)

        empty = QVBoxLayout()
        empty.setSpacing(6)
        empty.addStretch(1)
        empty.addWidget(self.lbl_state)
        empty.addWidget(self.lbl_hint)
        empty.addStretch(1)

        # A widget rather than a bare layout, so the whole block can be hidden
        # in one call once there are works to draw over it.
        self.empty_panel = as_pane(QWidget())
        self.empty_panel.setLayout(empty)
        root.addWidget(self.empty_panel, stretch=1)

        self.btn_choose_root.clicked.connect(self.choose_root_clicked.emit)
        self.btn_rescan.clicked.connect(self.rescan_clicked.emit)

    # What the controller says ----------------------------------------------

    def show_no_root(self) -> None:
        """FR-BS-057: no folder chosen; the control that chooses one is live."""

        self.lbl_state.setText(NO_ROOT_TEXT)
        self.lbl_hint.setText(NO_ROOT_HINT)
        self.empty_panel.setVisible(True)
        self.btn_choose_root.setEnabled(True)
        self.btn_rescan.setEnabled(False)
        self.lbl_count.setText("")

    def show_no_books(self) -> None:
        """FR-BS-058: a root that holds nothing, naming the formats."""

        self.lbl_state.setText(NO_BOOKS_TEXT)
        self.lbl_hint.setText(NO_BOOKS_HINT)
        self.empty_panel.setVisible(True)
        self.btn_choose_root.setEnabled(True)
        self.btn_rescan.setEnabled(True)
        self.lbl_count.setText("")

    def show_scanning(self) -> None:
        """A scan is running. Both controls are shut while it does.

        The rescan control is disabled rather than left live, because a second
        scan over the same tree can only fight the first.
        """

        self.lbl_state.setText(SCANNING_TEXT)
        self.lbl_hint.setText(SCANNING_HINT)
        self.empty_panel.setVisible(True)
        self.btn_choose_root.setEnabled(False)
        self.btn_rescan.setEnabled(False)
        self.lbl_count.setText("")

    def show_problem(self, text: str, hint: str) -> None:
        """Something went wrong, said where the reader can act on it."""

        self.lbl_state.setText(text)
        self.lbl_hint.setText(hint)
        self.empty_panel.setVisible(True)
        self.btn_choose_root.setEnabled(True)
        self.btn_rescan.setEnabled(True)
        self.lbl_count.setText("")

    def show_count(self, works: int) -> None:
        """A shelf with works on it, until the grid draws them."""

        self.empty_panel.setVisible(False)
        self.btn_choose_root.setEnabled(True)
        self.btn_rescan.setEnabled(True)
        self.lbl_count.setText(f"{works} work" if works == 1 else f"{works} works")

    def ring_stops(self) -> tuple[QWidget, ...]:
        """The controls that take a keyboard stop, in visual order."""

        return (self.btn_choose_root, self.btn_rescan)
