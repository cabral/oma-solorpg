import random
import unittest

from helpers import DRAGONBANE, FIXTURES, RAGNA

from solo import SoloError, campaign, creation, packs

SYSTEM = packs.load_system(DRAGONBANE)


def hero(*picks, seed=1):
    return creation.build(SYSTEM, picks, random.Random(seed))


class BuildTest(unittest.TestCase):
    def test_a_seed_rebuilds_the_same_hero(self):
        self.assertEqual(hero(seed=4), hero(seed=4))
        self.assertNotEqual(hero(seed=4), hero(seed=5))

    def test_locking_a_choice_keeps_the_rolled_numbers(self):
        # Attributes are rolled before any table, so picking a kin later changes nothing else.
        rolled = sorted(hero("fighter", "adult", seed=9)["attributes"].values())
        self.assertEqual(sorted(hero("elf", "fighter", "adult", seed=9)["attributes"].values()), rolled)

    def test_picks_are_honoured_and_recorded(self):
        sheet = hero("dwarf", "fighter", "young")
        self.assertEqual(sheet["info"], {"kin": "Dwarf", "profession": "Fighter", "age": "Young"})
        self.assertEqual(sheet["abilities"][:2], ["Stone Sense", "Shield Wall"])
        # The solo rules: one more heroic ability, for a hero alone.
        self.assertIn(sheet["abilities"][2], ["Army of One", "Sole Survivor"])
        # The kin has no names of its own here: the bundled pack's list for dwarves.
        self.assertIn(sheet["name"], SYSTEM["creation"]["names"]["dwarf"])

    def test_rules_invariants_hold_for_many_heroes(self):
        for seed in range(200):
            sheet = hero(seed=seed)
            attributes, skills = sheet["attributes"], sheet["skills"]
            trained = [k for k, s in skills.items() if s["trained"]]
            extra = {"Young": 1, "Adult": 3, "Old": 5}[sheet["info"]["age"]]
            self.assertTrue(all(3 <= v <= 18 for v in attributes.values()), sheet)
            self.assertEqual(len(trained), 5 + extra, sheet["info"])
            self.assertEqual(sheet["tracks"], {"hp": attributes["con"], "wp": attributes["wil"]})
            for key, skill in skills.items():
                base = packs.base_chance(SYSTEM, attributes[SYSTEM["skills"][key]["attribute"]])
                self.assertEqual(skill["value"], base * 2 if skill["trained"] else base, key)
            magic = {"animism", "elementalism", "mentalism"} & set(skills)
            school = {"Animist": {"animism"}, "Elementalist": {"elementalism"}}
            self.assertEqual(magic, school.get(sheet["info"].get("school"), set()))
            self.assertFalse(any("{" in item for item in sheet["items"]), sheet["items"])

    def test_the_best_roll_goes_to_the_key_attribute(self):
        sheet = hero("human", "thief", "adult", seed=21)
        self.assertEqual(sheet["attributes"]["agl"], max(sheet["attributes"].values()))

    def test_age_changes_attributes_after_the_roll(self):
        adult, old = hero("human", "scholar", "adult", seed=3), hero("human", "scholar", "old", seed=3)
        for attribute, change in {"str": -1, "agl": -1, "con": 0, "int": 1, "wil": 1, "cha": 0}.items():
            self.assertEqual(old["attributes"][attribute], max(3, min(18, adult["attributes"][attribute] + change)))

    def test_movement_is_the_kin_base_plus_agility(self):
        sheet = hero("wolfkin", "thief", "adult", seed=2)
        agility = sheet["attributes"]["agl"]
        modifier = next(m for top, m in [[7, -2], [13, 0], [18, 2]] if agility <= top)
        self.assertEqual(sheet["ratings"]["Movement"], 12 + modifier)

    def test_a_school_implies_the_mage_and_trains_its_magic(self):
        sheet = hero("animist")
        self.assertEqual((sheet["info"]["profession"], sheet["info"]["school"]), ("Mage", "Animist"))
        self.assertTrue(sheet["skills"]["animism"]["trained"])

    def test_choices_that_dont_fit_are_refused(self):
        with self.assertRaisesRegex(SoloError, "'gnome' isn't a creation choice"):
            hero("gnome")
        with self.assertRaisesRegex(SoloError, "animist doesn't go with the other choices"):
            hero("fighter", "animist")


class CharacterTest(unittest.TestCase):
    def test_a_pre_made_hero_a_file_or_words(self):
        self.assertEqual(creation.character(SYSTEM, "ragna")["name"], "Ragna")
        self.assertEqual(creation.character(SYSTEM, str(RAGNA), name="Rag")["name"], "Rag")
        self.assertEqual(creation.character(SYSTEM, "elf scholar", seed=1)["info"]["kin"], "Elf")
        self.assertEqual(creation.character(SYSTEM, None, seed=6), creation.character(SYSTEM, "random", seed=6))

    def test_a_system_without_creation_tables_says_so(self):
        system = packs.load_system(FIXTURES / "yze" / "system")
        with self.assertRaisesRegex(SoloError, "no creation tables"):
            creation.character(system, "random")

    def test_the_sheet_lists_every_skill_the_hero_can_use(self):
        sheet = campaign.character_sheet(packs.load_data(RAGNA), SYSTEM)
        self.assertEqual(sheet["skills"]["swords"], {"value": 14, "attribute": "str", "name": "Swords", "trained": True})
        self.assertEqual(sheet["skills"]["sneaking"], {"value": 4, "attribute": "agl", "name": "Sneaking", "trained": False})
        self.assertNotIn("animism", sheet["skills"])
        self.assertEqual(sheet["abilities"], ["Unforgiving", "Veteran"])


if __name__ == "__main__":
    unittest.main()
