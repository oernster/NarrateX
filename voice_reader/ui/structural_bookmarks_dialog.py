"""Sections (Structural Bookmarks) dialog.

Read-only list of deterministic section landmarks.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Callable, Sequence

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)


def _in_tests() -> bool:
    return bool(os.getenv("PYTEST_CURRENT_TEST"))


def _display_label(label: str) -> str:
    s = str(label or "").strip()
    if not s:
        return "📌"
    if s.startswith("📌"):
        return s
    return f"📌 {s}"


@dataclass(frozen=True, slots=True)
class StructuralBookmarkListItem:
    label: str
    char_offset: int | None
    chunk_index: int | None
    kind: str
    level: int = 0


@dataclass(frozen=True, slots=True)
class StructuralBookmarksDialogActions:
    list_items: Callable[[], Sequence[StructuralBookmarkListItem]]
    go_to: Callable[[StructuralBookmarkListItem], None]


class StructuralBookmarksDialog(QDialog):
    def __init__(
        self,
        *,
        parent,
        actions: StructuralBookmarksDialogActions,
        book_title: str | None = None,
    ) -> None:
        super().__init__(parent)
        self._actions = actions

        # Explicit dark styling to avoid a white flash before the main window
        # stylesheet is applied/inherited.
        self.setObjectName("sectionsDialog")
        try:
            self.setAttribute(Qt.WA_StyledBackground, True)
        except Exception:  # pragma: no cover
            pass
        self.setStyleSheet(
            """
            QDialog#sectionsDialog { background: #0b0f17; }
            QListWidget { background: #121826; border: 1px solid #1f2937; }
            QListWidget::item:selected { background: #1f2a44; }
            QPushButton { background: #121826; border: 1px solid #1f2937; padding: 6px 10px; border-radius: 6px; }
            QPushButton:hover { border-color: #8b5cf6; }
            QPushButton:disabled { color: #94a3b8; }
            """
        )

        # On some Windows configurations Qt can briefly show an unstyled (white)
        # window background before the first paint with styles applied. Avoid that
        # by opening fully transparent, then revealing on the next UI tick.
        self._reveal_after_show = True
        try:
            self.setWindowOpacity(0.0)
        except Exception:  # pragma: no cover
            self._reveal_after_show = False

        self.setWindowTitle("Sections")
        self.setModal(True)
        self.resize(520, 420)

        try:
            self.setWindowFlag(Qt.WindowMinimizeButtonHint, False)
            self.setWindowFlag(Qt.WindowMaximizeButtonHint, False)
        except Exception:  # pragma: no cover
            pass

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        title = QLabel("Sections")
        title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        title.setStyleSheet("font-size: 14px; font-weight: 600;")
        root.addWidget(title)

        if book_title:
            subtitle = QLabel(str(book_title))
            subtitle.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            subtitle.setStyleSheet("color: #cbd5e1;")
            root.addWidget(subtitle)

        self.status = QLabel("")
        self.status.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.status.setStyleSheet("color: #94a3b8;")
        self.status.setVisible(False)
        root.addWidget(self.status)

        self.list = QListWidget()
        self.list.setSelectionMode(QListWidget.SingleSelection)
        self.list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        root.addWidget(self.list, stretch=1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.btn_goto = QPushButton("Go To")
        self.btn_close = QPushButton("Close")
        for b in (self.btn_goto, self.btn_close):
            b.setCursor(Qt.PointingHandCursor)

        btn_row.addWidget(self.btn_goto)
        btn_row.addStretch(1)
        btn_row.addWidget(self.btn_close)
        root.addLayout(btn_row)

        self.btn_goto.clicked.connect(self._on_goto)
        self.btn_close.clicked.connect(self.close)
        self.list.itemDoubleClicked.connect(lambda _item: self._on_goto())

        self.refresh()

    def showEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        super().showEvent(event)
        if not getattr(self, "_reveal_after_show", False):
            return

        def _reveal() -> None:
            try:
                self.setWindowOpacity(1.0)
            except Exception:  # pragma: no cover
                return

        try:
            QTimer.singleShot(0, _reveal)
        except Exception:  # pragma: no cover
            _reveal()

    def set_loading(self, *, message: str = "Loading sections…") -> None:
        """Show a lightweight loading state (non-blocking)."""

        try:
            self.status.setText(str(message))
            self.status.setVisible(True)
        except Exception:  # pragma: no cover
            pass

        try:
            self.btn_goto.setEnabled(False)
        except Exception:  # pragma: no cover
            pass

        try:
            self.list.clear()
            lw = QListWidgetItem(str(message))
            lw.setFlags(Qt.NoItemFlags)
            try:
                lw.setForeground(Qt.gray)
            except Exception:  # pragma: no cover
                pass
            self.list.addItem(lw)
        except Exception:  # pragma: no cover
            pass

    def set_items(self, *, items: Sequence[StructuralBookmarkListItem]) -> None:
        """Replace list contents (used after background computation finishes)."""

        self.list.clear()
        for it in list(items or []):
            lw = QListWidgetItem(_display_label(it.label))
            lw.setData(Qt.UserRole, it)
            self.list.addItem(lw)
        if self.list.count() > 0:
            self.list.setCurrentRow(0)
        try:
            self.btn_goto.setEnabled(self.list.count() > 0)
        except Exception:  # pragma: no cover
            pass
        try:
            self.status.setVisible(False)
        except Exception:  # pragma: no cover
            pass

    def set_empty(self, *, message: str = "No obvious sections found.") -> None:
        """Show an empty-state message."""

        self.list.clear()
        lw = QListWidgetItem(str(message))
        lw.setFlags(Qt.NoItemFlags)
        try:
            lw.setForeground(Qt.gray)
        except Exception:  # pragma: no cover
            pass
        self.list.addItem(lw)
        try:
            self.btn_goto.setEnabled(False)
        except Exception:  # pragma: no cover
            pass
        try:
            self.status.setText(str(message))
            self.status.setVisible(True)
        except Exception:  # pragma: no cover
            pass

    def refresh(self) -> None:
        self.list.clear()
        items = list(self._actions.list_items())
        for it in items:
            lw = QListWidgetItem(_display_label(it.label))
            lw.setData(Qt.UserRole, it)
            self.list.addItem(lw)
        if self.list.count() > 0:
            self.list.setCurrentRow(0)
        try:
            self.btn_goto.setEnabled(self.list.count() > 0)
        except Exception:  # pragma: no cover
            pass

    def _selected(self) -> StructuralBookmarkListItem | None:
        item = self.list.currentItem()
        if item is None:
            return None
        data = item.data(Qt.UserRole)
        return data if isinstance(data, StructuralBookmarkListItem) else None

    def _on_goto(self) -> None:
        it = self._selected()
        if it is None:
            self.list.setCurrentRow(0)
            return
        try:
            self._actions.go_to(it)
        except Exception as exc:  # noqa: BLE001
            if not _in_tests():
                box = QMessageBox(self)
                box.setWindowTitle("Sections")
                box.setText(f"Failed jumping to section: {exc}")
                box.open()
