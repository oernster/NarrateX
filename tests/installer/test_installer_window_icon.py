"""The installer's window wears the NarrateX mark at every staged size."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize
from PySide6.QtGui import QPixmap

from installer.ui import icons


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_the_window_icon_carries_every_staged_size(qapp) -> None:
    del qapp
    icon = icons.build_installer_window_icon(project_root=_repo_root())
    assert not icon.isNull()
    assert set(icons.BRAND_PNG_SIZES) <= {s.width() for s in icon.availableSizes()}


def test_only_the_sizes_present_are_used(qapp, tmp_path, monkeypatch) -> None:
    del qapp
    monkeypatch.setattr(icons, "_candidate_roots", lambda project_root: [tmp_path])
    assert QPixmap(64, 64).save(str(tmp_path / icons.brand_png_name(64)))

    icon = icons.build_installer_window_icon(project_root=tmp_path)
    assert [s for s in icon.availableSizes()] == [QSize(64, 64)]


def test_the_windows_icon_is_the_last_resort(qapp, tmp_path, monkeypatch) -> None:
    del qapp
    monkeypatch.setattr(icons, "_candidate_roots", lambda project_root: [tmp_path])
    assert icons.build_installer_window_icon(project_root=tmp_path).isNull()

    ico = _repo_root() / icons.BRAND_ICO
    (tmp_path / icons.BRAND_ICO).write_bytes(ico.read_bytes())
    assert not icons.build_installer_window_icon(project_root=tmp_path).isNull()
