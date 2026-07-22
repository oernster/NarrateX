"""The main window's controls rows: selection, transport and chapter nav.

Extracted from `_main_window_build` to keep both modules inside the 400-line
guardrail. Mutates `window` by attaching the control attributes tests and
controllers expect, and returns the two ready rows for the caller to place.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QSize, Qt
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

from voice_reader.ui.keeb_keys import install_keeb_keys

# The reference emoji size is the top icon buttons (🧠 and 🔖 at 16pt).
# The book and mic cues render at this size so every emoji reads equally.
_EMOJI_CUE_POINT_SIZE = 16
_EMOJI_CUE_FONT_FAMILY = "Segoe UI Emoji"

# The play/pause glyph is a text symbol, not an emoji; 18pt in its 52px
# circle visually matches the 16pt emoji footprint.
_TRANSPORT_GLYPH_POINT_SIZE = 18

# The stop button's painted red square, sized to sit with the larger cues.
_STOP_CUE_PX = 20

# Monochrome cue glyphs (the GB/US letter tiles, the sex symbols) take the
# painter's pen, so it must be the theme's light text colour; the default
# pen is black, invisible on the dark surface. Colour emoji ignore it.
_EMOJI_CUE_TEXT_COLOR = "#e5e7eb"


def _painted_bounds(image) -> tuple[int, int, int, int] | None:
    """Tight (left, top, right, bottom) of the non-transparent pixels."""

    left, top = image.width(), image.height()
    right, bottom = -1, -1
    for y in range(image.height()):
        for x in range(image.width()):
            if image.pixelColor(x, y).alpha() > 0:
                left = min(left, x)
                top = min(top, y)
                right = max(right, x)
                bottom = max(bottom, y)
    if right < 0:
        return None
    return left, top, right, bottom


def emoji_cue_pixmap(emoji: str) -> QPixmap:
    """Render one emoji at the reference cue size, optically centred.

    AlignCenter centres the font's line box, not the glyph: Segoe UI Emoji
    reserves tall emoji headroom, so a small glyph (the GB/US letter tiles)
    sits visibly low in it. The glyph's actual painted pixels are found and
    re-centred in the final square instead.
    """

    font = QFont(_EMOJI_CUE_FONT_FAMILY, _EMOJI_CUE_POINT_SIZE)
    metrics = QFontMetrics(font)
    side = max(metrics.height(), metrics.horizontalAdvance(emoji))

    # A double-size canvas so odd metrics can never clip the glyph.
    canvas = QPixmap(side * 2, side * 2)
    canvas.fill(Qt.transparent)
    p = QPainter(canvas)
    p.setFont(font)
    p.setPen(QColor(_EMOJI_CUE_TEXT_COLOR))
    p.drawText(canvas.rect(), Qt.AlignCenter, emoji)
    p.end()

    bounds = _painted_bounds(canvas.toImage())
    if bounds is None:
        return canvas.copy(0, 0, side, side)

    left, top, right, bottom = bounds
    glyph_w = right - left + 1
    glyph_h = bottom - top + 1
    out_side = max(side, glyph_w, glyph_h)

    out = QPixmap(out_side, out_side)
    out.fill(Qt.transparent)
    p = QPainter(out)
    p.drawPixmap(
        (out_side - glyph_w) // 2,
        (out_side - glyph_h) // 2,
        canvas.copy(left, top, glyph_w, glyph_h),
    )
    p.end()
    return out


def _split_leading_emoji(text: str) -> tuple[str | None, str]:
    """Split "📚 Select Book" into its emoji cue and its plain label.

    Custom strings without a leading emoji come back unchanged (cue None).
    """

    head, _, rest = str(text).partition(" ")
    if rest and not head.isascii():
        return head, rest
    return None, str(text)


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
        pm = emoji_cue_pixmap(book_cue)
        window.btn_select_book.setIcon(QIcon(pm))
        window.btn_select_book.setIconSize(pm.size())
    window.btn_select_book.setMinimumHeight(top_row_min_h)

    # Remove the current book from NarrateX's memory (bookmarks, resume,
    # ideas map, cached audio); the file on disk is never touched. Locked
    # until a book loads, like the picker.
    window.btn_remove_book = QToolButton()
    window.btn_remove_book.setText("❌")
    window.btn_remove_book.setToolTip("Remove current book (the file is kept)")
    window.btn_remove_book.setCursor(Qt.PointingHandCursor)
    window.btn_remove_book.setAutoRaise(True)
    window.btn_remove_book.setFixedSize(38, 38)
    window.btn_remove_book.setFont(QFont(_EMOJI_CUE_FONT_FAMILY, 13))
    window.btn_remove_book.setProperty("topIconButton", True)
    window.btn_remove_book.setEnabled(False)

    window.voice_combo = QComboBox()
    window.voice_combo.setMinimumWidth(220)
    window.voice_combo.setMinimumHeight(top_row_min_h)
    # No voice is defaulted: the combo rests on this placeholder until the
    # user chooses, and the picker stays disabled until a book loads.
    window.voice_combo.setPlaceholderText(strings.select_voice)

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
    window.volume_slider = QSlider(Qt.Horizontal)
    window.volume_slider.setRange(0, 100)
    # UX default: 25% until a persisted preference is loaded.
    window.volume_slider.setValue(25)
    window.volume_slider.setFixedWidth(140)
    window.volume_slider.setToolTip("Volume")
    # The volume STOP on the keyboard ring is the speaker button, never the
    # slider: the ring highlights the emoji and Up/Down adjust the level.
    window.volume_slider.setFocusPolicy(Qt.NoFocus)

    window.lbl_volume_icon = QToolButton()
    window.lbl_volume_icon.setText("🔊")
    window.lbl_volume_icon.setToolTip("Volume (Up/Down adjusts while focused)")
    window.lbl_volume_icon.setFont(QFont(_EMOJI_CUE_FONT_FAMILY, 13))
    window.lbl_volume_icon.setAutoRaise(True)
    window.lbl_volume_icon.setFixedSize(38, 38)
    window.lbl_volume_icon.setProperty("topIconButton", True)
    # The app-wide keeb filter reads this link to route Up/Down.
    window.lbl_volume_icon.keeb_volume_slider = window.volume_slider

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

    # Keeb key handling is app-wide now (Enter clicks the focused button,
    # Down/Enter open a closed dropdown, Up/Down drive the volume stop), so
    # every dialog inherits the same rules as the picker.
    install_keeb_keys()

    # Zone A: setup/content selection (left). The voice caption lives in
    # the combo's own placeholder now, so no external mic label repeats it.
    zone_a = QHBoxLayout()
    zone_a.setSpacing(8)
    zone_a.addWidget(window.btn_select_book)
    zone_a.addWidget(window.btn_remove_book)
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
