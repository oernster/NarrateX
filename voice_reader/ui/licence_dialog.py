"""Runtime licence dialogs.

The runtime UI needs to show two separate licence texts:

* UI licence: LGPL v3 (repo-root `LGPL3-LICENSE` file)
* Backend licence: repo-root `LICENSE` file

Both should render as plain text, wrap to the dialog width, and be vertically
scrollable.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QPlainTextEdit, QVBoxLayout


def _candidate_roots() -> list[Path]:
    roots: list[Path] = []

    # PyInstaller onefile extracts bundled data files to sys._MEIPASS.
    try:
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            roots.append(Path(meipass))
    except Exception:
        pass

    # Next to executable (frozen) or next to python executable (dev).
    try:
        roots.append(Path(sys.executable).resolve().parent)
    except Exception:
        pass

    # Repo layout fallback: voice_reader/ui/licence_dialog.py -> repo root is parents[2].
    try:
        roots.append(Path(__file__).resolve().parents[2])
    except Exception:
        pass

    # CWD as final fallback.
    try:
        roots.append(Path.cwd())
    except Exception:
        pass

    # De-dup while preserving order.
    seen: set[str] = set()
    out: list[Path] = []
    for r in roots:
        key = str(r)
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def read_licence_text(filename: str) -> str:
    """Read a licence text file from common dev/frozen locations."""

    tried: list[Path] = []
    for root in _candidate_roots():
        p = root / filename
        tried.append(p)
        try:
            if p.exists() and p.is_file():
                return p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

    raise FileNotFoundError(
        f"Unable to locate {filename}. Tried: " + ", ".join(str(p) for p in tried)
    )


class PlainTextLicenceDialog(QDialog):
    def __init__(
        self,
        *,
        title: str,
        text: str,
        initial_width: int = 760,
        initial_height: int = 560,
        parent=None,
    ) -> None:  # noqa: ANN001
        super().__init__(parent)

        self.setWindowTitle(title)
        self.setModal(True)
        self.setAttribute(Qt.WA_DeleteOnClose, True)

        # Wide enough for comfortable reading; scroll vertically for full text.
        self.resize(int(initial_width), int(initial_height))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        editor = QPlainTextEdit(self)
        editor.setObjectName("LicenceText")
        editor.setReadOnly(True)
        editor.setPlainText(text)
        editor.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        editor.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        layout.addWidget(editor, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Close, parent=self)
        buttons.rejected.connect(self.close)
        layout.addWidget(buttons)


