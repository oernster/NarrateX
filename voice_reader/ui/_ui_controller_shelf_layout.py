"""Tiles or rows; remembering which (FR-BS-051 and FR-BS-052).

Its own module because it is the one shelf concern that reaches the reader's
preferences: everything else the shelf remembers lives in the shelf's own index.

**The preferences are reached the way the rest of the controller reaches them.**
Through the narration service's `preferences_repo`, asked for by name, so a build
or a test with none wired draws the default layout and remembers nothing rather
than raising. A layout is a convenience; failing to remember one is never a
reason for the shelf not to open.
"""

from __future__ import annotations

from voice_reader.domain.shelf.layout import DEFAULT_LAYOUT, ShelfLayout


def apply_saved_layout(controller) -> None:
    """FR-BS-052: draw the shelf the way it was last drawn."""

    load = getattr(_preferences(controller), "load_shelf_layout", None)
    saved = load() if callable(load) else None
    controller.window.shelf_view.set_layout(saved or DEFAULT_LAYOUT)


def toggle_shelf_layout(controller) -> None:
    """FR-BS-051: switch to the other layout, then remember it."""

    grid = controller.window.shelf_view.grid
    current = grid.shelf_layout() if grid is not None else DEFAULT_LAYOUT
    chosen = current.other
    controller.window.shelf_view.set_layout(chosen)
    _remember(controller, chosen)


def _remember(controller, layout: ShelfLayout) -> None:
    """Save the layout where a save is possible; say nothing where it is not."""

    save = getattr(_preferences(controller), "save_shelf_layout", None)
    if callable(save):
        save(layout)


def _preferences(controller):
    """The reader's preferences, as the controller's other concerns find them."""

    return getattr(
        getattr(controller, "narration_service", None), "preferences_repo", None
    )
