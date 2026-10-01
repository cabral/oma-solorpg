import tempfile
import unittest
from pathlib import Path

from fake_book import BANNER, BODY, BOX, CELL, HEADER, HEADING, LABEL, FakeBook

from solo import SoloError
from solo.sections import Book, paragraphs


class SectionsTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)

    def book(self, made):
        made.folder = self.folder
        made.save()
        return Book(self.folder)

    def test_a_section_runs_from_its_bookmark_to_the_next(self):
        made = FakeBook(self.folder)
        made.line(1, 80, "FIRST", style=HEADING)
        made.mark(1, "First")
        made.lines(1, 100, "The first part goes on", "for two lines.")
        made.line(1, 140, "SECOND", style=HEADING)
        made.mark(1, "Second")
        made.lines(1, 160, "And the second one.")
        book = self.book(made)
        self.assertEqual(book.find("First").text(), "FIRST\n\nThe first part goes on for two lines.")
        self.assertEqual(book.find("Second").text(), "SECOND\n\nAnd the second one.")

    def test_body_text_goes_on_past_a_sidebar_to_the_section_it_interrupted(self):
        made = FakeBook(self.folder)
        made.line(1, 80, "RULES", style=HEADING)
        made.mark(1, "Rules")
        made.lines(1, 100, "A paragraph begins on the left and", "is cut short by a box, and")
        made.line(1, 140, "A SIDEBAR", x=310, style=BANNER)
        made.mark(2, "Sidebar: A Sidebar")
        made.lines(1, 160, "What the box says, in light type.", x=310, style=BOX)
        made.lines(1, 200, "then it goes on under the box.", x=310)
        book = self.book(made)
        self.assertEqual(book.find("Rules").text(own=True), "RULES\n\nA paragraph begins on the left and is cut short by a box, and then it goes on under the box.")
        self.assertEqual(book.find("Sidebar: A Sidebar").text(), "A SIDEBAR\n\nWhat the box says, in light type.")

    def test_a_table_owns_its_cells_and_the_text_after_it_goes_back_to_its_section(self):
        made = FakeBook(self.folder)
        made.line(1, 80, "GEAR", style=HEADING)
        made.mark(1, "Gear")
        made.line(1, 100, "Before the table.")
        made.line(1, 130, "THINGS", x=250, style=BANNER)
        made.mark(2, "Table: Things")
        made.table(1, 150, ["ITEM", "COST"], [["Rope", "1 gold"], ["Torch", "5 copper"]], [68, 150])
        made.line(1, 220, "After the table.")
        book = self.book(made)
        self.assertEqual([line["text"] for line in book.find("Table: Things").lines(own=True)], ["THINGS", "ITEM", "COST", "Rope", "1 gold", "Torch", "5 copper"])
        self.assertEqual(book.find("Gear").text(own=True), "GEAR\n\nBefore the table.\n\nAfter the table.")

    def test_a_span_is_every_line_to_the_next_section_whoever_owns_it(self):
        made = FakeBook(self.folder)
        made.line(1, 80, "FIRST KIN", style=HEADING)
        made.mark(2, "First Kin")
        made.lines(1, 100, "Words about the first kin.")
        made.line(1, 140, "D6 NAME", x=62, style=HEADER)
        made.line(1, 160, "1", x=66, style=CELL)
        made.line(1, 160, "Ann", x=90, style=CELL)
        made.line(1, 177, "2", x=66, style=CELL)
        made.mark(3, "Table: Name")
        made.line(1, 177, "Bo", x=90, style=CELL)
        made.line(1, 220, "SECOND KIN", style=HEADING)
        made.mark(2, "Second Kin")
        book = self.book(made)
        self.assertEqual([line["text"] for line in book.find("First Kin", "Table: Name").lines(own=True)], ["2", "Bo"])
        self.assertEqual([line["text"] for line in book.find("First Kin").span()], ["FIRST KIN", "Words about the first kin.", "D6 NAME", "1", "Ann", "2", "Bo"])

    def test_a_big_initial_missing_from_the_text_is_the_letter_that_makes_the_most_common_word(self):
        made = FakeBook(self.folder)
        made.line(1, 80, "CHAPTER", style=HEADING)
        made.mark(1, "Chapter")
        made.line(1, 100, "he first words of the chapter go on", x=92)
        made.line(1, 112, "and on for a while until the margin", x=92)
        made.lines(1, 124, "is back at last. The rest of the", "words are the same as the others are,", "and a roll of the dice is a roll of", "the dice, however the game is played.", x=62)
        made.line(1, 190, "oll the dice for the first time.", x=92)
        made.line(1, 202, "Then go on with the story, the end.", x=92)
        made.lines(1, 214, "Nothing more is said here of the game,", "or of the things that the players do,", "or of the rest of it, whatever it is.", x=62)
        book = self.book(made)
        self.assertEqual(book.find("Chapter").text(own=True).split("\n\n")[1][:34], "The first words of the chapter go ")
        self.assertEqual(book.notes, ["p. 1: the big initial before 'he' is not in the PDF's text; read as 'T'", "p. 1: the big initial before 'oll' is not in the PDF's text; read as 'R'"])

    def test_labels_under_a_heading_are_its_own(self):
        made = FakeBook(self.folder)
        made.line(1, 80, "FIREBALL", style=HEADING)
        made.mark(1, "Fireball")
        made.lines(1, 100, "✦Rank: 1", "✦Range: 20 meters", style=LABEL)
        made.lines(1, 130, "The spell sends a fireball.")
        made.line(1, 160, "FROST", style=HEADING)
        made.mark(1, "Frost")
        book = self.book(made)
        self.assertEqual(book.find("Fireball").text(), "FIREBALL\n\n✦Rank: 1\n\n✦Range: 20 meters\n\nThe spell sends a fireball.")

    def test_a_bookmark_that_names_a_page_and_no_place_starts_at_its_heading(self):
        made = FakeBook(self.folder)
        made.line(1, 80, "ONE", style=HEADING)
        made.mark(1, "One")
        made.lines(1, 100, "Text of one.")
        made.line(1, 130, "TWO AND A HALF", style=HEADING)
        made.outline.append({"level": 1, "title": "Two and a half", "page": 1, "x": None, "y": None})
        made.lines(1, 150, "Text of two.")
        book = self.book(made)
        self.assertEqual(book.find("One").text(), "ONE\n\nText of one.")
        self.assertEqual(book.find("Two and a half").text(), "TWO AND A HALF\n\nText of two.")

    def test_children_join_a_section_unless_only_its_own_lines_are_asked_for(self):
        made = FakeBook(self.folder)
        made.line(1, 80, "MAGIC", style=HEADING)
        made.mark(1, "Magic")
        made.lines(1, 100, "About magic.")
        made.line(1, 130, "SPELLS", style=HEADING)
        made.mark(2, "Spells")
        made.lines(1, 150, "About spells.")
        book = self.book(made)
        self.assertEqual(book.find("Magic").text(own=True), "MAGIC\n\nAbout magic.")
        self.assertEqual(book.find("Magic").text(), "MAGIC\n\nAbout magic.\n\nSPELLS\n\nAbout spells.")
        self.assertEqual(book.find("Magic", "Spells").pages, [1])

    def test_finding_by_a_path_takes_the_shallowest_and_a_missing_title_names_the_printing(self):
        made = FakeBook(self.folder)
        made.line(1, 80, "SKILLS", style=HEADING)
        made.mark(1, "Skills")
        made.line(1, 100, "ABILITIES", style=HEADING)
        made.mark(2, "Abilities")
        made.line(1, 120, "ABILITIES", style=HEADING)
        made.mark(3, "Abilities")
        book = self.book(made)
        self.assertEqual(book.find("Skills", "Abilities").level, 2)
        with self.assertRaisesRegex(SoloError, r"no section 'Spells' under 'Skills'.*another printing"):
            book.find("Skills", "Spells")

    def test_an_extract_without_layout_says_to_extract_again(self):
        (self.folder / "manifest.json").write_text('{"source": "old.pdf"}', encoding="utf-8")
        with self.assertRaisesRegex(SoloError, "extract"):
            Book(self.folder)

    def test_the_fingerprint_follows_the_bookmarks_and_not_the_words(self):
        first, second = FakeBook(self.folder / "a"), FakeBook(self.folder / "b")
        for made, words in ((first, "one"), (second, "another")):
            made.line(1, 80, "HEAD", style=HEADING)
            made.mark(1, "Head")
            made.line(1, 100, f"{words} text")
        self.assertEqual(self.book_in(first).fingerprint(), self.book_in(second).fingerprint())
        second.outline[0]["title"] = "Other"
        self.assertNotEqual(self.book_in(first).fingerprint(), self.book_in(second).fingerprint())

    def book_in(self, made):
        made.save()
        return Book(made.folder)


