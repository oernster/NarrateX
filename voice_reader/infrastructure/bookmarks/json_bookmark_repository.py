"""JSON-backed bookmark persistence.

File format per book:

{
  "resume": {"char_offset": 1, "chunk_index": 0, "updated_at": "..."} | null,
  "bookmarks": [
     {"bookmark_id": 1, "name": "Bookmark 1", ...}
  ]
}

Rules:
- Missing file is treated as empty. A damaged or unreadable one reads as
  empty but is never saved over: a save keeps a damaged file aside under
  `<id>.json.damaged` (numbered when that name is taken) and refuses outright
  when the file cannot be read.
- Writes are atomic via write-to-temp then replace.
- Manual bookmarks are sorted by bookmark_id.
- Bookmark IDs are monotonically increasing and never reused.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from voice_reader.domain.entities.bookmark import Bookmark, ResumePosition
from voice_reader.domain.interfaces.bookmark_repository import BookmarkRepository
from voice_reader.infrastructure import json_document


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _safe_int(value: object, default: int) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except Exception:  # noqa: BLE001
        return int(default)


def _dt_to_iso_z(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    # Use "Z" suffix for readability.
    return dt.isoformat().replace("+00:00", "Z")


def _dt_from_iso(value: str) -> datetime:
    # Accept either "+00:00" or "Z".
    v = str(value).strip()
    if v.endswith("Z"):
        v = v[:-1] + "+00:00"
    return datetime.fromisoformat(v)


@dataclass(frozen=True, slots=True)
class JSONBookmarkRepository(BookmarkRepository):
    bookmarks_dir: Path

    def _path_for(self, *, book_id: str) -> Path:
        safe = str(book_id).strip()
        return self.bookmarks_dir / f"{safe}.json"

    def delete_book(self, *, book_id: str) -> None:
        """Delete every bookmark and the resume position for one book."""

        try:
            self._path_for(book_id=book_id).unlink(missing_ok=True)
        except Exception:  # noqa: BLE001
            return

    def carry_over(self, *, from_id: str, to_id: str) -> bool:
        """Move one book's record to a new id when the new id has none.

        True when a record moved. A record already under `to_id` wins, since
        it is the newer of the two.
        """

        source = self._path_for(book_id=from_id)
        target = self._path_for(book_id=to_id)
        if source == target or target.exists() or not source.is_file():
            return False
        source.rename(target)
        return True

    def keep_aside_if_damaged(self, *, book_id: str) -> Path | None:
        """Keep a damaged record aside and answer the kept copy; None when sound."""

        path = self._path_for(book_id=book_id)
        try:
            json_document.read_object(path)
        except json_document.DamagedDocumentError:
            return json_document.keep_aside(path)
        except OSError:
            return None
        return None

    def _load_doc(self, *, book_id: str) -> dict:
        """The record for reading: damaged or unreadable reads as empty.

        Reading never changes the file. Only a save decides what happens to a
        damaged one (see `_load_doc_for_update`).
        """

        try:
            doc = json_document.read_object(self._path_for(book_id=book_id))
        except (OSError, json_document.DamagedDocumentError):
            doc = None
        return self._normalised(doc or {})

    def _load_doc_for_update(self, *, book_id: str) -> dict:
        """The record a save changes; a damaged file is kept aside first."""

        path = self._path_for(book_id=book_id)
        return self._normalised(json_document.object_for_update(path))

    @staticmethod
    def _normalised(doc: dict) -> dict:
        resume = doc.get("resume")
        if resume is not None and not isinstance(resume, dict):
            resume = None

        bookmarks = doc.get("bookmarks")
        if not isinstance(bookmarks, list):
            bookmarks = []

        next_id = doc.get("next_bookmark_id", "")
        try:
            next_id_int = int(next_id)
        except Exception:  # noqa: BLE001
            next_id_int = 1
        next_id_int = max(1, next_id_int)

        # If the file predates the next_bookmark_id field, derive from max seen.
        max_existing = 0
        for item in bookmarks:
            if not isinstance(item, dict):
                continue
            try:
                max_existing = max(max_existing, int(item.get("bookmark_id", 0)))
            except Exception:  # noqa: BLE001
                continue
        next_id_int = max(next_id_int, max_existing + 1)

        return {
            "resume": resume,
            "bookmarks": bookmarks,
            "next_bookmark_id": next_id_int,
        }

    def _write_doc(self, *, book_id: str, doc: dict) -> None:
        json_document.write_object(self._path_for(book_id=book_id), doc)

    @staticmethod
    def _bookmark_from_dict(d: dict) -> Bookmark:
        return Bookmark(
            bookmark_id=int(d["bookmark_id"]),
            name=str(d["name"]),
            char_offset=int(d["char_offset"]),
            chunk_index=int(d["chunk_index"]),
            created_at=_dt_from_iso(str(d["created_at"])),
        )

    @staticmethod
    def _bookmark_to_dict(b: Bookmark) -> dict:
        return {
            "bookmark_id": int(b.bookmark_id),
            "name": str(b.name),
            "char_offset": int(b.char_offset),
            "chunk_index": int(b.chunk_index),
            "created_at": _dt_to_iso_z(b.created_at),
        }

    def list_bookmarks(self, *, book_id: str) -> list[Bookmark]:
        doc = self._load_doc(book_id=book_id)
        out: list[Bookmark] = []
        for item in doc["bookmarks"]:
            if not isinstance(item, dict):
                continue
            try:
                out.append(self._bookmark_from_dict(item))
            except Exception:  # noqa: BLE001
                continue
        out.sort(key=lambda b: b.bookmark_id)
        return out

    def add_bookmark(
        self,
        *,
        book_id: str,
        char_offset: int,
        chunk_index: int,
    ) -> Bookmark:
        doc = self._load_doc_for_update(book_id=book_id)
        next_id = int(doc.get("next_bookmark_id") or 1)
        next_id = max(1, next_id)
        bm = Bookmark(
            bookmark_id=next_id,
            name=f"Bookmark {next_id}",
            char_offset=int(char_offset),
            chunk_index=int(chunk_index),
            created_at=_utcnow(),
        )

        # Advance the monotonic counter (never reuse IDs).
        doc["next_bookmark_id"] = int(next_id) + 1
        bookmarks = [b for b in doc["bookmarks"] if isinstance(b, dict)]
        bookmarks.append(self._bookmark_to_dict(bm))

        # Ensure stable order.
        parsed = []
        for d in bookmarks:
            try:
                parsed.append(self._bookmark_from_dict(d))
            except Exception:  # noqa: BLE001
                continue
        parsed.sort(key=lambda b: b.bookmark_id)
        doc["bookmarks"] = [self._bookmark_to_dict(b) for b in parsed]
        self._write_doc(book_id=book_id, doc=doc)
        return bm

    def delete_bookmark(self, *, book_id: str, bookmark_id: int) -> None:
        doc = self._load_doc_for_update(book_id=book_id)
        kept: list[dict] = []
        for item in doc["bookmarks"]:
            if not isinstance(item, dict):
                continue
            try:
                raw_id = item.get("bookmark_id", "")
                if int(raw_id) == int(bookmark_id):
                    continue
            except Exception:  # noqa: BLE001
                pass
            kept.append(item)

        # Normalize + sort.
        parsed: list[Bookmark] = []
        for d in kept:
            try:
                parsed.append(self._bookmark_from_dict(d))
            except Exception:  # noqa: BLE001
                continue
        parsed.sort(key=lambda b: b.bookmark_id)
        doc["bookmarks"] = [self._bookmark_to_dict(b) for b in parsed]
        self._write_doc(book_id=book_id, doc=doc)

    def load_resume_position(self, *, book_id: str) -> ResumePosition | None:
        doc = self._load_doc(book_id=book_id)
        resume = doc.get("resume")
        if not isinstance(resume, dict):
            return None
        try:
            return ResumePosition(
                char_offset=int(resume["char_offset"]),
                chunk_index=int(resume["chunk_index"]),
                updated_at=_dt_from_iso(str(resume["updated_at"])),
            )
        except Exception:  # noqa: BLE001
            return None

    def save_resume_position(
        self,
        *,
        book_id: str,
        char_offset: int,
        chunk_index: int,
    ) -> None:
        doc = self._load_doc_for_update(book_id=book_id)
        doc["resume"] = {
            "char_offset": int(char_offset),
            "chunk_index": int(chunk_index),
            "updated_at": _dt_to_iso_z(_utcnow()),
        }
        if "bookmarks" not in doc or not isinstance(doc.get("bookmarks"), list):
            doc["bookmarks"] = []
        self._write_doc(book_id=book_id, doc=doc)
