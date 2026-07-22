"""Light and dark themes (QSS) for the installer UI.

Teal is the accent (the app's chapter-spine teal, #14b8a6): headings, the
progress fill and the border around every standard button. Interaction
states follow platform convention rather than the app's ring language: a
hovered or focused button brightens its teal border, a disabled control
goes muted grey. Every button is rounded, with each radius kept at or
below half the rendered height because Qt silently drops a larger radius
and paints square corners.
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
        QLabel#HeaderTitle { font-size: 38px; font-weight: 700; color: #0f766e; }
        QLabel#HeaderVersion { font-size: 14px; color: #6b7280; }
        QLabel#SubTitle { font-size: 22px; font-weight: 700; color: #0f766e; }
        QLabel#StatusLine { font-size: 13px; color: #6b7280; }

        QCheckBox { spacing: 10px; font-size: 13px; }
        QCheckBox::indicator { width: 16px; height: 16px; }

        QPushButton#ThemeToggle, QPushButton#LicenceButton {
            background: #ffffff; color: #1f2937;
            border: 2px solid #0f766e;
            padding: 6px 18px; border-radius: 18px; font-weight: 600;
            min-height: 42px; max-height: 42px;
        }
        QPushButton#ThemeToggle:enabled:hover,
        QPushButton#ThemeToggle:enabled:focus,
        QPushButton#LicenceButton:enabled:hover,
        QPushButton#LicenceButton:enabled:focus {
            border-color: #14b8a6; background: #f0fdfa;
        }
        QPushButton#ThemeToggle:disabled,
        QPushButton#LicenceButton:disabled {
            border-color: #d1d5db; color: #9ca3af; background: #f3f4f6;
        }

        QPushButton#PrimaryAction {
            background: #ffffff; color: #1f2937;
            border: 2px solid #0f766e;
            padding: 6px 26px; border-radius: 26px; font-size: 14px;
            min-height: 52px; max-height: 52px;
            font-weight: 700; min-width: 150px;
        }
        QPushButton#PrimaryAction:enabled:hover,
        QPushButton#PrimaryAction:enabled:focus {
            border-color: #14b8a6; background: #f0fdfa;
        }
        QPushButton#PrimaryAction:disabled {
            border-color: #d1d5db; color: #9ca3af; background: #f3f4f6;
        }

        QPushButton#DangerAction {
            background: #b91c1c; color: white;
            border: 2px solid transparent;
            padding: 6px 26px; border-radius: 23px; font-size: 13px;
            min-height: 46px; max-height: 46px;
            font-weight: 700; min-width: 190px;
        }
        QPushButton#DangerAction:enabled:hover,
        QPushButton#DangerAction:enabled:focus {
            background: #dc2626;
        }
        QPushButton#DangerAction:disabled {
            background: #f3f4f6; border-color: #d1d5db; color: #9ca3af;
        }

        QLineEdit {
            background: white;
            border: 1px solid #d1d5db;
            border-radius: 10px;
            padding: 8px;
        }
        QLineEdit:enabled:focus { border-color: #14b8a6; }

        QPushButton#BrowseButton {
            background: #ffffff;
            border: 2px solid #0f766e;
            border-radius: 17px;
            padding: 4px 12px;
            min-height: 34px; max-height: 34px;
        }
        QPushButton#BrowseButton:enabled:hover,
        QPushButton#BrowseButton:enabled:focus {
            border-color: #14b8a6; background: #f0fdfa;
        }
        QPushButton#BrowseButton:disabled {
            border-color: #d1d5db; color: #9ca3af; background: #f3f4f6;
        }

        QProgressBar#ProgressBar {
            background: white;
            border: 1px solid #d1d5db;
            border-radius: 10px;
            height: 16px;
            text-align: center;
        }
        QProgressBar#ProgressBar::chunk {
            background: #14b8a6;
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
        QLabel#HeaderTitle { font-size: 38px; font-weight: 700; color: #14b8a6; }
        QLabel#HeaderVersion { font-size: 14px; color: #94a3b8; }
        QLabel#SubTitle { font-size: 22px; font-weight: 700; color: #14b8a6; }
        QLabel#StatusLine { font-size: 13px; color: #cbd5e1; }

        QCheckBox { spacing: 10px; font-size: 13px; }
        QCheckBox::indicator { width: 16px; height: 16px; }

        QPushButton#ThemeToggle, QPushButton#LicenceButton {
            background: #121826; color: #e5e7eb;
            border: 2px solid #14b8a6;
            padding: 6px 18px; border-radius: 18px; font-weight: 600;
            min-height: 42px; max-height: 42px;
        }
        QPushButton#ThemeToggle:enabled:hover,
        QPushButton#ThemeToggle:enabled:focus,
        QPushButton#LicenceButton:enabled:hover,
        QPushButton#LicenceButton:enabled:focus {
            border-color: #2dd4bf; background: #16202f;
        }
        QPushButton#ThemeToggle:disabled,
        QPushButton#LicenceButton:disabled {
            border-color: #374151; color: #64748b; background: #0f1420;
        }

        QPushButton#PrimaryAction {
            background: #121826; color: #e5e7eb;
            border: 2px solid #14b8a6;
            padding: 6px 26px; border-radius: 26px; font-size: 14px;
            min-height: 52px; max-height: 52px;
            font-weight: 700; min-width: 150px;
        }
        QPushButton#PrimaryAction:enabled:hover,
        QPushButton#PrimaryAction:enabled:focus {
            border-color: #2dd4bf; background: #16202f;
        }
        QPushButton#PrimaryAction:disabled {
            border-color: #374151; color: #64748b; background: #0f1420;
        }

        QPushButton#DangerAction {
            background: #7a1f25; color: #e5e7eb;
            border: 2px solid transparent;
            padding: 6px 26px; border-radius: 23px; font-size: 13px;
            min-height: 46px; max-height: 46px;
            font-weight: 700; min-width: 190px;
        }
        QPushButton#DangerAction:enabled:hover,
        QPushButton#DangerAction:enabled:focus {
            background: #96262e;
        }
        QPushButton#DangerAction:disabled {
            background: #0f1420; border-color: #374151; color: #64748b;
        }

        QLineEdit {
            background: #121826;
            border: 1px solid #1f2937;
            border-radius: 10px;
            padding: 8px;
        }
        QLineEdit:enabled:focus { border-color: #14b8a6; }

        QPushButton#BrowseButton {
            background: #121826;
            border: 2px solid #14b8a6;
            border-radius: 17px;
            padding: 4px 12px;
            min-height: 34px; max-height: 34px;
            color: #e5e7eb;
        }
        QPushButton#BrowseButton:enabled:hover,
        QPushButton#BrowseButton:enabled:focus {
            border-color: #2dd4bf; background: #16202f;
        }
        QPushButton#BrowseButton:disabled {
            border-color: #374151; color: #64748b; background: #0f1420;
        }

        QProgressBar#ProgressBar {
            background: #121826;
            border: 1px solid #1f2937;
            border-radius: 10px;
            height: 16px;
            text-align: center;
        }
        QProgressBar#ProgressBar::chunk {
            background: #14b8a6;
            border-radius: 8px;
        }
    """,
)