class ParagraphsTest(unittest.TestCase):
    def lines(self, *rows):
        """(text, x, y) rows as the layout has them, in one column of one page."""
        return [{"text": text, "x0": x, "y0": y, "size": 10.0, "col": 0, "page": 1} for text, x, y in rows]

    def test_a_soft_hyphen_at_a_line_end_joins_the_word_and_a_gap_starts_a_paragraph(self):
        text = paragraphs(self.lines(("A word broken in the mid­", 62, 100), ("dle of it.", 62, 112), ("Next one.", 62, 140)))
        self.assertEqual(text, "A word broken in the middle of it.\n\nNext one.")

    def test_a_first_line_set_in_from_the_margin_starts_a_paragraph(self):
        text = paragraphs(self.lines(("One paragraph ends here.", 62, 100), ("Another starts", 76, 112), ("and goes on.", 62, 124)))
        self.assertEqual(text, "One paragraph ends here.\n\nAnother starts and goes on.")

    def test_with_a_hanging_indent_the_set_in_lines_stay_and_a_line_back_at_the_margin_starts_a_paragraph(self):
        lines = self.lines(("Resist: Takes half damage from", 80, 100), ("most blows, but not fire.", 94, 112), ("Wings: It flies.", 80, 124), ("Flock: Many of them", 80, 136), ("attack as one.", 94, 148))
        self.assertEqual(paragraphs(lines, hanging=True), "Resist: Takes half damage from most blows, but not fire.\n\nWings: It flies.\n\nFlock: Many of them attack as one.")

    def test_a_bullet_starts_one_and_its_wrapped_line_stays_with_it(self):
        text = paragraphs(self.lines(("✦First point, which is long", 62, 100), ("enough to wrap.", 75, 112), ("✦Second point.", 62, 124), ("Body text after the list.", 62, 136)))
        self.assertEqual(text, "✦First point, which is long enough to wrap.\n\n✦Second point.\n\nBody text after the list.")

    def test_a_sentence_cut_by_the_end_of_a_column_goes_on_but_a_new_one_does_not(self):
        rows = self.lines(("The sentence is cut at the", 62, 700))
        rows += [{"text": "end of the column.", "x0": 315, "y0": 100, "size": 10.0, "col": 1, "page": 1}]
        self.assertEqual(paragraphs(rows), "The sentence is cut at the end of the column.")
        rows[1]["text"] = "A new paragraph starts."
        self.assertEqual(paragraphs(rows), "The sentence is cut at the\n\nA new paragraph starts.")


class CellsTest(unittest.TestCase):
    def test_a_line_of_cells_is_one_cell_to_a_gap(self):
        from solo.books.grid import _cells
        line = {"text": "5 silver Common", "words": [[154.5, 160.2], [162.1, 185.6], [192.8, 229.8]]}
        self.assertEqual(_cells(line), [("5 silver", 154.5, 185.6), ("Common", 192.8, 229.8)])
        self.assertEqual(CELL[1], 9.0)


if __name__ == "__main__":
    unittest.main()
