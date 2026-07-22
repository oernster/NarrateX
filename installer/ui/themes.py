"""Light and dark themes (QSS) for the installer UI.

The dark theme is the app's own palette (the window background, panel,
purple accent, blue primary and the interaction-ring scheme from
`voice_reader/ui/window_helpers.py`): a green ring on hover or focus of an
enabled control, a permanent red ring on a disabled one. The light theme
is the same scheme translated onto light surfaces.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Theme:
    name: str
    toggle_label: str
    qss: str


LIGHT = Theme(
    name="light",
    toggle_label="Dark Theme",
    qss="""
        QWidget {
            background: #f4f4f6; color: #1f2937;
            font-family: 'Segoe UI'; outline: none;
        }
        QLabel#HeaderTitle { font-size: 38px; font-weight: 700; color: #7c3aed; }
        QLabel#HeaderVersion { font-size: 14px; color: #6b7280; }
        QLabel#SubTitle { font-size: 22px; font-weight: 700; color: #7c3aed; }
        QLabel#StatusLine { font-size: 13px; color: #6b7280; }

        QCheckBox { spacing: 10px; font-size: 13px; }
        QCheckBox::indicator { width: 16px; height: 16px; }

        QPushButton#ThemeToggle, QPushButton#LicenceButton {
            background: #ffffff; color: #1f2937;
            border: 2px solid #d1d5db;
            padding: 10px 18px; border-radius: 18px; font-weight: 600;
        }
        QPushButton#ThemeToggle:enabled:hover,
        QPushButton#ThemeToggle:enabled:focus,
        QPushButton#LicenceButton:enabled:hover,
        QPushButton#LicenceButton:enabled:focus {
            border-color: #16a34a;
        }
        QPushButton#ThemeToggle:disabled,
        QPushButton#LicenceButton:disabled {
            border-color: #dc2626; color: #9ca3af;
        }

        QPushButton#PrimaryAction {
            background: #ffffff; color: #1f2937;
            border: 2px solid #2563eb;
            padding: 14px 26px; border-radius: 26px; font-size: 14px;
            font-weight: 700; min-width: 150px;
        }
        QPushButton#PrimaryAction:enabled:hover,
        QPushButton#PrimaryAction:enabled:focus {
            border-color: #16a34a;
        }
        QPushButton#PrimaryAction:disabled {
            border-color: #dc2626; color: #9ca3af;
        }

        QPushButton#DangerAction {
            background: #b91c1c; color: white;
            border: 2px solid transparent;
            padding: 12px 26px; border-radius: 22px; font-size: 13px;
            font-weight: 700; min-width: 190px;
        }
        QPushButton#DangerAction:enabled:hover,
        QPushButton#DangerAction:enabled:focus {
            border-color: #16a34a;
        }
        QPushButton#DangerAction:disabled {
            background: #ffffff; border-color: #dc2626; color: #9ca3af;
        }

        QLineEdit {
            background: white;
            border: 1px solid #d1d5db;
            border-radius: 10px;
            padding: 8px;
        }
        QLineEdit:enabled:focus { border-color: #16a34a; }

        QPushButton#BrowseButton {
            background: #ffffff;
            border: 2px solid #d1d5db;
            border-radius: 10px;
            padding: 8px 12px;
        }
        QPushButton#BrowseButton:enabled:hover,
        QPushButton#BrowseButton:enabled:focus {
            border-color: #16a34a;
        }
        QPushButton#BrowseButton:disabled {
            border-color: #dc2626; color: #9ca3af;
        }

        QProgressBar#ProgressBar {
            background: white;
            border: 1px solid #d1d5db;
            border-radius: 10px;
            height: 16px;
            text-align: center;
        }
        QProgressBar#ProgressBar::chunk {
            background: #8b5cf6;
            border-radius: 8px;
        }
    """,
)


DARK = Theme(
    name="dark",
    toggle_label="Light Theme",
    qss="""
        QWidget {
            background: #0b0f17; color: #e5e7eb;
            font-family: 'Segoe UI'; outline: none;
        }
        QLabel#HeaderTitle { font-size: 38px; font-weight: 700; color: #8b5cf6; }
        QLabel#HeaderVersion { font-size: 14px; color: #94a3b8; }
        QLabel#SubTitle { font-size: 22px; font-weight: 700; color: #8b5cf6; }
        QLabel#StatusLine { font-size: 13px; color: #cbd5e1; }

        QCheckBox { spacing: 10px; font-size: 13px; }
        QCheckBox::indicator { width: 16px; height: 16px; }

        QPushButton#ThemeToggle, QPushButton#LicenceButton {
            background: #121826; color: #e5e7eb;
            border: 2px solid #1f2937;
            padding: 10px 18px; border-radius: 18px; font-weight: 600;
        }
        QPushButton#ThemeToggle:enabled:hover,
        QPushButton#ThemeToggle:enabled:focus,
        QPushButton#LicenceButton:enabled:hover,
        QPushButton#LicenceButton:enabled:focus {
            border-color: #22c55e;
        }
        QPushButton#ThemeToggle:disabled,
        QPushButton#LicenceButton:disabled {
            border-color: #dc2626; color: #94a3b8;
        }

        QPushButton#PrimaryAction {
            background: #121826; color: #e5e7eb;
            border: 2px solid rgba(59, 130, 246, 0.62);
            padding: 14px 26px; border-radius: 26px; font-size: 14px;
            font-weight: 700; min-width: 150px;
        }
        QPushButton#PrimaryAction:enabled:hover,
        QPushButton#PrimaryAction:enabled:focus {
            border-color: #22c55e;
        }
        QPushButton#PrimaryAction:disabled {
            border-color: #dc2626; color: #94a3b8;
        }

        QPushButton#DangerAction {
            background: #7a1f25; color: #e5e7eb;
            border: 2px solid transparent;
            padding: 12px 26px; border-radius: 22px; font-size: 13px;
            font-weight: 700; min-width: 190px;
        }
        QPushButton#DangerAction:enabled:hover,
        QPushButton#DangerAction:enabled:focus {
            border-color: #22c55e;
        }
        QPushButton#DangerAction:disabled {
            background: #121826; border-color: #dc2626; color: #94a3b8;
        }

        QLineEdit {
            background: #121826;
            border: 1px solid #1f2937;
            border-radius: 10px;
            padding: 8px;
        }
        QLineEdit:enabled:focus { border-color: #22c55e; }

        QPushButton#BrowseButton {
            background: #121826;
            border: 2px solid #1f2937;
            border-radius: 10px;
            padding: 8px 12px;
            color: #e5e7eb;
        }
        QPushButton#BrowseButton:enabled:hover,
        QPushButton#BrowseButton:enabled:focus {
            border-color: #22c55e;
        }
        QPushButton#BrowseButton:disabled {
            border-color: #dc2626; color: #94a3b8;
        }

        QProgressBar#ProgressBar {
            background: #121826;
            border: 1px solid #1f2937;
            border-radius: 10px;
            height: 16px;
            text-align: center;
        }
        QProgressBar#ProgressBar::chunk {
            background: #8b5cf6;
            border-radius: 8px;
        }
    """,
)
