"""The shelf layout round-trips through the JSON repository (FR-BS-052)."""

from __future__ import annotations

import json

from voice_reader.domain.shelf.layout import ShelfLayout
from voice_reader.infrastructure.preferences.json_preferences_repository import (
    JSONPreferencesRepository,
)


def _repo(tmp_path):
    return JSONPreferencesRepository(path=tmp_path / "preferences.json")


def test_a_fresh_install_has_no_layout(tmp_path):
    assert _repo(tmp_path).load_shelf_layout() is None


def test_a_saved_layout_is_loaded_back(tmp_path):
    repo = _repo(tmp_path)
    repo.save_shelf_layout(ShelfLayout.LIST)
    assert repo.load_shelf_layout() is ShelfLayout.LIST


def test_the_layout_is_stored_as_a_word(tmp_path):
    """A word says what it is to somebody reading the file; a flag does not."""

    repo = _repo(tmp_path)
    repo.save_shelf_layout(ShelfLayout.LIST)
    assert json.loads(repo.path.read_text(encoding="utf-8"))["shelf_layout"] == "list"


def test_saving_a_layout_preserves_the_other_preferences(tmp_path):
    repo = _repo(tmp_path)
    repo.path.write_text(json.dumps({"playback_volume": 0.5}), encoding="utf-8")
    repo.save_shelf_layout(ShelfLayout.GRID)
    assert json.loads(repo.path.read_text(encoding="utf-8"))["playback_volume"] == 0.5


def test_a_layout_the_build_does_not_know_is_no_layout(tmp_path):
    """A file written by hand or by another build is met, not refused."""

    repo = _repo(tmp_path)
    repo.path.write_text(json.dumps({"shelf_layout": "carousel"}), encoding="utf-8")
    assert repo.load_shelf_layout() is None
