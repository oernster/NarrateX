"""Logging configuration."""

from __future__ import annotations

import logging
import os
import sys


def _level_from_env(default: int) -> int:
    raw = os.getenv("NARRATEX_LOG_LEVEL", "").strip()
    if not raw:
        return default
    # Accept either numeric levels or names like DEBUG/INFO.
    if raw.isdigit():
        return int(raw)
    return int(getattr(logging, raw.upper(), default))


def configure_logging(level: int = logging.INFO) -> None:
    level = _level_from_env(level)
    logging.basicConfig(
        level=level,
        format=(
            "%(asctime)s | %(levelname)s | %(threadName)s | %(name)s | %(message)s"
        ),
        handlers=[logging.StreamHandler(sys.stdout)],
    )
