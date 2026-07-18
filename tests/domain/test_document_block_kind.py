"""Tests for block-kind display/narration policy."""

from __future__ import annotations

import pytest

from voice_reader.domain.document.block_kind import BlockKind


@pytest.mark.parametrize(
    "kind",
    [
        BlockKind.HEADING,
        BlockKind.PARAGRAPH,
        BlockKind.LIST_ITEM,
        BlockKind.BLOCK_QUOTE,
        BlockKind.CODE,
    ],
)
def test_body_kinds_are_displayed(kind: BlockKind) -> None:
    assert kind.is_displayed is True


@pytest.mark.parametrize(
    "kind",
    [
        BlockKind.TOC_ENTRY,
        BlockKind.PAGE_NUMBER,
        BlockKind.RUNNING_HEAD,
        BlockKind.SEPARATOR,
    ],
)
def test_artefact_kinds_are_not_displayed(kind: BlockKind) -> None:
    assert kind.is_displayed is False


@pytest.mark.parametrize(
    "kind",
    [
        BlockKind.HEADING,
        BlockKind.PARAGRAPH,
        BlockKind.LIST_ITEM,
        BlockKind.BLOCK_QUOTE,
    ],
)
def test_prose_kinds_are_spoken(kind: BlockKind) -> None:
    assert kind.is_spoken is True


@pytest.mark.parametrize(
    "kind",
    [
        BlockKind.CODE,
        BlockKind.TOC_ENTRY,
        BlockKind.PAGE_NUMBER,
        BlockKind.RUNNING_HEAD,
        BlockKind.SEPARATOR,
    ],
)
def test_non_prose_kinds_are_not_spoken(kind: BlockKind) -> None:
    assert kind.is_spoken is False


def test_code_is_displayed_but_not_spoken() -> None:
    # The two questions are independent; code is the case that proves it.
    assert BlockKind.CODE.is_displayed is True
    assert BlockKind.CODE.is_spoken is False


def test_every_spoken_kind_is_also_displayed() -> None:
    # Narrating something the reader cannot see would break highlighting.
    for kind in BlockKind:
        if kind.is_spoken:
            assert kind.is_displayed, f"{kind} is spoken but not displayed"
