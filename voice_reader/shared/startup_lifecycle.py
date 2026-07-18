"""What the application does on the way in and on the way out.

Both halves are best-effort by design. A failure while shutting down must not
stop the rest of the shutdown, and a failure while warming the speech model
must not reach the user at all: the warm-up is an optimisation, and the app
works without it.

Collaborators arrive as arguments rather than imports, so this stays in the
shared layer without reaching up into the application layer above it.
"""

from __future__ import annotations

import threading
from typing import Callable

_WARMUP_THREAD_NAME = "tts-startup-warmup"


def shutdown(controller, narration_service, *, log) -> None:  # noqa: ANN001
    """Stop narration and let the controller settle, whatever goes wrong.

    Each step is guarded on its own so that one failure does not skip the
    steps after it. Losing the resume position because indexing raised first
    would be a poor trade.
    """

    try:
        controller.on_app_exit()
    except Exception:
        log.exception("Failed stopping Ideas indexing on app exit")

    try:
        narration_service.on_app_exit()
    except Exception:
        log.exception("Failed saving resume position on app exit")

    try:
        narration_service.stop()
    except Exception:
        log.exception("Failed stopping narration")


def warm_up_tts(voice_service, narration_service, *, log) -> None:  # noqa: ANN001
    """Load the speech model so the first Play is not the slow one.

    Emits SYNTHESIZING then IDLE, so the progress bar shows the work rather
    than the app appearing to hang on first use.
    """

    try:
        voices = voice_service.list_profiles()
        if not voices:
            return
        narration_service.startup_warmup(voices[0])
    except Exception:
        log.debug("Startup TTS warmup failed", exc_info=True)


def start_tts_warmup(
    voice_service,  # noqa: ANN001
    narration_service,  # noqa: ANN001
    *,
    log,  # noqa: ANN001
    spawn: Callable[..., threading.Thread] = threading.Thread,
) -> threading.Thread:
    """Run the warm-up on a daemon thread so startup is not held up by it."""

    thread = spawn(
        target=lambda: warm_up_tts(voice_service, narration_service, log=log),
        name=_WARMUP_THREAD_NAME,
        daemon=True,
    )
    thread.start()
    return thread
