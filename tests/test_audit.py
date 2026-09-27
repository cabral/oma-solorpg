import json
import tempfile
import textwrap
import unittest
from pathlib import Path

from test_cli import CliCase

from solo import SoloError, audit


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text).lstrip(), encoding="utf-8")


def make_adventure(root):
    write(root / "adventure.toml", """
        title = "The Test Crypt"
        system = "dragonbane"
        start = "gate"

        [clocks.flood]
        label = "The flood"
        segments = 4

        [scenes.gate]
        title = "The Gate"
        exits = { crypt = "Down" }

        [scenes.crypt]
        title = "The Crypt"
        """)
    write(root / "scenes" / "gate.md", "A gate.\n")
    write(root / "npcs" / "ghoul.toml", 'name = "Ghoul"\n')
    write(root / "tables" / "omens.toml", 'name = "Omens"\nformula = "1d6"\nresults = [{ range = [1, 6], text = "Dripping" }]\n')
    write(root / "rules" / "drowning.md", "# Drowning\n")


def make_extract(root, pages):
    """What solo extract writes, for the parts the audit reads: pages with text, a manifest, chapters."""
    for number, text in pages.items():
        write(root / "pages" / f"{number:04d}.txt", text)
    write(root / "manifest.json", json.dumps({"source": "crypt.pdf", "pages": len(pages)}))
    write(root / "toc.json", json.dumps([
        {"level": 1, "title": "Credits", "start": 1, "end": 1},
        {"level": 1, "title": "The Crypt", "start": 2, "end": 4},
    ]))


LONG = "Enough text on this page that it is clearly a page of the book, not a stray number.\n"


class AuditTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.tmp = Path(folder.name)
        self.pack = self.tmp / "crypt"
        make_adventure(self.pack)
        self.book = self.tmp / "source"
        make_extract(self.book, {1: LONG, 2: LONG, 3: LONG + "Omens (D6)\n1–6 Dripping, somewhere below.\n", 4: "12\n"})

    def inventory(self, items):
        write(self.pack / "inventory.toml", f'source = "The Test Crypt"\nextract = "{self.book}"\n\n' + textwrap.dedent(items))
        return audit.audit(self.pack, "adventure")

    COMPLETE = """
        [items.credits]
        kind = "other"
        pages = [1]
        status = "skipped"
        note = "credits"

        [items.the_crypt]
        kind = "place"
        pages = ["2-3"]
        status = "mapped"
        to = ["scenes/gate", "scenes/crypt.md", "adventure.toml:clocks.flood", "tables/omens.toml"]

        [items.ghoul]
        kind = "creature"
        pages = [3]
        status = "mapped"
        to = ["npcs/ghoul"]

        [items.drowning]
        kind = "mechanic"
        status = "house"
        to = ["rules/drowning.md"]
        note = "the book gives no rule for it: a CON roll a round"
        """

    def test_a_complete_inventory_passes(self):
        report = self.inventory(self.COMPLETE)
        self.assertFalse(audit.failed(report), audit.render(report))
        self.assertEqual(report["counts"], {"mapped": 2, "house": 1, "engine": 0, "skipped": 1, "todo": 0})
        text = audit.render(report)
        self.assertIn("Everything is accounted for.", text)
        # Page 4 holds a page number and nothing else: there is nothing on it to cite.
        self.assertIn("3 of 3 pages with text are cited", text)

    def test_a_tables_own_dice_need_not_be_printed_but_its_results_must_be(self):
        make_extract(self.book, {1: LONG, 2: LONG, 3: LONG + "Omens\n1-6 Dripping, somewhere below.\n", 4: "12\n"})
        self.assertFalse(audit.failed(self.inventory(self.COMPLETE)))
        make_extract(self.book, {1: LONG, 2: LONG, 3: LONG + "Omens\n1-6 Silence.\n", 4: "12\n"})
        report = self.inventory(self.COMPLETE)
        self.assertEqual(report["unverified"], ['the_crypt: tables/omens.toml result 1-6 "Dripping" isn\'t on p. 2-3 (no dripping)'])

    def test_a_word_split_by_a_soft_hyphen_is_still_on_the_page(self):
        make_extract(self.book, {1: LONG, 2: LONG, 3: LONG + "Omens\n1-6 Drip\u00ad\nping, somewhere below.\n", 4: "12\n"})
        self.assertEqual(self.inventory(self.COMPLETE)["unverified"], [])

    def test_a_mechanic_only_in_rules_pages_is_pointed_out(self):
        report = self.inventory(self.COMPLETE.replace('status = "house"', 'status = "mapped"\npages = [3]'))
        self.assertEqual([i["id"] for i in report["prose_only"]], ["drowning"])
        self.assertFalse(audit.failed(report))
        self.assertIn("## Mechanics only in rules pages (1)\n", audit.render(report))

    def test_pack_content_no_item_claims_is_reported(self):
        report = self.inventory(self.COMPLETE.replace('"npcs/ghoul"', '"skill:solo-gm"'))
        self.assertEqual(report["unclaimed"], ["npcs/ghoul"])
        self.assertTrue(audit.failed(report))
        self.assertIn("- npcs/ghoul", audit.render(report))

    def test_references_must_name_something_in_the_pack(self):
        report = self.inventory(self.COMPLETE.replace('"npcs/ghoul"', '"npcs/ghoul", "npcs/wight", "adventure.toml:clocks.tide", "scenes/vault", "skill:nope"'))
        self.assertEqual(sorted(report["problems"]), [
            "item ghoul: to 'adventure.toml:clocks.tide': no key 'clocks.tide' in adventure.toml",
            "item ghoul: to 'npcs/wight': no such file",
            "item ghoul: to 'scenes/vault': no such scene",
            "item ghoul: to 'skill:nope': no skill called 'nope'",
        ])

    def test_each_status_asks_for_what_it_needs(self):
        report = self.inventory("""
            [items.a]
            kind = "mechanic"
            pages = [2]
            status = "mapped"

            [items.b]
            kind = "spell"
            pages = [2]
            status = "engine"

            [items.c]
            kind = "other"
            status = "skipped"

            [items.d]
            kind = "gadget"
            pages = ["5-3"]
            status = "done"
            """)
        self.assertEqual(sorted(report["problems"]), sorted([
            "item a: mapped but `to` names nothing in the pack",
            "item b: engine needs a note saying what the engine needs to run it",
            "item c: skipped needs a note saying why it's left out",
            "item c: no pages (every item from the book cites where it is)",
            "item d: status 'done', expected one of mapped, house, engine, skipped, todo",
            "item d: kind 'gadget', expected one of " + ", ".join(audit.KINDS),
            "item d: page range '5-3' runs backwards",
            "item d: no pages (every item from the book cites where it is)",
        ]))

    def test_todo_items_and_uncited_pages_fail_by_chapter(self):
        report = self.inventory("""
            [items.ghoul]
            kind = "creature"
            pages = [3]
            status = "todo"
            """)
        self.assertEqual([i["id"] for i in report["todo"]], ["ghoul"])
        self.assertEqual(report["pages"]["uncited"], [1, 2])
        text = audit.render(report)
        self.assertIn("## Not decided yet (1)\n- ghoul: Ghoul (p. 3)", text)
        self.assertIn("- Credits (p. 1): 1", text)
        self.assertIn("- The Crypt (p. 2-4): 2", text)

    def test_pages_past_the_end_are_wrong(self):
        report = self.inventory(self.COMPLETE.replace("pages = [3]", "pages = [3, 9]"))
        self.assertEqual(report["pages"]["beyond"], [9])
        self.assertTrue(audit.failed(report))

    def test_without_an_extract_the_pages_go_unchecked(self):
        write(self.pack / "inventory.toml", textwrap.dedent(self.COMPLETE))
        report = audit.audit(self.pack, "adventure")
        self.assertIsNone(report["pages"])
        self.assertFalse(audit.failed(report))
        self.assertIn("Not checked", audit.render(report))

    def test_a_pack_without_an_inventory(self):
        with self.assertRaisesRegex(SoloError, "no inventory.toml"):
            audit.audit(self.pack, "adventure")

    def test_page_lists_and_spans(self):
        self.assertEqual(audit.parse_pages([7, "2-4", "3"]), [2, 3, 4, 7])
        self.assertEqual(audit.spans([1, 2, 3, 7, 9, 10]), "1-3, 7, 9-10")
        with self.assertRaises(ValueError):
            audit.parse_pages(["p. 4"])


