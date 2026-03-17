"""UiController Ideas dialog wiring.

Phase 2 scope:

- If a completed idea index exists for the loaded book: open a read-only Ideas dialog.
- Otherwise: show a calm placeholder message.

Index generation is out of scope for this phase.
"""

from __future__ import annotations

import logging

try:
    # Module-level import so tests can monkeypatch
    # voice_reader.ui._ui_controller_ideas.QTimer.
    # (Importing inside _open_message_box bypasses monkeypatching.)
    from PySide6.QtCore import QTimer
except Exception:  # pragma: no cover
    QTimer = None  # type: ignore[assignment]

from PySide6.QtWidgets import QMessageBox

from voice_reader.ui.ideas_dialog import IdeaListItem, IdeasDialog, IdeasDialogActions
from voice_reader.ui._ideas_navigation import go_to_idea
from voice_reader.ui._message_box_utils import (
    NO_BOOK_WIDTH_PAD,
    open_nonblocking_message_box,
)


def _touch_qtimer_for_flake8() -> None:  # pragma: no cover
    # Explicitly touch the imported name so this module-level import (kept for
    # monkeypatching in tests) is not flagged as unused by flake8.
    _ = QTimer


def _touch_qtimer_for_coverage() -> None:  # pragma: no cover
    """Reserved for environments that strip Qt timers; keep stable coverage."""

    try:
        from PySide6.QtCore import QTimer

        del QTimer
    except Exception:
        return


