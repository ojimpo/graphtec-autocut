"""GP-GL cut-path generation (Phase 2 entrance).

This module turns a LayoutResult into GP-GL plotter commands. It is written to
be fully testable WITHOUT the cutter: `generate()` produces the command string
and `parse_polylines()` reads it back into millimetre coordinates, so a
round-trip self-check proves the geometry is correct before any real cut.

Machine-specific constants are deliberately parameters, not hard-coded, because
they must be confirmed against the actual CE5000-40-CRP and the material during
试し切り (cut-condition tuning):

  * units_per_mm  - GP-GL coordinates are integer machine *steps*, not mm. The
                    step size is configurable on the cutter (commonly 0.1 / 0.05
                    / 0.025 / 0.01 mm). Default here is 0.05 mm/step => 20
                    steps/mm. VERIFY this matches the machine setting.
  * origin/flip_y - origin location and Y direction depend on how the material
                    is loaded; expose them rather than assume.
  * terminator    - GP-GL command terminator (default ETX, 0x03). VERIFY.
  * preamble/postamble - initialization and cut-condition commands (speed/force)
                    are left to the caller because they ARE the tuning values.

Only pen-up move `M x,y` and pen-down draw `D x,y,...` geometry is generated
here; those are the well-defined part. Everything machine-dependent is a knob.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .models import LayoutResult, Placement


@dataclass
class GpglOptions:
    units_per_mm: float = 20.0          # 0.05 mm/step; VERIFY against the cutter
    flip_y: bool = False                # invert Y (depends on material loading)
    sheet_height_mm: float | None = None  # required when flip_y is True
    offset_mm: tuple[float, float] = (0.0, 0.0)  # added before scaling
    terminator: str = "\x03"            # GP-GL command terminator (ETX); VERIFY
    preamble: list[str] = field(default_factory=list)   # init + cut conditions
    postamble: list[str] = field(default_factory=list)  # e.g. return-to-home

    def to_units(self, x_mm: float, y_mm: float) -> tuple[int, int]:
        x = x_mm + self.offset_mm[0]
        y = y_mm
        if self.flip_y:
            if self.sheet_height_mm is None:
                raise ValueError("flip_y=True requires sheet_height_mm")
            y = self.sheet_height_mm - y
        y = y + self.offset_mm[1]
        return round(x * self.units_per_mm), round(y * self.units_per_mm)

    def to_mm(self, ux: float, uy: float) -> tuple[float, float]:
        x = ux / self.units_per_mm - self.offset_mm[0]
        yv = uy / self.units_per_mm - self.offset_mm[1]
        if self.flip_y:
            y = self.sheet_height_mm - yv  # type: ignore[operator]
        else:
            y = yv
        return x, y


def _rect_corners(p: Placement) -> list[tuple[float, float]]:
    """Closed rectangle path (5 points, last == first), clockwise from top-left."""
    return [
        (p.x, p.y),
        (p.x + p.w, p.y),
        (p.x + p.w, p.y + p.h),
        (p.x, p.y + p.h),
        (p.x, p.y),
    ]


def _commands_for_polyline(pts: list[tuple[float, float]], opt: GpglOptions) -> list[str]:
    ux, uy = opt.to_units(*pts[0])
    cmds = [f"M{ux},{uy}"]                 # pen up, go to start
    draw_pts = []
    for x, y in pts[1:]:
        dux, duy = opt.to_units(x, y)
        draw_pts.append(f"{dux},{duy}")
    if draw_pts:
        cmds.append("D" + ",".join(draw_pts))  # pen down, draw through points
    return cmds


def generate(layout: LayoutResult, opt: GpglOptions | None = None) -> str:
    """Generate the GP-GL command string for every placed (non-overflow) piece."""
    opt = opt or GpglOptions()
    if opt.flip_y and opt.sheet_height_mm is None:
        # Default the flip reference to the used length so callers can just set flip_y.
        opt.sheet_height_mm = (
            layout.sheet.length
            if layout.sheet.length is not None
            else layout.used_length
        )
    cmds: list[str] = list(opt.preamble)
    for pl in layout.placements:
        if pl.overflow:
            continue  # do not cut pieces that fall outside the sheet
        cmds.extend(_commands_for_polyline(_rect_corners(pl), opt))
    cmds.extend(opt.postamble)
    return opt.terminator.join(cmds) + opt.terminator


_NUM = re.compile(r"-?\d+")


def parse_polylines(text: str, opt: GpglOptions | None = None) -> list[list[tuple[float, float]]]:
    """Inverse of generate(): read M/D commands back into mm polylines.

    Used for offline self-verification. Non-M/D commands (preamble etc.) are
    ignored.
    """
    opt = opt or GpglOptions()
    polylines: list[list[tuple[float, float]]] = []
    current: list[tuple[float, float]] | None = None
    for token in text.split(opt.terminator):
        token = token.strip()
        if not token:
            continue
        head = token[0]
        if head not in ("M", "D"):
            continue
        nums = [int(n) for n in _NUM.findall(token)]
        pts = [opt.to_mm(nums[i], nums[i + 1]) for i in range(0, len(nums) - 1, 2)]
        if head == "M":
            if current:
                polylines.append(current)
            current = list(pts)
        else:  # D
            if current is None:
                current = []
            current.extend(pts)
    if current:
        polylines.append(current)
    return polylines


def verify_roundtrip(layout: LayoutResult, opt: GpglOptions | None = None,
                     *, tol_mm: float = 0.05) -> tuple[bool, str]:
    """Generate GP-GL then parse it back and confirm each cut rectangle matches
    its placement (position and size) within tol_mm. Returns (ok, message)."""
    opt = opt or GpglOptions()
    text = generate(layout, opt)
    polys = parse_polylines(text, opt)
    expected = [pl for pl in layout.placements if not pl.overflow]

    if len(polys) != len(expected):
        return False, f"polyline count {len(polys)} != placements {len(expected)}"

    for poly, pl in zip(polys, expected):
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        got = (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
        want = (pl.x, pl.y, pl.w, pl.h)
        if any(abs(g - w) > tol_mm for g, w in zip(got, want)):
            return False, (f"rect mismatch for {pl.piece.name}: "
                           f"got {tuple(round(v,3) for v in got)} want {want}")

    return True, f"{len(expected)} rectangles round-trip within {tol_mm}mm"
