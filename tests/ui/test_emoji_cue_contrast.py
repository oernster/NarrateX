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
