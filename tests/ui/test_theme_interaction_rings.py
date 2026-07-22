"""The app-wide interaction rings: green on hover/focus, red when disabled.

QSS cannot be asserted visually here, so these tests pin the contract at the
stylesheet level: every hover and focus rule is gated on :enabled and the
disabled ring is the plain :disabled form (a hover-gated :disabled:hover rule
is unmatchable in Qt, so permanence is the only expressible form).
"""

from __future__ import annotations

from voice_reader.ui.main_window import MainWindow

GREEN = "#22c55e"
RED = "#dc2626"


def test_hover_and_focus_rings_are_green_and_gated_on_enabled(qapp) -> None:
    del qapp
    sheet = MainWindow().styleSheet()

    for selector in (
        "QPushButton:enabled:hover",
        "QPushButton:enabled:focus",
        "QComboBox:enabled:hover",
        "QComboBox:enabled:focus",
    ):
        assert selector in sheet, f"missing {selector}"
    assert GREEN in sheet

    # No ungated hover rules for buttons: a disabled control must never
    # light up under the mouse.
    assert "QPushButton:hover {" not in sheet
    assert "QComboBox:hover {" not in sheet


def test_disabled_controls_ring_red_permanently(qapp) -> None:
    del qapp
    sheet = MainWindow().styleSheet()

    for selector in (
        "QPushButton:disabled",
        "QComboBox:disabled",
        "QToolButton#playPauseButton:disabled",
        "QPushButton#stopButton:disabled",
    ):
        assert selector in sheet, f"missing {selector}"
    assert RED in sheet

    # The unmatchable hover-gated form must not sneak in.
    assert ":disabled:hover" not in sheet
