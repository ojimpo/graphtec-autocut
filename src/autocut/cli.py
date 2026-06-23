"""Command-line entry point.

Canonical workflow:
    python -m autocut template -o pieces.xlsx     # emit a blank template
    # ...people fill it in and send it back...
    python -m autocut pack pieces.xlsx -o preview.svg   # Phase 1 preview
"""
from __future__ import annotations

import argparse
import sys

from .excel_io import read_pieces
from .layout import pack
from .models import Sheet
from .svg_out import to_svg
from .template import write_template


def _cmd_template(args) -> int:
    write_template(args.out, with_examples=not args.blank)
    print(f"wrote template: {args.out}")
    return 0


def _cmd_pack(args) -> int:
    pieces = read_pieces(args.input, expand=True)
    if not pieces:
        print("no pieces found in input", file=sys.stderr)
        return 1

    sheet = Sheet(width=args.sheet_width, length=args.sheet_length)
    result = pack(pieces, sheet, gap=args.gap, allow_rotate=not args.no_rotate)

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(to_svg(result))

    n_types = len({p.name for p in pieces})
    print(f"pieces: {len(pieces)} ({n_types} types)")
    print(f"placed: {len(result.placements)}, unplaced: {len(result.unplaced)}")
    print(f"sheet:  {args.sheet_width:.1f}mm wide x "
          f"{'roll' if args.sheet_length is None else f'{args.sheet_length:.1f}mm'}")
    print(f"used length: {result.used_length:.1f}mm")
    if result.unplaced:
        print("  unplaced (too wide for sheet):")
        for p in result.unplaced:
            print(f"    - {p.name} {p.w}x{p.h}")
    if result.overflowed:
        print("  WARNING: some pieces overflow the sheet length (shown in red)")
    print(f"wrote {args.out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="autocut")
    sub = ap.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("template", help="write a blank fill-in .xlsx template")
    t.add_argument("-o", "--out", default="pieces_template.xlsx", help="output .xlsx path")
    t.add_argument("--blank", action="store_true", help="omit the example rows")
    t.set_defaults(func=_cmd_template)

    p = sub.add_parser("pack", help="Excel -> layout -> SVG preview (Phase 1)")
    p.add_argument("input", help="input .xlsx with piece definitions")
    p.add_argument("-o", "--out", default="preview.svg", help="output SVG path")
    p.add_argument("--sheet-width", type=float, default=350.0,
                   help="usable sheet width in mm (default: 350)")
    p.add_argument("--sheet-length", type=float, default=None,
                   help="sheet length in mm; omit for a roll (auto length)")
    p.add_argument("--gap", type=float, default=2.0,
                   help="spacing between pieces in mm (default: 2.0)")
    p.add_argument("--no-rotate", action="store_true",
                   help="disallow 90-degree rotation of pieces")
    p.set_defaults(func=_cmd_pack)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
