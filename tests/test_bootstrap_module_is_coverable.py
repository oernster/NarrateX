from __future__ import annotations

import importlib
from unittest.mock import MagicMock

from voice_reader import bootstrap


def test_bootstrap_module_is_importable_and_coverable() -> None:
    bootstrap._touch()


def test_resolve_app_wiring_swallows_tick_fn_exception(monkeypatch) -> None:
    """tick_fn raising must not abort wiring."""
    target: dict = {}
    calls: list[int] = []

    def _boom() -> None:
        calls.append(1)
        raise RuntimeError("tick exploded")

    monkeypatch.setattr(
        importlib,
        "import_module",
        lambda mod: MagicMock(**{"__name__": mod, "FakeSym": object()}),
    )

    # Use a single-entry wiring table to keep the test fast.
    monkeypatch.setattr(
        bootstrap,
        "_APP_WIRING_IMPORTS",
        {"FakeSym": ("fake.module", "FakeSym")},
    )

    bootstrap.resolve_app_wiring(target, tick_fn=_boom)

    assert calls, "tick_fn must have been called"
    assert "FakeSym" in target, "symbol must still be populated after tick_fn raised"
