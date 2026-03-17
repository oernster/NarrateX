from __future__ import annotations


from voice_reader.ui.structural_bookmarks_dialog import (
    StructuralBookmarkListItem,
    StructuralBookmarksDialog,
    StructuralBookmarksDialogActions,
)


def test_sections_dialog_renders_items_and_invokes_goto(qapp) -> None:
    del qapp

    calls: list[StructuralBookmarkListItem] = []

    items = [
        StructuralBookmarkListItem(
            label="Chapter 1: Start",
            char_offset=10,
            chunk_index=None,
            kind="chapter",
            level=0,
        )
    ]

    dlg = StructuralBookmarksDialog(
        parent=None,
        actions=StructuralBookmarksDialogActions(
            list_items=lambda: items,
            go_to=lambda it: calls.append(it),
        ),
        book_title="Book",
    )

    assert dlg.windowTitle() == "Sections"
    assert dlg.list.count() == 1
    assert dlg.list.item(0).text() == "📌 Chapter 1: Start"

    dlg.list.setCurrentRow(0)
    dlg.btn_goto.click()
    assert calls and calls[0].label == "Chapter 1: Start"

