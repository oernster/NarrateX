"""Sections (Structural Bookmarks) dialog.

Read-only list of deterministic section landmarks.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Callable, Sequence

from PySide6.QtCore import Qt
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

    def refresh(self) -> None:
        self.list.clear()
        items = list(self._actions.list_items())
        for it in items:
            lw = QListWidgetItem(_display_label(it.label))
            lw.setData(Qt.UserRole, it)
            self.list.addItem(lw)
        if self.list.count() > 0:
            self.list.setCurrentRow(0)

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
