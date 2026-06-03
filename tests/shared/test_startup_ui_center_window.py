from __future__ import annotations

from voice_reader.shared import startup_ui


def test_center_window_on_screen_moves_window() -> None:
    _center_pt = object()

    class _AvailGeo:
        def center(self):  # noqa: N802
            return _center_pt

    class _FrameGeo:
        def __init__(self) -> None:
            self.centered_to = None
            self.top_left = object()

        def moveCenter(self, pt) -> None:  # noqa: N802
            self.centered_to = pt

        def topLeft(self):  # noqa: N802
            return self.top_left

    class _Screen:
        def availableGeometry(self):  # noqa: N802
            return _AvailGeo()

    _frame = _FrameGeo()

    class _Window:
        def __init__(self) -> None:
            self.moved_to = None

        def frameGeometry(self):  # noqa: N802
            return _frame

        def move(self, pt) -> None:
            self.moved_to = pt

    class _App:
        def primaryScreen(self):  # noqa: N802
            return _Screen()

    w = _Window()
    startup_ui.center_window_on_screen(_App(), w)
    assert _frame.centered_to is _center_pt
    assert w.moved_to is _frame.top_left


def test_center_window_on_screen_no_screen_is_noop() -> None:
    class _App:
        def primaryScreen(self):  # noqa: N802
            return None

    class _Window:
        def frameGeometry(self):  # noqa: N802
            raise AssertionError("should not be called")

    startup_ui.center_window_on_screen(_App(), _Window())


def test_center_window_on_screen_swallows_exception() -> None:
    class _App:
        def primaryScreen(self):  # noqa: N802
            raise RuntimeError("no screen")

    startup_ui.center_window_on_screen(_App(), object())
