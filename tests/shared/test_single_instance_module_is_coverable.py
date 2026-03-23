from __future__ import annotations

from voice_reader.shared import single_instance


def test_single_instance_module_is_importable_and_coverable() -> None:
    single_instance._touch()
