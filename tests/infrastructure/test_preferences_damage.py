"""A damaged preferences file is kept aside, never saved over (round 3, N-9).

Preferences were written in place and any read error read as empty, so a file
an interrupted write had cut in half lost the auto-load book, the skipped
update version and the shelf layout at the next volume change.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from voice_reader.domain.value_objects.playback_volume import PlaybackVolume
from voice_reader.infrastructure.preferences.json_preferences_repository import (
    JSONPreferencesRepository,
)

SAVED = {
    "last_book_path": "C:/books/a.txt",
    "playback_volume": 0.5,
    "shelf_layout": "grid",
    "skipped_update_version": "9.9.9",
}


def _half_written(path: Path) -> bytes:
    text = json.dumps(SAVED, indent=2).encode("utf-8")
    path.write_bytes(text[: len(text) // 2])
    return path.read_bytes()


def test_a_save_keeps_a_damaged_file_aside(tmp_path: Path) -> None:
    path = tmp_path / "preferences.json"
    damaged = _half_written(path)
    repo = JSONPreferencesRepository(path=path)

    repo.save_playback_volume(PlaybackVolume(0.7))

    assert (tmp_path / "preferences.json.damaged").read_bytes() == damaged
    assert repo.load_playback_volume() == PlaybackVolume(0.7)


def test_a_damaged_file_still_reads_as_defaults(tmp_path: Path) -> None:
    path = tmp_path / "preferences.json"
    _half_written(path)
    repo = JSONPreferencesRepository(path=path)

    assert repo.load_skipped_update_version() is None
    assert path.read_bytes()  # reading changed nothing


def test_a_file_that_cannot_be_read_is_never_written_over(tmp_path: Path) -> None:
    path = tmp_path / "preferences.json"
    path.mkdir()
    repo = JSONPreferencesRepository(path=path)

    with pytest.raises(OSError):
        repo.save_skipped_update_version("1.0.0")

    assert path.is_dir()


def test_a_save_replaces_the_file_whole(tmp_path: Path) -> None:
    path = tmp_path / "preferences.json"
    repo = JSONPreferencesRepository(path=path)

    repo.save_skipped_update_version("1.0.0")
    repo.save_playback_volume(PlaybackVolume(0.25))

    assert json.loads(path.read_text(encoding="utf-8")) == {
        "playback_volume": 0.25,
        "skipped_update_version": "1.0.0",
    }
    assert not (tmp_path / "preferences.json.tmp").exists()
