"""Core data models for graphtec-autocut Phase 1.

All dimensions are in millimetres (mm), matching the cutter's native units.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Piece:
    """A rectangular piece to cut. `w`/`h` are the dimensions as read from input.

    For the company sheet the input columns are 短辺 (short side) -> w and
    長辺 (long side) -> h, but the layout engine may rotate pieces freely when
    rotation is allowed, so do not assume w<=h downstream.
    """

    name: str
    w: float
    h: float
    qty: int = 1
    group: str = ""        # e.g. Const column: Front / Mount / Rear ...
    shape: str = ""        # e.g. 形状 column: 短冊 / 短冊切り欠き (notch ignored in v1)
    inst: int = 0          # instance index when a piece with qty>1 is expanded


@dataclass
class Placement:
    """A piece placed on the sheet. (x, y) is the top-left corner in mm,
    (w, h) the placed dimensions (already rotated if `rotated`)."""

    piece: Piece
    x: float
    y: float
    w: float
    h: float
    rotated: bool = False
    overflow: bool = False  # placed beyond the sheet length limit


@dataclass
class Sheet:
    """Material sheet. `length` is None for a roll (length auto-computed)."""

    width: float = 350.0           # effective cut width of CE5000-40-CRP (~350mm)
    length: float | None = None    # None => roll, grow as needed


@dataclass
class LayoutResult:
    sheet: Sheet
    placements: list[Placement] = field(default_factory=list)
    unplaced: list[Piece] = field(default_factory=list)
    used_length: float = 0.0

    @property
    def overflowed(self) -> bool:
        return any(p.overflow for p in self.placements)
