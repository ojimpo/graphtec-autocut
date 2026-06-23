# graphtec-autocut

[![CI](https://github.com/ojimpo/graphtec-autocut/actions/workflows/ci.yml/badge.svg)](https://github.com/ojimpo/graphtec-autocut/actions/workflows/ci.yml)

Auto-layout and cut rectangular pieces on a Graphtec **Craft ROBO Pro
(CE5000-40-CRP)** cutter from a simple Excel sheet.

The vendor software (ROBO Master Pro) is abandoned on Windows 11, but the
hardware speaks the open **GP-GL** protocol, so it can be revived with OSS.
Define your pieces in a spreadsheet, let the tool pack them onto the material,
preview the layout as SVG, and (Phase 2) stream the cut paths over USB.

## Workflow

```bash
# 1. Generate a blank order sheet
python -m autocut template -o order.xlsx

# 2. Fill in the conditions (top block) and the pieces (table below),
#    collect everyone's pieces into one sheet, and send it back.

# 3. Pack the pieces and preview the layout
python -m autocut pack order.xlsx -o preview.svg

# 4. (Phase 2) Generate GP-GL cut paths + offline self-check
python -m autocut gpgl order.xlsx -o cut.gpgl
```

Sheet/layout settings come from the order sheet; CLI flags
(`--sheet-width`, `--sheet-length`, `--gap`, `--no-rotate`) override per run.

## Order sheet format

One `.xlsx` is the whole order: cut conditions on top, pieces below. Saving the
filled sheet records exactly what was cut and with what settings, so the next
similar job starts from a copy.

**Condition header** (label / value rows): order name, date, material, blade,
sheet width/length, piece gap, 90° rotation, speed, force, blade offset, passes.

**Pieces table** — the reader auto-detects this header row, accepts common
variants such as `部品名/短辺/長辺/必要数`, and strips furigana:

| 名前 | 幅mm | 高さmm | 数量 | グループ | メモ |
|------|------|--------|------|----------|------|

In v1 the cut conditions are reported by `gpgl` so they can be entered on the
cutter panel (`PRIORITY=MANUAL`); driving them via GP-GL command codes
(`PRIORITY=COMD`) is a later step.

## Status

- **Phase 1 — Excel → layout → SVG preview: working.**
  - Bin packing via a self-implemented Shelf FFDH packer.
  - **No third-party dependencies** — pure Python standard library
    (`.xlsx` is read/written by parsing the underlying zip+XML), so it runs on a
    minimal Python without pip.
- **Phase 2 — GP-GL cut-path generation: working (offline).**
  `gpgl` emits `M`/`D` cut paths and self-verifies by parsing the output back to
  mm and comparing against the layout (no machine needed). Machine-specific
  constants (steps/mm, origin, Y direction, terminator, init & cut-condition
  commands) are parameters to confirm on the real cutter during cut tuning.
- **Phase 2 — USB send + cut-condition tuning: not yet.**
  Target route: `usbipd-win` (USB/IP) to attach the cutter into WSL2, then send
  GP-GL from Python.

## Project layout

```text
src/autocut/
  models.py      # Piece / Sheet / Placement / LayoutResult
  excel_io.py    # tolerant .xlsx reader (stdlib)
  xlsx_write.py  # minimal .xlsx writer (stdlib)
  template.py    # blank fill-in template generator
  layout.py      # Shelf FFDH packer (swappable for rectpack later)
  svg_out.py     # SVG preview renderer
  gpgl.py        # GP-GL cut-path generation + offline round-trip self-check
  cli.py         # `template` / `pack` / `gpgl` subcommands
tests/           # stdlib unittest (no third-party deps)
```

The layout and Excel-reader interfaces are kept separable so `rectpack` and
`openpyxl` can be slotted in once a richer Python environment is available.

## Hardware notes (CE5000-40-CRP)

Max speed 60 cm/s · precision ~500 µm · max material thickness 250 µm ·
effective cut width ~350 mm · USB / RS-232C · GP-GL / HP-GL.

## License

MIT
