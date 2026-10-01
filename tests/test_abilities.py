"""Heroic abilities the engine runs: what they cost, what they add to an attack, a defence, a rest or the
initiative, and the ones that change the sheet. Played on the made-up test rules (tests/fixtures/house)."""

from helpers import BEASTS, CampaignTest, Dice

from solo import SoloError, campaign, cli


class Abilities(CampaignTest):
    system = BEASTS

    def gain(self, c, *names):
        return c.commit({"pc": {"abilities": {"add": list(names)}}})

    def test_an_ability_that_raises_a_track_does_so_each_time_it_is_taken(self):
        with self.session() as c:
            self.gain(c, "Tough", "Tough")
            self.assertEqual(c.state["pc"]["tracks"]["hp"], {"value": 20, "max": 20})
            self.gain(c, "Focus")
            self.assertEqual(c.state["pc"]["tracks"]["wp"], {"value": 13, "max": 13})
            self.assertEqual(c.state["pc"]["abilities"].count("Tough"), 2)

    def test_an_ability_the_hero_doesnt_meet_the_requirement_for_comes_with_a_warning(self):
        with self.session() as c:
            event = self.gain(c, "Quickdraw", "Slayer")
            self.assertEqual(event["warnings"], ["Quickdraw needs Evade at 12 (the best is 10)"])  # Slayer's any weapon skill 12 is met by swords 14

    def monster(self, c, name="moss_troll"):
        c.commit({"npc": {name: {"name": name.replace("_", " ").capitalize(), "monster": name}}})
        c.fight([name], rng=Dice(1, 2, 3))

    def test_an_attack_that_hits_with_an_ability_adds_its_dice_and_pays_for_it(self):
        with self.session() as c:
            self.gain(c, "Slayer")
            self.monster(c)
            c.attack("moss_troll", "broadsword", use="slayer", rng=Dice(3, 4, 4, 2, 5))  # 2d6 (4+4) + STR 1d4 (2) + 1d6 (5)
            paid, blow = c.events[-2], c.events[-1]
            self.assertEqual((paid["type"], paid["cost"], blow["expr"], blow["dealt"]), ("ability", {"wp": 3}, "2d6+1d4+1d6", 15))
            self.assertEqual(c.state["pc"]["tracks"]["wp"]["value"], 8)

    def test_a_miss_costs_nothing_and_a_foe_that_is_no_monster_is_refused_before_the_roll(self):
        with self.session() as c:
            self.gain(c, "Slayer")
            self.monster(c)
            c.attack("moss_troll", "broadsword", use="slayer", rng=Dice(19))
            self.assertEqual(c.state["pc"]["tracks"]["wp"]["value"], 11)
        with self.session() as c:
            c.end_fight()
            c.fight(["cultist"], rng=Dice(1, 1))
            with self.assertRaisesRegex(SoloError, "Slayer is for monsters, and Cultist isn't one"):
                c.attack("cultist", "broadsword", use="slayer")

    def test_an_ability_the_hero_cant_pay_for_is_refused_before_the_roll(self):
        with self.session() as c:
            self.gain(c, "Slayer")
            c.commit({"pc": {"wp": 2}})
            self.monster(c)
            with self.assertRaisesRegex(SoloError, "Slayer costs 3 WP, and Ragna has 2"):
                c.attack("moss_troll", "broadsword", use="slayer")

    def test_an_ability_for_a_weapon_held_in_two_hands_is_refused_with_one_in_one(self):
        with self.session() as c:
            self.gain(c, "Heavy swing")
            self.monster(c)
            with self.assertRaisesRegex(SoloError, "needs a weapon held in 2 hands"):
                c.attack("moss_troll", "broadsword", use="heavy swing")
            c.commit({"pc": {"items": {"add": ["Long axe"]}}})
            c.attack("moss_troll", "long axe", use="heavy swing", rng=Dice(3, 5, 4, 2, 6))
            self.assertEqual(c.events[-1]["expr"], "2d6+1d4+1d8")

    def test_an_extra_parry_costs_what_the_ability_says_and_a_boon_ability_gives_a_boon(self):
        with self.session() as c:
            self.gain(c, "Guard stance", "Shield wall")
            c.fight(["cultist"], rng=Dice(1, 1))
            c.enemy(rng=Dice(5))
            c.defend("parry", "broadsword", use="guard stance", rng=Dice(9))
            self.assertEqual((c.events[-2]["type"], c.state["pc"]["tracks"]["wp"]["value"]), ("ability", 8))
            with self.assertRaisesRegex(SoloError, "Guard stance doesn't help with evade"):
                c.enemy(rng=Dice(2))
                c.defend("evade", use="guard stance")

    def test_shield_wall_parries_what_a_monster_could_not_and_with_a_boon(self):
        with self.session() as c:
            self.gain(c, "Shield wall")
            self.monster(c)
            c.enemy(rng=Dice(1))  # a monster's blow: it can't be parried
            with self.assertRaisesRegex(SoloError, "can't be parried"):
                c.defend("parry", "shield")
            parry = c.defend("parry", "shield", use="shield wall", rng=Dice(2, 9))  # a boon: two dice, the better counts
            self.assertEqual((parry["boons"], parry["outcome"]["result"]), (1, 2))
            self.assertEqual(c.state["pc"]["tracks"]["wp"]["value"], 9)

    def test_an_ability_that_heals_adds_to_the_rest_it_is_for(self):
        with self.session() as c:
            self.gain(c, "Mender")
            c.commit({"pc": {"hp": 4}})
            c.rest("stretch", rng=Dice(3, 2, 1), use="mender")  # the ability's 1d4 (3), then 1d8 hp (2) and 1d8 wp (1)
            self.assertEqual(c.state["pc"]["tracks"]["hp"]["value"], 4 + 2 + 3)
            self.assertEqual(c.state["pc"]["tracks"]["wp"]["value"], 11 - 2 + 1)
            with self.assertRaisesRegex(SoloError, "Mender adds nothing to a round rest"):
                c.rest("round", use="mender")

    def test_one_ability_takes_the_better_of_two_initiative_cards_and_another_keeps_last_rounds(self):
        with self.session() as c:
            self.gain(c, "Quickdraw", "Steady")
            c.fight(["cultist"], rng=Dice(5, 2))  # Ragna 5, the cultist 2
            c.next_round(rng=Dice(5, 2, 1), use="quickdraw")  # Ragna draws 5 and a spare 1, and keeps the 1; the cultist 2
            self.assertEqual([(f["id"], f["card"]) for f in c.events[-1]["order"]], [("pc", 1), ("cultist", 2)])
            c.next_round(rng=Dice(4), use="steady")  # last round's 1 stays with Ragna; the cultist draws from the rest
            self.assertEqual([(f["id"], f["card"]) for f in c.events[-1]["order"]], [("pc", 1), ("cultist", 5)])
            self.assertEqual(c.state["pc"]["tracks"]["wp"]["value"], 11 - 2 - 1)

    def test_an_ability_the_gm_runs_is_paid_for_with_solo_ability(self):
        with self.session() as c:
            self.gain(c, "Far gaze")
            with self.assertRaisesRegex(SoloError, "costs what the hero chooses to spend"):
                c.use("far gaze")
            event = c.use("far gaze", cost=4)
            self.assertEqual((event["cost"], c.state["pc"]["tracks"]["wp"]["value"]), ({"wp": 4}, 7))
            self.assertIn("uses Far gaze (pays 4 WP)", cli.campaign.describe(event))
            with self.assertRaisesRegex(SoloError, "Ragna doesn't have Slayer"):
                c.use("slayer")
            with self.assertRaisesRegex(SoloError, "no heroic ability 'nonsense'"):
                c.use("nonsense")


