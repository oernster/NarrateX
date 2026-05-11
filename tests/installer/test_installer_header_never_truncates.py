from __future__ import annotations

import os
from types import SimpleNamespace

import pytest


@pytest.mark.skipif(os.name != "nt", reason="Installer UI is Windows-only")
def test_installer_header_title_fits_without_eliding(qapp, monkeypatch) -> None:
    """Regression test: ensure the in-window header never truncates 'Setup'.

    This targets the bug shown in [`crapinstaller.png`](crapinstaller.png:1)
    where DPI/text scaling caused the last character to be clipped.
    """

    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFontMetrics

    # Avoid touching the real registry in tests.
    import installer.ui.main_window as mw

    monkeypatch.setattr(mw, "read_uninstall_entry", lambda _key: None)

    win = mw.InstallerMainWindow(SimpleNamespace(uninstall=False))
    win.show()
    qapp.processEvents()

    title = getattr(win, "_header_title", None)
    assert title is not None, "Expected installer to keep a reference to the header title label"

    # Let any deferred resize/font-fitting run.
    qapp.processEvents()

    fm = QFontMetrics(title.font())
    available = max(0, title.contentsRect().width())
    elided = fm.elidedText(title.text(), Qt.ElideRight, available)
    assert (
        elided == title.text()
    ), f"Expected header title to fit without truncation; got {elided!r}"

