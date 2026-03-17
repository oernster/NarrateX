from __future__ import annotations

from datetime import datetime, timezone

from voice_reader.domain.entities.bookmark import Bookmark
from voice_reader.ui.bookmarks_dialog import BookmarksDialog, BookmarksDialogActions


def test_bookmarks_dialog_smoke(qapp) -> None:
    del qapp

    calls: list[str] = []
    bookmarks = [
        Bookmark(
            bookmark_id=1,
            name="Bookmark 1",
            char_offset=10,
            chunk_index=0,
            created_at=datetime(2026, 3, 14, 0, 0, 0, tzinfo=timezone.utc),
        )
    ]

    actions = BookmarksDialogActions(
        list_bookmarks=lambda: bookmarks,
        add_bookmark=lambda: calls.append("add"),
        go_to_bookmark=lambda bm: calls.append(f"goto:{bm.bookmark_id}"),
        delete_bookmark=lambda bm: calls.append(f"del:{bm.bookmark_id}"),
    )

    dlg = BookmarksDialog(parent=None, actions=actions)
    dlg.refresh()

    assert dlg.list.count() == 1
    assert dlg.list.item(0).text() == "📌 Bookmark 1"
    dlg.btn_goto.click()
    dlg.btn_delete.click()
    dlg.btn_add.click()

    assert calls[:2] == ["goto:1", "del:1"]

    # Cover the error paths (handlers catch exceptions and show a warning box).
    actions_err = BookmarksDialogActions(
        list_bookmarks=lambda: bookmarks,
        add_bookmark=lambda: (_ for _ in ()).throw(RuntimeError("boom")),
        go_to_bookmark=lambda bm: (_ for _ in ()).throw(RuntimeError("boom")),
        delete_bookmark=lambda bm: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    dlg2 = BookmarksDialog(parent=None, actions=actions_err)
    dlg2.refresh()
    dlg2.btn_add.click()
    dlg2.btn_goto.click()
    dlg2.btn_delete.click()
