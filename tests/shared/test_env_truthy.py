"""Tests for the shared best-effort environment-flag reader."""

from __future__ import annotations

import pytest

from voice_reader.shared.startup_diagnostics import env_truthy


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "y", "on", " On "])
def test_a_plainly_on_value_reads_true(value):
    assert env_truthy("X", getenv=lambda n, d="": value) is True


@pytest.mark.parametrize("value", ["", "0", "false", "off", "no", "banana"])
def test_anything_else_reads_false(value):
    assert env_truthy("X", getenv=lambda n, d="": value) is False


def test_an_unreadable_environment_degrades_to_off():
    def boom(name, default=""):
        raise RuntimeError("environment unavailable")

    assert env_truthy("X", getenv=boom) is False


def test_the_real_environment_is_read_by_default(monkeypatch):
    monkeypatch.setenv("NARRATEX_ENV_TRUTHY_PROBE", "yes")
    assert env_truthy("NARRATEX_ENV_TRUTHY_PROBE") is True
    monkeypatch.delenv("NARRATEX_ENV_TRUTHY_PROBE")
    assert env_truthy("NARRATEX_ENV_TRUTHY_PROBE") is False
