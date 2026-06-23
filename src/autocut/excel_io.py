"""Read pieces from an Excel (.xlsx) workbook using only the standard library.

Why no openpyxl: the target environment ships a minimal Python without pip, so
we parse the .xlsx (a zip of XML) directly. The reader is deliberately tolerant
of real-world company sheets:

- the header row is not necessarily row 1 (title/blank rows above it),
- string cells carry furigana/phonetic ruby (<rPh>) that must be stripped,
- column names vary, so we map by alias (部品名/名前, 必要数/数量, 短辺/幅, 長辺/高さ).

Swap-in note: a future openpyxl-backed reader can replace read_pieces() while
keeping the same signature.
"""
from __future__ import annotations

import re
import zipfile
from xml.etree import ElementTree as ET

from .models import Piece

_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

# Column aliases -> canonical field. Compared after normalisation (strip+lower,
# spaces and a trailing "mm" removed). Order within a list is irrelevant.
_ALIASES = {
    "name": ["部品名", "名前", "品名", "name", "部品"],
    "qty": ["必要数", "数量", "個数", "枚数", "qty", "quantity", "count"],
    "w": ["短辺", "幅", "width", "短"],
    "h": ["長辺", "高さ", "height", "長", "縦"],
    "group": ["const", "部位", "グループ", "group"],
    "shape": ["形状", "shape"],
}


def _norm(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"mm$", "", s)
    return s


def _col_to_num(ref: str) -> int:
    letters = re.match(r"[A-Z]+", ref).group()
    n = 0
    for c in letters:
        n = n * 26 + (ord(c) - 64)
    return n


def _read_shared_strings(z: zipfile.ZipFile) -> list[str]:
    name = "xl/sharedStrings.xml"
    if name not in z.namelist():
        return []
    root = ET.fromstring(z.read(name))
    out: list[str] = []
    for si in root.findall(_NS + "si"):
        # Drop phonetic/ruby runs before gathering text.
        for parent in si.iter():
            for child in list(parent):
                if child.tag == _NS + "rPh":
                    parent.remove(child)
        out.append("".join(t.text or "" for t in si.iter(_NS + "t")))
    return out


def _first_sheet_path(z: zipfile.ZipFile) -> str:
    # Sheets are referenced from workbook.xml.rels; for our single-sheet inputs
    # the conventional path is enough, with a fallback scan.
    if "xl/worksheets/sheet1.xml" in z.namelist():
        return "xl/worksheets/sheet1.xml"
    for n in z.namelist():
        if n.startswith("xl/worksheets/") and n.endswith(".xml"):
            return n
    raise ValueError("no worksheet found in workbook")


def _grid(z: zipfile.ZipFile) -> list[dict[int, object]]:
    shared = _read_shared_strings(z)
    sheet = ET.fromstring(z.read(_first_sheet_path(z)))
    rows: list[dict[int, object]] = []
    for row in sheet.iter(_NS + "row"):
        cells: dict[int, object] = {}
        for c in row.findall(_NS + "c"):
            ref = c.attrib["r"]
            t = c.attrib.get("t")
            v = c.find(_NS + "v")
            isel = c.find(_NS + "is")
            if t == "s" and v is not None:
                val: object = shared[int(v.text)]
            elif t == "inlineStr" and isel is not None:
                val = "".join(x.text or "" for x in isel.iter(_NS + "t"))
            elif v is not None:
                txt = v.text
                try:
                    val = float(txt)
                except (TypeError, ValueError):
                    val = txt
            else:
                val = None
            cells[_col_to_num(ref)] = val
        rows.append(cells)
    return rows


def _match_field(cell_text: str) -> str | None:
    n = _norm(cell_text)
    if not n:
        return None
    for field, aliases in _ALIASES.items():
        for a in aliases:
            an = _norm(a)
            if n == an or an in n:
                return field
    return None


def _find_header(rows: list[dict[int, object]]) -> tuple[int, dict[str, int]]:
    """Return (row_index, {field: col_num}). Picks the row that maps the most
    of the required fields; requires at least name + w + h."""
    best: tuple[int, dict[str, int]] | None = None
    for i, cells in enumerate(rows):
        mapping: dict[str, int] = {}
        for col, val in cells.items():
            if not isinstance(val, str):
                continue
            field = _match_field(val)
            if field and field not in mapping:
                mapping[field] = col
        if {"name", "w", "h"} <= mapping.keys():
            score = len(mapping)
            if best is None or score > len(best[1]):
                best = (i, mapping)
    if best is None:
        raise ValueError(
            "could not locate a header row with 部品名/短辺/長辺 (or name/width/height)"
        )
    return best


def read_pieces(path: str, *, expand: bool = False) -> list[Piece]:
    """Read pieces from `path` (.xlsx).

    expand=False returns one Piece per row (with .qty set).
    expand=True returns qty copies, each with .inst = 1..qty.
    """
    with zipfile.ZipFile(path) as z:
        rows = _grid(z)
    hdr_i, col = _find_header(rows)

    pieces: list[Piece] = []
    for cells in rows[hdr_i + 1:]:
        name = cells.get(col["name"])
        w = cells.get(col["w"])
        h = cells.get(col["h"])
        if name in (None, "") or w is None or h is None:
            continue  # skip blank / incomplete rows
        try:
            w = float(w)
            h = float(h)
        except (TypeError, ValueError):
            continue
        qty_raw = cells.get(col["qty"]) if "qty" in col else 1
        try:
            qty = int(float(qty_raw)) if qty_raw not in (None, "") else 1
        except (TypeError, ValueError):
            qty = 1
        group = str(cells.get(col["group"], "")) if "group" in col else ""
        shape = str(cells.get(col["shape"], "")) if "shape" in col else ""
        pieces.append(
            Piece(name=str(name).strip(), w=w, h=h, qty=max(qty, 1),
                  group=group.strip(), shape=shape.strip())
        )

    if not expand:
        return pieces
    out: list[Piece] = []
    for p in pieces:
        for i in range(p.qty):
            out.append(Piece(p.name, p.w, p.h, 1, p.group, p.shape, inst=i + 1))
    return out
