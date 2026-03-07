"""Logging configuration."""

from __future__ import annotations

import logging
import os
import sys
import warnings


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

    # Reduce noise from upstream libs. We prefer to keep our own logs clean.
    # These warnings do not affect NarrateX runtime behavior.
    warnings.filterwarnings(
        "ignore",
        message=r".*torch\.nn\.utils\.weight_norm.*deprecated.*",
        category=FutureWarning,
    )
    warnings.filterwarnings(
        "ignore",
        message=r".*dropout option adds dropout after all but last recurrent layer.*",
        category=UserWarning,
    )

    logging.basicConfig(
        level=level,
        format=(
            "%(asctime)s | %(levelname)s | %(threadName)s | %(name)s | %(message)s"
        ),
        handlers=[logging.StreamHandler(sys.stdout)],
    )
