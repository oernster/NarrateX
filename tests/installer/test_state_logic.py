from __future__ import annotations

from pathlib import Path

import pytest

from installer.state.model import InstalledInfo, InstallerState, Operation


def test_not_installed_shows_install_only() -> None:
    st = InstallerState(installer_version="1.0.0", installed=None)
    assert st.allowed_operations() == frozenset({Operation.INSTALL})


def test_same_version() -> None:
    st = InstallerState(
        installer_version="1.0.0",
        installed=InstalledInfo(version="1.0.0", location=Path("C:/X")),
    )
    assert st.allowed_operations() == frozenset(
        {Operation.REINSTALL, Operation.REPAIR, Operation.UNINSTALL}
    )


def test_installed_older_and_installer_newer() -> None:
    st = InstallerState(
        installer_version="1.0.1",
        installed=InstalledInfo(version="1.0.0", location=Path("C:/X")),
    )
    assert st.allowed_operations() == frozenset(
        {Operation.UPGRADE, Operation.UNINSTALL}
    )


def test_installed_newer_no_downgrade() -> None:
    st = InstallerState(
        installer_version="1.0.0",
        installed=InstalledInfo(version="2.0.0", location=Path("C:/X")),
    )
    assert st.allowed_operations() == frozenset({Operation.REPAIR, Operation.UNINSTALL})
