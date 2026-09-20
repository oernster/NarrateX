"""Shared UI helpers for MainWindow.

Extracted to keep [`MainWindow`](voice_reader/ui/main_window.py:40) compact.
"""

from __future__ import annotations

from PySide6.QtWidgets import QProxyStyle, QStyle, QStyleFactory

from voice_reader.ui._help_dialogs import build_about_dialog, open_licence_dialog

__all__ = [
    "apply_main_window_theme",
    "build_about_dialog",
    "open_licence_dialog",
]


# How long the pointer rests on a control before its tooltip opens. The
# platform default (700ms) reads as a lag on picture buttons, whose tooltip is
# the only place their purpose is written.
TOOLTIP_WAKE_UP_MS = 100


class _NoFocusRectStyle(QProxyStyle):
    """Drop the native focus rectangle everywhere; open tooltips promptly.

    The QSS green ring is the app's one focus indicator; some platform
    styles additionally draw an inner focus rectangle (white on the dark
    theme) on focused buttons and sliders. Suppressing the primitive at the
    style level constrains that out of existence for every control and
    every dialog, rather than chasing it per widget with outline rules.
    """

    def styleHint(  # noqa: N802 (Qt naming)
        self, hint, option=None, widget=None, return_data=None
    ) -> int:
        if hint == QStyle.StyleHint.SH_ToolTip_WakeUpDelay:
            return TOOLTIP_WAKE_UP_MS
        return super().styleHint(hint, option, widget, return_data)

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


# The interaction ring, in one place because more than the stylesheet draws it.
# A shelf tile is painted by a delegate rather than styled by a sheet; a second
# green written there would be a second theme able to drift from this one.
RING_GREEN = "#22c55e"
RING_RED = "#dc2626"
RING_ATTENTION = "#f59e0b"


def apply_main_window_theme(window) -> None:
    """Apply the app stylesheet to the given QMainWindow and the QApplication.

    Setting the stylesheet on QApplication ensures all dialogs (QMessageBox,
    QProgressDialog, etc.) inherit the dark theme rather than getting the
    platform's default white background.
    """
    from PySide6.QtWidgets import QApplication

    # Dark theme with teal accents (the chapter spine's rail teal).
    teal = "#14b8a6"
    blue = "#2563eb"
    bg = "#0b0f17"
    panel = "#121826"
    text = "#e5e7eb"
    # Text on the blue selection: the theme text measures 4.17:1 there, under
    # the WCAG AA 4.5:1 floor; white measures 5.17:1.
    selected_text = "#ffffff"

    # Interaction rings, applied uniformly to every control:
    # - hover or keyboard focus on an ENABLED control shows a green ring
    #   (terminal green, matching command text in the dev tooling)
    # - a DISABLED control shows a permanent red ring until re-enabled,
    #   with a muted fill so the red reads on it
    # Hover and focus rules are gated on :enabled because Qt's stylesheet
    # engine nests :hover under enabled anyway; the red ring must be the
    # plain :disabled form to be permanent rather than hover-gated.
    ring_green = RING_GREEN
    ring_red = RING_RED
    # The choose-a-voice prompt: an amber ring the picker flashes after a
    # book loads, held steady after first interaction, cleared on choice.
    ring_attention = RING_ATTENTION
    disabled_text = "#94a3b8"
    divider = "#374151"
    # One corner radius for every bordered button, text or picture.
    control_radius = "6px"
    window.setStyleSheet(f"""
            QMainWindow {{ background: {bg}; }}
            /* outline: none suppresses the native inner focus rectangle on
               every control (buttons, sliders, lists); the green QSS border
               is the one and only focus indicator. */
            QWidget {{ color: {text}; font-family: Segoe UI; outline: none; }}
            /* A text view is a pane: it rings in NO state, focus included,
               as in ClearBudget, AudioDeck and Fulcrum. */
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

            /* The Help menu: the dropdown list's dark panel and blue
               selection. With no rule of its own it took the style's white
               background under the light text set on every QWidget. */
            QMenu {{
                background: {panel};
                color: {text};
                border: 1px solid {divider};
                padding: 4px 0px;
            }}
            QMenu::item {{
                background: transparent;
                padding: 6px 20px;
            }}
            QMenu::item:selected {{
                background: {blue};
                color: {selected_text};
            }}
            QMenu::item:disabled {{ color: {disabled_text}; }}
            QMenu::separator {{
                height: 1px;
                background: {divider};
                margin: 4px 8px;
            }}

            QLabel#cover {{
                background: {panel};
                border: 1px solid #1f2937;
            }}
            QPushButton {{
                background: {panel};
                border: 2px solid #1f2937;
                padding: 6px 10px;
                border-radius: {control_radius};
            }}
            QPushButton:enabled:hover {{ border-color: {ring_green}; }}
            QPushButton:enabled:focus {{ border-color: {ring_green}; }}
            QPushButton:pressed {{ background: #111827; }}
            QPushButton:disabled {{
                border: 2px solid {ring_red};
                background: {panel};
                color: {disabled_text};
            }}

            /* Every picture button: a rounded square ring, transparent at
               rest. The ring sits inside the button's box on whole pixels,
               where a circle drawn to the box's edge lost its antialiased rim
               at the four points it touched the edge. */
            QToolButton[iconButton="true"] {{
                background: transparent;
                border: 2px solid transparent;
                border-radius: {control_radius};
                padding: 0px;
                color: {text};
            }}
            QToolButton[iconButton="true"]:enabled:hover {{
                border-color: {ring_green};
            }}
            QToolButton[iconButton="true"]:enabled:focus {{
                border-color: {ring_green};
            }}
            QToolButton[iconButton="true"]:pressed {{
                background: rgba(255, 255, 255, 0.08);
            }}
            QToolButton[iconButton="true"]:disabled {{
                border-color: {ring_red};
                color: {disabled_text};
            }}

            /* A tick box wears its ring round the SQUARE, not round the
               words: the square is what a checkbox is read as. It cannot be
               drawn from here, because naming ::indicator makes Qt take the
               whole subcontrol over and the tick goes with it, while a rule
               scoped to :focus alone changes nothing. So `ringed_check.py`
               paints it and reads its two colours from the properties below;
               the padding is what leaves room for it. */
            QCheckBox {{
                border: 2px solid transparent;
                border-radius: {control_radius};
                padding: 3px 6px;
                qproperty-ringColour: {ring_green};
                qproperty-dangerColour: {ring_red};
            }}
            QCheckBox:disabled {{ color: {disabled_text}; }}

            /* The foot strip's divider between donate and the licences. */
            QFrame#bottomTraySeparator {{
                border: none;
                background: {divider};
                max-width: 1px;
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
            QProgressBar::chunk {{ background: {teal}; }}

            /* Ideas progress bar removed (Sections-only brain button). */

            QMessageBox {{ background: {bg}; color: {text}; }}
            QMessageBox QLabel {{ color: {text}; }}
            QDialog {{ background: {bg}; color: {text}; }}
            QDialog QLabel {{ color: {text}; }}

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


# build_about_dialog and open_licence_dialog live in
# voice_reader/ui/_help_dialogs.py and are re-exported above.
