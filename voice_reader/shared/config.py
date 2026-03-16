"""Configuration and path management.

Avoid global mutable state; instantiate Config in app wiring.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import sys

from platformdirs import user_cache_dir, user_data_dir

from voice_reader.version import APP_AUTHOR, APP_NAME


@dataclass(frozen=True, slots=True)
class AppPaths:
    project_root: Path
    voices_dir: Path
    cache_dir: Path
    ideas_work_dir: Path
    temp_books_dir: Path
    bookmarks_dir: Path
    preferences_path: Path


@dataclass(frozen=True, slots=True)
class Config:
    paths: AppPaths
    default_language: str = "en"

    @staticmethod
    def from_project_root(project_root: Path) -> "Config":
        project_root = project_root.resolve()

        # When bundled into a single-file exe (e.g., Nuitka onefile), the
        # extraction directory should be treated as read-only. Use per-user
        # directories for any writable data.
        frozen = bool(getattr(sys, "frozen", False))
        force_user_dirs = os.getenv("NARRATEX_USER_DIRS", "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

        if frozen or force_user_dirs:
            data_root = Path(user_data_dir(APP_NAME, APP_AUTHOR)).resolve()
            cache_root = Path(user_cache_dir(APP_NAME, APP_AUTHOR)).resolve()
            voices_dir = data_root / "voices"
            temp_books_dir = data_root / "temp_books"
            cache_dir = cache_root / "cache"
            ideas_work_dir = cache_dir / "ideas_work"
            bookmarks_dir = data_root / "bookmarks"
            preferences_path = data_root / "preferences.json"
        else:
            voices_dir = project_root / "voices"
            cache_dir = project_root / "cache"
            ideas_work_dir = cache_dir / "ideas_work"
            temp_books_dir = project_root / "temp_books"
            bookmarks_dir = project_root / "bookmarks"
            preferences_path = project_root / "preferences.json"

        paths = AppPaths(
            project_root=project_root,
            voices_dir=voices_dir,
            cache_dir=cache_dir,
            ideas_work_dir=ideas_work_dir,
            temp_books_dir=temp_books_dir,
            bookmarks_dir=bookmarks_dir,
            preferences_path=preferences_path,
        )
        return Config(paths=paths)

    def ensure_directories(self) -> None:
        self.paths.voices_dir.mkdir(parents=True, exist_ok=True)
        self.paths.cache_dir.mkdir(parents=True, exist_ok=True)
        self.paths.ideas_work_dir.mkdir(parents=True, exist_ok=True)
        self.paths.temp_books_dir.mkdir(parents=True, exist_ok=True)
        self.paths.bookmarks_dir.mkdir(parents=True, exist_ok=True)
