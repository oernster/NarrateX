"""PySide6 main window."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QImage, QPixmap, QTextCursor
from PySide6.QtWidgets import QMainWindow, QMessageBox, QTextEdit

from voice_reader.version import APP_NAME
from voice_reader.ui.window_helpers import (
    build_about_dialog,
    open_licence_dialog,
)
from voice_reader.ui._main_window_build import build_main_window_widgets


@dataclass(frozen=True, slots=True)
class UiStrings:
    select_book: str = "📚 Select Book"
    select_voice: str = "🎙 Select Voice"
    # Windows renders the official Pause/Stop "button" emoji codepoints as blue
    # emoji glyphs. Use monochrome symbol characters instead so they stay
    # readable on the dark theme and match text height.
    play: str = "▶ Play"
    pause: str = "Ⅱ Pause"
    stop: str = "■ Stop"
    play_tooltip: str = "Play"
    pause_tooltip: str = "Pause"


class MainWindow(QMainWindow):
    select_book_clicked = Signal()
    play_pause_clicked = Signal()
    stop_clicked = Signal()
    bookmarks_clicked = Signal()
    ideas_clicked = Signal()
    # Search removed (was tied to Ideas mapping).
    speed_changed = Signal(str)
    volume_changed = Signal(int)

    # Reader: click-to-seek.
    # Emits an absolute character offset into the displayed normalized text.
    reader_seek_requested = Signal(int)

    previous_chapter_clicked = Signal()
    next_chapter_clicked = Signal()

    def __init__(self, strings: UiStrings | None = None) -> None:
        super().__init__()
        self._strings = strings or UiStrings()

        build_main_window_widgets(self, strings=self._strings)
        self._connect_signals()

        # Default: disabled until a chapter index is loaded.
        try:
            self.set_chapter_controls_enabled(previous=False, next_=False)
        except Exception:
            pass

    def _connect_signals(self) -> None:
        self.btn_select_book.clicked.connect(self.select_book_clicked.emit)
        self.btn_stop.clicked.connect(self.stop_clicked.emit)
        self.btn_bookmarks.clicked.connect(self.bookmarks_clicked.emit)
        self.btn_ideas.clicked.connect(self.ideas_clicked.emit)
        self.speed_combo.currentTextChanged.connect(self.speed_changed.emit)
        self.volume_slider.valueChanged.connect(self.volume_changed.emit)
        self.btn_prev_chapter.clicked.connect(self.previous_chapter_clicked.emit)
        self.btn_next_chapter.clicked.connect(self.next_chapter_clicked.emit)

        try:
            self.btn_play_pause.clicked.connect(self._on_play_pause_clicked)
        except Exception:
            pass

        try:
            self.btn_ui_licence.clicked.connect(self._show_ui_licence_dialog)
        except Exception:
            pass

        try:
            self.btn_backend_licence.clicked.connect(self._show_backend_licence_dialog)
        except Exception:
            pass

        try:
            self.btn_help.clicked.connect(self.show_about_dialog)
        except Exception:
            pass

        # Keep volume icon consistent with current slider position.
        self.volume_slider.valueChanged.connect(self._update_volume_icon)

        # Reader click-to-seek (best-effort; the reader widget may be swapped in tests).
        try:
            if hasattr(self, "reader") and hasattr(self.reader, "seek_requested"):
                self.reader.seek_requested.connect(self.reader_seek_requested.emit)
        except Exception:
            pass

    def _on_play_pause_clicked(self, checked: bool) -> None:
        """Emit unified Play/Pause without visually flipping ahead of state.

        QToolButton is checkable for styling, but we keep the checked state driven
        by narration state updates.
        """

        del checked
        try:
            self.btn_play_pause.setChecked(bool(self._transport_is_playing))
        except Exception:
            pass
        self.play_pause_clicked.emit()

    def _update_volume_icon(self, value: int) -> None:
        v = int(value)
        if v <= 0:
            icon = "🔇"
        elif v <= 50:
            icon = "🔉"
        else:
            icon = "🔊"
        self.lbl_volume_icon.setText(icon)

    def set_transport_playing(self, *, is_playing: bool) -> None:
        """Update the Play/Pause toggle button to reflect playback state."""

        self._transport_is_playing = bool(is_playing)
        try:
            self.btn_play_pause.setChecked(bool(is_playing))
            self.btn_play_pause.setText("Ⅱ" if is_playing else "▶")
            self.btn_play_pause.setToolTip(
                self._strings.pause_tooltip
                if is_playing
                else self._strings.play_tooltip
            )
        except Exception:
            pass

    def set_chapter_controls_enabled(self, *, previous: bool, next_: bool) -> None:
        self.btn_prev_chapter.setEnabled(bool(previous))
        self.btn_next_chapter.setEnabled(bool(next_))

    def show_about_dialog(self) -> None:
        # Non-blocking.
        build_about_dialog(parent=self).open()

    def build_about_dialog(self) -> QMessageBox:
        """Backwards-compatible wrapper for older callers/tests."""

        return build_about_dialog(parent=self)

    def _show_ui_licence_dialog(self) -> None:
        open_licence_dialog(
            owner=self,
            attr_name="_ui_licence_dialog",
            title="UI licence",
            filename="LGPL3-LICENSE",
        )

    def _show_backend_licence_dialog(self) -> None:
        open_licence_dialog(
            owner=self,
            attr_name="_backend_licence_dialog",
            title="Backend licence",
            filename="LICENSE",
            initial_width=475,
        )

    def set_reader_text(self, text: str) -> None:
        self.reader.setPlainText(text)

    def highlight_range(self, start: int | None, end: int | None) -> None:
        if start is None or end is None or start >= end:
            self.reader.setExtraSelections([])
            return
        cursor = self.reader.textCursor()
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.KeepAnchor)

        sel = QTextEdit.ExtraSelection()
        sel.cursor = cursor
        sel.format.setBackground(QColor("#2a1d5a"))
        sel.format.setForeground(QColor("#ffffff"))
        self.reader.setExtraSelections([sel])
        self.reader.setTextCursor(cursor)
        self.reader.ensureCursorVisible()

    def append_log(self, line: str) -> None:
        # Backwards-compatible no-op: we no longer show an in-app log panel.
        del line

    def set_cover_image(self, image_bytes: bytes | None) -> None:
        """Set the displayed book cover.

        Args:
            image_bytes: Encoded image bytes (PNG/JPG/etc.) or None to clear.
        """

        # Always reset state first so we never accidentally keep a previous pixmap
        # when new cover bytes are missing/invalid.
        self.cover.setPixmap(QPixmap())
        self.cover.setText("No cover")

        if not image_bytes:
            return

        img = QImage.fromData(image_bytes)
        if img.isNull():
            return

        pm = QPixmap.fromImage(img)
        pm = pm.scaled(
            self.cover.width(),
            self.cover.height(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.cover.setText("")
        self.cover.setPixmap(pm)

        # Force repaint so users don't see a stale pixmap due to event-loop timing.
        # (Observed in some environments when rapidly switching books.)
        self.cover.repaint()
