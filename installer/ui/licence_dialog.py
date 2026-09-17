"""Installer licence dialog.

Shows the full GNU LGPL v3 text in a vertically scrollable, read-only view,
under a note saying the licence covers this setup program alone: the
application it installs carries its own two licences, which a reader could
otherwise take this one to describe.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
)

from installer.ui.lgpl3_license_text import LGPL_V3_TEXT
from voice_reader.version import APP_NAME

SCOPE_NOTE = (
    f"This licence applies to the {APP_NAME} setup program only. {APP_NAME} "
    "itself is dual licensed: the application under the GNU General Public "
    "License v3.0 and its user interface layer under the GNU Lesser General "
    f"Public License v3.0. Both are shown in {APP_NAME} from the licence "
    "buttons at the foot of its window."
)


class InstallerLicenceDialog(QDialog):
    def __init__(self, parent=None) -> None:  # noqa: ANN001 (Qt API)
        super().__init__(parent)

        self.setWindowTitle("Installer licence")
        self.setModal(True)
        # Delete on close to avoid stale windows accumulating.
        self.setAttribute(Qt.WA_DeleteOnClose, True)

        # Large enough to read comfortably; not absurd on smaller displays.
        self.resize(760, 560)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        scope = QLabel(SCOPE_NOTE, self)
        scope.setObjectName("LicenceScope")
        scope.setWordWrap(True)
        layout.addWidget(scope)

        text = QPlainTextEdit(self)
        text.setObjectName("LicenceText")
        text.setReadOnly(True)
        text.setPlainText(LGPL_V3_TEXT)
        text.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        text.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        layout.addWidget(text, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Close, parent=self)
        buttons.rejected.connect(self.close)
        layout.addWidget(buttons)
