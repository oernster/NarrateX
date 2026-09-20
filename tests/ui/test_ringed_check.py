"""The ring a tick box paints round its own square."""

from __future__ import annotations

from PySide6.QtGui import QImage

from voice_reader.ui.ringed_check import RingedCheckBox

GREEN = "#22c55e"
RED = "#dc2626"


def _painted(box: RingedCheckBox) -> QImage:
    """The box drawn into an image, so the pixels can be read back."""

    canvas = QImage(box.size(), QImage.Format.Format_ARGB32)
    canvas.fill(0)
    box.render(canvas)
    return canvas


def _pixels(canvas: QImage, colour: str) -> int:
    from PySide6.QtGui import QColor

    wanted = QColor(colour).rgb()
    return sum(
        1
        for y in range(canvas.height())
        for x in range(canvas.width())
        if canvas.pixelColor(x, y).rgb() == wanted
    )


def _box(qapp) -> RingedCheckBox:
    del qapp
    box = RingedCheckBox("Horror")
    box.setProperty("ringColour", GREEN)
    box.setProperty("dangerColour", RED)
    box.resize(box.sizeHint())
    return box


def test_a_box_at_rest_wears_no_ring(qapp) -> None:
    box = _box(qapp)

    assert box.ring_now() == ""


def test_a_box_that_cannot_be_pressed_wears_the_danger_colour(qapp) -> None:
    box = _box(qapp)
    box.setEnabled(False)

    assert box.ring_now() == RED


def test_a_focused_box_wears_the_ring(qapp) -> None:
    """The box has to sit in an active window before Qt will focus it."""

    import warnings

    from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

    window = QWidget()
    QVBoxLayout(window).addWidget(_box(qapp))
    box = window.findChild(RingedCheckBox)
    window.show()
    with warnings.catch_warnings():
        # The undeprecated `activateWindow` does not make a window active on
        # the offscreen platform, measured; this one does.
        warnings.simplefilter("ignore", DeprecationWarning)
        QApplication.setActiveWindow(window)
    box.setFocus()

    assert box.hasFocus()
    assert box.ring_now() == GREEN
    window.close()


def test_the_ring_reaches_the_pixels(qapp) -> None:
    """A ring that is decided and never drawn looks identical from outside."""

    box = _box(qapp)
    box.setEnabled(False)

    assert _pixels(_painted(box), RED) > 0


def test_a_box_at_rest_draws_no_ring_pixels(qapp) -> None:
    box = _box(qapp)

    canvas = _painted(box)

    assert _pixels(canvas, RED) == 0
    assert _pixels(canvas, GREEN) == 0


def test_the_stylesheet_is_what_hands_the_colours_down(qapp) -> None:
    """The palette stays the one home for both values."""

    del qapp
    from voice_reader.ui.main_window import MainWindow
    from voice_reader.ui.window_helpers import RING_GREEN, RING_RED

    window = MainWindow()
    box = RingedCheckBox("Horror", window)
    box.ensurePolished()

    assert box.property("ringColour") == RING_GREEN
    assert box.property("dangerColour") == RING_RED
