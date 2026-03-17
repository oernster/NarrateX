"""PySide6 main window."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPixmap, QTextCursor
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QDialog,
    QMainWindow,
    QPushButton,
    QProgressBar,
    QMessageBox,
    QSlider,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from voice_reader.version import APP_NAME
from voice_reader.ui.window_helpers import (
    apply_main_window_theme,
    build_about_dialog,
    open_licence_dialog,
)


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

    previous_chapter_clicked = Signal()
    next_chapter_clicked = Signal()

    def __init__(self, strings: UiStrings | None = None) -> None:
        super().__init__()
        self._strings = strings or UiStrings()

        # Transport UI is driven by narration state (see [`apply_state()`](voice_reader/ui/_ui_controller_state.py:19)).
        # Keep local state so the Play/Pause toggle never visually flips ahead of
        # the backend (e.g., during LOADING/CHUNKING/SYNTHESIZING).
        self._transport_is_playing: bool = False

        self.setWindowTitle(APP_NAME)
        self.resize(1100, 700)

        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # Top panel: controls + progress (left) + device/engine (right).
        top_panel = QHBoxLayout()
        top_panel.setSpacing(12)
        top_panel.setAlignment(Qt.AlignTop)

        left_panel = QVBoxLayout()
        left_panel.setSpacing(8)
        left_panel.setAlignment(Qt.AlignTop)

        # Controls row
        controls = QHBoxLayout()
        controls.setSpacing(8)

        # Slightly taller top-row controls to harmonize with the chapter-nav row.
        top_row_min_h = 42

        self.btn_select_book = QPushButton(self._strings.select_book)
        self.btn_select_book.setMinimumHeight(top_row_min_h)
        self.voice_combo = QComboBox()
        self.voice_combo.setMinimumWidth(220)
        self.voice_combo.setMinimumHeight(top_row_min_h)

        self.speed_combo = QComboBox()
        self.speed_combo.setMinimumWidth(95)
        self.speed_combo.setMinimumHeight(top_row_min_h)
        for s in ["0.75x", "1.00x", "1.25x", "1.50x", "2.00x"]:
            self.speed_combo.addItem(s)
        self.speed_combo.setCurrentText("1.00x")

        # Primary playback control: one large circular Play/Pause toggle.
        self.btn_play_pause = QToolButton()
        self.btn_play_pause.setObjectName("playPauseButton")
        self.btn_play_pause.setCheckable(True)
        self.btn_play_pause.setAutoRaise(False)
        self.btn_play_pause.setCursor(Qt.PointingHandCursor)
        self.btn_play_pause.setToolTip("Play")
        self.btn_play_pause.setText("▶")
        self.btn_play_pause.setFixedSize(48, 48)
        self.btn_play_pause.setFont(QFont("Segoe UI", 14))
        self.btn_play_pause.clicked.connect(self._on_play_pause_clicked)

        self.btn_stop = QPushButton(self._strings.stop)
        self.btn_stop.setCursor(Qt.PointingHandCursor)
        self.btn_stop.setMinimumHeight(top_row_min_h)

        # Volume control (session-only, editable during playback).
        self.lbl_volume_icon = QLabel("🔊")
        self.lbl_volume_icon.setToolTip("Volume")
        self.lbl_volume_icon.setFont(QFont("Segoe UI Emoji", 13))

        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(100)
        self.volume_slider.setFixedWidth(140)
        self.volume_slider.setToolTip("Volume")

        self.btn_bookmarks = QToolButton()
        self.btn_bookmarks.setText("🔖")
        self.btn_bookmarks.setToolTip("Bookmarks")
        self.btn_bookmarks.setCursor(Qt.PointingHandCursor)
        self.btn_bookmarks.setAutoRaise(True)
        self.btn_bookmarks.setFixedSize(38, 38)
        self.btn_bookmarks.setFont(QFont("Segoe UI Emoji", 16))
        self.btn_bookmarks.setProperty("bookmarkButton", True)
        self.btn_bookmarks.setProperty("topIconButton", True)

        self.btn_ideas = QToolButton()
        self.btn_ideas.setText("🧠")
        self.btn_ideas.setToolTip("Sections")
        self.btn_ideas.setCursor(Qt.PointingHandCursor)
        self.btn_ideas.setAutoRaise(True)
        self.btn_ideas.setFixedSize(38, 38)
        self.btn_ideas.setFont(QFont("Segoe UI Emoji", 16))
        self.btn_ideas.setProperty("topIconButton", True)

        # Search removed in Sections-only brain button design.

        # Zone A: setup/content selection (left)
        zone_a = QHBoxLayout()
        zone_a.setSpacing(8)
        zone_a.addWidget(self.btn_select_book)
        zone_a.addWidget(QLabel(self._strings.select_voice))
        zone_a.addWidget(self.voice_combo)
        zone_a.addWidget(QLabel("Speed"))
        zone_a.addWidget(self.speed_combo)

        # Zone B: primary playback (center)
        zone_b = QHBoxLayout()
        zone_b.setSpacing(8)
        zone_b.addWidget(self.btn_play_pause)
        zone_b.addWidget(self.btn_stop)
        zone_b.addWidget(self.lbl_volume_icon)
        zone_b.addWidget(self.volume_slider)

        controls.addLayout(zone_a)
        controls.addStretch(1)
        controls.addLayout(zone_b)
        controls.addStretch(1)
        left_panel.addLayout(controls)

        # Chapter navigation row (larger buttons for visibility).
        chapter_nav = QHBoxLayout()
        chapter_nav.setSpacing(8)

        self.btn_prev_chapter = QPushButton("⏮ Previous Chapter")
        self.btn_next_chapter = QPushButton("Next Chapter ⏭")
        for b in (self.btn_prev_chapter, self.btn_next_chapter):
            b.setCursor(Qt.PointingHandCursor)
            b.setMinimumHeight(42)
            b.setMinimumWidth(190)
            b.setFont(QFont("Segoe UI", 12))

        # Harmonize top-row button height with chapter-nav row without making
        # the UI feel oversized.
        try:
            self.btn_stop.setMinimumHeight(42)
            self.btn_select_book.setMinimumHeight(42)
            self.voice_combo.setMinimumHeight(42)
            self.speed_combo.setMinimumHeight(42)
        except Exception:
            pass

        chapter_nav.addWidget(self.btn_prev_chapter)
        chapter_nav.addWidget(self.btn_next_chapter)
        chapter_nav.addStretch(1)
        left_panel.addLayout(chapter_nav)

        # Status/progress row (kept on the left)
        status = QHBoxLayout()
        status.setSpacing(12)

        self.lbl_status = QLabel("Idle")
        self.lbl_status.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.lbl_status.setMinimumWidth(260)

        self.lbl_progress = QLabel("0/0")
        self.lbl_progress.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        status.addWidget(self.lbl_status)
        status.addStretch(1)
        status.addWidget(self.lbl_progress)
        status.addWidget(self.progress)
        left_panel.addLayout(status)

        # Give the left panel the expandable width so Zone B can read as centered.
        top_panel.addLayout(left_panel, stretch=1)

        # Right side: right-justified device/engine labels.
        right_panel = QVBoxLayout()
        right_panel.setSpacing(6)
        right_panel.setAlignment(Qt.AlignTop | Qt.AlignRight)

        # Top-right buttons.
        # Add UI/Backend licence buttons to the left of the About button.
        self.btn_ui_licence = QToolButton()
        self.btn_ui_licence.setText("📜")
        self.btn_ui_licence.setObjectName("uiLicenceButton")
        self.btn_ui_licence.setToolTip("UI licence")
        self.btn_ui_licence.setCursor(Qt.PointingHandCursor)
        self.btn_ui_licence.setAutoRaise(True)
        self.btn_ui_licence.setFixedSize(38, 38)
        self.btn_ui_licence.setFont(QFont("Segoe UI Emoji", 16))
        self.btn_ui_licence.setProperty("topIconButton", True)
        self.btn_ui_licence.clicked.connect(self._show_ui_licence_dialog)

        self.btn_backend_licence = QToolButton()
        self.btn_backend_licence.setText("📃")
        self.btn_backend_licence.setObjectName("backendLicenceButton")
        self.btn_backend_licence.setToolTip("Backend licence")
        self.btn_backend_licence.setCursor(Qt.PointingHandCursor)
        self.btn_backend_licence.setAutoRaise(True)
        self.btn_backend_licence.setFixedSize(38, 38)
        self.btn_backend_licence.setFont(QFont("Segoe UI Emoji", 16))
        self.btn_backend_licence.setProperty("topIconButton", True)
        self.btn_backend_licence.clicked.connect(self._show_backend_licence_dialog)

        # Info button (top-right) that opens About directly.
        self.btn_help = QToolButton()
        # Blue help/info glyph as requested.
        self.btn_help.setText("ℹ")
        self.btn_help.setObjectName("helpButton")
        self.btn_help.setToolTip(f"About {APP_NAME}")
        self.btn_help.setCursor(Qt.PointingHandCursor)
        self.btn_help.setAutoRaise(True)
        self.btn_help.setFixedSize(38, 38)
        self.btn_help.setFont(QFont("Segoe UI", 16))
        self.btn_help.setProperty("topIconButton", True)
        self.btn_help.clicked.connect(self.show_about_dialog)

        help_row = QHBoxLayout()
        help_row.setContentsMargins(0, 0, 0, 0)
        help_row.setSpacing(6)
        help_row.addStretch(1)

        # Zone C: unified utility cluster (far right)
        help_row.addWidget(self.btn_bookmarks)
        help_row.addWidget(self.btn_ideas)
        help_row.addWidget(self.btn_ui_licence)
        help_row.addWidget(self.btn_backend_licence)
        help_row.addWidget(self.btn_help)
        right_panel.addLayout(help_row)

        self.lbl_device = QLabel("Device: -")
        self.lbl_engine = QLabel("Engine: -")
        for lbl in (self.lbl_device, self.lbl_engine):
            lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        right_panel.addWidget(self.lbl_device)
        right_panel.addWidget(self.lbl_engine)
        right_panel.addStretch(1)

        top_panel.addLayout(right_panel)

        root.addLayout(top_panel)

        # Reader row: text on the left, cover on the right.
        reader_row = QHBoxLayout()
        reader_row.setSpacing(12)

        from voice_reader.ui.chapter_spine_widget import ChapterSpineWidget

        self.chapter_spine = ChapterSpineWidget()
        reader_row.addWidget(self.chapter_spine, stretch=0)

        self.reader = QTextEdit()
        self.reader.setReadOnly(True)
        self.reader.setFont(QFont("Segoe UI", 11))
        reader_row.addWidget(self.reader, stretch=1)

        cover_panel = QVBoxLayout()
        cover_panel.setSpacing(6)
        cover_panel.setAlignment(Qt.AlignTop | Qt.AlignRight)
        self.cover = QLabel("No cover")
        self.cover.setAlignment(Qt.AlignCenter)
        # Make cover prominently visible (approx 1.5x previous size).
        self.cover.setFixedSize(225, 330)
        self.cover.setScaledContents(False)
        self.cover.setObjectName("cover")
        cover_panel.addWidget(self.cover)
        cover_panel.addStretch(1)
        reader_row.addLayout(cover_panel)

        root.addLayout(reader_row, stretch=3)

        # Logs panel removed from the main UI. For normal usage, stdout logging
        # is sufficient and keeps the interface focused.
        self.log = None

        self.setCentralWidget(central)
        apply_main_window_theme(self)
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

        # Keep volume icon consistent with current slider position.
        self.volume_slider.valueChanged.connect(self._update_volume_icon)

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
                self._strings.pause_tooltip if is_playing else self._strings.play_tooltip
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
