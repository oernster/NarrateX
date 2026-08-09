"""The skipped-update preference round-trips through the JSON repository."""

from __future__ import annotations

import json

from voice_reader.infrastructure.preferences.json_preferences_repository import (
    JSONPreferencesRepository,
)


def _repo(tmp_path):
    return JSONPreferencesRepository(path=tmp_path / "preferences.json")


def test_a_fresh_install_has_no_skipped_version(tmp_path):
    assert _repo(tmp_path).load_skipped_update_version() is None


def test_a_saved_skip_is_loaded_back(tmp_path):
    repo = _repo(tmp_path)
    repo.save_skipped_update_version("4.2.0")
    assert repo.load_skipped_update_version() == "4.2.0"


def test_saving_a_skip_preserves_the_other_preferences(tmp_path):
    repo = _repo(tmp_path)
    repo.path.parent.mkdir(parents=True, exist_ok=True)
    repo.path.write_text(json.dumps({"playback_volume": 0.5}), encoding="utf-8")
    repo.save_skipped_update_version("4.2.0")
    data = json.loads(repo.path.read_text(encoding="utf-8"))
    assert data["playback_volume"] == 0.5
    assert data["skipped_update_version"] == "4.2.0"


def test_a_non_string_or_empty_value_reads_as_no_skip(tmp_path):
    repo = _repo(tmp_path)
    repo.path.parent.mkdir(parents=True, exist_ok=True)
    for value in (7, "", None):
        repo.path.write_text(
            json.dumps({"skipped_update_version": value}), encoding="utf-8"
        )
        assert repo.load_skipped_update_version() is None
