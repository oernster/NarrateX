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


class MainWindow(QMainWindow):
    select_book_clicked = Signal()
    play_clicked = Signal()
    pause_clicked = Signal()
    stop_clicked = Signal()
    bookmarks_clicked = Signal()
    ideas_clicked = Signal()
    search_clicked = Signal()
    speed_changed = Signal(str)
    volume_changed = Signal(int)

    previous_chapter_clicked = Signal()
    next_chapter_clicked = Signal()

    def __init__(self, strings: UiStrings | None = None) -> None:
        super().__init__()
        self._strings = strings or UiStrings()

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
        self.btn_select_book = QPushButton(self._strings.select_book)
        self.voice_combo = QComboBox()
        self.voice_combo.setMinimumWidth(220)

        self.speed_combo = QComboBox()
        self.speed_combo.setMinimumWidth(95)
        for s in ["0.75x", "1.00x", "1.25x", "1.50x", "2.00x"]:
            self.speed_combo.addItem(s)
        self.speed_combo.setCurrentText("1.00x")

        # Volume control (session-only, editable during playback).
        self.lbl_volume_icon = QLabel("🔊")
        self.lbl_volume_icon.setToolTip("Volume")
        self.lbl_volume_icon.setFont(QFont("Segoe UI Emoji", 13))

        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(100)
        self.volume_slider.setFixedWidth(120)
        self.volume_slider.setToolTip("Volume")

        self.btn_play = QPushButton(self._strings.play)
        self.btn_pause = QPushButton(self._strings.pause)
        self.btn_stop = QPushButton(self._strings.stop)
        for b in [self.btn_select_book, self.btn_play, self.btn_pause, self.btn_stop]:
            b.setCursor(Qt.PointingHandCursor)

        self.btn_bookmarks = QToolButton()
        self.btn_bookmarks.setText("🔖")
        self.btn_bookmarks.setToolTip("Bookmarks")
        self.btn_bookmarks.setCursor(Qt.PointingHandCursor)
        self.btn_bookmarks.setAutoRaise(True)
        self.btn_bookmarks.setFixedSize(34, 34)
        self.btn_bookmarks.setFont(QFont("Segoe UI Emoji", 15))
        self.btn_bookmarks.setProperty("bookmarkButton", True)

        self.btn_ideas = QToolButton()
        self.btn_ideas.setText("🧠")
        self.btn_ideas.setToolTip("Map the book")
        self.btn_ideas.setCursor(Qt.PointingHandCursor)
        self.btn_ideas.setAutoRaise(True)
        self.btn_ideas.setFixedSize(34, 34)
        self.btn_ideas.setFont(QFont("Segoe UI Emoji", 15))
        self.btn_ideas.setProperty("topIconButton", True)

        # Dedicated progress indicator for background idea mapping.
        # Keep it compact and visually associated with the 🧠 control.
        self.ideas_progress = QProgressBar()
        self.ideas_progress.setObjectName("ideasProgress")
        self.ideas_progress.setRange(0, 100)
        self.ideas_progress.setValue(0)
        self.ideas_progress.setTextVisible(False)
        self.ideas_progress.setFixedWidth(70)
        self.ideas_progress.setVisible(False)

        self.btn_search = QToolButton()
        self.btn_search.setText("🔎")
        self.btn_search.setToolTip(
            "Search requires an idea map. Click 🧠 to map the book."
        )
        self.btn_search.setCursor(Qt.PointingHandCursor)
        self.btn_search.setAutoRaise(True)
        self.btn_search.setFixedSize(34, 34)
        self.btn_search.setFont(QFont("Segoe UI Emoji", 15))
        self.btn_search.setEnabled(False)
        self.btn_search.setProperty("searchButton", True)

        controls.addWidget(self.btn_select_book)
        controls.addWidget(QLabel(self._strings.select_voice))
        controls.addWidget(self.voice_combo)
        controls.addWidget(QLabel("Speed"))
        controls.addWidget(self.speed_combo)

        controls.addWidget(self.lbl_volume_icon)
        controls.addWidget(self.volume_slider)
        controls.addStretch(1)

        controls.addWidget(self.btn_play)
        controls.addWidget(self.btn_pause)
        controls.addWidget(self.btn_stop)
        controls.addWidget(self.btn_bookmarks)
        # Group 🧠 with its progress.
        ideas_group = QVBoxLayout()
        ideas_group.setSpacing(2)
        ideas_group.setContentsMargins(0, 0, 0, 0)
        ideas_group.addWidget(self.btn_ideas, alignment=Qt.AlignHCenter)
        ideas_group.addWidget(self.ideas_progress, alignment=Qt.AlignHCenter)
        controls.addLayout(ideas_group)
        controls.addWidget(self.btn_search)
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

        top_panel.addLayout(left_panel)
        top_panel.addStretch(1)

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
        self.btn_ui_licence.setFixedSize(34, 34)
        self.btn_ui_licence.setFont(QFont("Segoe UI Emoji", 15))
        self.btn_ui_licence.setProperty("topIconButton", True)
        self.btn_ui_licence.clicked.connect(self._show_ui_licence_dialog)

        self.btn_backend_licence = QToolButton()
        self.btn_backend_licence.setText("📃")
        self.btn_backend_licence.setObjectName("backendLicenceButton")
        self.btn_backend_licence.setToolTip("Backend licence")
        self.btn_backend_licence.setCursor(Qt.PointingHandCursor)
        self.btn_backend_licence.setAutoRaise(True)
        self.btn_backend_licence.setFixedSize(34, 34)
        self.btn_backend_licence.setFont(QFont("Segoe UI Emoji", 15))
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
        self.btn_help.setFixedSize(34, 34)
        self.btn_help.setFont(QFont("Segoe UI", 15))
        self.btn_help.setProperty("topIconButton", True)
        self.btn_help.clicked.connect(self.show_about_dialog)

        help_row = QHBoxLayout()
        help_row.setContentsMargins(0, 0, 0, 0)
        help_row.setSpacing(4)
        help_row.addStretch(1)
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
        self.btn_play.clicked.connect(self.play_clicked.emit)
        self.btn_pause.clicked.connect(self.pause_clicked.emit)
        self.btn_stop.clicked.connect(self.stop_clicked.emit)
        self.btn_bookmarks.clicked.connect(self.bookmarks_clicked.emit)
        self.btn_ideas.clicked.connect(self.ideas_clicked.emit)
        self.btn_search.clicked.connect(self.search_clicked.emit)
        self.speed_combo.currentTextChanged.connect(self.speed_changed.emit)
        self.volume_slider.valueChanged.connect(self.volume_changed.emit)
        self.btn_prev_chapter.clicked.connect(self.previous_chapter_clicked.emit)
        self.btn_next_chapter.clicked.connect(self.next_chapter_clicked.emit)

        # Keep volume icon consistent with current slider position.
        self.volume_slider.valueChanged.connect(self._update_volume_icon)

    def _update_volume_icon(self, value: int) -> None:
        v = int(value)
        if v <= 0:
            icon = "🔇"
        elif v <= 50:
            icon = "🔉"
        else:
            icon = "🔊"
        self.lbl_volume_icon.setText(icon)

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
