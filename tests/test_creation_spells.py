"""A new mage knows the spells and tricks the profession lets them pick, from their school and general magic, and holds them ready. Made-up rules (tests/fixtures/house)."""

import unittest

from helpers import BEASTS

from solo import creation, packs


class MageStartTest(unittest.TestCase):
    def setUp(self):
        self.system = packs.load_system(BEASTS)

    def test_a_mage_knows_so_many_spells_of_a_rank_and_so_many_tricks_of_their_school_and_general_magic(self):
        sheet = creation.character(self.system, "elf mage elementalist", seed=3)
        spells = self.system["spells"]
        known = {name: next(spell for spell in spells.values() if spell["name"] == name) for name in sheet["spells"]}
        self.assertEqual(len(known), 3)
        self.assertEqual(sorted(spell.get("trick", False) for spell in known.values()), [False, False, True])
        self.assertTrue(all(spell["school"] in ("elementalism", "general") for spell in known.values()))
        self.assertTrue(all(spell["rank"] == 1 for spell in known.values() if not spell.get("trick")))

    def test_the_spells_are_held_ready_and_a_trick_is_never_held(self):
        sheet = creation.character(self.system, "dwarf mage animist", seed=5)
        self.assertEqual(sheet["prepared"], [name for name in sheet["spells"] if name in sheet["prepared"]])
        tricks = {spell["name"] for spell in self.system["spells"].values() if spell.get("trick")}
        self.assertFalse(set(sheet["prepared"]) & tricks)

    def test_another_profession_knows_no_spells_and_a_seed_still_makes_the_same_hero(self):
        self.assertNotIn("spells", creation.character(self.system, "human fighter", seed=3))
        first, second = (creation.character(self.system, "elf mage elementalist", seed=7) for _ in range(2))
        self.assertEqual(first, second)
        self.assertEqual({key: value for key, value in first.items() if key not in ("spells", "prepared")}["skills"], second["skills"])


if __name__ == "__main__":
    unittest.main()
