"""The cue glyphs must be visible on the dark theme.

Regression: the pixmap painter's default pen is black, so the GB/US letter
tiles and the sex symbols rendered dark on dark and vanished. The cue
renderer must paint monochrome glyphs in the theme's light text colour.
"""

from __future__ import annotations

from voice_reader.ui._main_window_controls import emoji_cue_pixmap

# Anything above this channel value reads as light on the dark surface.
LIGHT_CHANNEL = 180


def _has_light_pixels(pm) -> bool:
    image = pm.toImage()
    for y in range(image.height()):
        for x in range(image.width()):
            c = image.pixelColor(x, y)
            if c.alpha() > 0 and max(c.red(), c.green(), c.blue()) >= LIGHT_CHANNEL:
                return True
    return False


def test_the_region_tile_renders_light_on_dark(qapp) -> None:
    del qapp
    assert _has_light_pixels(emoji_cue_pixmap("🇬🇧"))


def test_the_sex_symbols_render_light_on_dark(qapp) -> None:
    del qapp
    assert _has_light_pixels(emoji_cue_pixmap("♀"))
    assert _has_light_pixels(emoji_cue_pixmap("♂"))


def _glyph_centre_offset(pm) -> tuple[float, float]:
    """How far the painted pixels' centre sits from the pixmap centre."""

    image = pm.toImage()
    left, top = image.width(), image.height()
    right, bottom = -1, -1
    for y in range(image.height()):
        for x in range(image.width()):
            if image.pixelColor(x, y).alpha() > 0:
                left = min(left, x)
                top = min(top, y)
                right = max(right, x)
                bottom = max(bottom, y)
    assert right >= 0, "empty glyph"
    glyph_cx = (left + right) / 2
    glyph_cy = (top + bottom) / 2
    return (
        abs(glyph_cx - (image.width() - 1) / 2),
        abs(glyph_cy - (image.height() - 1) / 2),
    )


def test_cue_glyphs_are_optically_centred(qapp) -> None:
    """Regression: the GB tile sat low because AlignCenter centres the
    emoji font's tall line box, not the glyph's painted pixels."""

    del qapp
    for glyph in ("🇬🇧", "🇺🇸", "♀", "♂"):
        dx, dy = _glyph_centre_offset(emoji_cue_pixmap(glyph))
        assert dx <= 1.0, f"{glyph} horizontally off by {dx}px"
        assert dy <= 1.0, f"{glyph} vertically off by {dy}px"
