"""Every source install carries the spaCy model misaki needs (round 3, N-8).

misaki downloads `en_core_web_sm` at the first synthesis when it is missing,
which breaks the promise that reading makes no network call and fails offline.
The Linux requirements file, the one LINUX-INSTALLATION.md names, lacked it.
The Flatpak is not a source install: its manifest bundles the model itself.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]

_SOURCE_INSTALLS = (
    "requirements.txt",
    "requirements-mac.txt",
    "requirements-linux.txt",
)

_MODEL_LINE = re.compile(
    r"^en[-_]core[-_]web[-_]sm @ https://github\.com/explosion/spacy-models/"
    r"releases/download/en_core_web_sm-[\d.]+/en_core_web_sm-[\d.]+-py3-none-any\.whl$",
    re.MULTILINE,
)


@pytest.mark.parametrize("name", _SOURCE_INSTALLS)
def test_the_spacy_model_is_installed_with_the_requirements(name: str) -> None:
    text = (_ROOT / name).read_text(encoding="utf-8")

    assert _MODEL_LINE.search(text), f"{name} does not install en_core_web_sm"
