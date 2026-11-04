"""The payload is built and unpacked on every core; it lands the same on one."""

from __future__ import annotations

import hashlib
import io
import os
import threading
import zipfile
from pathlib import Path

import pytest

from installer import zip_writer
from installer.build_payload import write_payload
from installer.ops import cores
from installer.ops.parallel_extract import extract_members, split_by_size
from installer.ops.staging import extract_payload_to

# Sizes spread so the largest-first scheduling has something to reorder; one
# member spans several extraction chunks.
_SIZES = {
    "NarrateX.exe": 3000,
    "_internal/base_library.zip": 70_000,
    "_internal/torch/lib/torch_cpu.dll": 9 * 1024 * 1024,
    "_internal/PySide6/Qt6Core.dll": 250_000,
    "_internal/espeak/voices/café.txt": 12,
    "_internal/empty.txt": 0,
}
_MANY_THREADS = 4


def _bundle(root: Path) -> Path:
    for name, size in _SIZES.items():
        path = root / "bundle" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        seed = hashlib.sha256(name.encode()).digest()
        path.write_bytes((seed * (size // len(seed) + 1))[:size])
    return root / "bundle"


def _contents(root: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(root)).replace("\\", "/"): p.read_bytes()
        for p in root.rglob("*")
        if p.is_file()
    }


@pytest.fixture
def bundle(tmp_path: Path) -> Path:
    return _bundle(tmp_path)


class TestBuild:
    def test_one_thread_and_many_write_the_same_bytes(
        self, bundle: Path, tmp_path: Path
    ) -> None:
        one = tmp_path / "one.zip"
        many = tmp_path / "many.zip"
        write_payload(bundle, one, workers=1)
        write_payload(bundle, many, workers=_MANY_THREADS)
        assert one.read_bytes() == many.read_bytes()

    def test_zipfile_reads_every_member_back_as_lzma(
        self, bundle: Path, tmp_path: Path
    ) -> None:
        payload = tmp_path / "payload.zip"
        write_payload(bundle, payload, workers=_MANY_THREADS)
        with zipfile.ZipFile(payload) as zf:
            assert zf.testzip() is None
            assert {i.compress_type for i in zf.infolist()} == {zipfile.ZIP_LZMA}
            assert {i.filename: zf.read(i) for i in zf.infolist()} == _contents(bundle)

    def test_members_are_in_sorted_order(self, bundle: Path, tmp_path: Path) -> None:
        payload = tmp_path / "payload.zip"
        write_payload(bundle, payload, workers=_MANY_THREADS)
        with zipfile.ZipFile(payload) as zf:
            names = zf.namelist()
        assert names == sorted(names)

    def test_the_manifest_hashes_what_was_written(
        self, bundle: Path, tmp_path: Path
    ) -> None:
        entries = write_payload(bundle, tmp_path / "p.zip", workers=_MANY_THREADS)
        expected = _contents(bundle)
        assert {e.path: e.size for e in entries} == {
            k: len(v) for k, v in expected.items()
        }
        for e in entries:
            assert e.sha256 == hashlib.sha256(expected[e.path]).hexdigest()

    def test_a_non_ascii_name_is_flagged_utf8(
        self, bundle: Path, tmp_path: Path
    ) -> None:
        payload = tmp_path / "payload.zip"
        write_payload(bundle, payload, workers=1)
        with zipfile.ZipFile(payload) as zf:
            flags = {i.filename: i.flag_bits for i in zf.infolist()}
        assert flags["_internal/espeak/voices/café.txt"] & 0x800
        assert not flags["NarrateX.exe"] & 0x800


class TestClassicLimits:
    def test_a_member_past_the_classic_limit_is_refused(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(zip_writer, "CLASSIC_SIZE_LIMIT", 10)
        member = zip_writer.PackedMember("big", 11, 0, "", b"x")
        with pytest.raises(ValueError, match="ZIP64"):
            zip_writer.write_zip(io.BytesIO(), [member])

    def test_too_many_members_are_refused(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(zip_writer, "CLASSIC_COUNT_LIMIT", 1)
        members = [zip_writer.PackedMember(n, 0, 0, "", b"") for n in "ab"]
        with pytest.raises(ValueError, match="ZIP64"):
            zip_writer.write_zip(io.BytesIO(), members)


class TestExtract:
    @pytest.mark.parametrize("workers", [1, _MANY_THREADS])
    def test_every_file_lands_intact(
        self, bundle: Path, tmp_path: Path, workers: int
    ) -> None:
        payload = tmp_path / "payload.zip"
        write_payload(bundle, payload, workers=_MANY_THREADS)
        staging = tmp_path / f"staging{workers}"

        extract_payload_to(staging, zip_path=payload, workers=workers)

        assert _contents(staging) == _contents(bundle)

    def test_progress_still_only_rises_across_threads(
        self, bundle: Path, tmp_path: Path
    ) -> None:
        payload = tmp_path / "payload.zip"
        write_payload(bundle, payload, workers=1)
        seen: list[int] = []

        extract_payload_to(
            tmp_path / "staging",
            zip_path=payload,
            workers=_MANY_THREADS,
            progress=lambda p: seen.append(p["pct"]),
        )

        assert len(seen) > 2
        assert seen == sorted(seen)

    def test_a_cancel_mid_way_stops_every_thread(
        self, bundle: Path, tmp_path: Path
    ) -> None:
        payload = tmp_path / "payload.zip"
        write_payload(bundle, payload, workers=1)
        cancel = threading.Event()

        def cancel_on_first_report(_payload) -> None:  # noqa: ANN001
            cancel.set()

        with pytest.raises(Exception, match="Cancelled"):
            extract_payload_to(
                tmp_path / "staging",
                zip_path=payload,
                workers=_MANY_THREADS,
                progress=cancel_on_first_report,
                cancel_event=cancel,
            )

    def test_a_failing_thread_fails_the_extraction(
        self, bundle: Path, tmp_path: Path
    ) -> None:
        payload = tmp_path / "payload.zip"
        write_payload(bundle, payload, workers=1)
        with zipfile.ZipFile(payload) as zf:
            members = zf.infolist()
        out = tmp_path / "out"
        out.mkdir()
        targets = {m.filename: out / f"{i}.bin" for i, m in enumerate(members)}
        # A folder where a file must go: opening it for writing fails.
        blocked = max(members, key=lambda m: m.file_size).filename
        targets[blocked].mkdir()

        with pytest.raises(OSError):
            extract_members(payload, members, targets, workers=_MANY_THREADS)


class TestShares:
    def _members(self, sizes: list[int]) -> list[zipfile.ZipInfo]:
        members = []
        for index, size in enumerate(sizes):
            info = zipfile.ZipInfo(f"m{index}")
            info.file_size = size
            members.append(info)
        return members

    def test_shares_balance_bytes_largest_first(self) -> None:
        shares = split_by_size(self._members([9, 5, 4, 3, 3]), 2)
        assert sorted(sum(m.file_size for m in s) for s in shares) == [12, 12]

    def test_never_more_shares_than_members(self) -> None:
        assert len(split_by_size(self._members([1, 2]), 8)) == 2

    def test_no_members_still_makes_one_share(self) -> None:
        assert split_by_size([], 8) == [[]]


class TestCores:
    def test_at_least_one(self) -> None:
        assert cores.usable_cores() >= 1

    def test_an_unknown_count_falls_back_to_one(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delattr(os, "process_cpu_count", raising=False)
        monkeypatch.setattr(os, "cpu_count", lambda: None)
        assert cores.usable_cores() == 1
