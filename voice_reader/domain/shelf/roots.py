"""Which folders the shelf watches; how a new one joins them.

FR-BS-001a to FR-BS-001c. A rule rather than a setting, because the mistake it
prevents is one the reference library invites: `H:\\Books\\FIXED\\uncatalogued`
sits inside `H:\\Books`, so nominating both would walk 716 files twice and put
every one of them on the shelf as a second entry.
"""

from __future__ import annotations

from pathlib import Path


def normalised(root: Path) -> Path:
    """The form two roots are compared in.

    Only the spelling is settled here. Whether the folder exists is a question
    for the code that can look; a root that has gone missing is still a root
    (FR-BS-007).
    """

    return Path(str(root).replace("\\", "/").rstrip("/") or str(root))


def contains(parent: Path, child: Path) -> bool:
    """True when `child` is `parent` itself or sits somewhere beneath it."""

    first, second = normalised(parent), normalised(child)
    if first == second:
        return True
    try:
        second.relative_to(first)
    except ValueError:
        return False
    return True


def covering(roots: tuple[Path, ...], candidate: Path) -> Path | None:
    """The existing root that already covers `candidate`; None when none does."""

    for root in roots:
        if contains(root, candidate):
            return root
    return None


def covered_by(roots: tuple[Path, ...], candidate: Path) -> tuple[Path, ...]:
    """The existing roots that `candidate` would swallow."""

    return tuple(root for root in roots if contains(candidate, root))


def added(roots: tuple[Path, ...], candidate: Path) -> tuple[Path, ...]:
    """The roots after adding `candidate`.

    A candidate already covered changes nothing; the caller is expected to say
    so rather than leaving the reader wondering why their choice vanished. A
    candidate that covers existing roots replaces them, since keeping both
    would walk the same files twice.
    """

    if covering(roots, candidate) is not None:
        return roots
    swallowed = covered_by(roots, candidate)
    kept = tuple(root for root in roots if root not in swallowed)
    return kept + (normalised(candidate),)


def removed(roots: tuple[Path, ...], unwanted: Path) -> tuple[Path, ...]:
    """The roots after removing one, compared on the settled spelling."""

    target = normalised(unwanted)
    return tuple(root for root in roots if normalised(root) != target)
