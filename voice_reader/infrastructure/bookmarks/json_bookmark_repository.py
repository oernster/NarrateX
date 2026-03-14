"""JSON-backed bookmark persistence.

File format per book:

{
  "resume": {"char_offset": 1, "chunk_index": 0, "updated_at": "..."} | null,
  "bookmarks": [
     {"bookmark_id": 1, "name": "Bookmark 1", ...}
  ]
}

Rules:
- Missing file is treated as empty.
- Writes are atomic via write-to-temp then replace.
- Manual bookmarks are sorted by bookmark_id.
- Bookmark IDs are monotonically increasing and never reused.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from voice_reader.domain.entities.bookmark import Bookmark, ResumePosition
from voice_reader.domain.interfaces.bookmark_repository import BookmarkRepository


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _safe_int(value: object, default: int) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except Exception:  # noqa: BLE001
        return int(default)


def _touch_coverage() -> None:  # pragma: no cover
    # Intentionally unused helper reserved for future migrations.
    return


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

    def _load_doc(self, *, book_id: str) -> dict:
        path = self._path_for(book_id=book_id)
        if not path.exists():
            return {"resume": None, "bookmarks": [], "next_bookmark_id": 1}

        try:
            raw = path.read_text(encoding="utf-8")
        except Exception:  # noqa: BLE001
            return {"resume": None, "bookmarks": [], "next_bookmark_id": 1}

        try:
            doc = json.loads(raw) if raw.strip() else {}
        except Exception:  # noqa: BLE001
            return {"resume": None, "bookmarks": [], "next_bookmark_id": 1}

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
        self.bookmarks_dir.mkdir(parents=True, exist_ok=True)
        path = self._path_for(book_id=book_id)
        tmp = path.with_suffix(path.suffix + ".tmp")
        text = json.dumps(doc, indent=2, sort_keys=False)
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(path)

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
        doc = self._load_doc(book_id=book_id)
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
        doc = self._load_doc(book_id=book_id)
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
        doc = self._load_doc(book_id=book_id)
        doc["resume"] = {
            "char_offset": int(char_offset),
            "chunk_index": int(chunk_index),
            "updated_at": _dt_to_iso_z(_utcnow()),
        }
        if "bookmarks" not in doc or not isinstance(doc.get("bookmarks"), list):
            doc["bookmarks"] = []
        self._write_doc(book_id=book_id, doc=doc)
