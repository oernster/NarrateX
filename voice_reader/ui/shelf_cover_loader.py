"""Reading covers for the tiles on screen, off the thread that draws them.

A cover costs from 1.3 ms for a Kindle header to 55 ms for a rastered PDF page.
Twenty of the second kind on the thread that paints is a window that stops
answering, so the reads happen on one worker and each finished picture is
announced back on the Qt thread (FR-BS-038).

**One worker, not a pool.** The work is a disk read, which a second thread does
not make faster; one worker means the cover service is touched from exactly
one place besides the Qt thread.

**The queue is the visible screenful, not the collection.** A work asked for
while a reader scrolls past it is still queued, so the queue is bounded by what
was asked for rather than by the shelf's size; asking twice for the same work
while it waits costs nothing.
"""

from __future__ import annotations

import queue
import threading

from PySide6.QtCore import QObject, Signal

from voice_reader.domain.shelf.works import Work

# How long the worker waits for the next request before looking at the stop flag
# again. Short enough that closing the shelf is immediate, long enough that an
# idle shelf costs nothing.
_WAIT_SECONDS = 0.2


class ShelfCoverLoader(QObject):
    """Asks the cover service for pictures, one at a time, in the background."""

    picture_ready = Signal(str)

    def __init__(self, covers, *, parent=None) -> None:
        super().__init__(parent)
        self._covers = covers
        self._queue: queue.Queue[Work | None] = queue.Queue()
        self._wanted: set[str] = set()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def want(self, work: Work) -> None:
        """Ask for this work's picture, unless it is already asked for."""

        if self._covers is None or self._stop.is_set():
            return
        token = work.token
        with self._lock:
            if token in self._wanted:
                return
            self._wanted.add(token)
        self._queue.put(work)
        self._ensure_running()

    def stop(self) -> None:
        """Ask the worker to finish, without waiting on the disk read in flight."""

        self._stop.set()
        self._queue.put(None)
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=_WAIT_SECONDS)

    # Internals ------------------------------------------------------------

    def _ensure_running(self) -> None:
        thread = self._thread
        if thread is not None and thread.is_alive():
            return
        self._thread = threading.Thread(
            target=self._work, name="shelf-covers", daemon=True
        )
        self._thread.start()

    def _work(self) -> None:
        while not self._stop.is_set():
            try:
                work = self._queue.get(timeout=_WAIT_SECONDS)
            except queue.Empty:
                return
            if work is None:
                return
            self._one(work)

    def _one(self, work: Work) -> None:
        """One picture, announced whether it was found or not.

        A miss is announced too: the tile has nothing new to draw, yet the model
        must drop the request so a later scroll past the same work does not queue
        it forever.
        """

        try:
            self._covers.thumbnail(work)
        except Exception:  # noqa: BLE001
            # Deliberately broad; deliberately not re-raised on a worker
            # whose death would leave every later tile blank with nothing said.
            # The cover service already treats an unreadable file as no picture,
            # so reaching here means something rarer; the tile keeps its
            # placeholder and the shelf carries on.
            pass
        finally:
            with self._lock:
                self._wanted.discard(work.token)
        self.picture_ready.emit(work.token)
