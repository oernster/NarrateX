"""Shared UI helpers for MainWindow.

Extracted to keep [`MainWindow`](voice_reader/ui/main_window.py:40) compact.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QMessageBox, QWidget

from voice_reader.ui.licence_dialog import PlainTextLicenceDialog, read_licence_text
from voice_reader.version import APP_AUTHOR, APP_COPYRIGHT, APP_NAME, __version__


def apply_main_window_theme(window) -> None:
    """Apply the app stylesheet to the given QMainWindow."""

    # Dark theme with purple accents.
    purple = "#8b5cf6"
    bg = "#0b0f17"
    panel = "#121826"
    text = "#e5e7eb"

    # Locked dropdown accent: amber (readable on dark UI, clearly different
    # from normal focus/hover purple).
    locked_bg = "#172033"
    locked_border = "#f59e0b"
    window.setStyleSheet(f"""
            QMainWindow {{ background: {bg}; }}
            QWidget {{ color: {text}; font-family: Segoe UI; }}
            QTextEdit, QPlainTextEdit {{
                background: {panel};
                border: 1px solid #1f2937;
            }}
            QComboBox {{
                background: {panel};
                border: 1px solid #1f2937;
                padding: 4px 8px;
            }}

            /* Clearly indicate "locked while playing" dropdowns. */
            QComboBox[locked="true"] {{
                background: {locked_bg};
                border: 1px solid {locked_border};
                color: {text};
            }}
            QComboBox[locked="true"]::drop-down {{
                border-left: 1px solid {locked_border};
            }}
            QComboBox[locked="true"]:disabled {{
                /* Keep text readable even when disabled. */
                color: #cbd5e1;
            }}

            QLabel#cover {{
                background: {panel};
                border: 1px solid #1f2937;
            }}
            QPushButton {{
                background: {panel};
                border: 1px solid #1f2937;
                padding: 6px 10px;
                border-radius: 6px;
            }}
            QPushButton:hover {{ border-color: {purple}; }}
            QPushButton:pressed {{ background: #111827; }}

            QToolButton[topIconButton="true"] {{
                background: transparent;
                border: 2px solid transparent;
                border-radius: 17px;
                padding: 0px;
                color: {text};
            }}
            QToolButton[topIconButton="true"]:hover {{
                border-color: #ffffff;
            }}
            QToolButton[topIconButton="true"]:pressed {{
                background: rgba(255, 255, 255, 0.08);
            }}
            QToolButton#helpButton {{
                color: #3b82f6;
            }}

            QProgressBar {{
                background: {panel};
                border: 1px solid #1f2937;
                height: 18px;
            }}
            QProgressBar::chunk {{ background: {purple}; }}
            """)


def build_about_dialog(*, parent: QWidget) -> QMessageBox:
    box = QMessageBox(parent)
    box.setWindowTitle(f"About {APP_NAME}")
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

    thanks = "<br>".join(
        [
            "PySide6 (Qt for Python) developers",
            "The Python development team",
            "Kokoro TTS library",
            "EbookLib",
            "PyMuPDF",
            "sounddevice",
        ]
    )

    box.setText(
        """
            <div>
              <div style="font-size: 16px;">
                <b>{app}</b>
                <span style="font-size: 12px;">v{ver}</span>
              </div>
              <div style="margin-top: 6px;">{copyright}</div>
              <div style="margin-top: 10px;"><b>Author</b>: {author}</div>
              <div style="margin-top: 10px;"><b>Thanks</b>:</div>
              <div style="margin-top: 4px;">{thanks}</div>
            </div>
            """.format(
            app=APP_NAME,
            ver=__version__,
            author=APP_AUTHOR,
            copyright=APP_COPYRIGHT,
            thanks=thanks,
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
