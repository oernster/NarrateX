from __future__ import annotations

import pytest

from installer.state.versioning import compare_versions, parse_version


def test_parse_version_invalid_falls_back_to_zero() -> None:
    pv = parse_version("not-a-version")
    assert str(pv.parsed) == "0.0.0"


@pytest.mark.parametrize(
    ("installer", "installed", "expected"),
    [
        ("1.0.0", "1.0.0", 0),
        ("1.0.1", "1.0.0", 1),
        ("1.0.0", "1.0.1", -1),
        ("1.0", "1.0.0", 0),
    ],
)
def test_compare_versions(installer: str, installed: str, expected: int) -> None:
    assert compare_versions(installer, installed) == expected
