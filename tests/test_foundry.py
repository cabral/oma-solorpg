import json
import tempfile
import unittest
from pathlib import Path

from helpers import DRAGONBANE, FIXTURES

from solo import campaign, foundry, packs

EXPORT = FIXTURES / "foundry"


class AdventureImportTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.out = Path(folder.name) / "adventure"
        foundry.import_adventure([EXPORT / "adventure"], self.out)
        self.scenes = json.loads((self.out / "scenes.json").read_text())

    def test_pages_become_scenes_and_links_become_exits_npcs_and_tables(self):
        self.assertEqual(list(self.scenes), ["the_old_road", "the_palisade_gate", "chieftains_hall"])
        gate = self.scenes["the_palisade_gate"]
        self.assertEqual(gate["exits"], {"chieftains_hall": "Into the hall", "the_old_road": "back to the road"})
        self.assertEqual(gate["tables"], ["omens"])
        # Export Data drops the actor's _id; its compendiumSource still resolves the link
        self.assertEqual(self.scenes["chieftains_hall"]["npcs"], ["grukk_red_tusk"])

    def test_scene_text_keeps_structure_and_marks_secrets(self):
        gate = (self.out / "scenes" / "the_palisade_gate.md").read_text()
        hall = (self.out / "scenes" / "chieftains_hall.md").read_text()
        self.assertIn("::: gm\nTwo guards watch. On a failed **SNEAKING** roll", gate)
        self.assertIn("Roll 1d6 for the patrol.", gate)
        self.assertIn("A torch gutters above it.", gate)
        for fragment in ("## The Hall", "- Two guards", "| 1-3 | Grukk laughs |", '> "Who dares?"'):
            self.assertIn(fragment, hall)
        self.assertNotIn("@UUID", hall)

    def test_actors_and_tables(self):
        grukk = json.loads((self.out / "npcs" / "grukk_red_tusk.json").read_text())
        wolf = json.loads((self.out / "npcs" / "dire_wolf.json").read_text())
        omens = json.loads((self.out / "tables" / "omens.json").read_text())
        self.assertEqual((grukk["stats"]["hitPoints"], grukk["skills"], grukk["gear"]), (16, {"axes": 14}, ["Battleaxe"]))
        self.assertEqual(grukk["description"], "A broad orc with a *split tusk*.")
        self.assertEqual((wolf["stats"]["attackTable"], wolf["stats"]["ferocity"]), ("dire_wolf_attacks", 2))
        self.assertEqual(omens["formula"], "1d6")
        self.assertEqual([r["range"] for r in omens["results"]], [[1, 3], [4, 5], [6, 6]])

    def test_the_result_validates_and_reimporting_keeps_authored_files(self):
        system = packs.load_system(DRAGONBANE)
        self.assertEqual(packs.validate(system, packs.load_adventure(self.out)), [])
        (self.out / "adventure.toml").write_text('title = "Mine"\nstart = "chieftains_hall"\n')
        foundry.import_adventure([EXPORT / "adventure"], self.out)
        self.assertEqual(packs.load_adventure(self.out)["start"], "chieftains_hall")


class RulesAndCharacterImportTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.tmp = Path(folder.name)

    def test_rules_pages_item_descriptions_and_skills(self):
        out = foundry.import_rules([EXPORT / "rules.json"], self.tmp / "system")
        self.assertIn("See Sneaking.", (out / "rules" / "pushing_your_roll.md").read_text())
        self.assertEqual((out / "rules" / "sneaking.md").read_text(), "# Sneaking\n\nMoving without being noticed.\n\n::: gm\nGuards get a boon at night.\n:::\n")
        self.assertEqual(json.loads((out / "skills.json").read_text())["sneaking"], {"attribute": "agl", "name": "Sneaking"})

    def test_character_maps_through_the_system_pack(self):
        system = packs.load_system(DRAGONBANE)
        out = foundry.import_character([EXPORT / "character.json"], self.tmp / "pc.json", system)
        sheet = campaign.character_sheet(json.loads(out.read_text()), system)
        self.assertEqual(sheet["conditions"], ["scared"])
        self.assertEqual(sheet["tracks"]["hp"], {"value": 12, "max": 14})
        self.assertEqual(sheet["info"], {"age": "adult", "kin": "Dwarf", "profession": "Fighter"})
        self.assertEqual(sheet["items"], ["Broadsword"])
        # Foundry says "none" for the magic school's attribute; the system pack knows it's WIL
        self.assertEqual(sheet["skills"]["elementalism"]["attribute"], "wil")


class MarkdownTest(unittest.TestCase):
    def test_links_and_enrichers(self):
        text, links = foundry.html_to_markdown(
            "<p>@UUID[JournalEntry.a.JournalEntryPage.b]{Go} @Actor[xyz]{Him} @Check[type:str]{Strength check} [[/r 2d6]]</p>"
        )
        self.assertEqual(text, "Go Him Strength check 2d6")
        self.assertEqual(links, [("JournalEntryPage", "b", "Go"), ("Actor", "xyz", "Him")])

    def test_nested_lists_keep_their_indentation(self):
        text, _ = foundry.html_to_markdown("<ul><li>One<ul><li>Inner</li></ul></li><li>Two</li></ul>")
        self.assertEqual(text, "- One\n  - Inner\n- Two")


if __name__ == "__main__":
    unittest.main()
