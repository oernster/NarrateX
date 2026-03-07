"""Configuration and path management.

Avoid global mutable state; instantiate Config in app wiring.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AppPaths:
    project_root: Path
    voices_dir: Path
    cache_dir: Path
    temp_books_dir: Path


@dataclass(frozen=True, slots=True)
class Config:
    paths: AppPaths
    default_language: str = "en"
    tts_model_name: str = "tts_models/multilingual/multi-dataset/xtts_v2"

    @staticmethod
    def from_project_root(project_root: Path) -> "Config":
        project_root = project_root.resolve()
        paths = AppPaths(
            project_root=project_root,
            voices_dir=project_root / "voices",
            cache_dir=project_root / "cache",
            temp_books_dir=project_root / "temp_books",
        )
        return Config(paths=paths)

    def ensure_directories(self) -> None:
        self.paths.voices_dir.mkdir(parents=True, exist_ok=True)
        self.paths.cache_dir.mkdir(parents=True, exist_ok=True)
        self.paths.temp_books_dir.mkdir(parents=True, exist_ok=True)
