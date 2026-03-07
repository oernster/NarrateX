from __future__ import annotations

from pathlib import Path

import pytest


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def qapp():
    """Create a QApplication for lightweight UI tests."""

    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])
