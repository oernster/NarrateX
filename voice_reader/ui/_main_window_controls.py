"""The main window's controls rows: selection, transport and chapter nav.

Extracted from `_main_window_build` to keep both modules inside the 400-line
guardrail. Mutates `window` by attaching the control attributes tests and
controllers expect, and returns the two ready rows for the caller to place.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QEvent, QObject, QSize, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QIcon,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QComboBox,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QToolButton,
)

# The reference emoji size is the top icon buttons (🧠 and 🔖 at 16pt).
# The book and mic cues render at this size so every emoji reads equally.
_EMOJI_CUE_POINT_SIZE = 16
_EMOJI_CUE_FONT_FAMILY = "Segoe UI Emoji"

# The play/pause glyph is a text symbol, not an emoji; 18pt in its 52px
# circle visually matches the 16pt emoji footprint.
_TRANSPORT_GLYPH_POINT_SIZE = 18

# The stop button's painted red square, sized to sit with the larger cues.
_STOP_CUE_PX = 20


def _emoji_pixmap(emoji: str) -> QPixmap:
    """Render one emoji at the reference cue size on a transparent square."""

    font = QFont(_EMOJI_CUE_FONT_FAMILY, _EMOJI_CUE_POINT_SIZE)
    metrics = QFontMetrics(font)
    side = max(metrics.height(), metrics.horizontalAdvance(emoji))
    pm = QPixmap(side, side)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setFont(font)
    p.drawText(pm.rect(), Qt.AlignCenter, emoji)
    p.end()
    return pm


def _split_leading_emoji(text: str) -> tuple[str | None, str]:
    """Split "📚 Select Book" into its emoji cue and its plain label.

    Custom strings without a leading emoji come back unchanged (cue None).
    """

    head, _, rest = str(text).partition(" ")
    if rest and not head.isascii():
        return head, rest
    return None, str(text)


class PickerKeys(QObject):
    """Keeb key handling for the voice picker controls.

    - Return/Enter clicks a focused toggle button (Qt only honours Space in
      a main window).
    - Down on a CLOSED combo opens its popup instead of silently changing
      the value; the open popup then owns its own keys natively.
    """

    def eventFilter(self, obj, event) -> bool:  # noqa: N802 (Qt naming)
        if event.type() != QEvent.KeyPress:
            return False
        key = event.key()
        if isinstance(obj, QToolButton) and key in (Qt.Key_Return, Qt.Key_Enter):
            obj.click()
            return True
        if isinstance(obj, QComboBox) and key == Qt.Key_Down:
            if not obj.view().isVisible():
                obj.showPopup()
                return True
        return False


def build_controls_rows(window: Any, *, strings) -> tuple[QHBoxLayout, QHBoxLayout]:
    """Build the controls row and the chapter-nav row.

    Returns `(controls, chapter_nav)` for the caller to add to its panel.
    """

    controls = QHBoxLayout()
    controls.setSpacing(8)

    # Slightly taller top-row controls to harmonize with the chapter-nav row.
    top_row_min_h = 42

    # The book emoji renders as an icon cue at the reference size; inline in
    # the label it would be locked to the label's own font size.
    book_cue, book_label = _split_leading_emoji(strings.select_book)
    window.btn_select_book = QPushButton(book_label)
    if book_cue is not None:
        pm = _emoji_pixmap(book_cue)
        window.btn_select_book.setIcon(QIcon(pm))
        window.btn_select_book.setIconSize(pm.size())
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
    window.btn_play_pause.setFont(QFont("Segoe UI", _TRANSPORT_GLYPH_POINT_SIZE))

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
        cue_size = _STOP_CUE_PX
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
    window.btn_bookmarks.setFont(QFont(_EMOJI_CUE_FONT_FAMILY, _EMOJI_CUE_POINT_SIZE))
    window.btn_bookmarks.setProperty("bookmarkButton", True)
    window.btn_bookmarks.setProperty("topIconButton", True)

    window.btn_ideas = QToolButton()
    window.btn_ideas.setText("🧠")
    window.btn_ideas.setToolTip("Sections")
    window.btn_ideas.setCursor(Qt.PointingHandCursor)
    window.btn_ideas.setAutoRaise(True)
    window.btn_ideas.setFixedSize(38, 38)
    window.btn_ideas.setFont(QFont(_EMOJI_CUE_FONT_FAMILY, _EMOJI_CUE_POINT_SIZE))
    window.btn_ideas.setProperty("topIconButton", True)

    # Voice picker toggles: sex and region, filtering the dropdown.
    # Same family as the top icon buttons; glyphs and tooltips are kept
    # current by the controller's refresh.
    window.btn_voice_sex = QToolButton()
    window.btn_voice_region = QToolButton()
    for b in (window.btn_voice_sex, window.btn_voice_region):
        b.setCursor(Qt.PointingHandCursor)
        b.setAutoRaise(True)
        b.setFixedSize(38, 38)
        b.setFont(QFont(_EMOJI_CUE_FONT_FAMILY, _EMOJI_CUE_POINT_SIZE))
        b.setProperty("topIconButton", True)

    # Keeb key handling for the picker (Enter clicks toggles; Down opens a
    # closed dropdown rather than changing its value).
    window._picker_keys = PickerKeys(window)  # noqa: SLF001
    for w in (
        window.btn_voice_sex,
        window.btn_voice_region,
        window.voice_combo,
        window.speed_combo,
    ):
        w.installEventFilter(window._picker_keys)  # noqa: SLF001

    # Zone A: setup/content selection (left)
    zone_a = QHBoxLayout()
    zone_a.setSpacing(8)
    zone_a.addWidget(window.btn_select_book)
    # The mic emoji gets its own label at the reference cue size so it
    # matches the other emoji instead of the caption's font.
    voice_cue, voice_label = _split_leading_emoji(strings.select_voice)
    if voice_cue is not None:
        window.lbl_voice_icon = QLabel(voice_cue)
        window.lbl_voice_icon.setFont(
            QFont(_EMOJI_CUE_FONT_FAMILY, _EMOJI_CUE_POINT_SIZE)
        )
        window.lbl_voice_icon.setToolTip(voice_label)
        zone_a.addWidget(window.lbl_voice_icon)
    zone_a.addWidget(QLabel(voice_label))
    zone_a.addWidget(window.btn_voice_sex)
    zone_a.addWidget(window.btn_voice_region)
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

    return controls, chapter_nav
