"""PySide6 main window."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPixmap, QTextCursor
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QProgressBar,
    QMessageBox,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from voice_reader.version import APP_AUTHOR, APP_COPYRIGHT, APP_NAME, __version__


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
        self.btn_play = QPushButton(self._strings.play)
        self.btn_pause = QPushButton(self._strings.pause)
        self.btn_stop = QPushButton(self._strings.stop)
        for b in [self.btn_select_book, self.btn_play, self.btn_pause, self.btn_stop]:
            b.setCursor(Qt.PointingHandCursor)

        controls.addWidget(self.btn_select_book)
        controls.addWidget(QLabel(self._strings.select_voice))
        controls.addWidget(self.voice_combo)
        controls.addStretch(1)
        controls.addWidget(self.btn_play)
        controls.addWidget(self.btn_pause)
        controls.addWidget(self.btn_stop)
        left_panel.addLayout(controls)

        # Status/progress row (kept on the left)
        status = QHBoxLayout()
        status.setSpacing(12)
        self.lbl_progress = QLabel("0/0")
        self.lbl_progress.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
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
        self.btn_help.clicked.connect(self.show_about_dialog)

        help_row = QHBoxLayout()
        help_row.setContentsMargins(0, 0, 0, 0)
        help_row.addStretch(1)
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
        self._apply_theme()
        self._connect_signals()

    def _connect_signals(self) -> None:
        self.btn_select_book.clicked.connect(self.select_book_clicked.emit)
        self.btn_play.clicked.connect(self.play_clicked.emit)
        self.btn_pause.clicked.connect(self.pause_clicked.emit)
        self.btn_stop.clicked.connect(self.stop_clicked.emit)

    def _apply_theme(self) -> None:
        # Dark theme with purple accents.
        purple = "#8b5cf6"
        bg = "#0b0f17"
        panel = "#121826"
        text = "#e5e7eb"
        self.setStyleSheet(f"""
            QMainWindow {{ background: {bg}; }}
            QWidget {{ color: {text}; font-family: Segoe UI; }}
            QTextEdit, QPlainTextEdit {{
                background: {panel};
                border: 1px solid #1f2937;
            }}
            QComboBox {{
                background: {panel};
                border: 1px solid #1f2937;
                padding: 4px 8px;
            }}
            QLabel#cover {{
                background: {panel};
                border: 1px solid #1f2937;
            }}
            QPushButton {{
                background: {panel};
                border: 1px solid #1f2937;
                padding: 6px 10px;
                border-radius: 6px;
            }}
            QPushButton:hover {{ border-color: {purple}; }}
            QPushButton:pressed {{ background: #111827; }}

            QToolButton#helpButton {{
                background: transparent;
                border: 2px solid transparent;
                border-radius: 17px;
                padding: 0px;
                color: #3b82f6;
            }}
            QToolButton#helpButton:hover {{
                border-color: #ffffff;
            }}
            QToolButton#helpButton:pressed {{
                background: rgba(255, 255, 255, 0.08);
            }}

            QProgressBar {{
                background: {panel};
                border: 1px solid #1f2937;
                height: 18px;
            }}
            QProgressBar::chunk {{ background: {purple}; }}
            """)

    def build_about_dialog(self) -> QMessageBox:
        box = QMessageBox(self)
        box.setWindowTitle(f"About {APP_NAME}")
        box.setTextFormat(Qt.RichText)

        # Prefer the runtime-set window icon (which should be narratex.ico).
        icon = self.windowIcon()
        if not icon.isNull():
            try:
                box.setIconPixmap(icon.pixmap(64, 64))
            except Exception:
                # Not fatal.
                pass

        thanks = "<br>".join(
            [
                "PySide6 (Qt for Python) developers",
                "The Python development team",
                "The Nuitka team",
                "Kokoro TTS library",
                "Coqui TTS (TTS)",
                "EbookLib",
                "PyMuPDF",
                "sounddevice",
            ]
        )

        box.setText(
            """
            <div>
              <div style="font-size: 16px;"><b>{app}</b> <span style="font-size: 12px;">v{ver}</span></div>
              <div style="margin-top: 6px;">{copyright}</div>
              <div style="margin-top: 10px;"><b>Author</b>: {author}</div>
              <div style="margin-top: 10px;"><b>Thanks</b>:</div>
              <div style="margin-top: 4px;">{thanks}</div>
            </div>
            """.format(
                app=APP_NAME,
                ver=__version__,
                author=APP_AUTHOR,
                copyright=APP_COPYRIGHT,
                thanks=thanks,
            )
        )

        box.setStandardButtons(QMessageBox.Ok)
        return box

    def show_about_dialog(self) -> None:
        self.build_about_dialog().exec()

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