def open_ideas_dialog(controller) -> None:
    log = getattr(controller, "_log", logging.getLogger(__name__))

    book_id = None
    try:
        book_id = controller.narration_service.loaded_book_id()
    except Exception:  # pragma: no cover
        book_id = None

    if not book_id:
        box = QMessageBox(controller.window)
        box.setWindowTitle("Ideas")
        box.setText("Load a book to map ideas.")
        try:
            # NBSP padding widens the dialog without showing any visible characters.
            box.setInformativeText(NO_BOOK_WIDTH_PAD)
        except Exception:  # pragma: no cover
            pass
        open_nonblocking_message_box(box, min_width=420, qtimer=QTimer)
        return

    svc = getattr(controller, "idea_map_service", None)
    # In normal app composition this exists; in older tests/wiring it may not.
    if svc is None:  # pragma: no cover
        box = QMessageBox(controller.window)
        box.setWindowTitle("Ideas")
        box.setText("Ideas are not available.")
        open_nonblocking_message_box(box, min_width=420, qtimer=QTimer)
        return

    normalized_text = ""
    try:
        book = getattr(controller.narration_service, "_book", None)  # noqa: SLF001
        normalized_text = str(getattr(book, "normalized_text", ""))
    except Exception:  # pragma: no cover
        normalized_text = ""

    has_index = False
    try:
        if hasattr(svc, "has_completed_index_for_text"):
            has_index = bool(
                svc.has_completed_index_for_text(
                    book_id=book_id,
                    normalized_text=normalized_text,
                )
            )
        else:
            has_index = bool(
                getattr(svc, "has_completed_index", lambda **_: False)(book_id=book_id)
            )
    except Exception:  # pragma: no cover
        has_index = False

    if not has_index:
        # If an indexing job is already running, show a calm status message.
        try:
            running_id = getattr(
                controller, "_ideas_index_job_book_id", None
            )  # noqa: SLF001
        except Exception:  # pragma: no cover
            running_id = None
        try:
            launch_inflight = bool(
                getattr(controller, "_ideas_launch_inflight", False)
            )  # noqa: SLF001
        except Exception:  # pragma: no cover
            launch_inflight = False

        if running_id == book_id or launch_inflight:
            # Avoid extra transient dialogs while mapping: the main window shows
            # a dedicated progress bar under 🧠.
            try:
                if hasattr(controller.window, "lbl_status"):
                    controller.window.lbl_status.setText("Mapping ideas…")
            except Exception:  # pragma: no cover
                pass
            return

        # If we have a persisted status (e.g. app exited mid-index, or the book
        # text changed and the idea map is now stale), give the user a slightly
        # more informative prompt.
        status_hint = None
        try:
            persisted = getattr(svc, "load_index_doc", lambda **_: None)(
                book_id=book_id
            )
            if isinstance(persisted, dict):
                st = persisted.get("status")
                if isinstance(st, dict):
                    state = str(st.get("state", "")).strip().casefold()
                    if state in {"running", "error", "cancelled"}:
                        status_hint = state
                    elif state == "completed":
                        # If the doc is completed but doesn't match the currently
                        # loaded text fingerprint, treat it as stale.
                        try:
                            book = persisted.get("book")
                            if isinstance(book, dict) and hasattr(
                                svc, "fingerprint_sha256"
                            ):
                                persisted_fp = str(
                                    book.get("fingerprint_sha256", "") or ""
                                ).strip()
                                expected_fp = str(
                                    svc.fingerprint_sha256(
                                        normalized_text=normalized_text
                                    )
                                ).strip()
                                if (
                                    persisted_fp
                                    and expected_fp
                                    and persisted_fp != expected_fp
                                ):
                                    status_hint = "stale"
                        except Exception:  # pragma: no cover
                            pass
        except Exception:  # pragma: no cover
            status_hint = None

        # Permission prompt (non-blocking).
        box = QMessageBox(controller.window)
        box.setWindowTitle("Ideas")
        extra = ""
        if status_hint == "running":
            extra = (
                "\n\nPrevious mapping didn’t finish (for example, the app was closed)."
            )
        elif status_hint == "error":
            extra = "\n\nPrevious mapping failed."
        elif status_hint == "cancelled":
            extra = "\n\nPrevious mapping was cancelled."
        elif status_hint == "stale":
            extra = "\n\nThis idea map is out of date for the currently loaded book."

        prompt = (
            "Map this book now?\n\n"
            "This runs in the background and won’t interrupt playback."
        )
        box.setText(prompt + extra)
        box.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        try:
            ok_btn = box.button(QMessageBox.Ok)
            if ok_btn is not None:
                ok_btn.setText("Map")
        except Exception:  # pragma: no cover
            pass

        def _on_done(result: int) -> None:
            try:
                if int(result) == int(QMessageBox.Ok):
                    controller._start_ideas_indexing(book_id=book_id)  # noqa: SLF001
            except Exception:  # pragma: no cover
                pass

        try:
            box.finished.connect(_on_done)
        except Exception:  # pragma: no cover
            pass
        open_nonblocking_message_box(box, min_width=520, qtimer=QTimer)
        return

    doc = getattr(svc, "load_index_doc", lambda **_: None)(book_id=book_id)
    if not isinstance(doc, dict):
        box = QMessageBox(controller.window)
        box.setWindowTitle("Ideas")
        box.setText("Failed loading idea map.")
        open_nonblocking_message_box(box, min_width=420, qtimer=QTimer)
        return

    # Normalize doc lists (tolerant to older/invalid docs).
    nodes = doc.get("nodes")
    if not isinstance(nodes, list):
        nodes = []

    # v1 read-only list: show node labels only.
    def _list_items() -> list[IdeaListItem]:
        out: list[IdeaListItem] = []
        for n in nodes:
            if not isinstance(n, dict):
                continue
            node_id = str(n.get("node_id", "")).strip()
            label = str(n.get("label", "")).strip()
            if not node_id or not label:
                continue
            out.append(IdeaListItem(node_id=node_id, label=label))
        return out

    # Minimal navigation: try to find a primary anchor and jump by chunk_index.
    anchors = doc.get("anchors")
    if not isinstance(anchors, list):
        anchors = []
    anchors_by_id: dict[str, dict] = {}
    for a in anchors:
        if not isinstance(a, dict):
            continue
        aid = str(a.get("anchor_id", "")).strip()
        if aid:
            anchors_by_id[aid] = a

    nodes_by_id: dict[str, dict] = {}
    for n in nodes:
        if not isinstance(n, dict):
            continue
        nid = str(n.get("node_id", "")).strip()
        if nid:
            nodes_by_id[nid] = n

    def _go_to(it: IdeaListItem) -> None:
        go_to_idea(
            controller,
            book_id=book_id,
            item=it,
            nodes_by_id=nodes_by_id,
            anchors_by_id=anchors_by_id,
            log=log,
            qtimer=QTimer,
        )

    actions = IdeasDialogActions(list_items=_list_items, go_to=_go_to)

    # Ensure only one dialog instance.
    try:
        if getattr(controller, "_ideas_dialog", None) is not None:
            controller._ideas_dialog.close()  # noqa: SLF001
    except Exception:  # pragma: no cover
        pass

    book_title = None
    try:
        book = getattr(controller.narration_service, "_book", None)  # noqa: SLF001
        book_title = getattr(book, "title", None)
    except Exception:  # pragma: no cover
        book_title = None

    controller._ideas_dialog = IdeasDialog(  # noqa: SLF001
        parent=controller.window,
        actions=actions,
        book_title=book_title,
    )
    controller._ideas_dialog.open()  # noqa: SLF001


def _touch_coverage() -> None:  # pragma: no cover
    """Reserved for future UI wiring changes."""

    return
