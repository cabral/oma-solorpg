import json
import tempfile
import unittest
from pathlib import Path

from test_cli import CliCase

from solo import SoloError, extract

try:
    import pymupdf
except ImportError:  # extract is the one command with a dependency; play doesn't need it
    pymupdf = None


def make_book(path, bookmarks=True):
    """Five pages: a title, a two-column chapter, a roll table, a ruled table, and a scan."""
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "THE BOOK OF TESTS", fontsize=28)
    page.insert_text((72, 140), "A rulebook made to test solo extract. Credits and such go here.", fontsize=10)
    page = doc.new_page()
    page.insert_text((72, 80), "Combat", fontsize=22)
    page.insert_textbox(pymupdf.Rect(50, 110, 290, 700), "LEFT column. Initiative is dealt as cards every round, lowest first, until one side falls.", fontsize=10)
    page.insert_textbox(pymupdf.Rect(310, 110, 550, 700), "RIGHT column. Damage is rolled with the weapon's dice, and armor takes away its rating.", fontsize=10)
    page = doc.new_page()
    page.insert_text((72, 80), "Fear", fontsize=22)
    for i, line in enumerate(["1 Frozen in place", "2-3 Shaken", "4 Panic", "5 Scream", "6 Flee"]):
        page.insert_text((72, 120 + 16 * i), line, fontsize=10)
    page = doc.new_page()
    page.insert_text((72, 80), "Weapons", fontsize=22)
    for r, row in enumerate([["Weapon", "Damage"], ["Dagger", "D8"], ["Sword", "D10"]]):
        for c, cell in enumerate(row):
            rect = pymupdf.Rect(72 + c * 120, 110 + r * 20, 192 + c * 120, 130 + r * 20)
            page.draw_rect(rect, color=(0, 0, 0), width=0.8)
            page.insert_text((rect.x0 + 4, rect.y1 - 6), cell, fontsize=10)
    page = doc.new_page()
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 50, 50), False)
    pix.clear_with(200)
    page.insert_image(pymupdf.Rect(72, 72, 300, 300), pixmap=pix)
    if bookmarks:
        doc.set_toc([[1, "Introduction", 1], [1, "Combat", 2], [2, "Fear", 3], [2, "Weapons", 4], [1, "Plates", 5]])
    # The printed numbers start on the second page, as a book's do after its cover.
    doc.set_page_labels([{"startpage": 1, "prefix": "", "style": "D", "firstpagenum": 1}])
    doc.save(path)


@unittest.skipUnless(pymupdf, "PyMuPDF isn't installed")
class ExtractTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.tmp = Path(folder.name)
        make_book(self.tmp / "book.pdf")
        self.out, self.manifest = extract.extract(self.tmp / "book.pdf", self.tmp / "out")

    def read(self, name):
        return (self.out / name).read_text(encoding="utf-8")

    def test_every_page_is_a_file_and_book_md_marks_them(self):
        self.assertEqual(sorted(p.name for p in (self.out / "pages").iterdir()), [f"000{n}.txt" for n in range(1, 6)])
        book = self.read("book.md")
        self.assertIn("===== PAGE 1 =====", book)
        self.assertIn("===== PAGE 3 (printed 2) =====\n\nFear", book)
        self.assertEqual(self.manifest["labels"]["2"], "1")
        self.assertNotIn("1", self.manifest["labels"])

    def test_two_columns_are_read_left_then_right(self):
        text = self.read("pages/0002.txt")
        self.assertLess(text.index("Combat"), text.index("LEFT"))
        self.assertLess(text.index("until one side falls"), text.index("RIGHT"))

    def test_bookmarks_become_chapters_with_page_ranges(self):
        toc = json.loads(self.read("toc.json"))
        self.assertEqual([(e["title"], e["start"], e["end"]) for e in toc],
                         [("Introduction", 1, 1), ("Combat", 2, 4), ("Fear", 3, 3), ("Weapons", 4, 4), ("Plates", 5, 5)])
        self.assertEqual(self.manifest["toc_from"], "outline")
        self.assertEqual(toc[1]["file"], "chapters/02-combat.md")
        chapter = self.read("chapters/02-combat.md")
        self.assertTrue(chapter.startswith("# Combat (pages 2-4)"))
        self.assertIn("===== PAGE 4 (printed 3) =====", chapter)
        self.assertNotIn("PAGE 5", chapter)

    def test_tables_come_out_as_markdown_and_pictures(self):
        index = json.loads(self.read("tables/index.json"))
        self.assertIn({"page": 3, "kind": "roll", "lines": 5, "image": "p0003.png"}, index)
        self.assertIn({"page": 4, "kind": "grid", "file": "p0004-1.md", "image": "p0004.png"}, index)
        self.assertIn("|Dagger|D8|", self.read("tables/p0004-1.md"))
        self.assertTrue((self.out / "tables" / "p0003.png").exists())

    def test_a_page_with_only_a_picture_is_marked_for_ocr(self):
        self.assertEqual(self.manifest["scanned"], [5])

    def test_without_bookmarks_headings_are_guessed_from_font_sizes(self):
        make_book(self.tmp / "plain.pdf", bookmarks=False)
        out, manifest = extract.extract(self.tmp / "plain.pdf", self.tmp / "plain")
        self.assertEqual(manifest["toc_from"], "fonts")
        # The title is set bigger than the chapters, but a single entry isn't a chapter level.
        self.assertEqual(sorted(p.name for p in (out / "chapters").iterdir()), ["01-combat.md", "02-fear.md", "03-weapons.md"])

    def test_a_rerun_starts_the_generated_folders_over(self):
        (self.out / "pages" / "stale.txt").write_text("old")
        (self.out / "notes.md").write_text("mine")
        extract.extract(self.tmp / "book.pdf", self.out)
        self.assertFalse((self.out / "pages" / "stale.txt").exists())
        self.assertTrue((self.out / "notes.md").exists())

    def test_the_text_never_lands_in_the_repository(self):
        with self.assertRaisesRegex(SoloError, "inside the repository"):
            extract.extract(self.tmp / "book.pdf", extract.library.REPO / "sources")


