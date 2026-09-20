"""The shelf's entry points on the controller, as one capability.

Every one of them is a name a signal connects to, so they have to be methods on
the controller rather than free functions; gathering them in a mixin keeps the
controller a facade that can be read in one screen while the behaviour stays in
`_ui_controller_shelf.py`.

The imports are made when called, as the controller's other concerns do, so
importing the controller does not drag in the grid, the delegate and the cover
reader for a window that may never show the shelf.
"""

from __future__ import annotations


class ShelfApi:
    """What the window and the grid ask the controller to do about the shelf."""

    def toggle_shelf(self) -> None:
        from voice_reader.ui._ui_controller_shelf import toggle_shelf

        return toggle_shelf(self)

    def choose_shelf_root(self) -> None:
        from voice_reader.ui._ui_controller_shelf import choose_shelf_root

        return choose_shelf_root(self)

    def rescan_shelf(self) -> None:
        from voice_reader.ui._ui_controller_shelf import rescan_shelf

        return rescan_shelf(self)

    def open_work(self, work) -> None:
        from voice_reader.ui._ui_controller_shelf import open_work

        return open_work(self, work)

    def install_shelf_grid(self) -> None:
        from voice_reader.ui._ui_controller_shelf import install_shelf_grid

        return install_shelf_grid(self)

    def refresh_shelf(self) -> None:
        from voice_reader.ui._ui_controller_shelf import refresh_shelf

        return refresh_shelf(self)

    def filter_shelf(self) -> None:
        from voice_reader.ui._ui_controller_shelf import filter_shelf

        return filter_shelf(self)

    def tag_work(self, work) -> None:
        from voice_reader.ui._ui_controller_shelf import tag_work

        return tag_work(self, work)
