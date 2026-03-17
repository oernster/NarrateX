from __future__ import annotations

from dataclasses import dataclass

from voice_reader.application.services.idea_map_service import IdeaMapService


@dataclass
class _FakeRepo:
    doc: dict | None

    def load_doc(self, *, book_id: str):
        del book_id
        return self.doc

    def save_doc_atomic(self, *, book_id: str, doc: dict) -> None:
        del book_id, doc


def test_has_completed_index_false_when_missing() -> None:
    svc = IdeaMapService(repo=_FakeRepo(doc=None))  # type: ignore[arg-type]
    assert svc.has_completed_index(book_id="b1") is False


def test_has_completed_index_false_when_schema_missing() -> None:
    svc = IdeaMapService(repo=_FakeRepo(doc={"status": {"state": "completed"}}))  # type: ignore[arg-type]
    assert svc.has_completed_index(book_id="b1") is False


def test_has_completed_index_false_when_status_missing() -> None:
    svc = IdeaMapService(repo=_FakeRepo(doc={"schema_version": 1}))  # type: ignore[arg-type]
    assert svc.has_completed_index(book_id="b1") is False


def test_has_completed_index_true_when_completed() -> None:
    svc = IdeaMapService(
        repo=_FakeRepo(doc={"schema_version": 1, "status": {"state": "completed"}})  # type: ignore[arg-type]
    )
    assert svc.has_completed_index(book_id="b1") is True


def test_has_completed_index_for_text_false_when_fingerprint_missing() -> None:
    svc = IdeaMapService(
        repo=_FakeRepo(
            doc={
                "schema_version": 1,
                "status": {"state": "completed"},
                "book": {"title": "T"},
            }
        )  # type: ignore[arg-type]
    )
    assert (
        svc.has_completed_index_for_text(book_id="b1", normalized_text="hello") is False
    )


def test_has_completed_index_for_text_false_when_book_section_missing() -> None:
    svc = IdeaMapService(
        repo=_FakeRepo(doc={"schema_version": 1, "status": {"state": "completed"}})  # type: ignore[arg-type]
    )
    assert (
        svc.has_completed_index_for_text(book_id="b1", normalized_text="hello") is False
    )


def test_has_completed_index_for_text_false_when_schema_invalid() -> None:
    svc = IdeaMapService(
        repo=_FakeRepo(
            doc={
                "schema_version": 0,
                "status": {"state": "completed"},
                "book": {"fingerprint_sha256": "x"},
            }
        )  # type: ignore[arg-type]
    )
    assert (
        svc.has_completed_index_for_text(book_id="b1", normalized_text="hello") is False
    )


def test_has_completed_index_for_text_false_when_status_not_dict() -> None:
    svc = IdeaMapService(
        repo=_FakeRepo(
            doc={
                "schema_version": 1,
                "status": "completed",
                "book": {"fingerprint_sha256": "x"},
            }
        )  # type: ignore[arg-type]
    )
    assert (
        svc.has_completed_index_for_text(book_id="b1", normalized_text="hello") is False
    )


def test_has_completed_index_for_text_false_when_status_not_completed() -> None:
    expected = IdeaMapService.fingerprint_sha256(normalized_text="hello")
    svc = IdeaMapService(
        repo=_FakeRepo(
            doc={
                "schema_version": 1,
                "status": {"state": "running"},
                "book": {"fingerprint_sha256": expected},
            }
        )  # type: ignore[arg-type]
    )
    assert (
        svc.has_completed_index_for_text(book_id="b1", normalized_text="hello") is False
    )


def test_has_completed_index_for_text_true_when_fingerprint_matches() -> None:
    expected = IdeaMapService.fingerprint_sha256(normalized_text="hello")
    svc = IdeaMapService(
        repo=_FakeRepo(
            doc={
                "schema_version": 1,
                "status": {"state": "completed"},
                "book": {"fingerprint_sha256": expected},
            }
        )  # type: ignore[arg-type]
    )
    assert (
        svc.has_completed_index_for_text(book_id="b1", normalized_text="hello") is True
    )


def test_has_completed_index_for_text_false_when_fingerprint_mismatch() -> None:
    svc = IdeaMapService(
        repo=_FakeRepo(
            doc={
                "schema_version": 1,
                "status": {"state": "completed"},
                "book": {"fingerprint_sha256": "deadbeef"},
            }
        )  # type: ignore[arg-type]
    )
    assert (
        svc.has_completed_index_for_text(book_id="b1", normalized_text="hello") is False
    )


def test_load_index_doc_roundtrips_repo_value() -> None:
    doc = {"schema_version": 1, "status": {"state": "completed"}}
    svc = IdeaMapService(repo=_FakeRepo(doc=doc))  # type: ignore[arg-type]
    assert svc.load_index_doc(book_id="b1") == doc
