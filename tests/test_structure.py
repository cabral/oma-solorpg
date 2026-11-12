"""The layout model's regions (solo/structure.py): which lines each one holds, the subprocess
the extract runs in the ingest environment, and the numbers step 1 of docs/INGESTION_PLAN.md
measures. A stand-in for the ingest environment's Python writes known regions, so all of this
runs without Docling; the last class runs the real model when it is installed."""

import json
import os
import stat
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from test_cli import CliCase
from test_extract import make_book, pymupdf

from solo import SoloError, extract, structure


def line(x0, y0, x1, y1, text="words"):
    return {"x0": x0, "y0": y0, "x1": x1, "y1": y1, "text": text}


class CoveredTest(unittest.TestCase):
    def test_a_line_belongs_to_the_region_holding_most_of_it(self):
        box = [50, 100, 300, 200]
        self.assertTrue(structure.covered(box, line(60, 110, 200, 122)))
        self.assertTrue(structure.covered(box, line(60, 195, 200, 203)), "five of eight points inside")
        self.assertFalse(structure.covered(box, line(60, 198, 200, 210)), "two of twelve points inside")
        self.assertFalse(structure.covered(box, line(320, 110, 400, 122)))

    def test_a_line_with_no_area_counts_by_its_middle(self):
        self.assertTrue(structure.covered([0, 0, 10, 10], line(5, 5, 5, 5)))
        self.assertFalse(structure.covered([0, 0, 10, 10], line(15, 5, 15, 5)))

    def test_regions_get_the_indices_of_their_lines_and_keep_the_rest(self):
        lines = [line(72, 40, 150, 48, "HEADER"), line(72, 100, 300, 112), line(72, 300, 200, 312, "Dagger"), line(220, 300, 260, 312, "D8")]
        regions = structure.attach([{"kind": "page_header", "bbox": [70, 38, 160, 50], "ref": "#/texts/0"},
                                    {"kind": "table", "bbox": [70, 295, 270, 320], "ref": "#/tables/0", "caption": "Weapons"}], lines)
        self.assertEqual(regions, [{"kind": "page_header", "bbox": [70, 38, 160, 50], "ref": "#/texts/0", "lines": [0]},
                                   {"kind": "table", "bbox": [70, 295, 270, 320], "ref": "#/tables/0", "caption": "Weapons", "lines": [2, 3]}])


# What the stand-in's model "finds" in make_book's five pages: the ruled table of page 4, a
# page header over its heading (which the extract's repetition test doesn't take out, so the
# two disagree there), and a picture on page 5 classed as a map.
RAW = {"reader": "docling", "version": "9.9.9", "pages": {
    "1": {"width": 612.0, "height": 792.0, "regions": [{"kind": "section_header", "bbox": [70, 70, 500, 105], "ref": "#/texts/0"}]},
    "2": {"width": 612.0, "height": 792.0, "regions": []},
    "3": {"width": 612.0, "height": 792.0, "regions": []},
    "4": {"width": 612.0, "height": 792.0, "regions": [
        {"kind": "page_header", "bbox": [70, 55, 200, 88], "ref": "#/texts/1"},
        {"kind": "table", "bbox": [70, 108, 315, 172], "ref": "#/tables/0", "caption": "Weapons"}]},
    "5": {"width": 612.0, "height": 792.0, "regions": [
        {"kind": "picture", "bbox": [72, 72, 300, 300], "ref": "#/pictures/0", "class": "geographical_map"}]},
}}


def stand_in(folder, raw=RAW, fail=None):
    """An ingest environment whose Python, run as `python -m solo.structure <pdf> <out>`, writes `raw` to <out>, or fails."""
    (folder / "bin").mkdir(parents=True)
    (folder / "raw.json").write_text(json.dumps(raw))
    script = folder / "bin" / "python"
    body = f'echo "{fail}" >&2; exit 1' if fail else 'test "$1 $2" = "-m solo.structure" || exit 3\ncp "$(dirname "$0")/../raw.json" "$4"'
    script.write_text(f"#!/bin/sh\n{body}\n")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return folder


