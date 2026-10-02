"""Offline mode for the Hugging Face hub library, entered once the model is cached."""

from __future__ import annotations

from types import SimpleNamespace

import huggingface_hub
import pytest
from huggingface_hub import constants
from huggingface_hub.utils import get_session
from huggingface_hub.utils._http import OfflineAdapter

from voice_reader.shared.hub_offline import (
    HUB_MODULE,
    HUB_OFFLINE_ENV,
    HUB_OFFLINE_ON,
    enter_hub_offline_mode,
)

# Never contacted: only the adapter a request would use is inspected.
_HUB_URL = "https://huggingface.co/api/models/hexgrad/Kokoro-82M"


def test_a_library_not_yet_imported_is_covered_by_the_environment() -> None:
    environ: dict[str, str] = {}

    enter_hub_offline_mode(environ, {})

    assert environ == {HUB_OFFLINE_ENV: HUB_OFFLINE_ON}


def test_an_imported_library_has_its_flag_set_and_its_sessions_dropped() -> None:
    resets: list[bool] = []
    hub = SimpleNamespace(
        constants=SimpleNamespace(HF_HUB_OFFLINE=False),
        utils=SimpleNamespace(reset_sessions=lambda: resets.append(True)),
    )
    environ: dict[str, str] = {}

    enter_hub_offline_mode(environ, {HUB_MODULE: hub})

    assert environ[HUB_OFFLINE_ENV] == HUB_OFFLINE_ON
    assert hub.constants.HF_HUB_OFFLINE is True
    assert resets == [True]


def test_a_session_built_while_online_refuses_once_offline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The real library: a session cached before the switch must not survive it."""

    monkeypatch.setattr(constants, "HF_HUB_OFFLINE", False)
    huggingface_hub.utils.reset_sessions()
    # Cached while online, as the first-run download leaves it. Which adapter a
    # session would send through is read without sending anything.
    online = get_session().get_adapter(_HUB_URL)
    assert not isinstance(online, OfflineAdapter)

    try:
        enter_hub_offline_mode({}, {HUB_MODULE: huggingface_hub})
        assert isinstance(get_session().get_adapter(_HUB_URL), OfflineAdapter)
    finally:
        # monkeypatch restores the flag; the sessions built under it go too.
        monkeypatch.undo()
        huggingface_hub.utils.reset_sessions()
