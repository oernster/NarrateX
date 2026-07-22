"""Shared UI helpers for MainWindow.

Extracted to keep [`MainWindow`](voice_reader/ui/main_window.py:40) compact.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QMessageBox,
    QProxyStyle,
    QStyle,
    QStyleFactory,
    QWidget,
)

from voice_reader.ui.licence_dialog import PlainTextLicenceDialog, read_licence_text
from voice_reader.version import APP_AUTHOR, APP_COPYRIGHT, APP_NAME, __version__


class _NoFocusRectStyle(QProxyStyle):
    """Drop the platform style's native focus rectangle everywhere.

    The QSS green ring is the app's one focus indicator; some platform
    styles additionally draw an inner focus rectangle (white on the dark
    theme) on focused buttons and sliders. Suppressing the primitive at the
    style level constrains that out of existence for every control and
    every dialog, rather than chasing it per widget with outline rules.
    """

    def drawPrimitive(self, element, option, painter, widget=None) -> None:
        if element == QStyle.PrimitiveElement.PE_FrameFocusRect:
            return
        super().drawPrimitive(element, option, painter, widget)


def _install_no_focus_rect_style(app) -> None:
    """Wrap the application style once; further calls are no-ops."""

    if getattr(app, "_no_focus_rect_style", None) is not None:
        return
    base = QStyleFactory.create(app.style().objectName())
    style = _NoFocusRectStyle(base) if base is not None else _NoFocusRectStyle()
    app.setStyle(style)
    app._no_focus_rect_style = style  # noqa: SLF001 (idempotence anchor)


def apply_main_window_theme(window) -> None:
    """Apply the app stylesheet to the given QMainWindow and the QApplication.

    Setting the stylesheet on QApplication ensures all dialogs (QMessageBox,
    QProgressDialog, etc.) inherit the dark theme rather than getting the
    platform's default white background.
    """
    from PySide6.QtWidgets import QApplication

    # Dark theme with purple accents.
    purple = "#8b5cf6"
    blue = "#2563eb"
    bg = "#0b0f17"
    panel = "#121826"
    text = "#e5e7eb"

    # Interaction rings, applied uniformly to every control:
    # - hover or keyboard focus on an ENABLED control shows a green ring
    #   (terminal green, matching command text in the dev tooling)
    # - a DISABLED control shows a permanent red ring until re-enabled,
    #   with a muted fill so the red reads on it
    # Hover and focus rules are gated on :enabled because Qt's stylesheet
    # engine nests :hover under enabled anyway; the red ring must be the
    # plain :disabled form to be permanent rather than hover-gated.
    ring_green = "#22c55e"
    ring_red = "#dc2626"
    # The choose-a-voice prompt: an amber ring the picker flashes after a
    # book loads, held steady after first interaction, cleared on choice.
    ring_attention = "#f59e0b"
    disabled_text = "#94a3b8"
    window.setStyleSheet(f"""
            QMainWindow {{ background: {bg}; }}
            /* outline: none suppresses the native inner focus rectangle on
               every control (buttons, sliders, lists); the green QSS border
               is the one and only focus indicator. */
            QWidget {{ color: {text}; font-family: Segoe UI; outline: none; }}
            QTextEdit, QPlainTextEdit {{
                background: {panel};
                border: 1px solid #1f2937;
            }}
            QComboBox {{
                background: {panel};
                border: 2px solid #1f2937;
                padding: 4px 8px;
            }}
            /* Attention sits before hover and focus, so live interaction
               feedback still wins while the prompt is showing. */
            QComboBox[attention="true"] {{ border-color: {ring_attention}; }}
            QComboBox:enabled:hover {{ border-color: {ring_green}; }}
            QComboBox:enabled:focus {{ border-color: {ring_green}; }}
            QComboBox:disabled {{
                border: 2px solid {ring_red};
                background: {panel};
                color: {disabled_text};
            }}
            QComboBox QAbstractItemView {{
                background: {panel};
                color: {text};
                selection-background-color: {blue};
                selection-color: {text};
                border: 1px solid #374151;
                outline: 0;
            }}

            QLabel#cover {{
                background: {panel};
                border: 1px solid #1f2937;
            }}
            QPushButton {{
                background: {panel};
                border: 2px solid #1f2937;
                padding: 6px 10px;
                border-radius: 6px;
            }}
            QPushButton:enabled:hover {{ border-color: {ring_green}; }}
            QPushButton:enabled:focus {{ border-color: {ring_green}; }}
            QPushButton:pressed {{ background: #111827; }}
            QPushButton:disabled {{
                border: 2px solid {ring_red};
                background: {panel};
                color: {disabled_text};
            }}

            QToolButton[topIconButton="true"] {{
                background: transparent;
                border: 2px solid transparent;
                border-radius: 17px;
                padding: 0px;
                color: {text};
            }}
            QToolButton[topIconButton="true"]:enabled:hover {{
                border-color: {ring_green};
            }}
            QToolButton[topIconButton="true"]:enabled:focus {{
                border-color: {ring_green};
            }}
            QToolButton[topIconButton="true"]:pressed {{
                background: rgba(255, 255, 255, 0.08);
            }}
            QToolButton[topIconButton="true"]:disabled {{
                border-color: {ring_red};
                color: {disabled_text};
            }}
            QToolButton#helpButton {{
                color: #3b82f6;
            }}

            /* Primary transport control: single circular play/pause toggle. */
            QToolButton#playPauseButton {{
                background: #0b1220;
                border: 3px solid rgba(59, 130, 246, 0.62);
                border-radius: 26px;
                padding: 0px;
                color: {text};
            }}
            QToolButton#playPauseButton:enabled:hover {{
                border-color: {ring_green};
                background: #0d172a;
            }}
            QToolButton#playPauseButton:enabled:focus {{
                border-color: {ring_green};
            }}
            QToolButton#playPauseButton:pressed {{
                background: #0a1020;
            }}
            QToolButton#playPauseButton:checked {{
                /* Slightly stronger ring when actively playing. */
                border-color: {blue};
            }}
            QToolButton#playPauseButton:disabled {{
                border-color: {ring_red};
                color: {disabled_text};
            }}

            /* Secondary transport: Stop should read clearly, but stay subordinate. */
            QPushButton#stopButton {{
                background: {panel};
                border: 2px solid #334155;
                padding: 7px 12px;
                border-radius: 6px;
            }}
            QPushButton#stopButton:enabled:hover {{
                border-color: {ring_green};
            }}
            QPushButton#stopButton:enabled:focus {{
                border-color: {ring_green};
            }}
            QPushButton#stopButton:pressed {{
                background: #111827;
            }}
            QPushButton#stopButton:disabled {{
                border: 2px solid {ring_red};
                color: {disabled_text};
            }}

            /* Volume slider, themed: dark groove, blue fill, blue handle.
               It is not a focus stop (the speaker button is), so it never
               paints a ring of its own. */
            QSlider::groove:horizontal {{
                background: #1f2937;
                height: 6px;
                border-radius: 3px;
            }}
            QSlider::sub-page:horizontal {{
                background: {blue};
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background: #93c5fd;
                width: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }}
            QSlider::handle:horizontal:hover {{
                background: {ring_green};
            }}

            /* Search removed (was tied to Ideas mapping). */

            QProgressBar {{
                background: {panel};
                border: 1px solid #1f2937;
                height: 18px;
            }}
            QProgressBar::chunk {{ background: {purple}; }}

            /* Ideas progress bar removed (Sections-only brain button). */

            QMessageBox {{ background: {bg}; color: {text}; }}
            QMessageBox QLabel {{ color: {text}; }}
            QDialog {{ background: {bg}; color: {text}; }}
            QDialog QLabel {{ color: {text}; }}
            QDialog QPlainTextEdit {{
                background: {panel};
                color: {text};
                border: 1px solid #1f2937;
            }}

            QScrollBar:vertical {{
                background: {panel};
                width: 10px;
                border-radius: 5px;
                margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background: #475569;
                min-height: 24px;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: #64748b;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: none;
            }}

            QScrollBar:horizontal {{
                background: {panel};
                height: 10px;
                border-radius: 5px;
                margin: 0;
            }}
            QScrollBar::handle:horizontal {{
                background: #475569;
                min-width: 24px;
                border-radius: 5px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background: #64748b;
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0;
            }}
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
                background: none;
            }}
            """)

    try:
        app = QApplication.instance()
        if app is not None:
            _install_no_focus_rect_style(app)
            app.setStyleSheet(window.styleSheet())
    except Exception:
        pass


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
