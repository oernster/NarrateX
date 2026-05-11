from __future__ import annotations

from typing import Any

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QIcon,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QGraphicsDropShadowEffect
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QProgressBar,
    QSlider,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

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

    # Controls row
    controls = QHBoxLayout()
    controls.setSpacing(8)

    # Slightly taller top-row controls to harmonize with the chapter-nav row.
    top_row_min_h = 42

    window.btn_select_book = QPushButton(strings.select_book)
    window.btn_select_book.setMinimumHeight(top_row_min_h)
    window.voice_combo = QComboBox()
    window.voice_combo.setMinimumWidth(220)
    window.voice_combo.setMinimumHeight(top_row_min_h)

    window.speed_combo = QComboBox()
    window.speed_combo.setMinimumWidth(95)
    window.speed_combo.setMinimumHeight(top_row_min_h)
    for s in ["0.75x", "1.00x", "1.25x", "1.50x", "2.00x"]:
        window.speed_combo.addItem(s)
    window.speed_combo.setCurrentText("1.00x")

    # Primary playback control: one large circular Play/Pause toggle.
    window.btn_play_pause = QToolButton()
    window.btn_play_pause.setObjectName("playPauseButton")
    window.btn_play_pause.setCheckable(True)
    window.btn_play_pause.setAutoRaise(False)
    window.btn_play_pause.setCursor(Qt.PointingHandCursor)
    window.btn_play_pause.setToolTip("Play")
    window.btn_play_pause.setText("▶")
    # Slightly larger to read as the single primary transport control.
    window.btn_play_pause.setFixedSize(52, 52)
    window.btn_play_pause.setFont(QFont("Segoe UI", 15))

    # Subtle, premium glow (local effect only; does not restyle other controls).
    try:
        glow = QGraphicsDropShadowEffect(window.btn_play_pause)
        glow.setBlurRadius(18)
        glow.setOffset(0, 0)
        glow.setColor(QColor(59, 130, 246, 70))
        window.btn_play_pause.setGraphicsEffect(glow)
    except Exception:
        pass

    window.btn_stop = QPushButton(strings.stop)
    window.btn_stop.setObjectName("stopButton")
    window.btn_stop.setCursor(Qt.PointingHandCursor)
    window.btn_stop.setMinimumHeight(top_row_min_h)
    # Slightly larger than a standard button, but still secondary.
    window.btn_stop.setMinimumWidth(104)

    # Add a restrained red square stop cue via an icon, keeping the button
    # visually secondary without turning it into a warning-colored block.
    window.btn_stop.setText("Stop")
    try:
        cue_size = 12
        pm = QPixmap(cue_size, cue_size)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(QPen(QColor(0, 0, 0, 0)))
        p.setBrush(QColor("#ef4444"))
        r = pm.rect().adjusted(1, 1, -1, -1)
        p.drawRoundedRect(r, 2, 2)
        p.end()
        window.btn_stop.setIcon(QIcon(pm))
        window.btn_stop.setIconSize(QSize(cue_size, cue_size))
    except Exception:
        pass

    # Volume control (session-only, editable during playback).
    window.lbl_volume_icon = QLabel("🔊")
    window.lbl_volume_icon.setToolTip("Volume")
    window.lbl_volume_icon.setFont(QFont("Segoe UI Emoji", 13))

    window.volume_slider = QSlider(Qt.Horizontal)
    window.volume_slider.setRange(0, 100)
    # UX default: 25% until a persisted preference is loaded.
    window.volume_slider.setValue(25)
    window.volume_slider.setFixedWidth(140)
    window.volume_slider.setToolTip("Volume")

    window.btn_bookmarks = QToolButton()
    window.btn_bookmarks.setText("🔖")
    window.btn_bookmarks.setToolTip("Bookmarks")
    window.btn_bookmarks.setCursor(Qt.PointingHandCursor)
    window.btn_bookmarks.setAutoRaise(True)
    window.btn_bookmarks.setFixedSize(38, 38)
    window.btn_bookmarks.setFont(QFont("Segoe UI Emoji", 16))
    window.btn_bookmarks.setProperty("bookmarkButton", True)
    window.btn_bookmarks.setProperty("topIconButton", True)

    window.btn_ideas = QToolButton()
    window.btn_ideas.setText("🧠")
    window.btn_ideas.setToolTip("Sections")
    window.btn_ideas.setCursor(Qt.PointingHandCursor)
    window.btn_ideas.setAutoRaise(True)
    window.btn_ideas.setFixedSize(38, 38)
    window.btn_ideas.setFont(QFont("Segoe UI Emoji", 16))
    window.btn_ideas.setProperty("topIconButton", True)

    # Zone A: setup/content selection (left)
    zone_a = QHBoxLayout()
    zone_a.setSpacing(8)
    zone_a.addWidget(window.btn_select_book)
    zone_a.addWidget(QLabel(strings.select_voice))
    zone_a.addWidget(window.voice_combo)
    zone_a.addWidget(QLabel("Speed"))
    zone_a.addWidget(window.speed_combo)

    # Zone B: primary playback (center)
    zone_b = QHBoxLayout()
    zone_b.setSpacing(8)
    zone_b.addWidget(window.btn_play_pause)
    zone_b.addWidget(window.btn_stop)
    zone_b.addWidget(window.lbl_volume_icon)
    zone_b.addWidget(window.volume_slider)

    controls.addLayout(zone_a)
    controls.addStretch(1)
    controls.addLayout(zone_b)
    controls.addStretch(1)
    left_panel.addLayout(controls)

    # Chapter navigation row (larger buttons for visibility).
    chapter_nav = QHBoxLayout()
    chapter_nav.setSpacing(8)

    window.btn_prev_chapter = QPushButton("⏮ Previous Chapter")
    window.btn_next_chapter = QPushButton("Next Chapter ⏭")
    for b in (window.btn_prev_chapter, window.btn_next_chapter):
        b.setCursor(Qt.PointingHandCursor)
        b.setMinimumHeight(42)
        b.setMinimumWidth(190)
        b.setFont(QFont("Segoe UI", 12))

    # Harmonize top-row button height with chapter-nav row without making
    # the UI feel oversized.
    try:
        window.btn_stop.setMinimumHeight(42)
        window.btn_select_book.setMinimumHeight(42)
        window.voice_combo.setMinimumHeight(42)
        window.speed_combo.setMinimumHeight(42)
    except Exception:
        pass

    chapter_nav.addWidget(window.btn_prev_chapter)
    chapter_nav.addWidget(window.btn_next_chapter)
    chapter_nav.addStretch(1)
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
    reader_row.addWidget(window.reader, stretch=1)

    cover_panel = QVBoxLayout()
    cover_panel.setSpacing(6)
    cover_panel.setAlignment(Qt.AlignTop | Qt.AlignRight)
    window.cover = QLabel("No cover")
    window.cover.setAlignment(Qt.AlignCenter)
    window.cover.setFixedSize(cover_w, cover_h)
    window.cover.setScaledContents(False)
    window.cover.setObjectName("cover")
    cover_panel.addWidget(window.cover)
    cover_panel.addStretch(1)
    reader_row.addLayout(cover_panel)

    root.addLayout(reader_row, stretch=3)

    window.log = None

    window.setCentralWidget(central)
    apply_main_window_theme(window)
