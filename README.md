# graphtec-autocut

Auto-layout and cut rectangular pieces on a Graphtec **Craft ROBO Pro
(CE5000-40-CRP)** cutter from a simple Excel sheet.

The vendor software (ROBO Master Pro) is abandoned on Windows 11, but the
hardware speaks the open **GP-GL** protocol, so it can be revived with OSS.
Define your pieces in a spreadsheet, let the tool pack them onto the material,
preview the layout as SVG, and (Phase 2) stream the cut paths over USB.

## Workflow

```
# 1. Generate a blank fill-in template
python -m autocut template -o pieces.xlsx

# 2. Fill in the rows (name / width mm / height mm / qty / group / note),
#    collect everyone's pieces into one sheet, and send it back.

# 3. Pack the pieces and preview the layout
python -m autocut pack pieces.xlsx -o preview.svg
```

`pack` options:

| flag | default | meaning |
|------|---------|---------|
| `--sheet-width` | `350` | usable material width in mm (CE5000-40-CRP ≈ 350) |
| `--sheet-length` | roll | sheet length in mm; omit for a roll (auto length) |
| `--gap` | `2.0` | spacing between pieces in mm (blade offset / precision) |
| `--no-rotate` | off | disallow 90° rotation of pieces |

## Input format

The template has these columns (the reader also accepts common variants such as
`部品名/短辺/長辺/必要数`, auto-detects the header row, and strips furigana):

| 名前 | 幅mm | 高さmm | 数量 | グループ | メモ |
|------|------|--------|------|----------|------|

## Status

- **Phase 1 — Excel → layout → SVG preview: working.**
  - Bin packing via a self-implemented Shelf FFDH packer.
  - **No third-party dependencies** — pure Python standard library
    (`.xlsx` is read/written by parsing the underlying zip+XML), so it runs on a
    minimal Python without pip.
- **Phase 2 — GP-GL cut-path generation + USB send: planned.**
  Target route: `usbipd-win` (USB/IP) to attach the cutter into WSL2, then send
  GP-GL from Python.

## Project layout

```
src/autocut/
  models.py      # Piece / Sheet / Placement / LayoutResult
  excel_io.py    # tolerant .xlsx reader (stdlib)
  xlsx_write.py  # minimal .xlsx writer (stdlib)
  template.py    # blank fill-in template generator
  layout.py      # Shelf FFDH packer (swappable for rectpack later)
  svg_out.py     # SVG preview renderer
  cli.py         # `template` / `pack` subcommands
```

The layout and Excel-reader interfaces are kept separable so `rectpack` and
`openpyxl` can be slotted in once a richer Python environment is available.

## Hardware notes (CE5000-40-CRP)

Max speed 60 cm/s · precision ~500 µm · max material thickness 250 µm ·
effective cut width ~350 mm · USB / RS-232C · GP-GL / HP-GL.

## License

MIT
