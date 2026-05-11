from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent

from voice_reader.ui.seekable_text_edit import SeekableTextEdit


def _mouse_event(
    *,
    typ: QEvent.Type,
    pos: QPointF,
    button: Qt.MouseButton,
    buttons: Qt.MouseButtons,
    modifiers: Qt.KeyboardModifier = Qt.NoModifier,
) -> QMouseEvent:
    return QMouseEvent(
        typ,
        pos,
        pos,
        pos,
        button,
        buttons,
        modifiers,
    )


def test_seekable_text_edit_emits_seek_requested_on_click(qapp) -> None:
    del qapp

    w = SeekableTextEdit()
    w.setReadOnly(True)
    w.setPlainText("Hello\nWorld")
    w.show()

    got: list[int] = []
    w.seek_requested.connect(lambda off: got.append(int(off)))

    pos = QPointF(2, 2)
    w.mousePressEvent(
        _mouse_event(
            typ=QEvent.Type.MouseButtonPress,
            pos=pos,
            button=Qt.LeftButton,
            buttons=Qt.LeftButton,
        )
    )
    w.mouseReleaseEvent(
        _mouse_event(
            typ=QEvent.Type.MouseButtonRelease,
            pos=pos,
            button=Qt.LeftButton,
            buttons=Qt.NoButton,
        )
    )

    assert got
    assert got[-1] >= 0


def test_seekable_text_edit_does_not_seek_on_drag(qapp) -> None:
    del qapp

    w = SeekableTextEdit(click_drag_threshold_px=0)
    w.setReadOnly(True)
    w.setPlainText("Hello\nWorld")
    w.show()

    got: list[int] = []
    w.seek_requested.connect(lambda off: got.append(int(off)))

    w.mousePressEvent(
        _mouse_event(
            typ=QEvent.Type.MouseButtonPress,
            pos=QPointF(1, 1),
            button=Qt.LeftButton,
            buttons=Qt.LeftButton,
        )
    )
    # Any movement beyond 0 triggers dragging.
    w.mouseMoveEvent(
        _mouse_event(
            typ=QEvent.Type.MouseMove,
            pos=QPointF(10, 10),
            button=Qt.NoButton,
            buttons=Qt.LeftButton,
        )
    )
    w.mouseReleaseEvent(
        _mouse_event(
            typ=QEvent.Type.MouseButtonRelease,
            pos=QPointF(10, 10),
            button=Qt.LeftButton,
            buttons=Qt.NoButton,
        )
    )

    assert got == []


def test_seekable_text_edit_does_not_seek_with_modifiers(qapp) -> None:
    del qapp

    w = SeekableTextEdit()
    w.setReadOnly(True)
    w.setPlainText("Hello")
    w.show()

    got: list[int] = []
    w.seek_requested.connect(lambda off: got.append(int(off)))

    pos = QPointF(2, 2)
    w.mousePressEvent(
        _mouse_event(
            typ=QEvent.Type.MouseButtonPress,
            pos=pos,
            button=Qt.LeftButton,
            buttons=Qt.LeftButton,
            modifiers=Qt.ControlModifier,
        )
    )
    w.mouseReleaseEvent(
        _mouse_event(
            typ=QEvent.Type.MouseButtonRelease,
            pos=pos,
            button=Qt.LeftButton,
            buttons=Qt.NoButton,
            modifiers=Qt.ControlModifier,
        )
    )

    assert got == []


def test_mouse_pos_fallbacks_are_covered() -> None:
    # Cover the `pos()` fallback.
    @dataclass
    class _EvtPos:
        def pos(self):
            return QPoint(3, 4)

    assert SeekableTextEdit._mouse_pos(_EvtPos()) == QPoint(3, 4)

    # Cover the final default.
    class _EvtNone:
        pass

    assert SeekableTextEdit._mouse_pos(_EvtNone()) == QPoint(0, 0)


def test_seekable_text_edit_ignores_non_left_release_and_none_event(qapp) -> None:
    del qapp

    w = SeekableTextEdit()
    w.setReadOnly(True)
    w.setPlainText("Hello")
    w.show()

    got: list[int] = []
    w.seek_requested.connect(lambda off: got.append(int(off)))

    # Press left, release right: should not emit.
    pos = QPointF(2, 2)
    w.mousePressEvent(
        _mouse_event(
            typ=QEvent.Type.MouseButtonPress,
            pos=pos,
            button=Qt.LeftButton,
            buttons=Qt.LeftButton,
        )
    )
    w.mouseReleaseEvent(
        _mouse_event(
            typ=QEvent.Type.MouseButtonRelease,
            pos=pos,
            button=Qt.RightButton,
            buttons=Qt.NoButton,
        )
    )
    assert got == []

    # None event should also be ignored and not crash.
    w.mouseReleaseEvent(None)
    assert got == []

