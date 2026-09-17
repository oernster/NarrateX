"""The Help menu is readable: its text contrasts with what it is painted on.

Measured on the rendered pixels rather than the stylesheet text, because the
defect this guards (light theme text on the style's white menu background)
lived in a rule that was absent, which no selector check can see.
"""

from __future__ import annotations

from collections import Counter

from PySide6.QtGui import QColor

from voice_reader.ui.main_window import MainWindow

# WCAG 2.x AA minimum contrast ratio for body text.
WCAG_AA_TEXT_CONTRAST = 4.5

# WCAG relative luminance: the sRGB linearisation and its channel weights.
_SRGB_LINEAR_KNEE = 0.03928
_SRGB_LINEAR_DIVISOR = 12.92
_SRGB_GAMMA_OFFSET = 0.055
_SRGB_GAMMA_SCALE = 1.055
_SRGB_GAMMA = 2.4
_LUMINANCE_WEIGHTS = (0.2126, 0.7152, 0.0722)
_CONTRAST_FLARE = 0.05


def _luminance(colour: QColor) -> float:
    def linear(channel: float) -> float:
        if channel <= _SRGB_LINEAR_KNEE:
            return channel / _SRGB_LINEAR_DIVISOR
        return ((channel + _SRGB_GAMMA_OFFSET) / _SRGB_GAMMA_SCALE) ** _SRGB_GAMMA

    channels = (colour.redF(), colour.greenF(), colour.blueF())
    return sum(w * linear(c) for w, c in zip(_LUMINANCE_WEIGHTS, channels))


def _contrast(a: QColor, b: QColor) -> float:
    lighter, darker = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (lighter + _CONTRAST_FLARE) / (darker + _CONTRAST_FLARE)


def _dominant_and_pixels(menu) -> tuple[QColor, Counter]:
    image = menu.grab().toImage()
    pixels = Counter(
        image.pixel(x, y) for x in range(image.width()) for y in range(image.height())
    )
    return QColor(pixels.most_common(1)[0][0]), pixels


def _text_contrast(menu) -> float:
    """Contrast of the strongest text pixel against the dominant background."""

    background, pixels = _dominant_and_pixels(menu)
    return max(_contrast(QColor(p), background) for p in pixels)


def _open_help_menu(qapp):
    window = MainWindow()
    menu = window.build_help_menu()
    menu.popup(window.mapToGlobal(window.rect().center()))
    qapp.processEvents()
    # Keep the window alive for as long as the menu is measured.
    menu.owner_window = window
    return menu


def test_help_menu_text_is_readable_at_rest(qapp) -> None:
    menu = _open_help_menu(qapp)

    assert _text_contrast(menu) >= WCAG_AA_TEXT_CONTRAST


def test_help_menu_selected_item_is_readable(qapp) -> None:
    menu = _open_help_menu(qapp)
    # The only item: the selection then fills the dominant area measured.
    for action in menu.actions()[1:]:
        menu.removeAction(action)
    menu.setActiveAction(menu.actions()[0])
    qapp.processEvents()

    assert _text_contrast(menu) >= WCAG_AA_TEXT_CONTRAST


def test_help_menu_background_is_dark_like_the_window(qapp) -> None:
    menu = _open_help_menu(qapp)

    background, _ = _dominant_and_pixels(menu)
    assert _contrast(background, QColor("white")) > _contrast(
        background, QColor("black")
    )
