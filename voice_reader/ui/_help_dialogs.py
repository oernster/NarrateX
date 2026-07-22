"""The Help menu's dialogs: About and the licence viewer.

Extracted from [`window_helpers.py`](voice_reader/ui/window_helpers.py:1) to
keep that module inside the line cap.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QMessageBox, QWidget

from voice_reader.ui.licence_dialog import PlainTextLicenceDialog, read_licence_text
from voice_reader.version import APP_AUTHOR, APP_COPYRIGHT, APP_NAME, __version__

# Every load-bearing dependency the app ships, named with its licence. The
# long tail of transitive packages is not listed; these are the projects
# NarrateX is built on directly.
_CREDITS = (
    "PySide6 (Qt for Python) - LGPL-3.0",
    "Python - PSF licence",
    "Kokoro TTS - Apache-2.0",
    "misaki (grapheme-to-phoneme) - Apache-2.0",
    "eSpeak NG (via espeakng-loader) - GPL-3.0",
    "PyTorch - BSD-3-Clause",
    "Transformers and Hugging Face Hub - Apache-2.0",
    "spaCy and en_core_web_sm - MIT",
    "NumPy - BSD-3-Clause",
    "EbookLib - AGPL-3.0",
    "PyMuPDF - AGPL-3.0",
    "Beautiful Soup 4 - MIT",
    "lxml - BSD-3-Clause",
    "sounddevice (PortAudio backend) - MIT",
    "soundfile (bundles libsndfile, LGPL-2.1) - BSD-3-Clause",
    "platformdirs - MIT",
    "PyInstaller - GPL-2.0 with bootloader exception (packaging)",
    "pytest, pytest-cov, black, flake8, ruff - MIT (development)",
)


def build_about_dialog(*, parent: QWidget) -> QMessageBox:
    box = QMessageBox(parent)
    box.setWindowTitle(f"About {APP_NAME}")
    box.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
    box.setTextFormat(Qt.RichText)

    # Prefer the runtime-set window icon.
    try:
        icon = parent.windowIcon()
        if not icon.isNull():
            try:
                box.setIconPixmap(icon.pixmap(64, 64))
            except Exception:
                pass
    except Exception:
        pass

    credits = "<br>".join(_CREDITS)

    box.setText(
        """
            <div>
              <div style="font-size: 16px;">
                <b>{app}</b>
                <span style="font-size: 12px;">v{ver}</span>
              </div>
              <div style="margin-top: 6px;">{copyright}</div>
              <div style="margin-top: 10px;"><b>Author</b>: {author}</div>
              <div style="margin-top: 10px;"><b>Open source credits</b>:</div>
              <div style="margin-top: 4px; font-size: 12px;">{credits}</div>
              <div style="margin-top: 8px;">Built on the Python and Qt
              ecosystems, with thanks to their communities.</div>
            </div>
            """.format(
            app=APP_NAME,
            ver=__version__,
            author=APP_AUTHOR,
            copyright=APP_COPYRIGHT,
            credits=credits,
        )
    )

    box.setStandardButtons(QMessageBox.Ok)
    return box


def open_licence_dialog(
    *,
    owner: QWidget,
    attr_name: str,
    title: str,
    filename: str,
    initial_width: int = 760,
    initial_height: int = 560,
) -> None:
    existing = getattr(owner, attr_name, None)
    if isinstance(existing, QDialog):
        try:
            getattr(existing, "raise_", lambda: None)()
            getattr(existing, "activateWindow", lambda: None)()
            return
        except Exception:
            pass

    text = read_licence_text(filename)
    dlg = PlainTextLicenceDialog(
        parent=owner,
        title=title,
        text=text,
        initial_width=initial_width,
        initial_height=initial_height,
    )
    setattr(owner, attr_name, dlg)

    def _clear_ref() -> None:
        try:
            if getattr(owner, attr_name, None) is dlg:
                setattr(owner, attr_name, None)
        except Exception:
            pass

    try:
        dlg.finished.connect(_clear_ref)
    except Exception:
        pass

    # Non-blocking but modal.
    dlg.open()