@unittest.skipUnless(pymupdf, "PyMuPDF isn't installed")
class ExtractCliTest(CliCase):
    def test_extract_says_what_it_wrote_and_defaults_under_solo_home(self):
        make_book(self.tmp / "My Rule Book.pdf")
        code, out, err = self.solo("extract", str(self.tmp / "My Rule Book.pdf"))
        self.assertEqual(code, 0, err)
        folder = self.tmp / "games" / "sources" / "my-rule-book"
        self.assertIn(f"wrote {folder}", out)
        self.assertIn("5 pages", out)
        self.assertIn("3 chapters from the outline", out)
        self.assertIn("1 pages have almost no text and a picture: 5", out)
        self.assertIn("run ocrmypdf", out)
        self.assertTrue((folder / "manifest.json").exists())


if __name__ == "__main__":
    unittest.main()


class DamagedOutline(unittest.TestCase):
    def test_a_bookmark_past_the_last_page_is_left_out(self):
        class Doc:  # an outline damaged in a way PyMuPDF won't write, so a stand-in
            page_count = 2

            def get_toc(self, simple=False):
                return [[1, "Rules", 1, {}], [1, "Lost", 9, {}], [1, "Nowhere", -1, {}], [1, "Tables", 2, {}]]

        toc, source = extract._toc(Doc(), [{"chars": 10}, {"chars": 20}])
        self.assertEqual([(e["title"], e["start"], e["end"]) for e in toc], [("Rules", 1, 1), ("Tables", 2, 2)])
        self.assertEqual(source, "outline")


