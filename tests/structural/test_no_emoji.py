"""Structural guard: the application source carries no emoji.

Every picture in the interface is shipped artwork from `voice_reader/ui/artwork`.
An emoji renders differently on each platform (boxed letters for the flags on
Windows, a colour glyph beside monochrome text elsewhere), which is what the
artwork refresh replaced. This keeps one from creeping back in, comments
included, since a comment naming a control by its emoji goes stale with it.
"""

from __future__ import annotations

from pathlib import Path

# Emoji and the pictographic symbol blocks the interface used to draw from.
_EMOJI_RANGES: tuple[tuple[int, int], ...] = (
    (0x1F000, 0x1FAFF),  # emoji, flags (regional indicators), pictographs
    (0x2600, 0x27BF),  # miscellaneous symbols, dingbats
    (0x2300, 0x23FF),  # miscellaneous technical (media transport glyphs)
    (0x25A0, 0x25FF),  # geometric shapes (play triangle, stop square)
    (0x2160, 0x216F),  # roman numerals (the pause glyph)
    (0x2139, 0x2139),  # information source
    (0xFE0F, 0xFE0F),  # emoji presentation selector
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _is_emoji(char: str) -> bool:
    code = ord(char)
    return any(low <= code <= high for low, high in _EMOJI_RANGES)


def emoji_offenders(root: Path) -> list[str]:
    offenders: list[str] = []
    for path in sorted((root / "voice_reader").rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        for number, line in enumerate(lines, start=1):
            found = [c for c in line if _is_emoji(c)]
            if found:
                rel = path.relative_to(root).as_posix()
                codes = " ".join(f"U+{ord(c):04X}" for c in found)
                offenders.append(f"{rel}:{number}: {codes}")
    return offenders


def test_application_source_has_no_emoji() -> None:
    offenders = emoji_offenders(_repo_root())
    assert not offenders, (
        "Emoji found in the application source. Use artwork from "
        "voice_reader/ui/artwork (see voice_reader/ui/artwork.py) instead:\n"
        + "\n".join(offenders)
    )
