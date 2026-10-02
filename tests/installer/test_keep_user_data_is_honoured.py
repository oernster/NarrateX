"""The setup program's user-data choice must reach the uninstall it performs.

`--keep-user-data` is offered on the command line ("When uninstalling, keep user
data"), yet the window's uninstall used to delete the whole data root, which
holds the bookmarks and the shelf index, whatever was asked for.

The tests run the real entrypoint and the real window under the offscreen
platform. Only process-wide pieces are stubbed: the QApplication object (the
session already has one), the log location (a tmp dir), the taskbar identity
and the registry read. Nothing is uninstalled and no real folder is touched.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Installer is Windows-only")


class _FakeApp:
    def setApplicationName(self, _name: str) -> None:
        return

    def setApplicationVersion(self, _version: str) -> None:
        return

    def setWindowIcon(self, _icon) -> None:  # noqa: ANN001
        return

    def exec(self) -> int:
        return 0


def _window_built_by_main(monkeypatch, tmp_path: Path, argv: list[str]):
    import installer.app as installer_app
    import installer.ui.main_window as mw

    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    monkeypatch.setattr(
        installer_app, "setup_installer_logging", lambda: tmp_path / "setup.log"
    )
    monkeypatch.setattr(
        installer_app, "set_windows_app_user_model_id", lambda _app_id: None
    )
    monkeypatch.setattr(installer_app.inactive_tooltips, "install", lambda _app: None)
    monkeypatch.setattr(installer_app, "QApplication", lambda _argv: _FakeApp())
    monkeypatch.setattr(mw, "read_uninstall_entry", lambda _key: None)

    built: list[object] = []
    real_window = mw.InstallerMainWindow

    def _record(*args, **kwargs):
        window = real_window(*args, **kwargs)
        built.append(window)
        return window

    monkeypatch.setattr(installer_app, "InstallerMainWindow", _record)

    assert installer_app.main(argv) == 0
    assert len(built) == 1
    return built[0]


@pytest.mark.parametrize(
    ("argv", "expected_remove"),
    [
        (["--keep-user-data"], False),
        (["--remove-user-data"], True),
        ([], True),
    ],
)
def test_the_window_uninstalls_with_the_choice_it_was_launched_with(
    qapp, monkeypatch, tmp_path: Path, argv: list[str], expected_remove: bool
) -> None:
    from installer.state.model import Operation

    window = _window_built_by_main(monkeypatch, tmp_path, argv)
    try:
        _fn, kwargs = window._operation_callable(
            Operation.UNINSTALL, window._current_selections()
        )
        assert kwargs["opts"].remove_user_data is expected_remove
    finally:
        window.close()


def test_the_confirmation_names_the_bookmarks_and_shelf_it_will_delete() -> None:
    from installer.ui._main_window_uninstall import uninstall_confirmation_text

    text = uninstall_confirmation_text(True)

    assert "delete" in text
    assert "bookmarks" in text
    assert "shelf" in text


def test_the_confirmation_says_the_data_is_kept_when_it_is() -> None:
    from installer.ui._main_window_uninstall import uninstall_confirmation_text

    text = uninstall_confirmation_text(False)

    assert "kept" in text
    assert "delete" not in text
