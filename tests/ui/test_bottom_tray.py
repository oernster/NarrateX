"""The foot strip: donate first, a separator, then the UI and Backend licences.

No test opens a browser: the one seam, `open_externally`, is replaced.
"""

from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QFrame

from voice_reader.ui import links, main_window
from voice_reader.ui.bottom_tray import BottomTray
from voice_reader.ui.main_window import DONATE_OPEN_FAILED, MainWindow
from voice_reader.version import DONATE_URL


def test_donate_comes_first_then_a_separator_then_the_licences(qapp) -> None:
    del qapp
    tray = BottomTray()
    layout = tray.layout()
    order = [layout.itemAt(i).widget() for i in range(layout.count())]
    assert order[:4] == [
        tray.donate_button,
        tray.separator,
        tray.ui_licence_button,
        tray.backend_licence_button,
    ]
    assert tray.separator.frameShape() == QFrame.Shape.VLine
    assert tray.ring_stops() == (
        tray.donate_button,
        tray.ui_licence_button,
        tray.backend_licence_button,
    )
    assert tray.donate_button.isEnabled()
    assert "opens your browser" in tray.donate_button.toolTip()
    assert not tray.donate_button.icon().isNull()


def test_the_donate_button_calls_its_handler(qapp) -> None:
    del qapp
    calls: list[str] = []
    tray = BottomTray(open_donation=lambda: calls.append("donate"))
    tray.donate_button.click()
    assert calls == ["donate"]
    # The default handler does nothing and does not fail.
    quiet = BottomTray()
    quiet.donate_button.click()


def test_the_donation_address_is_this_apps_own() -> None:
    assert DONATE_URL == "https://www.paypal.com/ncp/payment/26YQ4HUNDHYXY"
    assert DONATE_URL.startswith("https://")


def test_pressing_donate_asks_the_desktop_for_that_one_address(
    qapp, monkeypatch
) -> None:
    del qapp
    asked: list[str] = []
    monkeypatch.setattr(
        main_window, "open_externally", lambda address: asked.append(address) or True
    )
    w = MainWindow()
    w.lbl_status.setText("Idle")
    w.bottom_tray.donate_button.click()
    assert asked == [DONATE_URL]
    assert w.lbl_status.text() == "Idle"


def test_a_desktop_that_refuses_is_reported(qapp, monkeypatch) -> None:
    del qapp
    monkeypatch.setattr(main_window, "open_externally", lambda address: False)
    w = MainWindow()
    w.bottom_tray.donate_button.click()
    assert w.lbl_status.text() == DONATE_OPEN_FAILED


def test_open_externally_hands_the_address_to_qt(monkeypatch) -> None:
    opened: list[QUrl] = []

    class _Desktop:
        @staticmethod
        def openUrl(url: QUrl) -> bool:  # noqa: N802 (Qt naming)
            opened.append(url)
            return True

    monkeypatch.setattr(links, "QDesktopServices", _Desktop)
    assert links.open_externally(DONATE_URL) is True
    assert [u.toString() for u in opened] == [DONATE_URL]
