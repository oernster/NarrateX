"""The version has exactly one source: the `VERSION` file at the repo root."""

from __future__ import annotations

from pathlib import Path

from voice_reader import version as version_module


def test_version_file_exists_at_the_repository_root() -> None:
    assert version_module.VERSION_FILE.is_file(), (
        "VERSION is the single source of truth and must exist at the repo root "
        f"(looked in {version_module.VERSION_FILE})"
    )


def test_module_version_is_the_contents_of_the_version_file() -> None:
    expected = version_module.VERSION_FILE.read_text(encoding="utf-8").strip()

    assert version_module.__version__ == expected
    assert version_module.__version__ != version_module.VERSION_FALLBACK


def test_read_version_strips_surrounding_whitespace(tmp_path: Path) -> None:
    path = tmp_path / "VERSION"
    path.write_text("  9.9.9\n\n", encoding="utf-8")

    assert version_module.read_version(path) == "9.9.9"


def test_read_version_falls_back_when_the_file_is_missing(tmp_path: Path) -> None:
    missing = tmp_path / "nowhere" / "VERSION"

    assert version_module.read_version(missing) == version_module.VERSION_FALLBACK


def test_read_version_falls_back_when_the_file_is_empty(tmp_path: Path) -> None:
    path = tmp_path / "VERSION"
    path.write_text("\n", encoding="utf-8")

    assert version_module.read_version(path) == version_module.VERSION_FALLBACK
