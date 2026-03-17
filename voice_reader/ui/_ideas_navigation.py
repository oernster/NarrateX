from __future__ import annotations

from typing import Any


def go_to_idea(
    controller: Any,
    *,
    book_id: str,
    item,
    nodes_by_id: dict[str, dict],
    anchors_by_id: dict[str, dict],
    log,
    qtimer,
) -> None:
    """Navigate playback to a selected idea item (best-effort).

    This is UI-layer orchestration:
    - avoid stopping immediately; request graceful stop at next chunk boundary
    - fall back to forced stop after a grace period
    - restart playback from a stable position (prefer absolute char offset)
    """

    voice = controller._selected_voice()  # noqa: SLF001
    if voice is None:
        return

    node = nodes_by_id.get(item.node_id) or {}
    anchor_id = str(node.get("primary_anchor_id", "")).strip()
    anchor = anchors_by_id.get(anchor_id) or {}

    # Prefer stable absolute char offsets for navigation.
    # Persisted chunk_index is not stable across runtime candidate filtering.
    try:
        off_raw = anchor.get("char_offset", None)
        char_offset = int(off_raw)  # type: ignore[arg-type]
    except Exception:
        char_offset = None

    chunk_index: int | None = None
    if char_offset is None:
        try:
            idx_raw = anchor.get("chunk_index", None)
            chunk_index = int(idx_raw)  # type: ignore[arg-type]
        except Exception:
            return

    try:
        log.info(
            "Ideas GoTo: book_id=%s node_id=%s label=%r "
            "anchor_id=%s char_offset=%s chunk_index=%s voice=%s",
            book_id,
            item.node_id,
            item.label,
            anchor_id or None,
            char_offset,
            chunk_index,
            getattr(voice, "name", None),
        )
    except Exception:  # pragma: no cover
        pass

    controller._last_prepared_voice_id = voice.name  # noqa: SLF001

    def _thread_alive() -> bool:
        try:
            t = getattr(controller.narration_service, "_play_thread", None)
            return bool(t is not None and t.is_alive())
        except Exception:
            return False

    # Remember the most recent queued jump; last-click wins.
    token = object()
    try:
        controller._ideas_goto_token = (  # type: ignore[attr-defined]  # noqa: SLF001
            token
        )
    except Exception:  # pragma: no cover
        pass

    def _still_latest() -> bool:
        try:
            return (
                getattr(controller, "_ideas_goto_token", None) is token
            )  # noqa: SLF001
        except Exception:
            return True

    def _set_wait_ui(message: str | None) -> None:
        try:
            if hasattr(controller.window, "lbl_status") and message:
                controller.window.lbl_status.setText(str(message))
        except Exception:
            pass
        try:
            if hasattr(controller.window, "progress"):
                if message:
                    controller.window.progress.setRange(0, 0)
                else:
                    controller.window.progress.setRange(0, 100)
        except Exception:
            pass

    def _prepare_and_start() -> None:
        if not _still_latest():
            return

        try:
            # Stop right before we restart, so we don't fight the audio streamer.
            try:
                controller.narration_service.stop(persist_resume=False)
            except Exception:  # pragma: no cover
                try:
                    log.exception("Ideas GoTo: stop() failed")
                except Exception:
                    pass

            if char_offset is not None:
                # IMPORTANT: use force_start_char so chunking begins at the target.
                controller.narration_service.prepare(
                    voice=voice,
                    start_char_offset=int(char_offset),
                    force_start_char=int(char_offset),
                    skip_essay_index=False,
                    persist_resume=False,
                )
            else:
                if chunk_index is None:  # pragma: no cover
                    return
                controller.narration_service.prepare(
                    voice=voice,
                    start_playback_index=int(chunk_index),
                )

            log.info("Ideas GoTo: prepare complete; starting playback")
            controller.narration_service.start()
        except Exception:  # pragma: no cover
            try:
                log.exception("Ideas GoTo: prepare/start failed")
            except Exception:
                pass
            return

        _set_wait_ui(None)

        try:
            if getattr(controller, "_ideas_dialog", None) is not None:
                controller._ideas_dialog.close()  # noqa: SLF001
        except Exception:  # pragma: no cover
            pass

    def _wait_then_start(*, ticks: int, force_stop_at: int) -> None:
        if not _still_latest():
            return

        if not _thread_alive():
            _prepare_and_start()
            return

        # Request graceful stop once at the beginning.
        if int(ticks) == 0:
            try:
                if hasattr(
                    controller.narration_service, "request_stop_after_current_chunk"
                ):
                    controller.narration_service.request_stop_after_current_chunk()
            except Exception:  # pragma: no cover
                pass

        # After a grace period, fall back to an interrupting stop.
        if int(ticks) >= int(force_stop_at):
            try:
                log.warning("Ideas GoTo: grace period elapsed; forcing stop()")
            except Exception:  # pragma: no cover
                pass
            try:
                controller.narration_service.stop(persist_resume=False)
            except Exception:  # pragma: no cover
                pass

        try:
            log.info(
                "Ideas GoTo: waiting for stop (ticks=%s force_stop_at=%s)",
                int(ticks),
                int(force_stop_at),
            )
        except Exception:  # pragma: no cover
            pass

        _set_wait_ui(f"Please wait… jumping to '{item.label}'")

        single_shot = getattr(qtimer, "singleShot", None)
        if callable(single_shot):
            single_shot(
                200,
                lambda: _wait_then_start(
                    ticks=int(ticks) + 1,
                    force_stop_at=int(force_stop_at),
                ),
            )

    _wait_then_start(ticks=0, force_stop_at=10)
    # Keep the dialog open while waiting so the user can see what's happening.
