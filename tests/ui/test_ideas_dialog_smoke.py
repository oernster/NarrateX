from __future__ import annotations

from voice_reader.ui.ideas_dialog import IdeaListItem, IdeasDialog, IdeasDialogActions


def test_ideas_dialog_smoke(qapp) -> None:
    del qapp
    calls: list[str] = []
    items = [IdeaListItem(node_id="n1", label="Decision fatigue")]

    dlg = IdeasDialog(
        parent=None,
        actions=IdeasDialogActions(
            list_items=lambda: items,
            go_to=lambda it: calls.append(it.node_id),
        ),
        book_title="T",
    )
    assert dlg.windowTitle() == "Ideas"
    # Simulate button click by invoking the action directly.
    dlg._actions.go_to(items[0])  # noqa: SLF001
    assert calls == ["n1"]

