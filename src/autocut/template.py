"""Generate the clean fill-in template that the team uses to request cuts.

This is the canonical input format: the program emits the template, people fill
rows in, send it back, and a batch gets cut at once. The reader (excel_io) is
tolerant of variants, but this template is what we tell users to use.
"""
from __future__ import annotations

from .xlsx_write import write_xlsx

# Canonical columns. excel_io maps these (and common variants) by alias.
HEADER = ["名前", "幅mm", "高さmm", "数量", "グループ", "メモ"]

_EXAMPLE_ROWS = [
    ["Sample Part A", 10, 10, 2, "GroupX", "例: 記入後この行は消してOK"],
    ["Sample Part B", 4.5, 12, 2, "GroupX", ""],
    ["Sample Bracket", 12, 12, 1, "GroupY", ""],
]


def build_rows(with_examples: bool = True) -> list[list]:
    rows = [list(HEADER)]
    if with_examples:
        rows.extend([list(r) for r in _EXAMPLE_ROWS])
    return rows


def write_template(path: str, *, with_examples: bool = True) -> None:
    write_xlsx(path, build_rows(with_examples), sheet_name="pieces")
