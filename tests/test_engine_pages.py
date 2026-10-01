"""The rules pages the engine writes from a pack's data: what `solo rule` says about gear, Dragons, monsters, loads,
journeys and spells is what the engine does, because it is worded from the same numbers."""

import unittest

from helpers import BEASTS, DRAGONS

from solo import packs


def pages(path):
    return {page["title"]: page["text"] for page in packs.engine_rules(packs.load_system(path))}


class EnginePages(unittest.TestCase):
    def test_gear_dragons_and_monsters_in_a_fight_say_what_the_data_makes_true(self):
        text = pages(DRAGONS)["Gear, Dragons and monsters in a fight"]
        for sentence in ("asks for more STR than the hero has", "solo attack <foe> --range <meters>", "A parry against a blow worse than the weapon's durability",
                         "solo dragon double", "counterattack", "rolls the pack's mishap table"):
            self.assertIn(sentence, text)

    def test_monster_rules_appear_when_a_monster_has_them_and_a_defence_number_is_the_packs(self):
        text = pages(BEASTS)["Gear, Dragons and monsters in a fight"]
        self.assertIn("doesn't use one attack on two turns running", text)
        self.assertIn("A monster rolls against 12", text)
        self.assertIn("regeneration", text)

    def test_the_load_the_journey_and_the_magic_have_their_pages(self):
        found = pages(BEASTS)
        self.assertIn("Capacity is the hero's STR over 2, rounded up; a backpack adds 2", found["Load the hero carries"])
        self.assertIn("covers 12 kilometers on foot and 24 mounted", found["Travel with solo journey"])
        self.assertIn("costs 3 WP a power level", found["Casting spells with solo cast"])

    def test_the_abilities_the_engine_runs_are_listed_with_what_they_cost_and_where_to_use_them(self):
        text = pages(BEASTS)["Abilities the engine runs"]
        self.assertIn('Slayer: 1d6 more damage against monsters; costs 3 WP, when the blow hits: solo attack --use "Slayer".', text)
        self.assertIn("Tough: raises HP by 3 when the hero takes it (and again each time it is taken).", text)
        self.assertIn('Steady: keep last round\'s initiative card; costs 1 WP: solo fight --round --use "Steady".', text)

    def test_a_price_line_shows_a_weapons_stats_and_what_armor_hampers(self):
        system = packs.load_system(BEASTS)
        sword = packs._price_line(system, "hook_sword", {"name": "Hook sword", "price": "5 gold"})
        self.assertIn("1H, STR 18, range 2, durability 6; slashing", sword)
        mail = packs._price_line(system, "chainmail", system["gear"]["chainmail"])
        self.assertIn("armor 3; bane on sneaking", mail)

    def test_the_threats_page_tells_which_rule_is_in_force(self):
        from helpers import ACTIVITY
        self.assertIn("once for each activity", pages(ACTIVITY)["Threats"])
        self.assertIn("when the hero spends a stretch or more", pages(BEASTS)["Threats"])


if __name__ == "__main__":
    unittest.main()
