"""The genre catalogue as tick boxes, grouped by main with its styles under it.

Ported from Stellody's `genre_grid`, whose reasoning holds here unchanged.

A grid of boxes rather than a line to type in, because a genre is chosen from a
settled list rather than invented: typing invites a third spelling of a name
the catalogue already holds two of.

**Grouped, because the catalogue has two levels** (FR-BS-040). Space Opera is a
kind of Science Fiction, so it is indented beneath it rather than set beside
it. The groups are dealt into columns by height rather than in order, since
Crime carries seven styles while nine mains carry none at all; filling column
by column would leave one twice the length of another.

**The same boxes answer two different questions**, which is what `Manner` is
for. Asking the shelf what to show is not the same act as saying what a book
is; they differ in exactly one place, which is whether ticking a style also
ticks the main above it. Saying a book is Space Opera says it is science fiction, so
the main is ticked with it (FR-BS-046). Asking for Space Opera does not ask for
every kind of science fiction, so nothing is ticked on the reader's behalf
(FR-BS-042).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from voice_reader.domain.shelf.genre_catalogue import CATALOGUE, STYLE_PARENT
from voice_reader.domain.shelf.genres import catalogue_order
from voice_reader.ui.ringed_check import RingedCheckBox

# Three columns, as Stellody measured for a catalogue of this shape: 51 boxes
# over two columns is a dialog taller than a laptop screen; a fourth column
# costs more width than the height it saves.
COLUMNS = 3

# How far a style sits in from the main it belongs to. Enough to read as
# beneath it rather than beside it.
INDENT_PX = 18

ASK_HINT = "Every tick adds to what is shown. A style shows that style alone."
STATE_HINT = "A book can carry several. What you tick replaces what it carries."


@dataclass(frozen=True, slots=True)
class Manner:
    """What a grid of these boxes is being used FOR.

    One distinction with one consequence: describing a book states what it is,
    while asking the shelf states what to show.
    """

    hint: str
    couples_mains: bool


#: Saying what a book is: ticking a style ticks the main above it.
STATING = Manner(hint=STATE_HINT, couples_mains=True)
#: Asking the shelf: a tick is a question, so nothing is ticked for the reader.
ASKING = Manner(hint=ASK_HINT, couples_mains=False)


def mnemonic_safe(name: str) -> str:
    """A genre as Qt should draw it.

    Qt reads a single ampersand in a control's text as the marker before a
    shortcut key, so a genre holding one would render with a stray underline.
    Doubling it is how one is asked for literally.
    """

    return name.replace("&", "&&")


def dealt_into_columns(
    catalogue: tuple[tuple[str, tuple[str, ...]], ...], columns: int
) -> tuple[tuple[tuple[str, tuple[str, ...]], ...], ...]:
    """The groups spread over that many columns, kept as even in height as they go.

    Each group goes to whichever column is shortest at the time, so the order
    within a column is still the catalogue's. Height is counted in boxes, one
    for the main plus one per style, since that is what the eye measures.
    """

    dealt: list[list[tuple[str, tuple[str, ...]]]] = [[] for _ in range(columns)]
    heights = [0] * columns
    for group in catalogue:
        into = heights.index(min(heights))
        dealt[into].append(group)
        heights[into] += 1 + len(group[1])
    return tuple(tuple(column) for column in dealt)


class GenreGrid(QWidget):
    """The catalogue as tick boxes, remembered by the name each stands for."""

    def __init__(
        self,
        ticked: Iterable[str] = (),
        parent: QWidget | None = None,
        manner: Manner = ASKING,
    ) -> None:
        super().__init__(parent)
        self._manner = manner
        # A container is never a stop on the keyboard ring; the boxes are.
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.boxes: dict[str, RingedCheckBox] = {}
        already = set(ticked)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        hint = QLabel(manner.hint, self)
        hint.setWordWrap(True)
        font = hint.font()
        font.setItalic(True)
        hint.setFont(font)
        outer.addWidget(hint)
        outer.addLayout(self._build_columns(already))

    def _build_columns(self, ticked: set[str]) -> QHBoxLayout:
        """One column of groups beside another, each a main and its own styles."""

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        for column in dealt_into_columns(CATALOGUE, COLUMNS):
            stack = QVBoxLayout()
            stack.setContentsMargins(0, 0, 0, 0)
            for main, styles in column:
                stack.addWidget(self._box(main, ticked))
                for style in styles:
                    indented = QHBoxLayout()
                    indented.setContentsMargins(0, 0, 0, 0)
                    indented.addSpacing(INDENT_PX)
                    indented.addWidget(self._box(style, ticked))
                    stack.addLayout(indented)
            stack.addStretch()
            row.addLayout(stack)
        return row

    def _box(self, name: str, ticked: set[str]) -> RingedCheckBox:
        box = RingedCheckBox(mnemonic_safe(name), self)
        box.setChecked(name in ticked)
        box.toggled.connect(lambda on, which=name: self._agree_with(which, on))
        self.boxes[name] = box
        return box

    def _agree_with(self, name: str, on: bool) -> None:
        """Keep the ticks saying what the answer they produce would say.

        Two rules, both following from a style stating its main: ticking a
        style ticks that main; clearing a main clears its styles. The pair a
        reader would find surprising, clearing a style clearing its main, is
        deliberately absent: a book may still be science fiction after they
        decide it is not specifically space opera.

        Neither applies while the boxes are asking rather than stating.
        """

        if not self._manner.couples_mains:
            return
        if on and name in STYLE_PARENT:
            self.boxes[STYLE_PARENT[name]].setChecked(True)
            return
        if not on:
            for style, main in STYLE_PARENT.items():
                if main == name:
                    self.boxes[style].setChecked(False)

    def set_all(self, on: bool) -> None:
        """Tick or clear every box in one go.

        Each box is set individually, so the coupling rules see every change
        exactly as they would see a press.
        """

        for box in self.boxes.values():
            box.setChecked(on)

    def chosen(self) -> tuple[str, ...]:
        """Every genre ticked, in catalogue order.

        Walked over the catalogue rather than over the boxes, since the boxes
        are built column by column and a column is not the catalogue's order.
        """

        return tuple(name for name in catalogue_order() if self.boxes[name].isChecked())
