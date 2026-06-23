"""Render a LayoutResult to an SVG preview (Phase 1 output).

The SVG uses millimetre units directly (width="...mm") with a 1:1 viewBox, so
the on-screen geometry equals the real cut geometry. y grows downward, matching
the packer's coordinate system.
"""
from __future__ import annotations

from xml.sax.saxutils import escape

from .models import LayoutResult

_SHEET_FILL = "#fafafa"
_SHEET_STROKE = "#888"
_PIECE_FILL = "#cfe8ff"
_PIECE_STROKE = "#1f6feb"
_OVER_FILL = "#ffd6d6"
_OVER_STROKE = "#d1242f"


def _fmt(v: float) -> str:
    return f"{v:.3f}".rstrip("0").rstrip(".")


def to_svg(layout: LayoutResult, *, margin: float = 5.0) -> str:
    sheet = layout.sheet
    sheet_len = sheet.length if sheet.length is not None else layout.used_length
    sheet_len = max(sheet_len, layout.used_length, 1.0)

    total_w = sheet.width + 2 * margin
    total_h = sheet_len + 2 * margin
    # Label font scaled to the sheet so it stays readable but unobtrusive.
    fs = max(min(sheet.width, sheet_len) * 0.012, 1.2)

    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{_fmt(total_w)}mm" height="{_fmt(total_h)}mm" '
        f'viewBox="0 0 {_fmt(total_w)} {_fmt(total_h)}">'
    )
    parts.append(f'<g transform="translate({_fmt(margin)},{_fmt(margin)})">')

    # Sheet outline
    parts.append(
        f'<rect x="0" y="0" width="{_fmt(sheet.width)}" height="{_fmt(sheet_len)}" '
        f'fill="{_SHEET_FILL}" stroke="{_SHEET_STROKE}" stroke-width="0.3"/>'
    )

    for pl in layout.placements:
        fill = _OVER_FILL if pl.overflow else _PIECE_FILL
        stroke = _OVER_STROKE if pl.overflow else _PIECE_STROKE
        parts.append(
            f'<rect x="{_fmt(pl.x)}" y="{_fmt(pl.y)}" '
            f'width="{_fmt(pl.w)}" height="{_fmt(pl.h)}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="0.2"/>'
        )
        label = pl.piece.name
        if pl.piece.inst:
            label += f" #{pl.piece.inst}"
        rot = " ⟳" if pl.rotated else ""
        cx, cy = pl.x + pl.w / 2, pl.y + pl.h / 2
        parts.append(
            f'<text x="{_fmt(cx)}" y="{_fmt(cy)}" font-size="{_fmt(fs)}" '
            f'text-anchor="middle" dominant-baseline="middle" '
            f'fill="#222" font-family="sans-serif">'
            f'{escape(label)}{rot}</text>'
        )
        parts.append(
            f'<text x="{_fmt(cx)}" y="{_fmt(cy + fs * 1.2)}" font-size="{_fmt(fs * 0.85)}" '
            f'text-anchor="middle" dominant-baseline="middle" '
            f'fill="#555" font-family="sans-serif">'
            f'{_fmt(pl.w)}×{_fmt(pl.h)}</text>'
        )

    parts.append("</g>")
    parts.append("</svg>")
    return "\n".join(parts)
