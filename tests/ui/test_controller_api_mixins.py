"""Every entry point a signal reaches, called through the controller.

The behaviour behind each of these is tested where it lives. What is checked here
is the one thing those tests cannot see: that the method on the controller exists
and reaches the right function, since a signal connected to a name that moved
fails only when a reader clicks the control.
"""

from __future__ import annotations

from voice_reader.ui import _ui_controller_transport_api as transport
from voice_reader.ui import _ui_controller_shelf as shelf_helpers
from voice_reader.ui._ui_controller_shelf_api import ShelfApi
from voice_reader.ui._ui_controller_transport_api import TransportApi


class _Controller(ShelfApi, TransportApi):
    """Nothing but the two mixins, so nothing else can answer the call."""


def test_every_shelf_entry_point_reaches_its_helper(monkeypatch) -> None:
    reached: list[str] = []
    controller = _Controller()
    work = object()
    for name in (
        "toggle_shelf",
        "choose_shelf_root",
        "rescan_shelf",
        "install_shelf_grid",
        "refresh_shelf",
    ):
        monkeypatch.setattr(shelf_helpers, name, lambda _c, _n=name: reached.append(_n))
    monkeypatch.setattr(
        shelf_helpers, "open_work", lambda _c, given: reached.append(f"open:{given}")
    )

    controller.toggle_shelf()
    controller.choose_shelf_root()
    controller.rescan_shelf()
    controller.install_shelf_grid()
    controller.refresh_shelf()
    controller.open_work(work)

    assert reached == [
        "toggle_shelf",
        "choose_shelf_root",
        "rescan_shelf",
        "install_shelf_grid",
        "refresh_shelf",
        f"open:{work}",
    ]


def test_every_transport_entry_point_reaches_its_helper(monkeypatch) -> None:
    reached: list[str] = []
    controller = _Controller()
    # Patched on the mixin's own module: it imports the helpers by name at
    # import time, so patching where they are defined would not be seen.
    for name in ("play", "pause", "stop", "toggle_play_pause"):
        monkeypatch.setattr(transport, name, lambda _c, _n=name: reached.append(_n))
    monkeypatch.setattr(
        transport, "set_speed", lambda _c, text: reached.append(f"speed:{text}")
    )
    monkeypatch.setattr(
        transport, "set_volume", lambda _c, value: reached.append(f"volume:{value}")
    )

    controller.play()
    controller.pause()
    controller.stop()
    controller.toggle_play_pause()
    controller.set_speed("1.25x")
    controller.set_volume(40)

    assert reached == [
        "play",
        "pause",
        "stop",
        "toggle_play_pause",
        "speed:1.25x",
        "volume:40",
    ]
