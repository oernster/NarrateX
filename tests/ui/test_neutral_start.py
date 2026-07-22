"""On launch nothing is focused, so no control paints the green ring.

Regression: Qt hands initial focus to the first focusable control, which is
the play/pause button, and the focus ring made it light up green before the
user touched anything. A 0x0 sink takes that first focus and then drops out
of the tab chain.
"""

from __future__ import annotations

from voice_reader.ui.main_window import MainWindow


def test_no_real_control_is_focused_on_launch(qapp) -> None:
    w = MainWindow()
    w.show()
    qapp.processEvents()

    focused = w.focusWidget()
    assert focused is not w.btn_play_pause
    assert focused is not w.btn_select_book
    assert focused is not w.btn_stop
    assert focused is w._neutral_start  # noqa: SLF001

    w.close()


def test_the_sink_leaves_the_tab_chain_after_first_focus(qapp) -> None:
    from PySide6.QtCore import Qt

    w = MainWindow()
    w.show()
    qapp.processEvents()

    # Focus moves on (as the first Tab would); the sink must drop out.
    w.btn_select_book.setFocus(Qt.FocusReason.TabFocusReason)
    qapp.processEvents()

    policy = w._neutral_start.focusPolicy()  # noqa: SLF001
    assert policy == Qt.FocusPolicy.NoFocus

    w.close()
