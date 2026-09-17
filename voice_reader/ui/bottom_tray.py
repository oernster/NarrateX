"""The strip along the foot of the window: donate, then the two licences.

Donate sits first and apart, behind a separator, because it belongs to nothing
else on screen; the licences follow it, UI then Backend. Every button comes
from the same picture-button factory as the rest of the window, so the strip
matches the controls above it by construction.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QToolButton, QWidget

from voice_reader.ui._icon_buttons import icon_button
from voice_reader.ui.artwork import Artwork
from voice_reader.version import APP_NAME

DONATE_TOOLTIP = f"Donate to support {APP_NAME} (opens your browser)"
DONATE_TEXT = "Donate"
UI_LICENCE_TITLE = "UI licence"
BACKEND_LICENCE_TITLE = "Backend licence"


class BottomTray(QWidget):
    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        open_donation: Callable[[], None] = lambda: None,
    ) -> None:
        super().__init__(parent)
        # A container is never a keyboard stop; said rather than assumed.
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.donate_button = icon_button(
            artwork=Artwork.DONATE,
            text=DONATE_TEXT,
            tooltip=DONATE_TOOLTIP,
            parent=self,
            object_name="donateButton",
        )
        self.donate_button.clicked.connect(lambda _checked=False: open_donation())

        self.separator = QFrame(self)
        self.separator.setObjectName("bottomTraySeparator")
        self.separator.setFrameShape(QFrame.Shape.VLine)
        self.separator.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.ui_licence_button = icon_button(
            artwork=Artwork.UI_LICENCE,
            text=UI_LICENCE_TITLE,
            tooltip=UI_LICENCE_TITLE,
            parent=self,
            object_name="uiLicenceButton",
        )
        self.backend_licence_button = icon_button(
            artwork=Artwork.BACKEND_LICENCE,
            text=BACKEND_LICENCE_TITLE,
            tooltip=BACKEND_LICENCE_TITLE,
            parent=self,
            object_name="backendLicenceButton",
        )

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self.donate_button)
        row.addWidget(self.separator)
        row.addWidget(self.ui_licence_button)
        row.addWidget(self.backend_licence_button)
        row.addStretch(1)

    def ring_stops(self) -> tuple[QToolButton, ...]:
        """This strip's controls, left to right as they are drawn."""

        return (
            self.donate_button,
            self.ui_licence_button,
            self.backend_licence_button,
        )
