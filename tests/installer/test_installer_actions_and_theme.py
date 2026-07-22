"""The installer's action rows must hold their shape and share one colour.

Three defects sat here. The box layout hands word-wrapping labels their
height-for-width allocation first, so a window sized to the plain layout
minimum starved the fixed-height button rows below their minimums and they
collided. Uninstall wore a warning red although it is a perfectly valid
action. And the in-window Uninstall button ran the operation directly; only
the Settings-launched path asked for confirmation first.
"""

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

from installer.ui.themes import DARK, LIGHT


def _block(qss: str, selector: str) -> str:
    start = qss.index(selector)
    return qss[start : qss.index("}", start)]


class TestUninstallSharesTheStandardColour:
    def test_no_red_survives_in_either_theme(self) -> None:
        for red in ["#b91c1c", "#dc2626", "#7a1f25", "#96262e"]:
            assert red not in LIGHT.qss
            assert red not in DARK.qss

    def test_uninstall_wears_the_same_border_as_the_primary_actions(self) -> None:
        for theme in [LIGHT, DARK]:
            primary = _block(theme.qss, "QPushButton#PrimaryAction {")
            danger = _block(theme.qss, "QPushButton#DangerAction {")

            def _border(block: str) -> str:
                line = next(ln for ln in block.splitlines() if "border:" in ln)
                return line.strip()

            assert _border(danger) == _border(primary)


@pytest.mark.skipif(os.name != "nt", reason="Installer UI is Windows-only")
class TestTheRowsHoldTheirShape:
    @pytest.fixture()
    def window(self, qapp, monkeypatch, tmp_path):
        import installer.ui.main_window as mw
        from voice_reader.version import __version__

        # The colliding screenshot was the installed state: Reinstall and
        # Repair above, Uninstall below, so that is the state under test.
        install_dir = tmp_path / "NarrateX"
        install_dir.mkdir()
        (install_dir / "NarrateX.exe").write_bytes(b"stub")
        entry = SimpleNamespace(
            display_version=__version__,
            install_location=install_dir,
            shortcut_desktop=True,
            shortcut_start_menu=True,
        )
        monkeypatch.setattr(mw, "read_uninstall_entry", lambda _key: entry)
        win = mw.InstallerMainWindow(SimpleNamespace(uninstall=False))
        win.show()
        qapp.processEvents()
        win._header_fit.ensure_now()
        qapp.processEvents()
        yield win
        win.close()

    def test_the_window_covers_the_height_for_width_answer(self, window) -> None:
        # The plain layout minimum is not enough: wrapped labels are handed
        # their height-for-width first, and whatever that takes comes out of
        # the fixed-height rows unless the window covers it too.
        root = window.centralWidget()
        layout = root.layout()
        assert layout.hasHeightForWidth()
        assert window.minimumHeight() >= layout.heightForWidth(root.width())

    def test_no_layout_row_is_squeezed_below_its_minimum(self, window) -> None:
        outer = window.centralWidget().layout()
        for index in range(outer.count()):
            item = outer.itemAt(index)
            assert (
                item.geometry().height() >= item.minimumSize().height()
            ), f"outer layout item {index} was starved below its minimum"

    def test_uninstall_sits_clear_of_the_primary_row(self, window) -> None:
        root = window.centralWidget()
        primary_bottom = window._btn_primary_left.mapTo(
            root, window._btn_primary_left.rect().bottomLeft()
        ).y()
        uninstall_top = window._btn_uninstall.mapTo(
            root, window._btn_uninstall.rect().topLeft()
        ).y()
        assert uninstall_top - primary_bottom >= root.layout().spacing()

    def test_toggling_the_theme_moves_nothing(self, window, qapp) -> None:
        # The header lock used to re-measure on every theme application with
        # the previous lock still in place, so each toggle grew the header by
        # the SafeLabel buffer and walked the whole UI down the window.
        root = window.centralWidget()

        def _snapshot():
            button = window._btn_primary_left
            return (
                window.height(),
                window.minimumHeight(),
                window._header_title.minimumHeight(),
                button.mapTo(root, button.rect().topLeft()).y(),
            )

        before = _snapshot()
        for _ in range(3):
            window._toggle_theme()
            qapp.processEvents()
            window._header_fit.ensure_now()
            qapp.processEvents()

        assert _snapshot() == before

    def test_the_uninstall_button_asks_before_acting(
        self, window, qapp, monkeypatch
    ) -> None:
        import installer.ui.main_window as mw

        asked: list[object] = []
        monkeypatch.setattr(
            mw, "confirm_and_run_uninstall", lambda win: asked.append(win)
        )

        window._btn_uninstall.click()
        qapp.processEvents()

        assert asked == [window]
        assert window._op_controller.is_running is False
