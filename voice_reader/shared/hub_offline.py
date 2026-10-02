"""Stop the Hugging Face hub library asking the network once the model is cached.

Kokoro fetches its weights and voices through ``huggingface_hub``, which checks
every cached file with huggingface.co on each load unless offline mode is on.
Measured on 2026-10-02: loading a cached voice looked up huggingface.co:443;
with offline mode on it looked up nothing and loaded the same voice.

The first run still needs the network to download, so offline mode is entered
only after the model pre-flight has confirmed every file is cached.

The library reads its offline flag when it is imported and again only when it
builds an HTTP session, which it then caches. So the environment variable alone
covers a library not yet imported and any child process. A library the
download already imported also needs its flag set and its cached sessions
dropped; otherwise a session built while online would go on reaching the
network.
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from types import ModuleType

HUB_OFFLINE_ENV = "HF_HUB_OFFLINE"
HUB_OFFLINE_ON = "1"
HUB_MODULE = "huggingface_hub"


def enter_hub_offline_mode(
    environ: MutableMapping[str, str], modules: Mapping[str, ModuleType]
) -> None:
    """Turn the hub library's offline mode on, imported yet or not."""

    environ[HUB_OFFLINE_ENV] = HUB_OFFLINE_ON
    hub = modules.get(HUB_MODULE)
    if hub is None:
        return
    hub.constants.HF_HUB_OFFLINE = True
    hub.utils.reset_sessions()
