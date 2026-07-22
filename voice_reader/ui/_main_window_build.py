from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from voice_reader.ui._main_window_controls import build_controls_rows
from voice_reader.ui.window_helpers import apply_main_window_theme
from voice_reader.version import APP_NAME


def build_main_window_widgets(window: Any, *, strings) -> None:
    """Build and attach the MainWindow widget tree.

    This module exists to keep [`MainWindow`](voice_reader/ui/main_window.py:57)
    small enough to satisfy the hard <=400 LOC guardrail.

    It mutates `window` by attaching the same widget attributes that tests and
    controllers expect (btn_select_book, reader, cover, etc.).
    """

    # Keep cover column dimensions in one place so related alignment (like the
    # subtle progress block) can intentionally snap to the same boundary.
    cover_w, cover_h = 225, 330

    # Transport UI is driven by narration state.
    window._transport_is_playing = False  # noqa: SLF001

    window.setWindowTitle(APP_NAME)
    window.resize(1100, 700)

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

    controls, chapter_nav = build_controls_rows(window, strings=strings)
    left_panel.addLayout(controls)
    left_panel.addLayout(chapter_nav)

    # Status/progress row (kept on the left)
    status = QHBoxLayout()
    status.setSpacing(12)

    window.lbl_status = QLabel("Idle")
    window.lbl_status.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    window.lbl_status.setMinimumWidth(260)

    window.lbl_progress = QLabel("0/0")
    window.lbl_progress.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    window.progress = QProgressBar()
    window.progress.setRange(0, 100)
    window.progress.setValue(0)

    progress_wrap = QWidget()
    progress_wrap.setObjectName("progressWrap")
    progress_layout = QHBoxLayout(progress_wrap)
    progress_layout.setContentsMargins(0, 0, 0, 0)
    progress_layout.setSpacing(10)
    progress_layout.addWidget(window.lbl_progress)
    progress_layout.addWidget(window.progress)
    progress_layout.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

    # Keep a stable width so the right edge of the progress block reads as a
    # column aligned with the cover panel.
    progress_wrap.setMinimumWidth(cover_w)

    status.addWidget(window.lbl_status)
    status.addStretch(1)
    status.addWidget(progress_wrap)
    left_panel.addLayout(status)

    # Give the left panel the expandable width so Zone B can read as centered.
    top_panel.addLayout(left_panel, stretch=1)

    # Right side: right-justified device/engine labels.
    right_panel = QVBoxLayout()
    right_panel.setSpacing(6)
    right_panel.setAlignment(Qt.AlignTop | Qt.AlignRight)

    window.btn_ui_licence = QToolButton()
    window.btn_ui_licence.setText("📜")
    window.btn_ui_licence.setObjectName("uiLicenceButton")
    window.btn_ui_licence.setToolTip("UI licence")
    window.btn_ui_licence.setCursor(Qt.PointingHandCursor)
    window.btn_ui_licence.setAutoRaise(True)
    window.btn_ui_licence.setFixedSize(38, 38)
    window.btn_ui_licence.setFont(QFont("Segoe UI Emoji", 16))
    window.btn_ui_licence.setProperty("topIconButton", True)

    window.btn_backend_licence = QToolButton()
    window.btn_backend_licence.setText("📃")
    window.btn_backend_licence.setObjectName("backendLicenceButton")
    window.btn_backend_licence.setToolTip("Backend licence")
    window.btn_backend_licence.setCursor(Qt.PointingHandCursor)
    window.btn_backend_licence.setAutoRaise(True)
    window.btn_backend_licence.setFixedSize(38, 38)
    window.btn_backend_licence.setFont(QFont("Segoe UI Emoji", 16))
    window.btn_backend_licence.setProperty("topIconButton", True)

    # Info button (top-right) that opens About directly.
    window.btn_help = QToolButton()
    # Blue help/info glyph.
    window.btn_help.setText("ℹ")
    window.btn_help.setObjectName("helpButton")
    window.btn_help.setToolTip(f"About {APP_NAME}")
    window.btn_help.setCursor(Qt.PointingHandCursor)
    window.btn_help.setAutoRaise(True)
    window.btn_help.setFixedSize(38, 38)
    window.btn_help.setFont(QFont("Segoe UI", 16))
    window.btn_help.setProperty("topIconButton", True)

    help_row = QHBoxLayout()
    help_row.setContentsMargins(0, 0, 0, 0)
    help_row.setSpacing(6)
    help_row.addStretch(1)

    # Zone C: unified utility cluster (far right)
    help_row.addWidget(window.btn_bookmarks)
    help_row.addWidget(window.btn_ideas)
    help_row.addWidget(window.btn_ui_licence)
    help_row.addWidget(window.btn_backend_licence)
    help_row.addWidget(window.btn_help)
    right_panel.addLayout(help_row)

    window.lbl_device = QLabel("Device: -")
    window.lbl_engine = QLabel("Engine: -")
    for lbl in (window.lbl_device, window.lbl_engine):
        lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

    right_panel.addWidget(window.lbl_device)
    right_panel.addWidget(window.lbl_engine)
    right_panel.addStretch(1)

    right_panel_widget = QWidget()
    right_panel_widget.setFixedWidth(cover_w)
    right_panel_widget.setLayout(right_panel)
    top_panel.addWidget(right_panel_widget)

    root.addLayout(top_panel)

    # Reader row: text on the left, cover on the right.
    reader_row = QHBoxLayout()
    reader_row.setSpacing(12)

    from voice_reader.ui.chapter_spine_widget import ChapterSpineWidget

    window.chapter_spine = ChapterSpineWidget()
    reader_row.addWidget(window.chapter_spine, stretch=0)

    from voice_reader.ui.seekable_text_edit import SeekableTextEdit

    window.reader = SeekableTextEdit()
    window.reader.setReadOnly(True)
    window.reader.setFont(QFont("Segoe UI", 11))
    # The reader is the scrollable-content stop: the arrows scroll it and
    # Tab leaves it. Without this, a read-only QTextEdit swallows Tab.
    window.reader.setTabChangesFocus(True)
    reader_row.addWidget(window.reader, stretch=1)

    cover_panel = QVBoxLayout()
    cover_panel.setContentsMargins(0, 0, 0, 0)
    cover_panel.setSpacing(6)
    cover_panel.setAlignment(Qt.AlignTop | Qt.AlignRight)
    window.cover = QLabel("No cover")
    window.cover.setAlignment(Qt.AlignCenter)
    window.cover.setFixedSize(cover_w, cover_h)
    window.cover.setScaledContents(False)
    window.cover.setObjectName("cover")
    cover_panel.addWidget(window.cover)
    cover_panel.addStretch(1)

    # The whole column is hidden when a book has no cover, so the reader text
    # takes the full width rather than sitting beside an empty placeholder. The
    # panel is a widget, not a bare layout, so its visibility can be toggled.
    window.cover_panel = QWidget()
    window.cover_panel.setLayout(cover_panel)
    reader_row.addWidget(window.cover_panel, stretch=0)

    root.addLayout(reader_row, stretch=3)

    window.log = None

    window.setCentralWidget(central)

    # Explicit keyboard ring in visual order, replacing creation-order
    # traversal. Qt wraps from the last stop back to the first, so Tab on
    # Next Chapter proceeds to Select Book. Disabled stops are skipped by
    # Qt natively.
    ring = [
        window.btn_select_book,
        window.btn_remove_book,
        window.btn_voice_sex,
        window.btn_voice_region,
        window.voice_combo,
        window.speed_combo,
        window.btn_play_pause,
        window.btn_stop,
        window.lbl_volume_icon,
        window.btn_bookmarks,
        window.btn_ideas,
        window.btn_ui_licence,
        window.btn_backend_licence,
        window.btn_help,
        window.reader,
        window.btn_prev_chapter,
        window.btn_next_chapter,
    ]
    for earlier, later in zip(ring, ring[1:]):
        QWidget.setTabOrder(earlier, later)

    apply_main_window_theme(window)
