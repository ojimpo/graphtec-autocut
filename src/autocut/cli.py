"""Command-line entry point.

Canonical workflow:
    python -m autocut template -o pieces.xlsx     # emit a blank template
    # ...people fill it in and send it back...
    python -m autocut pack pieces.xlsx -o preview.svg   # Phase 1 preview
"""
from __future__ import annotations

import argparse
import sys

from .excel_io import read_order
from .gpgl import GpglOptions, generate, verify_roundtrip
from .layout import pack
from .models import Sheet
from .svg_out import to_svg
from .template import write_template


def _resolve(flag, from_sheet, default):
    """CLI flag wins; else the order-sheet value; else the hardcoded default."""
    if flag is not None:
        return flag
    if from_sheet is not None:
        return from_sheet
    return default


def _load_job(args):
    """Read the order sheet and resolve sheet/layout settings (flags override)."""
    cond, pieces = read_order(args.input, expand=True)
    width = _resolve(args.sheet_width, cond.sheet_width, 350.0)
    length = _resolve(args.sheet_length, cond.sheet_length, None)
    gap = _resolve(args.gap, cond.gap, 2.0)
    if args.no_rotate:
        allow_rotate = False
    elif cond.allow_rotate is not None:
        allow_rotate = cond.allow_rotate
    else:
        allow_rotate = True
    sheet = Sheet(width=width, length=length)
    result = pack(pieces, sheet, gap=gap, allow_rotate=allow_rotate)
    return cond, pieces, result


def _cmd_template(args) -> int:
    write_template(args.out, with_examples=not args.blank)
    print(f"wrote template: {args.out}")
    return 0


def _cmd_pack(args) -> int:
    cond, pieces, result = _load_job(args)
    if not pieces:
        print("no pieces found in input", file=sys.stderr)
        return 1

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(to_svg(result))

    n_types = len({p.name for p in pieces})
    print(f"pieces: {len(pieces)} ({n_types} types)")
    print(f"placed: {len(result.placements)}, unplaced: {len(result.unplaced)}")
    print(f"sheet:  {result.sheet.width:.1f}mm wide x "
          f"{'roll' if result.sheet.length is None else f'{result.sheet.length:.1f}mm'}")
    print(f"used length: {result.used_length:.1f}mm")
    if result.unplaced:
        print("  unplaced (too wide for sheet):")
        for p in result.unplaced:
            print(f"    - {p.name} {p.w}x{p.h}")
    if result.overflowed:
        print("  WARNING: some pieces overflow the sheet length (shown in red)")
    print(f"wrote {args.out}")
    return 0


def _print_conditions(cond) -> None:
    """Report the order's cut conditions (set these on the cutter panel when
    running with PRIORITY=MANUAL)."""
    fields = [
        ("order", cond.order_name), ("date", cond.date),
        ("material", cond.material), ("blade", cond.blade),
        ("speed cm/s", cond.speed), ("force", cond.force),
        ("offset mm", cond.offset), ("passes", cond.passes),
    ]
    shown = [(k, v) for k, v in fields if v not in (None, "")]
    if not shown:
        print("cut conditions: (none filled in on the order sheet)")
        return
    print("cut conditions (set on panel / PRIORITY=MANUAL):")
    for k, v in shown:
        print(f"    {k}: {v}")


def _cmd_gpgl(args) -> int:
    cond, pieces, result = _load_job(args)
    if not pieces:
        print("no pieces found in input", file=sys.stderr)
        return 1

    opt = GpglOptions(units_per_mm=args.units_per_mm, flip_y=args.flip_y)
    ok, msg = verify_roundtrip(result, opt)
    text = generate(result, opt)
    with open(args.out, "w", encoding="ascii") as f:
        f.write(text)

    cut = sum(1 for p in result.placements if not p.overflow)
    print(f"pieces: {len(pieces)}, cut paths: {cut}, skipped (overflow): "
          f"{sum(1 for p in result.placements if p.overflow)}")
    _print_conditions(cond)
    print(f"units_per_mm: {args.units_per_mm}  (VERIFY against the cutter)")
    print(f"self-check: {'OK' if ok else 'FAIL'} - {msg}")
    print(f"wrote {args.out}")
    return 0 if ok else 2


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="autocut")
    sub = ap.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("template", help="write a blank fill-in .xlsx template")
    t.add_argument("-o", "--out", default="pieces_template.xlsx", help="output .xlsx path")
    t.add_argument("--blank", action="store_true", help="omit the example rows")
    t.set_defaults(func=_cmd_template)

    p = sub.add_parser("pack", help="Excel -> layout -> SVG preview (Phase 1)")
    p.add_argument("input", help="input order sheet .xlsx")
    p.add_argument("-o", "--out", default="preview.svg", help="output SVG path")
    p.add_argument("--sheet-width", type=float, default=None,
                   help="override usable sheet width in mm (default: order sheet, else 350)")
    p.add_argument("--sheet-length", type=float, default=None,
                   help="override sheet length in mm; roll if unset everywhere")
    p.add_argument("--gap", type=float, default=None,
                   help="override spacing between pieces in mm (default: order sheet, else 2.0)")
    p.add_argument("--no-rotate", action="store_true",
                   help="disallow 90-degree rotation of pieces")
    p.set_defaults(func=_cmd_pack)

    g = sub.add_parser("gpgl", help="Excel -> layout -> GP-GL cut paths (Phase 2)")
    g.add_argument("input", help="input order sheet .xlsx")
    g.add_argument("-o", "--out", default="cut.gpgl", help="output GP-GL path")
    g.add_argument("--units-per-mm", type=float, default=20.0,
                   help="GP-GL steps per mm (default 20 = 0.05mm/step); VERIFY")
    g.add_argument("--flip-y", action="store_true", help="invert Y axis")
    g.add_argument("--sheet-width", type=float, default=None,
                   help="override usable sheet width in mm (default: order sheet, else 350)")
    g.add_argument("--sheet-length", type=float, default=None,
                   help="override sheet length in mm; roll if unset everywhere")
    g.add_argument("--gap", type=float, default=None,
                   help="override spacing between pieces in mm (default: order sheet, else 2.0)")
    g.add_argument("--no-rotate", action="store_true",
                   help="disallow 90-degree rotation of pieces")
    g.set_defaults(func=_cmd_gpgl)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
