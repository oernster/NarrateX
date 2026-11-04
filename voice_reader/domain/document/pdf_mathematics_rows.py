"""The rows of a rebuilt maths group and what stands on, over and under them.

`pdf_mathematics_layout` decides which blocks are rebuilt together. This
module takes the pieces of one such group and sorts out the geometry: which
pieces share a row, which small pieces are scripts of what, which stand over
or under a large operator as its limits and which rows are the halves of a
fraction. Each decision reads off the boxes the extractor reported.

Pure: every rule here is testable without opening a PDF.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from voice_reader.domain.document.pdf_mathematics import (
    BIG_OPERATORS,
    COMPOSITE_FONT,
    PdfSpan,
    abuts,
    fraction_text,
    render_group,
)

# Baselines within this fraction of the row's size are one row.
_ROW_TOLERANCE_RATIO = 0.3

# A piece whose box shares at least this fraction of the shorter height with
# a row's box is on that row whatever its baseline says: a ceiling bracket is
# drawn taller than its line and reports a baseline a few points below it.
_ROW_OVERLAP_RATIO = 0.5

# A row this close to another, in fractions of the size, can be its numerator
# or denominator. Lines of prose sit further apart than their size; the
# halves of a fraction sit nearer than it.
_STACK_REACH_RATIO = 0.95

# A limit stands within this many sizes of its operator's baseline.
_LIMIT_REACH_RATIO = 2.0

# A limit may overhang its operator by this fraction of the size either side.
_LIMIT_OVERHANG_RATIO = 0.5

# A script sits within this many of its base's sizes from the base's baseline.
_ATTACHMENT_REACH_RATIO = 1.0


@dataclass(slots=True)
class Row:
    """Working state while a group is rebuilt; never leaves the rebuild."""

    pieces: list[PdfSpan]
    extras: list[PdfSpan] = field(default_factory=list)

    @property
    def baseline(self) -> float:
        """The baseline of the widest piece: a fence may report its own."""

        return max(self.pieces, key=lambda p: p.right - p.left).baseline

    @property
    def top(self) -> float:
        return min(p.top for p in self.pieces)

    @property
    def bottom(self) -> float:
        return max(p.bottom for p in self.pieces)

    @property
    def all_pieces(self) -> list[PdfSpan]:
        return self.pieces + self.extras


def _on_row(row: Row, piece: PdfSpan, *, size: float) -> bool:
    if abs(piece.baseline - row.baseline) <= _ROW_TOLERANCE_RATIO * size:
        return True
    shared = min(piece.bottom, row.bottom) - max(piece.top, row.top)
    shorter = min(piece.bottom - piece.top, row.bottom - row.top)
    return shorter > 0 and shared >= _ROW_OVERLAP_RATIO * shorter


def rows_of(pieces: list[PdfSpan], *, size: float) -> list[Row]:
    """Cluster the row-sized pieces into rows, top to bottom."""

    rows: list[Row] = []
    for piece in sorted(pieces, key=lambda p: p.baseline):
        if rows and _on_row(rows[-1], piece, size=size):
            rows[-1].pieces.append(piece)
        else:
            rows.append(Row(pieces=[piece]))
    return rows


def _nearest_row(rows: list[Row], piece: PdfSpan) -> Row:
    return min(rows, key=lambda row: abs(row.baseline - piece.baseline))


def _attachment(rows: list[Row], piece: PdfSpan) -> tuple[Row, PdfSpan] | None:
    """What this piece is set hard against (with its row), if anything.

    A script starts where its base ends and a space where the word before it
    ends. That is stronger evidence of where a piece belongs than its
    baseline, which for a space the extractor reports anywhere at all.
    """

    best: tuple[float, Row, PdfSpan] | None = None
    for row in rows:
        for held in row.all_pieces:
            if held.text.isspace() or held.left > piece.left:
                continue
            if not abuts(held, piece):
                continue
            if (
                abs(held.baseline - piece.baseline)
                > _ATTACHMENT_REACH_RATIO * held.size
            ):
                continue
            # A script's box may overlap its base's by a point; what matters
            # is how near the two edges are, not which side the overlap falls.
            distance = abs(piece.left - held.right)
            if best is None or distance < best[0]:
                best = (distance, row, held)
    return None if best is None else (best[1], best[2])


def _is_operator(piece: PdfSpan) -> bool:
    return piece.text.strip() in BIG_OPERATORS


def _composite(text: str, pieces: list[PdfSpan], *, baseline: float, size: float):
    return PdfSpan(
        text=text,
        font=COMPOSITE_FONT,
        size=size,
        bold=any(p.bold for p in pieces),
        left=min(p.left for p in pieces),
        top=min(p.top for p in pieces),
        right=max(p.right for p in pieces),
        bottom=max(p.bottom for p in pieces),
        baseline=baseline,
    )


def _limit_target(
    rows: list[Row], script: PdfSpan, *, size: float
) -> tuple[Row, int] | None:
    """The operator this script stands over or under, if any; the nearest wins."""

    overhang = _LIMIT_OVERHANG_RATIO * size
    best: tuple[float, Row, int] | None = None
    for row in rows:
        for index, piece in enumerate(row.pieces):
            if not _is_operator(piece):
                continue
            distance = abs(piece.baseline - script.baseline)
            if distance > _LIMIT_REACH_RATIO * size:
                continue
            if script.left >= piece.right + overhang or script.right <= (
                piece.left - overhang
            ):
                continue
            if best is None or distance < best[0]:
                best = (distance, row, index)
    return None if best is None else (best[1], best[2])


def place_scripts(
    rows: list[Row], scripts: list[PdfSpan], spaces: list[PdfSpan], *, size: float
) -> None:
    """Give every script and space a row; fold each operator's limits into it.

    Larger scripts first, so a script of a script finds its base already
    placed. A script set hard against something belongs with it, unless that
    something is a large operator, whose scripts are its limits however near
    they stand; one standing free over or under a large operator is its limit
    too; anything else goes to the row whose baseline is nearest.
    """

    limits: dict[tuple[int, int], tuple[list[PdfSpan], list[PdfSpan]]] = {}
    for script in sorted(scripts, key=lambda p: -p.size):
        found = _attachment(rows, script)
        row = None if found is None else found[0]
        if found is None or _is_operator(found[1]):
            target = _limit_target(rows, script, size=size)
            if target is not None:
                row, index = target
                upper, lower = limits.setdefault((id(row), index), ([], []))
                operator = row.pieces[index]
                (upper if script.baseline < operator.baseline else lower).append(script)
                continue
        if row is None:
            row = _nearest_row(rows, script)
        row.extras.append(script)

    for space in spaces:
        found = _attachment(rows, space)
        row = _nearest_row(rows, space) if found is None else found[0]
        row.extras.append(space)

    for row in rows:
        for index, piece in enumerate(row.pieces):
            entry = limits.get((id(row), index))
            if entry is None:
                continue
            upper, lower = entry
            text = piece.text.strip()
            if lower:
                text += f"_{{{render_group(lower)}}}"
            if upper:
                text += f"^{{{render_group(upper)}}}"
            row.pieces[index] = _composite(
                f" {text} ", [piece, *upper, *lower], baseline=piece.baseline, size=size
            )


def _gaps(row: Row) -> list[tuple[float, float]]:
    """The open intervals of a row: before, between and after its pieces."""

    edges = sorted((p.left, p.right) for p in row.pieces)
    gaps = [(float("-inf"), edges[0][0])]
    for (_, right), (left, _) in zip(edges, edges[1:]):
        gaps.append((right, left))
    gaps.append((edges[-1][1], float("inf")))
    return gaps


def _within(row: Row, gap: tuple[float, float]) -> list[PdfSpan]:
    return [p for p in row.all_pieces if gap[0] <= p.centre <= gap[1]]


def _stack_in_gap(
    above: Row, below: Row, gap: tuple[float, float], *, size: float
) -> tuple[list[PdfSpan], list[PdfSpan]]:
    """The numerator and denominator standing in a gap of the main row.

    The pieces of both rows in the gap are joined into clusters wherever one
    stands within a size of the next. A gap closed at both ends holds one
    fraction, so it is all one cluster; a gap open at one end runs to the
    edge of the page, so only the cluster nearest its closed end is the
    fraction and anything further out stays where it was.
    """

    candidates = sorted(
        [(p, True) for p in _within(above, gap)]
        + [(p, False) for p in _within(below, gap)],
        key=lambda item: item[0].left,
    )
    clusters: list[list[tuple[PdfSpan, bool]]] = []
    reach = float("-inf")
    for piece, is_numerator in candidates:
        if piece.left > reach:
            clusters.append([])
        clusters[-1].append((piece, is_numerator))
        reach = max(reach, piece.right + size)
    if not clusters:
        return [], []
    open_left, open_right = gap[0] == float("-inf"), gap[1] == float("inf")
    if open_left and not open_right:
        clusters = clusters[-1:]
    elif open_right and not open_left:
        clusters = clusters[:1]
    chosen = [item for cluster in clusters for item in cluster]
    return (
        [p for p, is_numerator in chosen if is_numerator],
        [p for p, is_numerator in chosen if not is_numerator],
    )


def _remove(row: Row, pieces: list[PdfSpan]) -> None:
    row.pieces = [p for p in row.pieces if p not in pieces]
    row.extras = [p for p in row.extras if p not in pieces]


def _neighbour(rows: list[Row], row: Row, *, size: float, above: bool) -> Row | None:
    reach = _STACK_REACH_RATIO * size
    candidates = [
        other
        for other in rows
        if other.pieces
        and 0
        < (row.baseline - other.baseline if above else other.baseline - row.baseline)
        <= reach
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda other: abs(other.baseline - row.baseline))


def attach_fractions(rows: list[Row], *, size: float) -> None:
    """Fold each numerator and denominator into the row they stand beside.

    A fraction is a row just above and a row just below the main row, meeting
    in a gap the main row leaves for the bar. Everything the two rows hold in
    that gap is the fraction; what they hold elsewhere stays theirs.
    """

    for row in rows:
        if not row.pieces:
            continue
        above = _neighbour(rows, row, size=size, above=True)
        below = _neighbour(rows, row, size=size, above=False)
        if above is None or below is None:
            continue
        baseline = row.baseline
        for gap in _gaps(row):
            numerator, denominator = _stack_in_gap(above, below, gap, size=size)
            if not numerator or not denominator:
                continue
            text = fraction_text(render_group(numerator), render_group(denominator))
            row.pieces.append(
                _composite(
                    f" {text} ", numerator + denominator, baseline=baseline, size=size
                )
            )
            _remove(above, numerator)
            _remove(below, denominator)
