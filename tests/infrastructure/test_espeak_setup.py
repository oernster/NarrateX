from __future__ import annotations

import pytest

from voice_reader.infrastructure.tts import _espeak_setup
from voice_reader.infrastructure.tts._espeak_setup import (
    _DATA_ENV,
    _LIBRARY_ENV,
    configure_espeak,
)


@pytest.fixture(autouse=True)
def _clear_espeak_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(_LIBRARY_ENV, raising=False)
    monkeypatch.delenv(_DATA_ENV, raising=False)


class _Wrapper:
    def __init__(self, *, found: bool) -> None:
        self._found = found

    def library(self) -> str:
        if not self._found:
            raise RuntimeError("failed to find espeak library")
        return "/usr/lib/libespeak-ng.so.1"


class _Loader:
    @staticmethod
    def get_library_path() -> str:
        return "/bundled/libespeak-ng.so"

    @staticmethod
    def get_data_path() -> str:
        return "/bundled/espeak-ng-data"


def test_skips_when_library_env_already_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(_LIBRARY_ENV, "/preset/lib.so")

    def _boom():  # pragma: no cover - must not be called
        raise AssertionError("wrapper should not be loaded")

    monkeypatch.setattr(_espeak_setup, "_load_espeak_wrapper", _boom)

    configure_espeak()

    import os

    assert os.environ[_LIBRARY_ENV] == "/preset/lib.so"


def test_returns_when_wrapper_import_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise():
        raise ImportError("no phonemizer")

    monkeypatch.setattr(_espeak_setup, "_load_espeak_wrapper", _raise)

    configure_espeak()

    import os

    assert _LIBRARY_ENV not in os.environ


def test_returns_when_system_espeak_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        _espeak_setup, "_load_espeak_wrapper", lambda: _Wrapper(found=True)
    )

    def _boom():  # pragma: no cover - must not be called
        raise AssertionError("loader should not be used when system espeak exists")

    monkeypatch.setattr(_espeak_setup, "_load_espeakng_loader", _boom)

    configure_espeak()

    import os

    assert _LIBRARY_ENV not in os.environ


def test_returns_when_loader_import_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        _espeak_setup, "_load_espeak_wrapper", lambda: _Wrapper(found=False)
    )

    def _raise():
        raise ImportError("no espeakng_loader")

    monkeypatch.setattr(_espeak_setup, "_load_espeakng_loader", _raise)

    configure_espeak()

    import os

    assert _LIBRARY_ENV not in os.environ


def test_sets_env_from_loader_when_no_system_espeak(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        _espeak_setup, "_load_espeak_wrapper", lambda: _Wrapper(found=False)
    )
    monkeypatch.setattr(_espeak_setup, "_load_espeakng_loader", lambda: _Loader())

    configure_espeak()

    import os

    assert os.environ[_LIBRARY_ENV] == "/bundled/libespeak-ng.so"
    assert os.environ[_DATA_ENV] == "/bundled/espeak-ng-data"


def test_load_espeak_wrapper_returns_class() -> None:
    wrapper = _espeak_setup._load_espeak_wrapper()
    assert hasattr(wrapper, "library")


def test_load_espeakng_loader_returns_module() -> None:
    loader = _espeak_setup._load_espeakng_loader()
    assert hasattr(loader, "get_library_path")


def test_preserves_existing_data_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(_DATA_ENV, "/preset/data")
    monkeypatch.setattr(
        _espeak_setup, "_load_espeak_wrapper", lambda: _Wrapper(found=False)
    )
    monkeypatch.setattr(_espeak_setup, "_load_espeakng_loader", lambda: _Loader())

    configure_espeak()

    import os

    # Library override is applied, but a pre-set data path is respected.
    assert os.environ[_LIBRARY_ENV] == "/bundled/libespeak-ng.so"
    assert os.environ[_DATA_ENV] == "/preset/data"
