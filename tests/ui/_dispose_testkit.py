"""Deterministic disposal of the windows a UI test built."""

from __future__ import annotations


def dispose(*widgets) -> None:
    """Close and delete what a test built, before the shared window cleanup."""

    from PySide6.QtCore import QCoreApplication, QEvent

    for widget in widgets:
        widget.close()
        widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
