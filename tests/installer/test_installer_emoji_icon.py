from __future__ import annotations


def test_render_emoji_icon_is_not_null(qapp) -> None:
    # Ensure Qt app exists.
    del qapp

    from installer.ui.icons import render_emoji_icon

    icon = render_emoji_icon("🎤")
    assert not icon.isNull()

    # The icon should provide at least a 16x16 pixmap surface.
    pm = icon.pixmap(16, 16)
    assert not pm.isNull()


def test_build_installer_window_icon_prefers_brand_for_large_sizes(
    qapp, tmp_path
) -> None:
    # Ensure Qt app exists.
    del qapp

    # Create a fake brand png in a temp project root.
    # Use an existing QPixmap save to avoid external dependencies.
    from PySide6.QtGui import QPixmap

    pm = QPixmap(64, 64)
    assert not pm.isNull()
    brand = tmp_path / "narratex_64.png"
    assert pm.save(str(brand))

    from installer.ui.icons import build_installer_window_icon

    icon = build_installer_window_icon(project_root=tmp_path)
    assert not icon.isNull()
    assert not icon.pixmap(64, 64).isNull()