class SystemAuditTest(unittest.TestCase):
    def test_sections_of_tables_are_claimed_entry_by_entry(self):
        with tempfile.TemporaryDirectory() as folder:
            pack = Path(folder) / "game"
            write(pack / "system.toml", """
                name = "Game"
                family = "d20-under"
                untrained = 5

                [attributes]
                str = "Strength"

                [weapons]
                dagger = { skill = "knives", damage = "1d8" }
                sword = { skill = "swords", damage = "1d10" }

                [foundry]
                attributes = "x"
                """)
            write(pack / "inventory.toml", """
                [items.weapons]
                kind = "gear"
                pages = [40]
                status = "mapped"
                to = ["system.toml:weapons.dagger", "system.toml:attributes"]
                """)
            report = audit.audit(pack, "system")
        # name, family and foundry describe the pack, not the game
        self.assertEqual(report["unclaimed"], ["system.toml:untrained", "system.toml:weapons.sword"])


class AuditCliTest(CliCase):
    def test_audit_prints_the_report_and_fails_when_something_is_unaccounted_for(self):
        pack = self.tmp / "crypt"
        make_adventure(pack)
        write(pack / "inventory.toml", AuditTest.COMPLETE.replace('"npcs/ghoul"', '"skill:solo-gm"'))
        code, out, err = self.solo("audit", "--adventure", str(pack))
        self.assertEqual(code, 1)
        self.assertIn("# Audit of crypt", out)
        self.assertIn("- npcs/ghoul", out)
        self.assertIn("something is unaccounted for", err)
        write(pack / "inventory.toml", AuditTest.COMPLETE)
        code, out, err = self.solo("audit", "--adventure", str(pack))
        self.assertEqual(code, 0, err + out)
        self.assertIn("Everything is accounted for.", out)


if __name__ == "__main__":
    unittest.main()