class Powers(CampaignTest):
    """What state.json gives the Table of the hero's abilities: where each is asked for, what it costs, whether the hero can pay."""

    system = BEASTS

    def powers(self, c):
        return {a["name"]: a for a in campaign.snapshot(c.system, c.state, c.adventure)["abilities"]}

    def test_each_ability_says_where_it_is_asked_for(self):
        with self.session() as c:
            c.commit({"pc": {"abilities": {"add": ["Heavy swing", "Guard stance", "Shield wall", "Mender", "Quickdraw", "Steady", "Trailwise", "Far gaze", "Tough"]}}})
            found = {name: (a["use"], a["on"]) for name, a in self.powers(c).items()}
            self.assertEqual(found, {"Heavy swing": ("attack", None), "Guard stance": ("defend", "parry"), "Shield wall": ("defend", "parry"),
                                     "Mender": ("rest", "stretch"), "Quickdraw": ("round", None), "Steady": ("round", None),
                                     "Trailwise": ("journey", None), "Far gaze": ("alone", None), "Tough": (None, None)})

    def test_the_hero_is_told_what_each_costs_and_whether_they_can_pay_now(self):
        with self.session() as c:
            c.commit({"pc": {"abilities": {"add": ["Heavy swing", "Far gaze"]}}})
            self.assertEqual([(a["cost"], a["afford"]) for a in self.powers(c).values()], [({"wp": 2}, True), ("varies", True)])
            c.commit({"pc": {"wp": 1}})
            self.assertEqual([a["afford"] for a in self.powers(c).values()], [False, True])
            c.commit({"pc": {"wp": 0}})
            self.assertEqual([a["afford"] for a in self.powers(c).values()], [False, False])

    def test_an_ability_the_pack_doesnt_run_is_left_out(self):
        with self.session() as c:
            c.commit({"pc": {"abilities": {"add": ["Whistling"]}}})
            self.assertNotIn("Whistling", self.powers(c))
