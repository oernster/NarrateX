"""Picture controls: every button or list row that shows artwork is built here.

One construction path is what keeps the buttons matched by construction: the
same box, the same ring (the `iconButton` stylesheet property), the same cursor
and the same fallback when a picture is missing.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QToolButton, QWidget

from voice_reader.ui.artwork import (
    ICON_BUTTON_PX,
    ICON_PX,
    LIST_ROW_ICON_PX,
    Artwork,
    artwork_path,
)

# The stylesheet property every picture button carries; the theme draws the
# interaction ring from it.
ICON_BUTTON_PROPERTY = "iconButton"


def artwork_icon(name: Artwork) -> QIcon:
    """The shipped picture for `name`; a null icon when the file is absent."""

    path = artwork_path(name)
    return QIcon(str(path)) if path.is_file() else QIcon()


def set_button_artwork(button: QToolButton, name: Artwork, text: str) -> None:
    """Show `name` on the button, with `text` as its words.

    The words are never drawn beside the picture; they are what accessibility
    tooling reads and they stand in for the picture if its file is missing, so
    a button never goes blank without saying what it does.
    """

    icon = artwork_icon(name)
    button.setText(text)
    button.setIcon(icon)
    button.setToolButtonStyle(
        Qt.ToolButtonStyle.ToolButtonTextOnly
        if icon.isNull()
        else Qt.ToolButtonStyle.ToolButtonIconOnly
    )


def icon_button(
    *,
    artwork: Artwork,
    text: str,
    tooltip: str,
    parent: QWidget | None = None,
    button_px: int = ICON_BUTTON_PX,
    icon_px: int = ICON_PX,
    object_name: str | None = None,
) -> QToolButton:
    """A square picture button with the app's interaction ring."""

    button = QToolButton(parent)
    if object_name:
        button.setObjectName(object_name)
    button.setProperty(ICON_BUTTON_PROPERTY, True)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setAutoRaise(True)
    button.setFixedSize(button_px, button_px)
    button.setIconSize(QSize(icon_px, icon_px))
    button.setToolTip(tooltip)
    button.setAccessibleName(tooltip)
    set_button_artwork(button, artwork, text)
    return button


class ArtworkList(QListWidget):
    """A list whose every row wears the same picture beside its label."""

    def __init__(self, artwork: Artwork, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._row_icon = artwork_icon(artwork)
        self.setIconSize(QSize(LIST_ROW_ICON_PX, LIST_ROW_ICON_PX))

    def add_row(self, label: str) -> QListWidgetItem:
        item = QListWidgetItem(self._row_icon, str(label or "").strip())
        self.addItem(item)
        return item
