from __future__ import annotations

import logging

import voice_reader.shared.logging_utils as lu


def test_level_from_env_default_when_missing(monkeypatch) -> None:
    monkeypatch.delenv("NARRATEX_LOG_LEVEL", raising=False)
    assert lu._level_from_env(logging.INFO) == logging.INFO


def test_level_from_env_accepts_numeric(monkeypatch) -> None:
    monkeypatch.setenv("NARRATEX_LOG_LEVEL", "10")
    assert lu._level_from_env(logging.INFO) == 10


def test_level_from_env_accepts_name(monkeypatch) -> None:
    monkeypatch.setenv("NARRATEX_LOG_LEVEL", "debug")
    assert lu._level_from_env(logging.INFO) == logging.DEBUG


def test_level_from_env_invalid_name_falls_back(monkeypatch) -> None:
    monkeypatch.setenv("NARRATEX_LOG_LEVEL", "not-a-level")
    assert lu._level_from_env(logging.WARNING) == logging.WARNING