@unittest.skipUnless(pymupdf, "PyMuPDF isn't installed")
class ExtractWithModelTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.tmp = Path(folder.name)
        make_book(self.tmp / "book.pdf")

    def run_extract(self, ingest, **options):
        with unittest.mock.patch.dict(os.environ, {"SOLO_INGEST": str(ingest)}):
            return extract.extract(self.tmp / "book.pdf", self.tmp / "out", **options)

    def page(self, out, number):
        return json.loads((out / "structure" / f"{number:04d}.json").read_text(encoding="utf-8"))

    def test_each_page_gets_its_regions_with_the_lines_they_hold(self):
        out, manifest = self.run_extract(stand_in(self.tmp / "ingest"))
        self.assertEqual(manifest["structure"]["reader"], "docling")
        self.assertEqual(manifest["structure"]["version"], "9.9.9")
        self.assertEqual({k: manifest["structure"][k] for k in ("pages", "tables", "pictures", "maps")}, {"pages": 5, "tables": 1, "pictures": 1, "maps": 1})
        self.assertNotIn("structure_note", manifest)
        lines = json.loads((out / "layout" / "0004.json").read_text(encoding="utf-8"))["lines"]
        table = next(r for r in self.page(out, 4)["regions"] if r["kind"] == "table")
        self.assertEqual(sorted(lines[i]["text"] for i in table["lines"]), ["D10", "D8", "Dagger", "Damage", "Sword", "Weapon"])
        self.assertEqual(table["caption"], "Weapons")
        self.assertEqual(self.page(out, 2), {"page": 2, "width": 612.0, "height": 792.0, "regions": []})

    def test_a_model_that_fails_leaves_the_rest_of_the_extract_written(self):
        out, manifest = self.run_extract(stand_in(self.tmp / "ingest", fail="RuntimeError: out of memory"))
        self.assertIsNone(manifest["structure"])
        self.assertIn("RuntimeError: out of memory", manifest["structure_note"])
        self.assertTrue((out / "pages" / "0004.txt").exists())

    def test_no_structure_leaves_the_model_alone(self):
        out, manifest = self.run_extract(stand_in(self.tmp / "ingest", fail="should not run"), structure=False)
        self.assertIsNone(manifest["structure"])
        self.assertNotIn("structure_note", manifest)

    def test_a_rerun_without_the_model_takes_the_old_regions_away(self):
        out, _ = self.run_extract(stand_in(self.tmp / "ingest"))
        out, manifest = self.run_extract(self.tmp / "gone")
        self.assertEqual(list((out / "structure").iterdir()), [])
        self.assertIsNone(manifest["structure"])

    def test_measure_counts_what_the_model_found_against_the_extract_and_the_inventory(self):
        out, _ = self.run_extract(stand_in(self.tmp / "ingest"))
        inventory = {"items": {"weapons": {"kind": "table", "pages": [4]}, "fear": {"kind": "table", "pages": [3]},
                               "combat": {"kind": "mechanic", "pages": [2]}}}
        found = structure.measure(out, inventory)
        self.assertEqual(found["pages"], 5)
        self.assertEqual(found["table_pages"], [4])
        self.assertEqual(found["extract_table_pages"], [3, 4], "the roll lines of page 3 and the ruled table of page 4")
        self.assertEqual(found["inventory_tables"], 2)
        self.assertEqual(found["inventory_tables_missed"], ["fear"])
        self.assertEqual(found["running_disagreed"], [4])
        self.assertEqual(found["picture_classes"], {"geographical_map": 1})
        self.assertEqual(found["map_pages"], [5])
        report = "\n".join(structure.report(found))
        self.assertIn("only the extract's rules: pages 3", report)
        self.assertIn("inventory: 1 of 2 tables are on a page the model found a table on", report)
        self.assertIn("not found: fear", report)
        self.assertIn("disagree on 1 pages: 4", report)
        self.assertIn("maps on pages 5", report)

    def test_measure_wants_an_extract_made_with_the_model(self):
        out, _ = self.run_extract(self.tmp / "gone")
        with self.assertRaisesRegex(SoloError, "make ingest-deps"):
            structure.measure(out)


@unittest.skipUnless(pymupdf, "PyMuPDF isn't installed")
class StructureCliTest(CliCase):
    def test_extract_says_what_the_model_found_and_solo_structure_compares_it(self):
        make_book(self.tmp / "book.pdf")
        stand_in(self.tmp / "ingest")
        code, out, err = self.solo("extract", str(self.tmp / "book.pdf"), "--out", str(self.tmp / "book"))
        self.assertEqual(code, 0, err)
        self.assertIn("reading the layout of 5 pages with docling", err)
        self.assertIn("structure/: docling 9.9.9", out)
        self.assertIn("1 tables, 1 pictures, 1 of them maps", out)
        code, out, err = self.solo("structure", str(self.tmp / "book"))
        self.assertEqual(code, 0, err)
        self.assertIn("5 pages read in", out)
        self.assertIn("pictures: 1 (geographical_map 1)", out)
        code, out, _ = self.solo("structure", str(self.tmp / "book"), "--json")
        self.assertEqual(json.loads(out)["map_pages"], [5])

    def test_extract_without_the_model_says_how_to_add_it(self):
        make_book(self.tmp / "book.pdf")
        code, out, err = self.solo("extract", str(self.tmp / "book.pdf"), "--out", str(self.tmp / "book"))
        self.assertEqual(code, 0, err)
        self.assertIn("make ingest-deps installs Docling", out)
        self.assertNotIn("reading the layout", err)


@unittest.skipUnless(pymupdf and structure.python(), "the ingest environment isn't installed (make ingest-deps)")
class DoclingTest(unittest.TestCase):
    """The real model on a made-up book: about a minute, most of it loading the models."""

    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory()
        tmp = Path(cls.folder.name)
        make_book(tmp / "book.pdf")
        cls.out, cls.manifest = extract.extract(tmp / "book.pdf", tmp / "out")

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def test_the_ruled_table_is_a_table_region_holding_its_cells(self):
        self.assertEqual(self.manifest["structure"]["reader"], "docling")
        self.assertEqual(self.manifest["structure"]["version"], structure.DOCLING)
        page = json.loads((self.out / "structure" / "0004.json").read_text(encoding="utf-8"))
        lines = json.loads((self.out / "layout" / "0004.json").read_text(encoding="utf-8"))["lines"]
        tables = [r for r in page["regions"] if r["kind"] == "table"]
        self.assertEqual(len(tables), 1)
        self.assertEqual(sorted(lines[i]["text"] for i in tables[0]["lines"]), ["D10", "D8", "Dagger", "Damage", "Sword", "Weapon"])
        x0, y0, x1, y1 = tables[0]["bbox"]
        self.assertLess(y0, y1)
        self.assertAlmostEqual(x0, 72, delta=5)
        self.assertAlmostEqual(y0, 110, delta=5, msg="top left origin, as layout/ has it")


if __name__ == "__main__":
    unittest.main()
