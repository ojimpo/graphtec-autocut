"""Rectangle layout (bin packing) for graphtec-autocut.

v1 uses a self-implemented Shelf First-Fit-Decreasing-Height (FFDH) packer,
which the design memo lists as an acceptable alternative to rectpack. The
public entry point is `pack()`; a future rectpack-backed implementation can be
slotted behind the same signature without touching callers.

Coordinate system: x runs across the sheet width (0..sheet.width), y runs along
the sheet length and grows downward (top of sheet = y 0), matching SVG.
"""
from __future__ import annotations

from .models import LayoutResult, Piece, Placement, Sheet

_EPS = 1e-9


def _oriented(p: Piece, allow_rotate: bool, sheet_width: float) -> tuple[float, float, bool]:
    """Choose (w, h, rotated) for a piece.

    With rotation allowed we lay each piece flat (wide and short: w=long side,
    h=short side) which minimises the length each shelf consumes. If that does
    not fit the sheet width we fall back to the standing orientation.
    """
    w, h = p.w, p.h
    rotated = False
    if allow_rotate:
        # lay flat: maximise width, minimise height
        if h > w:
            w, h, rotated = h, w, True
        # but if the flat width overflows the sheet, stand it up instead
        if w > sheet_width + _EPS and h <= sheet_width + _EPS:
            w, h, rotated = h, w, not rotated
    return w, h, rotated


def pack(
    pieces: list[Piece],
    sheet: Sheet,
    *,
    gap: float = 2.0,
    allow_rotate: bool = True,
) -> LayoutResult:
    """Pack `pieces` (already expanded to one Piece per physical part) onto `sheet`.

    `gap` is the spacing in mm left between pieces and between shelves to account
    for blade offset and cut precision.
    """
    prepared: list[tuple[Piece, float, float, bool]] = []
    unplaced: list[Piece] = []
    for p in pieces:
        w, h, rotated = _oriented(p, allow_rotate, sheet.width)
        if w > sheet.width + _EPS:
            unplaced.append(p)  # too wide even rotated
            continue
        prepared.append((p, w, h, rotated))

    # First-Fit-Decreasing-Height: tallest shelves first.
    prepared.sort(key=lambda t: -t[2])

    placements: list[Placement] = []
    shelf_y = 0.0       # top of the current shelf
    shelf_x = 0.0       # next free x within the current shelf
    shelf_h = 0.0       # height of the current (tallest piece) shelf
    for p, w, h, rotated in prepared:
        step = w if shelf_x == 0.0 else gap + w
        if shelf_x + step <= sheet.width + _EPS:
            x = shelf_x if shelf_x == 0.0 else shelf_x + gap
        else:
            # open a new shelf below the current one
            shelf_y = shelf_y + shelf_h + (gap if shelf_h > 0.0 else 0.0)
            shelf_x = 0.0
            shelf_h = 0.0
            x = 0.0
        placements.append(Placement(p, x, shelf_y, w, h, rotated=rotated))
        shelf_x = x + w
        shelf_h = max(shelf_h, h)

    used_length = shelf_y + shelf_h

    # Flag overflow against a fixed-length sheet (rolls have length=None).
    if sheet.length is not None:
        for pl in placements:
            if pl.y + pl.h > sheet.length + _EPS:
                pl.overflow = True

    return LayoutResult(
        sheet=sheet,
        placements=placements,
        unplaced=unplaced,
        used_length=used_length,
    )
