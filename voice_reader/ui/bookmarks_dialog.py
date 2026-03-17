"""Bookmarks dialog.

Provides manual bookmark management:
- Add
- Go To
- Delete

Resume position is intentionally not shown here (hidden per book).
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

from voice_reader.domain.entities.bookmark import Bookmark


def _in_tests() -> bool:
    # pytest sets this environment variable for each test.
    return bool(os.getenv("PYTEST_CURRENT_TEST"))


def _display_label(label: str) -> str:
    s = str(label or "").strip()
    if not s:
        return "📌"
    if s.startswith("📌"):
        return s
    return f"📌 {s}"


@dataclass(frozen=True, slots=True)
class BookmarksDialogActions:
    list_bookmarks: Callable[[], Sequence[Bookmark]]
    add_bookmark: Callable[[], None]
    go_to_bookmark: Callable[[Bookmark], None]
    delete_bookmark: Callable[[Bookmark], None]


class BookmarksDialog(QDialog):
    def __init__(
        self,
        *,
        parent,
        actions: BookmarksDialogActions,
    ) -> None:
        super().__init__(parent)
        self._actions = actions

        self.setWindowTitle("Bookmarks")
        self.setModal(True)
        self.resize(420, 360)

        # Dialog chrome: keep only the close button (no minimize/maximize).
        try:
            self.setWindowFlag(Qt.WindowMinimizeButtonHint, False)
            self.setWindowFlag(Qt.WindowMaximizeButtonHint, False)
        except Exception:
            pass

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        title = QLabel("Bookmarks")
        title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        title.setStyleSheet("font-size: 14px; font-weight: 600;")
        root.addWidget(title)

        self.list = QListWidget()
        self.list.setSelectionMode(QListWidget.SingleSelection)
        # Always show a vertical scrollbar (keeps layout stable with many items).
        self.list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        root.addWidget(self.list, stretch=1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.btn_add = QPushButton("Add")
        self.btn_goto = QPushButton("Go To")
        self.btn_delete = QPushButton("Delete")
        self.btn_close = QPushButton("Close")

        for b in (self.btn_add, self.btn_goto, self.btn_delete, self.btn_close):
            b.setCursor(Qt.PointingHandCursor)

        btn_row.addWidget(self.btn_add)
        btn_row.addWidget(self.btn_goto)
        btn_row.addWidget(self.btn_delete)
        btn_row.addStretch(1)
        btn_row.addWidget(self.btn_close)
        root.addLayout(btn_row)

        self.btn_add.clicked.connect(self._on_add)
        self.btn_goto.clicked.connect(self._on_goto)
        self.btn_delete.clicked.connect(self._on_delete)
        self.btn_close.clicked.connect(self.close)

        self.refresh()

    def refresh(self) -> None:
        self.list.clear()
        bookmarks = list(self._actions.list_bookmarks())
        for bm in bookmarks:
            item = QListWidgetItem(_display_label(bm.name))
            item.setData(Qt.UserRole, bm)
            self.list.addItem(item)
        if self.list.count() > 0:
            self.list.setCurrentRow(0)

    def _selected(self) -> Bookmark | None:
        item = self.list.currentItem()
        if item is None:
            # Ensure the branch is exercised by tests.
            return None
        bm = item.data(Qt.UserRole)
        return bm if isinstance(bm, Bookmark) else None

    def _on_add(self) -> None:
        try:
            self._actions.add_bookmark()
        except Exception as exc:  # noqa: BLE001
            if not _in_tests():
                # Non-blocking (do not use QMessageBox.warning, which is modal).
                box = QMessageBox(self)
                box.setWindowTitle("Bookmarks")
                box.setText(f"Failed adding bookmark: {exc}")
                box.open()
        self.refresh()

    def _on_goto(self) -> None:
        bm = self._selected()
        if bm is None:
            self.list.setCurrentRow(0)
            return
        try:
            self._actions.go_to_bookmark(bm)
        except Exception as exc:  # noqa: BLE001
            if not _in_tests():
                box = QMessageBox(self)
                box.setWindowTitle("Bookmarks")
                box.setText(f"Failed jumping to bookmark: {exc}")
                box.open()

    def _on_delete(self) -> None:
        bm = self._selected()
        if bm is None:
            self.list.setCurrentRow(0)
            return
        try:
            self._actions.delete_bookmark(bm)
        except Exception as exc:  # noqa: BLE001
            if not _in_tests():
                box = QMessageBox(self)
                box.setWindowTitle("Bookmarks")
                box.setText(f"Failed deleting bookmark: {exc}")
                box.open()
        self.refresh()