class RunningHeadTest(unittest.TestCase):
    def test_a_line_that_is_often_first_but_also_mid_page_is_the_books_text(self):
        # Twelve spell pages: the footer is always last; "Rank: 1" comes out first on five of
        # them (two columns read in their order) and in the middle of the other seven.
        spells = ["Fetch", "Flick", "Light", "Dispel", "Banish", "Sleep", "Frost", "Pillar", "Shatter", "Flight", "Levitate", "Scrying"]
        texts = {}
        for n, spell in enumerate(spells, 1):
            body = [f"{spell} does this.", f"And {spell} does that.", f"{spell} has a limit.", f"{spell} is done."]
            rank = [f"{spell.upper()}", "✦Rank: 1"]
            texts[n] = "\n".join(rank + body if n <= 5 else body[:2] + rank + body[2:]) + f"\nCHAPTER 5 – Magic {n}"
        cleaned, running, _ = extract.strip_running(texts)
        self.assertEqual(running, ["chapter # – magic #"])
        self.assertIn("✦Rank: 1", cleaned[1])
        self.assertNotIn("CHAPTER 5", cleaned[1])


    def test_cards_that_differ_in_their_dice_are_not_a_heading_but_page_numbers_are(self):
        # A deck: one card a page, each with its own dice and a frame's words that are the same on every card.
        cards = ["D6 copper coins", "2D6 copper coins", "3D6 copper coins", "D6 silver coins", "2D6 silver coins", "3D6 silver coins", "D6 gold coins", "2D6 gold coins"]
        texts = {n: f"DRAGONBANE CORE SET\n{card}\nVALUE\n{n + 1}" for n, card in enumerate(cards, 1)}
        cleaned, running, printed = extract.strip_running(texts)
        self.assertEqual(running, ["#", "dragonbane core set", "value"])
        self.assertIn("2D6 copper coins", cleaned[2])
        self.assertNotIn("VALUE", cleaned[2])
        self.assertEqual(printed[1], 2)

    def test_a_line_that_two_or_three_cards_share_is_theirs_and_only_the_frame_on_half_the_cards_is_not(self):
        texts = {n: f"DRAGONBANE CORE SET\nCARD {n}\n✦Roll to trip the enemy (page" + ("\nwords" if n <= 3 else "") for n in range(1, 13)}
        texts.update({n: f"DRAGONBANE CORE SET\nCARD {n}\nsomething else" for n in range(4, 13)})
        cleaned, running, _ = extract.strip_running(texts)
        self.assertIn("✦Roll to trip the enemy (page", cleaned[1])
        self.assertNotIn("DRAGONBANE", cleaned[1])


@unittest.skipUnless(pymupdf, "PyMuPDF isn't installed")
class LayoutTest(unittest.TestCase):
    """What an importer reads: every page's lines with their place and style, and where the bookmarks point."""

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.tmp = Path(folder.name)
        doc = pymupdf.open()
        page = doc.new_page()
        page.insert_text((72, 80), "SPELLS AND RITUALS OF THE OLD WORLD", fontsize=26)
        page.insert_textbox(pymupdf.Rect(50, 110, 290, 400), "LEFT column, where a spell begins and goes on for some time.", fontsize=10)
        page.insert_textbox(pymupdf.Rect(310, 110, 550, 400), "RIGHT column. Fireball: two lines\nof a small bold label.", fontsize=10)
        page.insert_text((312, 300), "Fireball", fontsize=11, fontname="hebo")
        page.insert_text((72, 760), "Running Head 1", fontsize=8)
        doc.new_page().insert_text((72, 760), "Running Head 2", fontsize=8)
        doc.set_toc([[1, "Spells", 1, {"kind": 1, "to": pymupdf.Point(72, 700)}], [2, "Fireball", 1, {"kind": 1, "to": pymupdf.Point(312, 480)}]])
        doc.save(self.tmp / "book.pdf")
        self.out, _ = extract.extract(self.tmp / "book.pdf", self.tmp / "out")

    def read(self, name):
        return json.loads((self.out / name).read_text(encoding="utf-8"))

    def test_every_page_has_its_lines_in_reading_order_with_their_column_and_style(self):
        lines = self.read("layout/0001.json")["lines"]
        by_text = {line["text"].split()[0]: line for line in lines}
        self.assertEqual([line["col"] for line in lines if line["text"].startswith(("SPELLS", "LEFT", "RIGHT"))], [2, 0, 1])
        self.assertEqual(by_text["SPELLS"]["size"], 26.0)
        self.assertEqual(by_text["Fireball"]["font"], "Helvetica-Bold")
        self.assertLess(lines.index(by_text["LEFT"]), lines.index(by_text["RIGHT"]))

    def test_the_words_of_a_line_know_where_they_start_and_end(self):
        line = next(line for line in self.read("layout/0001.json")["lines"] if line["text"].startswith("SPELLS"))
        self.assertEqual(len(line["words"]), len(line["text"].split()))
        self.assertAlmostEqual(line["words"][0][0], 72, delta=1)
        self.assertGreater(line["words"][0][1], line["words"][0][0] + 30)
        self.assertLess(line["words"][0][1], line["words"][1][0])

    def test_bookmarks_point_at_a_place_measured_from_the_top_of_the_page(self):
        outline = self.read("outline.json")
        self.assertEqual([(e["level"], e["title"], e["page"], e["x"]) for e in outline], [(1, "Spells", 1, 72.0), (2, "Fireball", 1, 312.0)])
        page = pymupdf.open(self.tmp / "book.pdf")[0]
        self.assertAlmostEqual(outline[0]["y"], page.rect.height - 700, delta=1)

    def test_the_manifest_says_the_layout_is_there(self):
        self.assertTrue(self.read("manifest.json")["layout"])
