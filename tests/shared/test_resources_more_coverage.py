from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

from voice_reader.shared import resources


def test_find_app_icon_path_prefers_project_root(tmp_path: Path) -> None:
    icon = tmp_path / "narratex.ico"
    icon.write_bytes(b"x")

    out = resources.find_app_icon_path(project_root=tmp_path)
    assert out == icon


def test_find_app_icon_path_meipass(monkeypatch, tmp_path: Path) -> None:
    meipass = tmp_path / "meipass"
    meipass.mkdir()
    (meipass / "narratex.ico").write_bytes(b"x")

    monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)
    out = resources.find_app_icon_path(project_root=None)
    assert out == meipass / "narratex.ico"


def test_iter_qt_window_icon_candidates_dedups_roots(
    monkeypatch, tmp_path: Path
) -> None:
    # Force CWD and project_root to be the same path so de-dup is exercised.
    monkeypatch.setattr(Path, "cwd", staticmethod(lambda: tmp_path))

    # Put an icon in one of the probed locations.
    (tmp_path / "narratex_64.png").write_bytes(b"x")
    cands = resources.iter_qt_window_icon_candidates(project_root=tmp_path)
    assert tmp_path / "narratex_64.png" in cands


def test_find_qt_window_icon_path_picks_existing(tmp_path: Path) -> None:
    (tmp_path / "narratex_256.png").write_bytes(b"x")
    out = resources.find_qt_window_icon_path(project_root=tmp_path)
    assert out == tmp_path / "narratex_256.png"
