"""The one place an address leaves the application for the desktop's browser.

A seam for a testing reason: calling Qt's opener straight from a window leaves
no way to prove which address was asked for without mocking Qt or opening a
browser in the middle of a test run. Tests replace this function instead.
"""

from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices


def open_externally(address: str) -> bool:
    """Ask the desktop to open `address`; False when it declined to."""

    return bool(QDesktopServices.openUrl(QUrl(address)))
