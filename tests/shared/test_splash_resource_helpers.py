from __future__ import annotations

from pathlib import Path

from voice_reader.shared.resources import find_splash_image_path


def test_find_splash_image_path_prefers_project_root(tmp_path: Path) -> None:
    (tmp_path / "narratex_256.png").write_bytes(b"x")
    out = find_splash_image_path(project_root=tmp_path)
    assert out == tmp_path / "narratex_256.png"
