"""PySide6 main window."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QTextCursor
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QPlainTextEdit,
    QProgressBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


@dataclass(frozen=True, slots=True)
class UiStrings:
    select_book: str = "📚 Select Book"
    select_voice: str = "🎙 Select Voice"
    play: str = "▶ Play"
    pause: str = "⏸ Pause"
    stop: str = "⏹ Stop"


class MainWindow(QMainWindow):
    select_book_clicked = Signal()
    play_clicked = Signal()
    pause_clicked = Signal()
    stop_clicked = Signal()

    def __init__(self, strings: UiStrings | None = None) -> None:
        super().__init__()
        self._strings = strings or UiStrings()
        self.setWindowTitle("Voice Reader")
        self.resize(1100, 700)

        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # Controls
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
        root.addLayout(controls)

        # Status row
        status = QHBoxLayout()
        status.setSpacing(12)
        self.lbl_device = QLabel("Device: -")
        self.lbl_engine = QLabel("Engine: -")
        self.lbl_progress = QLabel("0/0")
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        status.addWidget(self.lbl_device)
        status.addWidget(self.lbl_engine)
        status.addStretch(1)
        status.addWidget(self.lbl_progress)
        status.addWidget(self.progress)
        root.addLayout(status)

        # Reader
        self.reader = QTextEdit()
        self.reader.setReadOnly(True)
        self.reader.setFont(QFont("Segoe UI", 11))
        root.addWidget(self.reader, stretch=3)

        # Logs
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(5000)
        root.addWidget(self.log, stretch=1)

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
            QPushButton {{
                background: {panel};
                border: 1px solid #1f2937;
                padding: 6px 10px;
                border-radius: 6px;
            }}
            QPushButton:hover {{ border-color: {purple}; }}
            QPushButton:pressed {{ background: #111827; }}
            QProgressBar {{
                background: {panel};
                border: 1px solid #1f2937;
                height: 18px;
            }}
            QProgressBar::chunk {{ background: {purple}; }}
            """)

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
        self.log.appendPlainText(line)
