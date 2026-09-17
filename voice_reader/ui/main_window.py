"""PySide6 main window."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QImage, QPixmap, QTextCursor
from PySide6.QtWidgets import QMainWindow, QMenu, QMessageBox, QTextEdit, QWidget

from voice_reader.ui.window_helpers import (
    build_about_dialog,
    open_licence_dialog,
)
from voice_reader.ui._icon_buttons import set_button_artwork
from voice_reader.ui._main_window_build import build_main_window_widgets
from voice_reader.ui._main_window_controls import PAUSE_TEXT, PLAY_TEXT
from voice_reader.ui.artwork import Artwork
from voice_reader.ui.bottom_tray import BACKEND_LICENCE_TITLE, UI_LICENCE_TITLE
from voice_reader.ui.document_renderer import apply_render_plan
from voice_reader.ui.guide_dialog import GUIDE_TITLE, GuideDialog
from voice_reader.ui.links import open_externally
from voice_reader.version import APP_NAME, DONATE_URL

GUIDE_MENU_TEXT = GUIDE_TITLE

# Shown on the status line when the desktop will not open a browser.
DONATE_OPEN_FAILED = "Could not open a browser for the donation page"

# Used when the reader's own font reports no usable point size.
_FALLBACK_READER_POINT_SIZE = 11.0


@dataclass(frozen=True, slots=True)
class UiStrings:
    select_voice: str = "Select voice"


class _NeutralStart(QWidget):
    """A 0x0 focus sink so nothing is highlighted on launch.

    Without it, Qt hands initial focus to the first focusable control (the
    play/pause button), which now paints the green focus ring and reads as
    active before the user has touched anything. The sink takes that first
    focus; on losing it, it drops out of the tab chain so the cycle that
    follows holds only real controls.
    """

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setFixedSize(0, 0)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)

    def focusOutEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        super().focusOutEvent(event)


class MainWindow(QMainWindow):
    select_book_clicked = Signal()
    remove_book_clicked = Signal()
    voice_sex_toggle_clicked = Signal()
    voice_region_toggle_clicked = Signal()
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
        self._render_plan = None
        self._reader_positions = None

        build_main_window_widgets(self, strings=self._strings)
        self._connect_signals()

        # Neutral start: see _NeutralStart. Focused once in showEvent.
        self._neutral_start = _NeutralStart(self)
        self._started = False

        # Default: disabled until a chapter index is loaded.
        try:
            self.set_chapter_controls_enabled(previous=False, next_=False)
        except Exception:
            pass

    def showEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        super().showEvent(event)
        if not self._started:
            self._started = True
            self._neutral_start.setFocus(Qt.FocusReason.OtherFocusReason)

    def _connect_signals(self) -> None:
        self.btn_select_book.clicked.connect(self.select_book_clicked.emit)
        self.btn_remove_book.clicked.connect(self.remove_book_clicked.emit)
        self.btn_voice_sex.clicked.connect(self.voice_sex_toggle_clicked.emit)
        self.btn_voice_region.clicked.connect(self.voice_region_toggle_clicked.emit)
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
            self.btn_help.clicked.connect(self.show_help_menu)
        except Exception:
            pass

        self.bottom_tray.donate_button.clicked.connect(self.open_donation)

        # Reader click-to-seek (best-effort; the reader widget may be swapped in tests).
        try:
            if hasattr(self, "reader") and hasattr(self.reader, "seek_requested"):
                self.reader.seek_requested.connect(self.reader_seek_requested.emit)
        except Exception:
            pass

    def _on_play_pause_clicked(self, checked: bool) -> None:
        """Emit unified Play/Pause without visually flipping ahead of state.

        QToolButton is checkable for styling; we keep the checked state driven
        by narration state updates.
        """

        del checked
        try:
            self.btn_play_pause.setChecked(bool(self._transport_is_playing))
        except Exception:
            pass
        self.play_pause_clicked.emit()

    def open_donation(self) -> None:
        """Hand the donation page to whatever the desktop opens links with."""

        if not open_externally(DONATE_URL):
            self.lbl_status.setText(DONATE_OPEN_FAILED)

    def set_transport_playing(self, *, is_playing: bool) -> None:
        """Update the Play/Pause toggle button to reflect playback state."""

        self._transport_is_playing = bool(is_playing)
        try:
            self.btn_play_pause.setChecked(bool(is_playing))
            words = PAUSE_TEXT if is_playing else PLAY_TEXT
            set_button_artwork(
                self.btn_play_pause,
                Artwork.PAUSE if is_playing else Artwork.PLAY,
                words,
            )
            self.btn_play_pause.setToolTip(words)
            self.btn_play_pause.setAccessibleName(words)
        except Exception:
            pass

    def set_chapter_controls_enabled(self, *, previous: bool, next_: bool) -> None:
        self.btn_prev_chapter.setEnabled(bool(previous))
        self.btn_next_chapter.setEnabled(bool(next_))

    def build_help_menu(self) -> QMenu:
        """Help: the Guide first, then About."""

        menu = QMenu(self)
        menu.addAction(GUIDE_MENU_TEXT, self.show_guide)
        menu.addAction(f"About {APP_NAME}", self.show_about_dialog)
        return menu

    def show_help_menu(self) -> None:
        """Open the Help menu under its button, keyboard or mouse alike."""

        self._help_menu = self.build_help_menu()
        self._help_menu.popup(
            self.btn_help.mapToGlobal(self.btn_help.rect().bottomLeft())
        )

    def show_guide(self) -> None:
        self._guide_dialog = GuideDialog(self)
        self._guide_dialog.open()

    def show_about_dialog(self) -> None:
        # Non-blocking. The update controller is attached by the composition
        # root; without it the About dialog simply carries no check button.
        controller = getattr(self, "update_controller", None)
        on_check = controller.check_manually if controller is not None else None
        build_about_dialog(parent=self, on_check_updates=on_check).open()

    def build_about_dialog(self) -> QMessageBox:
        """Backwards-compatible wrapper for older callers/tests."""

        return build_about_dialog(parent=self)

    def _show_ui_licence_dialog(self) -> None:
        open_licence_dialog(
            owner=self,
            attr_name="_ui_licence_dialog",
            title=UI_LICENCE_TITLE,
            filename="LGPL3-LICENSE",
        )

    def _show_backend_licence_dialog(self) -> None:
        open_licence_dialog(
            owner=self,
            attr_name="_backend_licence_dialog",
            title=BACKEND_LICENCE_TITLE,
            filename="LICENSE",
            initial_width=475,
        )

    def set_reader_text(self, text: str) -> None:
        """Show raw text, with no structure. Clears any active render plan."""

        self._render_plan = None
        self._reader_positions = None
        self.reader.setPlainText(text)

    def set_reader_document(self, plan) -> None:
        """Render a document plan, with headings, spacing and indentation.

        Keeping the plan is what lets highlighting and click-to-seek continue
        to speak in book offsets while the pane shows something different.
        """

        self._render_plan = plan
        self._reader_positions = apply_render_plan(
            text_edit=self.reader,
            plan=plan,
            base_point_size=self._reader_base_point_size(),
        )

    @property
    def render_plan(self):
        """The active render plan; None when showing raw text."""

        return getattr(self, "_render_plan", None)

    @property
    def reader_positions(self):
        """Python-index to Qt-position map for the rendered text."""

        return getattr(self, "_reader_positions", None)

    def _reader_base_point_size(self) -> float:
        try:
            size = float(self.reader.font().pointSizeF())
        except Exception:
            size = 0.0
        return size if size > 0 else _FALLBACK_READER_POINT_SIZE

    def highlight_range(self, start: int | None, end: int | None) -> None:
        # Callers speak in book offsets. When a plan is active those are not
        # pane positions, so translate before touching the cursor.
        plan = self.render_plan
        if plan is not None and start is not None and end is not None:
            start, end = plan.to_render(int(start)), plan.to_render(int(end))
            positions = self.reader_positions
            if positions is not None:
                # Render offsets are Python indices; the cursor wants
                # UTF-16 units, which differ once an emoji appears.
                start, end = positions.to_qt(start), positions.to_qt(end)

        if start is None or end is None or start >= end:
            self.reader.setExtraSelections([])
            return
        cursor = self.reader.textCursor()
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.KeepAnchor)

        sel = QTextEdit.ExtraSelection()
        sel.cursor = cursor
        # Narration highlight: deep teal, matching the app's teal accents.
        sel.format.setBackground(QColor("#134e4a"))
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

        img = QImage.fromData(image_bytes) if image_bytes else QImage()
        if img.isNull():
            # No usable cover: hide the whole column so the reader takes the full
            # width rather than sitting beside an empty placeholder.
            self._set_cover_panel_visible(False)
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
        self._set_cover_panel_visible(True)

        # Force repaint so users don't see a stale pixmap due to event-loop timing.
        # (Observed in some environments when rapidly switching books.)
        self.cover.repaint()

    def _set_cover_panel_visible(self, visible: bool) -> None:
        panel = getattr(self, "cover_panel", None)
        if panel is not None:
            panel.setVisible(visible)
