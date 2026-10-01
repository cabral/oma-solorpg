"""`solo validate` on the data a fight, a journey and a spell run on: what is wrong with each says so."""

import copy
import unittest

from helpers import BEASTS

from solo import packs


class ValidatePlay(unittest.TestCase):
    def setUp(self):
        self.system = packs.load_system(BEASTS)

    def problems(self, change):
        system = copy.deepcopy(self.system)
        change(system)
        return [p for p in packs._validate_play(system)]

    def test_the_fixture_is_sound(self):
        self.assertEqual(packs._validate_play(self.system), [])

    def test_a_weapon_tables_stats_are_checked(self):
        found = self.problems(lambda s: s["weapons"]["hook_sword"].update(grip=3, str=-1, range="far", features="sharp"))
        self.assertEqual(len(found), 4)
        self.assertIn("system: weapon hook_sword: grip is 1 or 2 hands", found)

    def test_how_a_dragon_and_a_monster_play_is_checked(self):
        found = self.problems(lambda s: s["combat"].update(dragon="often", parry_dragon="always", monster_repeat="never", monster_defense=0, repair="welding"))
        self.assertEqual(len(found), 5)

    def test_a_demons_tables_must_exist(self):
        found = self.problems(lambda s: s["combat"].update(demon={"melee": "nothing_here"}))
        self.assertEqual(found, ["system: combat demon melee rolls unknown table nothing_here"])

    def test_a_load_and_what_armor_hampers_are_checked(self):
        found = self.problems(lambda s: (s["encumbrance"].update(attribute="luck", divisor=0, carriers={"backpack": "two"}), s["gear"]["chainmail"].update(banes=["flying"], weight=-1)))
        self.assertEqual(len(found), 5)

    def test_a_journey_needs_its_numbers_a_skill_and_a_table(self):
        found = self.problems(lambda s: s["journey"].update(foot=0, skill="flying", mishaps="mishaps"))
        self.assertEqual(len(found), 3)

    def test_magic_its_table_its_dice_and_its_dragon_are_checked(self):
        found = self.problems(lambda s: s["magic"].update(track="mana", mishap="none", body=["banana"], dragon=["fly"]))
        self.assertEqual(len(found), 4)

    def test_a_spell_says_what_is_wrong_with_it(self):
        found = self.problems(lambda s: s["spells"]["ember"].update(school="astrology", damage="lots", per_level={"dice": 0}, avoid=["hide"]))
        self.assertEqual(len(found), 4)
        self.assertIn("spell ember: avoid names hide, which is dodge or parry", found)

    def test_a_heroic_ability_says_what_is_wrong_with_it(self):
        found = self.problems(lambda s: s["abilities"]["slayer"].update(pay={"mana": 3}, max={"luck": 1}, extra_damage="much", requires={"skills": ["flying"], "kind": "gods"}))
        self.assertEqual(len(found), 5)

    def test_a_monsters_resistances_and_healing_are_checked(self):
        found = self.problems(lambda s: s["bestiary"]["moss_troll"]["stats"].update(regenerate="lots", resist=5))
        self.assertEqual(len(found), 2)


if __name__ == "__main__":
    unittest.main()
