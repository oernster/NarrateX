from __future__ import annotations

from pathlib import Path

from voice_reader.shared.single_instance import stable_server_name


def test_stable_server_name_is_deterministic(tmp_path: Path) -> None:
    lock = tmp_path / "NarrateX" / "single_instance.lock"
    a = stable_server_name(namespace="com.oliverernster.narratex", lock_path=lock)
    b = stable_server_name(namespace="com.oliverernster.narratex", lock_path=lock)
    assert a == b


def test_stable_server_name_changes_when_lock_path_changes(tmp_path: Path) -> None:
    a = stable_server_name(
        namespace="com.oliverernster.narratex", lock_path=tmp_path / "a.lock"
    )
    b = stable_server_name(
        namespace="com.oliverernster.narratex", lock_path=tmp_path / "b.lock"
    )
    assert a != b
