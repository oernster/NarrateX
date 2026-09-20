"""The shelf surface: what the main window shows instead of the reader.

FR-BS-050a makes the shelf a view of the existing window rather than a second
window, so this widget is one page of a stack whose other page is the reader
row. Nothing here reaches the disk or the index: the controller hands it works
and it draws them.

**Every container here is chrome.** A pane holds content rather than being
something to act on, so none of them takes a keyboard stop or paints a ring;
see the `noborderfocus` model. The controls inside them do both.

Four states are told apart because a reader acts differently on each: no folder
chosen yet (FR-BS-057), a folder that holds nothing readable (FR-BS-058), a scan
running, a shelf with works on it. Only the last one shows the grid; the grid
itself arrives from the controller, which is what holds the cover service.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from voice_reader.domain.shelf import formats
from voice_reader.ui._icon_buttons import icon_button
from voice_reader.ui.artwork import ICON_BUTTON_PX, ICON_PX, Artwork
from voice_reader.ui.pane_focus import as_pane
from voice_reader.ui.sentence_case_label import SentenceCaseLabel
from voice_reader.ui.shelf_grid import ShelfGrid

CHOOSE_ROOT_TEXT = "Choose a folder"
RESCAN_TEXT = "Rescan"
FILTER_TEXT = "Filter by genre"
FILTER_TOOLTIP = "Show only the genres you choose"
SEARCH_PLACEHOLDER = "Search by title or author"

NO_ROOT_TEXT = "No folder has been chosen yet"
NO_BOOKS_TEXT = "That folder holds nothing NarrateX can read"
SCANNING_TEXT = "Reading your folders"
SCANNING_HINT = "This takes a few seconds the first time."

# The words under the empty states. The extensions are read from the one
# declaration of what a book is, so this sentence cannot name a format the
# scanner does not look for.
NO_ROOT_HINT = "Choose the folder holding your books and NarrateX will read it."
NO_BOOKS_HINT = f"It looks for {', '.join(sorted(formats.RECOGNISED))}."

# How wide the search field is. Wide enough for an author's full name,
# narrow enough to leave the count where a reader already looks for it.
SEARCH_BOX_PX = 220

# What the count reads while the scan is still finding books (FR-BS-036).
FILLING_TEXT = "{words} so far"

_HEADING_POINT_SIZE = 14


def work_count_words(count: int) -> str:
    """How many works, worded so it still reads correctly at one."""

    return f"{count} work" if count == 1 else f"{count} works"


class ShelfView(QWidget):
    """The shelf, as one page of the main window's stack."""

    choose_root_clicked = Signal()
    rescan_clicked = Signal()
    filter_clicked = Signal()
    #: FR-BS-047: the reader typed; the shelf narrows to what they typed.
    search_changed = Signal(str)

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
        # A picture button beside two worded ones. Its box is taken from the
        # buttons it stands next to rather than from a number of its own, so
        # the row stays level whatever the font does to the words; see
        # `_match_the_row`, which does the measuring once the sheet is on.
        self.btn_filter = icon_button(
            artwork=Artwork.FILTER,
            text=FILTER_TEXT,
            tooltip=FILTER_TOOLTIP,
            parent=self,
        )
        self.btn_filter.setEnabled(False)
        # FR-BS-047. Ported from Stellody's search box, minus the button that
        # summons it: that exists because its tray has no room for a field,
        # while this row has a stretch in it doing nothing.
        self.txt_search = QLineEdit(self)
        self.txt_search.setObjectName("ShelfSearch")
        self.txt_search.setPlaceholderText(SEARCH_PLACEHOLDER)
        self.txt_search.setClearButtonEnabled(True)
        self.txt_search.setFixedWidth(SEARCH_BOX_PX)
        self.txt_search.setEnabled(False)
        controls.addWidget(self.btn_choose_root)
        controls.addWidget(self.btn_rescan)
        controls.addWidget(self.btn_filter)
        controls.addWidget(self.txt_search)
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

        # The grid arrives from the controller, which is what holds the cover
        # service; a view with no grid installed still draws its empty states.
        self.grid: ShelfGrid | None = None
        self._root = root

        self.btn_choose_root.clicked.connect(self.choose_root_clicked.emit)
        self.btn_rescan.clicked.connect(self.rescan_clicked.emit)
        self.btn_filter.clicked.connect(self.filter_clicked.emit)
        self.txt_search.textChanged.connect(self.search_changed.emit)

    # What the controller says ----------------------------------------------

    def install_grid(self, grid: ShelfGrid) -> None:
        """Take the grid the controller built and keep it hidden until it holds."""

        self.grid = grid
        self._root.addWidget(grid, stretch=1)
        grid.setVisible(False)
        # The window set its ring before the grid existed, so the grid takes its
        # place in the chain here: directly after the search field, which is the
        # last of the controls above it.
        QWidget.setTabOrder(self.txt_search, grid)

    def show_no_root(self) -> None:
        """FR-BS-057: no folder chosen; the control that chooses one is live."""

        self._say(NO_ROOT_TEXT, NO_ROOT_HINT, can_rescan=False)

    def show_no_books(self) -> None:
        """FR-BS-058: a root that holds nothing, naming the formats."""

        self._say(NO_BOOKS_TEXT, NO_BOOKS_HINT)

    def show_scanning(self) -> None:
        """A scan is running. Every control above the shelf is shut while it is.

        The rescan control is disabled rather than left live, because a second
        scan over the same tree can only fight the first; the filter and the
        search shut with it, since neither can narrow a shelf that is not there.
        """

        self._say(SCANNING_TEXT, SCANNING_HINT, can_choose=False, can_rescan=False)

    def show_problem(self, text: str, hint: str) -> None:
        """Something went wrong, said where the reader can act on it."""

        self._say(text, hint)

    def show_works(self, works) -> None:
        """The shelf itself: the grid takes the empty block's place."""

        self._draw(works)
        self._controls_live(True)
        self.lbl_count.setText(work_count_words(len(works)))

    def show_filling(self, works) -> None:
        """FR-BS-036: the shelf as the scan fills it.

        The grid replaces the words the moment there are books to stand in
        their place, while the three controls stay shut exactly as
        `show_scanning` left them: the scan is still running, so a second one
        would only fight it and a filter would narrow a shelf still arriving.

        The count says "so far" rather than a bare number, because a number
        that is about to change is a number a reader would otherwise read as
        the size of their library.
        """

        self._draw(works)
        self._controls_live(False)
        self.lbl_count.setText(FILLING_TEXT.format(words=work_count_words(len(works))))

    def _controls_live(self, live: bool) -> None:
        """The three controls above a drawn shelf, opened or shut together."""

        self.btn_choose_root.setEnabled(live)
        self.btn_rescan.setEnabled(live)
        self.btn_filter.setEnabled(live)
        self.txt_search.setEnabled(live)

    def _draw(self, works) -> None:
        """The grid, holding these works, in the empty block's place."""

        self.empty_panel.setVisible(False)
        if self.grid is not None:
            self.grid.show_works(tuple(works))
            self.grid.setVisible(True)

    def _say(
        self, text: str, hint: str, *, can_choose: bool = True, can_rescan: bool = True
    ) -> None:
        """One of the states with nothing to draw: the words, not the grid."""

        self.lbl_state.setText(text)
        self.lbl_hint.setText(hint)
        self.empty_panel.setVisible(True)
        self.btn_choose_root.setEnabled(can_choose)
        self.btn_rescan.setEnabled(can_rescan)
        # Nothing on the shelf is nothing to narrow, so the filter and the
        # search shut together rather than offering to narrow an empty
        # catalogue. The words the reader typed are left in the field: a
        # search that found nothing is exactly when they want to see it.
        self.btn_filter.setEnabled(False)
        self.txt_search.setEnabled(False)
        self.lbl_count.setText("")
        if self.grid is not None:
            self.grid.setVisible(False)

    def showEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        """Match the picture button to the worded ones beside it.

        Done here rather than while building. A widget built before the
        application's stylesheet reaches it carries the fallback font and none
        of the sheet's padding, so the height it reports then is not the
        height it settles at: measured offscreen, 20 pixels against 28.
        """

        super().showEvent(event)
        self._match_the_row()

    def _match_the_row(self) -> None:
        """Square the filter button on the height its neighbours actually have."""

        self.btn_rescan.ensurePolished()
        side = max(self.btn_rescan.height(), self.btn_rescan.sizeHint().height())
        self.btn_filter.setFixedSize(side, side)
        inner = round(side * ICON_PX / ICON_BUTTON_PX)
        self.btn_filter.setIconSize(QSize(inner, inner))

    def ring_stops(self) -> tuple[QWidget, ...]:
        """The controls that take a keyboard stop, in visual order.

        The grid is one of them: it is the control holding the works, not a pane
        holding controls, so the reader reaches the books with Tab and moves
        between them with the cursor keys (FR-BS-059).
        """

        stops = (
            self.btn_choose_root,
            self.btn_rescan,
            self.btn_filter,
            self.txt_search,
        )
        if self.grid is None:
            return stops
        return stops + (self.grid,)
