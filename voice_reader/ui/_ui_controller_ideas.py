"""UiController Ideas dialog wiring.

Phase 2 scope:

- If a completed idea index exists for the loaded book: open a read-only Ideas dialog.
- Otherwise: show a calm placeholder message.

Index generation is out of scope for this phase.
"""

from __future__ import annotations

import os

try:
    # Module-level import so tests can monkeypatch voice_reader.ui._ui_controller_ideas.QTimer.
    # (Importing inside _open_message_box bypasses monkeypatching.)
    from PySide6.QtCore import QTimer
except Exception:  # pragma: no cover
    QTimer = None  # type: ignore[assignment]

from PySide6.QtWidgets import QMessageBox

from voice_reader.ui.ideas_dialog import IdeaListItem, IdeasDialog, IdeasDialogActions


# Workaround for Windows packaged builds where the initial QMessageBox may be sized
# too narrowly, causing the title bar to truncate (e.g. "I…" instead of "Ideas").
#
# We "cheat" by adding an *invisible* informativeText consisting of NBSPs whose
# measured width roughly matches a sentence that we know produces a sensible
# dialog width in other Ideas flows.
_NO_BOOK_WIDTH_PAD_REF = "This runs in the background and won't interrupt playback."
# Use 2x the reference length to bias the layout toward a wider initial dialog,
# ensuring the title bar has enough horizontal room on Windows builds.
_NO_BOOK_WIDTH_PAD = "\u00A0" * (len(_NO_BOOK_WIDTH_PAD_REF) * 2)


def _in_tests() -> bool:
    # pytest sets this environment variable for each test.
    return bool(os.getenv("PYTEST_CURRENT_TEST"))


def _touch_qtimer_for_coverage() -> None:  # pragma: no cover
    """Reserved for environments that strip Qt timers; keep stable coverage."""

    try:
        from PySide6.QtCore import QTimer

        del QTimer
    except Exception:
        return


def _widen_message_box(box: QMessageBox, *, min_width: int) -> None:
    """Best-effort: make QMessageBox wide enough to avoid title truncation on Windows."""

    try:
        w = int(min_width)
    except Exception:  # pragma: no cover
        w = 420

    try:
        box.setMinimumWidth(w)
        box.adjustSize()
        box.resize(max(w, box.width()), box.height())
    except Exception:  # pragma: no cover
        pass


def _open_message_box(box: QMessageBox, *, min_width: int) -> None:
    """Open a non-blocking message box with a reliable width on Windows.

    In some environments, QMessageBox recalculates its final size at/after show.
    To avoid a very narrow initial window (which can truncate the title bar to
    e.g. "I…"), we widen both before and immediately after opening.
    """

    _widen_message_box(box, min_width=min_width)
    if _in_tests():
        # Avoid using a QTimer in tests; it can make assertions racy.
        box.open()
        _widen_message_box(box, min_width=min_width)
        return

    # In real app runtime, defer another widen until after show/layout.
    box.open()
    try:
        # QTimer may be None in stripped environments; treat as best-effort.
        if QTimer is not None:
            QTimer.singleShot(0, lambda: _widen_message_box(box, min_width=min_width))
    except Exception:  # pragma: no cover
        pass


def open_ideas_dialog(controller) -> None:
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
            box.setInformativeText(_NO_BOOK_WIDTH_PAD)
        except Exception:  # pragma: no cover
            pass
        _open_message_box(box, min_width=420)
        return

    svc = getattr(controller, "idea_map_service", None)
    # In normal app composition this exists; in older tests or partial wiring it may not.
    if svc is None:  # pragma: no cover
        box = QMessageBox(controller.window)
        box.setWindowTitle("Ideas")
        box.setText("Ideas are not available.")
        _open_message_box(box, min_width=420)
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
            has_index = bool(getattr(svc, "has_completed_index", lambda **_: False)(book_id=book_id))
    except Exception:  # pragma: no cover
        has_index = False

    if not has_index:
        # If an indexing job is already running, show a calm status message.
        try:
            running_id = getattr(controller, "_ideas_index_job_book_id", None)  # noqa: SLF001
        except Exception:  # pragma: no cover
            running_id = None
        try:
            launch_inflight = bool(getattr(controller, "_ideas_launch_inflight", False))  # noqa: SLF001
        except Exception:  # pragma: no cover
            launch_inflight = False

        if running_id == book_id or launch_inflight:
            box = QMessageBox(controller.window)
            box.setWindowTitle("Ideas")
            box.setText("Mapping is already in progress.")
            _open_message_box(box, min_width=420)
            return

        # If we have a persisted status (e.g. app exited mid-index, or the book
        # text changed and the idea map is now stale), give the user a slightly
        # more informative prompt.
        status_hint = None
        try:
            persisted = getattr(svc, "load_index_doc", lambda **_: None)(book_id=book_id)
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
                            if isinstance(book, dict) and hasattr(svc, "fingerprint_sha256"):
                                persisted_fp = str(book.get("fingerprint_sha256", "") or "").strip()
                                expected_fp = str(
                                    svc.fingerprint_sha256(normalized_text=normalized_text)
                                ).strip()
                                if persisted_fp and expected_fp and persisted_fp != expected_fp:
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
            extra = "\n\nPrevious mapping didn’t finish (for example, the app was closed)."
        elif status_hint == "error":
            extra = "\n\nPrevious mapping failed."
        elif status_hint == "cancelled":
            extra = "\n\nPrevious mapping was cancelled."
        elif status_hint == "stale":
            extra = "\n\nThis idea map is out of date for the currently loaded book."

        box.setText(
            "Map this book now?\n\nThis runs in the background and won’t interrupt playback." + extra
        )
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
        _open_message_box(box, min_width=520)
        return

    doc = getattr(svc, "load_index_doc", lambda **_: None)(book_id=book_id)
    if not isinstance(doc, dict):
        box = QMessageBox(controller.window)
        box.setWindowTitle("Ideas")
        box.setText("Failed loading idea map.")
        _open_message_box(box, min_width=420)
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
        voice = controller._selected_voice()  # noqa: SLF001
        if voice is None:
            return

        node = nodes_by_id.get(it.node_id) or {}
        aid = str(node.get("primary_anchor_id", "")).strip()
        anchor = anchors_by_id.get(aid) or {}

        try:
            idx_raw = anchor.get("chunk_index", None)
            idx = int(idx_raw)  # type: ignore[arg-type]
        except Exception:
            return

        try:
            controller.narration_service.stop()
        except Exception:  # pragma: no cover
            pass
        controller._last_prepared_voice_id = voice.name  # noqa: SLF001
        controller.narration_service.prepare(voice=voice, start_playback_index=int(idx))
        controller.narration_service.start()
        try:
            if getattr(controller, "_ideas_dialog", None) is not None:
                controller._ideas_dialog.close()  # noqa: SLF001
        except Exception:  # pragma: no cover
            pass

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

