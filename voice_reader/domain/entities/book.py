"""Domain entity: Book."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Book:
    id: str
    title: str
    raw_text: str
    normalized_text: str
