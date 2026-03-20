from __future__ import annotations

from voice_reader.shared import startup_ui


def test_startup_ui_module_is_importable_and_coverable() -> None:
    # Minimal smoke coverage for import + trivial functions.
    assert startup_ui.default_lock_dir(app_name="NarrateX")
    startup_ui.activate_window(object())
    startup_ui._touch()

