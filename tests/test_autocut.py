"""Offline tests for graphtec-autocut (stdlib unittest, no third-party deps)."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from autocut.excel_io import read_order, read_pieces
from autocut.gpgl import GpglOptions, generate, parse_polylines, verify_roundtrip
from autocut.layout import pack
from autocut.models import Piece, Sheet
from autocut.template import write_template


def _expand(pieces):
    out = []
    for p in pieces:
        for i in range(p.qty):
            out.append(Piece(p.name, p.w, p.h, 1, inst=i + 1))
    return out


class ExcelRoundTrip(unittest.TestCase):
    def test_template_write_read(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "t.xlsx")
            write_template(path)
            pieces = read_pieces(path)
            self.assertTrue(pieces)
            names = {p.name for p in pieces}
            self.assertIn("Sample Part A", names)
            a = next(p for p in pieces if p.name == "Sample Part A")
            self.assertEqual((a.w, a.h, a.qty), (10.0, 10.0, 2))


class OrderSheet(unittest.TestCase):
    def test_conditions_and_pieces(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "order.xlsx")
            write_template(path)
            cond, pieces = read_order(path, expand=True)
            # defaults baked into the template header block
            self.assertEqual(cond.sheet_width, 350.0)
            self.assertEqual(cond.gap, 2.0)
            self.assertEqual(cond.offset, 0.25)
            self.assertEqual(cond.passes, 1)
            self.assertTrue(cond.allow_rotate)
            self.assertIsNone(cond.sheet_length)  # blank => roll
            # pieces still read correctly from below the header block
            self.assertIn("Sample Part A", {p.name for p in pieces})

    def test_blade_and_force_not_confused(self):
        from autocut.xlsx_write import write_xlsx
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "order.xlsx")
            write_xlsx(path, [
                ["材料", "PET"], ["刃種", "標準刃"], ["刃圧", 10],
                ["速度cm/s", 30], [],
                ["名前", "幅mm", "高さmm", "数量"], ["x", 10, 10, 1],
            ])
            cond, _ = read_order(path)
            self.assertEqual(cond.blade, "標準刃")   # not the force value
            self.assertEqual(cond.force, 10.0)
            self.assertEqual(cond.speed, 30.0)

    def test_header_block_does_not_pollute_pieces(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "order.xlsx")
            write_template(path)
            pieces = read_pieces(path)
            names = {p.name for p in pieces}
            # condition labels must not be misread as pieces
            self.assertNotIn("シート幅mm", names)
            self.assertNotIn("速度cm/s", names)


class LayoutValid(unittest.TestCase):
    def test_no_overlap_within_width(self):
        pieces = _expand([Piece("p", 20, 30, 5), Piece("q", 40, 10, 5)])
        sheet = Sheet(width=100, length=None)
        res = pack(pieces, sheet, gap=2.0, allow_rotate=True)
        self.assertEqual(len(res.placements), 10)
        self.assertEqual(res.unplaced, [])
        for pl in res.placements:
            self.assertLessEqual(pl.x + pl.w, sheet.width + 1e-6)
            self.assertGreaterEqual(pl.x, -1e-6)
        # pairwise overlap check
        for i, a in enumerate(res.placements):
            for b in res.placements[i + 1:]:
                sep = (a.x + a.w <= b.x + 1e-9 or b.x + b.w <= a.x + 1e-9 or
                       a.y + a.h <= b.y + 1e-9 or b.y + b.h <= a.y + 1e-9)
                self.assertTrue(sep, f"overlap between {a.x,a.y,a.w,a.h} and {b.x,b.y,b.w,b.h}")

    def test_too_wide_is_unplaced(self):
        res = pack(_expand([Piece("big", 500, 500, 1)]), Sheet(width=350), allow_rotate=True)
        self.assertEqual(len(res.unplaced), 1)
        self.assertEqual(res.placements, [])


class GpglGeometry(unittest.TestCase):
    def test_roundtrip_matches_layout(self):
        pieces = _expand([Piece("a", 12, 8, 3), Piece("b", 5, 20, 2)])
        res = pack(pieces, Sheet(width=350, length=None), gap=2.0)
        ok, msg = verify_roundtrip(res, GpglOptions(units_per_mm=20.0))
        self.assertTrue(ok, msg)

    def test_units_scaling(self):
        opt = GpglOptions(units_per_mm=20.0)
        self.assertEqual(opt.to_units(10.0, 5.0), (200, 100))

    def test_generate_has_move_and_draw(self):
        res = pack(_expand([Piece("a", 10, 10, 1)]), Sheet(width=350))
        text = generate(res, GpglOptions())
        self.assertIn("M", text)
        self.assertIn("D", text)
        polys = parse_polylines(text, GpglOptions())
        self.assertEqual(len(polys), 1)
        self.assertEqual(len(polys[0]), 5)  # closed rectangle

    def test_flip_y_roundtrip(self):
        res = pack(_expand([Piece("a", 10, 10, 2)]), Sheet(width=350, length=200))
        ok, msg = verify_roundtrip(res, GpglOptions(units_per_mm=40.0, flip_y=True,
                                                    sheet_height_mm=200))
        self.assertTrue(ok, msg)


if __name__ == "__main__":
    unittest.main(verbosity=2)
