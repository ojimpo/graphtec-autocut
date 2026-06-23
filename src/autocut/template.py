"""Generate the order sheet: a single .xlsx holding BOTH the cut conditions
and the pieces to cut.

This is the canonical input/record format. The program emits the template,
people fill in the conditions (top block) and the pieces (table below), send it
back, and a batch gets cut at once. Saving the filled sheet documents exactly
what was cut and with what settings, so the next similar job starts from a copy.

Layout:
    [condition header block]   key / value rows (material, sheet, speed, ...)
    (blank row)
    [pieces table]             名前 / 幅mm / 高さmm / 数量 / グループ / メモ
"""
from __future__ import annotations

from .xlsx_write import write_xlsx

# Pieces table columns (excel_io maps these and common variants by alias).
HEADER = ["名前", "幅mm", "高さmm", "数量", "グループ", "メモ"]

# Condition header rows: (label, default value). Blank values are left for the
# operator to fill from the material ledger / cut tuning.
_CONDITION_ROWS = [
    ["オーダー名", ""],
    ["日付", ""],
    ["材料", ""],
    ["刃種", ""],
    ["シート幅mm", 350],
    ["シート長さmm", ""],      # blank = roll (auto length)
    ["ピース間隔mm", 2],
    ["90度回転許可", "はい"],
    ["速度cm/s", ""],
    ["刃圧", ""],
    ["オフセットmm", 0.25],
    ["パス数", 1],
]

_EXAMPLE_ROWS = [
    ["Sample Part A", 10, 10, 2, "GroupX", "例: 記入後この行は消してOK"],
    ["Sample Part B", 4.5, 12, 2, "GroupX", ""],
    ["Sample Bracket", 12, 12, 1, "GroupY", ""],
]


def build_rows(with_examples: bool = True) -> list[list]:
    rows: list[list] = [["カット指示書 (Order Sheet) — 上段に条件、下段にピースを記入"]]
    rows.extend([list(r) for r in _CONDITION_ROWS])
    rows.append([])  # blank separator between conditions and the pieces table
    rows.append(list(HEADER))
    if with_examples:
        rows.extend([list(r) for r in _EXAMPLE_ROWS])
    return rows


def write_template(path: str, *, with_examples: bool = True) -> None:
    write_xlsx(path, build_rows(with_examples), sheet_name="order")
