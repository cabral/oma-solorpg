"""Spells: what they cost, the school roll, damage and healing by power level, power from the body, a Dragon's choice,
a Demon's mishap, and learning and preparing. Played on the made-up test rules (tests/fixtures/house)."""

from helpers import BEASTS, MAGE, CampaignTest, Dice

from solo import SoloError, campaign, cli


class Magic(CampaignTest):
    system, character = BEASTS, MAGE

    def fight(self, c, *foes):
        c.fight(list(foes) or ["cultist"], rng=Dice(*range(1, 5)))

    def test_a_damage_spell_costs_wp_then_rolls_the_school_and_hits_the_foe(self):
        with self.session() as c:
            self.fight(c)
            c.cast("ember", targets=["cultist"], rng=Dice(5, 3, 4))  # elementalism 12: a 5; 2d4 is 3+4
            kinds = [e["type"] for e in c.events[-3:]]
            self.assertEqual(kinds, ["spell", "check", "wound"])
            self.assertEqual(c.state["pc"]["tracks"]["wp"]["value"], 10)  # 13 - 3
            wound = c.events[-1]
            self.assertEqual((wound["expr"], wound["dealt"], wound["kind"], wound["why"]), ("2d4", 7, "fire", "Ember"))
            self.assertEqual(c.state["combat"]["foes"]["cultist"]["hp"], 1)

    def test_each_power_level_costs_the_same_again_and_adds_to_the_damage(self):
        with self.session() as c:
            self.fight(c)
            c.cast("ember", power=2, targets=["cultist"], rng=Dice(5, 1, 1, 1))  # 3d4 at power 2
            self.assertEqual((c.events[-1]["expr"], c.state["pc"]["tracks"]["wp"]["value"]), ("3d4", 7))

    def test_a_failed_school_roll_still_costs_the_wp_and_does_nothing(self):
        with self.session() as c:
            self.fight(c)
            c.cast("ember", targets=["cultist"], rng=Dice(15))
            self.assertEqual(c.events[-1]["type"], "check")
            self.assertFalse(c.events[-1]["outcome"]["success"])
            self.assertEqual(c.state["pc"]["tracks"]["wp"]["value"], 10)

    def test_a_spell_that_heals_adds_a_die_for_each_level_beyond_the_first(self):
        with self.session() as c:
            c.commit({"pc": {"hp": 2}})
            c.cast("mend", power=2, rng=Dice(5, 1, 2, 3))  # animism 10: a 5; 2d4 + 1d4 = 1+2+3
            self.assertEqual((c.events[-1]["healed"], c.state["pc"]["tracks"]["hp"]["value"]), (6, 8))

    def test_a_spell_without_power_levels_always_costs_one_level_and_a_trick_one_wp_and_never_fails(self):
        with self.session() as c:
            c.cast("ward", power=3, rng=Dice(5))
            self.assertEqual(c.state["pc"]["tracks"]["wp"]["value"], 10)
            trick = c.cast("spark")
            self.assertEqual((trick["type"], trick["cost"], c.state["pc"]["tracks"]["wp"]["value"]), ("spell", 1, 9))

    def test_a_spell_the_hero_cant_pay_for_is_refused_and_the_body_can_make_up_the_difference(self):
        with self.session() as c:
            c.commit({"pc": {"wp": 2}})
            with self.assertRaisesRegex(SoloError, "Ember at power 1 costs 3 WP, and Sibyl has 2"):
                c.cast("ember", targets=[], rng=Dice(5))
            c.cast("ember", body="1d6", rng=Dice(5, 5))  # 2 WP is few enough; the die gives 5, of which 3 is spent; 5 is lost as harm
            paid = c.events[-2]
            self.assertEqual((paid["body"], c.state["pc"]["tracks"]["wp"]["value"], c.state["pc"]["tracks"]["hp"]["value"]), (5, 2, 7))

    def test_power_from_the_body_is_not_for_healing_or_for_a_hero_with_wp_to_spare(self):
        with self.session() as c:
            with self.assertRaisesRegex(SoloError, "power from the body is for a hero with 2 WP or none left"):
                c.cast("ember", body="1d6")
            c.commit({"pc": {"wp": 1}})
            with self.assertRaisesRegex(SoloError, "not for healing"):
                c.cast("mend", body="1d6")

    def test_a_spell_must_be_prepared_unless_it_is_cast_from_the_grimoire_and_not_a_reaction(self):
        with self.session() as c:
            with self.assertRaisesRegex(SoloError, "Lash isn't prepared"):
                c.cast("lash")
            with self.assertRaisesRegex(SoloError, "reaction spell, which can't be cast from the grimoire"):
                c.cast("gale", grimoire=True)
            self.fight(c)
            c.cast("lash", grimoire=True, targets=["cultist"], rng=Dice(15))
            self.assertTrue(c.events[-2]["grimoire"])

    def test_a_spell_the_hero_doesnt_know_is_refused(self):
        with self.session() as c:
            with self.assertRaisesRegex(SoloError, "Sibyl doesn't know Charm"):
                c.cast("charm")

    def test_a_spell_that_goes_on_to_more_foes_rolls_each_ones_dice_and_ignores_armor_when_it_says(self):
        with self.session() as c:
            c.commit({"pc": {"abilities": {"add": []}}, "npc": {"brute": {"name": "Brute", "template": "boss", "attacker": "melee"}}})
            c.fight(["brute", "cultist"], rng=Dice(1, 2, 3))
            c.cast("lash", grimoire=True, targets=["brute", "cultist"], rng=Dice(5, 4, 4, 3, 3))  # 2d8 = 8 (armor 3 doesn't count), then 2d6 = 6
            wounds = [e for e in c.events if e["type"] == "wound"]
            self.assertEqual([(w["target"], w["expr"], w["dealt"]) for w in wounds], [("brute", "2d8", 8), ("cultist", "2d6", 6)])

    def test_a_foe_can_dodge_a_spell_that_can_be_dodged_and_a_spell_that_cant_refuses_the_question(self):
        with self.session() as c:
            self.fight(c)
            with self.assertRaisesRegex(SoloError, "can't be avoided that way"):
                c.cast("ember", targets=["cultist"], defended="sidestep")
            c.cast("ember", targets=["cultist"], defended="dodge", rng=Dice(5, 4))  # the spell takes; the cultist's EVADE 5 (the stat block has none) rolls 4: dodged
            self.assertEqual([e["type"] for e in c.events[-2:]], ["check", "defence"])
            self.assertEqual(c.state["combat"]["foes"]["cultist"]["hp"], 8)

    def test_a_dragon_on_a_spell_is_the_players_choice(self):
        with self.session() as c:
            self.fight(c)
            c.cast("ember", targets=["cultist"], rng=Dice(1))
            self.assertEqual(c.state["choice"], {"of": c.events[-1]["of"], "kind": "spell", "options": ["double", "free", "another"], "target": None})
            with self.assertRaisesRegex(SoloError, "a Dragon is waiting"):
                c.cast("spark")
            c.dragon("double", rng=Dice(2, 2))  # 2d4 = 4, doubled
            wound = next(e for e in c.events if e["type"] == "wound")
            self.assertEqual((wound["double"], wound["dealt"]), (True, 8))
            self.assertIsNone(c.state["choice"])

    def test_a_dragon_can_pay_for_the_spell(self):
        with self.session() as c:
            c.cast("mend", rng=Dice(1, 2, 2))
            c.dragon("free")
            self.assertEqual(c.state["pc"]["tracks"]["wp"]["value"], 13)

    def test_a_demon_on_a_spell_rolls_the_mishap_and_a_condition_is_the_engines_to_give(self):
        with self.session() as c:
            c.cast("mend", power=2, rng=Dice(20, 1, 3))  # the mishap: dazed (and the ritual clock ticks)
            self.assertIn("dazed", c.state["pc"]["conditions"])

    def test_a_mishap_can_harm_a_die_for_each_power_level(self):
        with self.session() as c:
            c.cast("mend", power=2, rng=Dice(20, 2, 3, 4, 3))
            self.assertEqual(c.state["pc"]["tracks"]["hp"]["value"], 12 - 7)

    def test_a_mishap_can_drain_willpower(self):
        with self.session() as c:
            c.cast("ward", rng=Dice(20, 3, 3, 3))  # 1d4 a level
            self.assertEqual(c.state["pc"]["tracks"]["wp"]["value"], 13 - 3 - 3)

    def test_a_demon_when_the_hero_is_already_dazed_leaves_them_another_condition(self):
        with self.session() as c:
            c.commit({"pc": {"conditions": {"add": ["dazed"]}}})
            c.cast("ward", rng=Dice(20, 1, 3))
            self.assertEqual(c.state["pc"]["conditions"], ["dazed", "exhausted"])

    def test_metal_at_hand_is_said_and_left_to_the_gm(self):
        with self.session() as c:
            c.commit({"pc": {"items": {"add": ["Chainmail"]}}})
            event = c.cast("spark")
            self.assertEqual(event["metal"], ["chainmail"])
            self.assertIn("metal at hand: chainmail", cli.campaign.describe(event))


class Learning(CampaignTest):
    system, character = BEASTS, MAGE

    def test_the_hero_holds_as_many_spells_ready_as_the_limit_and_drops_one_to_make_room(self):
        with self.session() as c:
            c.commit({"pc": {"spells": {"add": ["Charm"]}, "prepared": {"add": ["Another", "And another", "And a third"]}}})  # six ready: the limit, the base chance of INT 15
            with self.assertRaisesRegex(SoloError, "can hold 6 spells prepared"):
                c.prepare("charm")
            with self.assertRaisesRegex(SoloError, "'Mist' isn't prepared|no spell called 'mist'"):
                c.prepare("charm", drop="mist")
            c.prepare("charm", drop="Ward")
            self.assertEqual(sorted(c.state["pc"]["prepared"]), sorted(["Ember", "Mend", "Another", "And another", "And a third", "Charm"]))

    def test_a_magic_trick_is_always_ready(self):
        with self.session() as c:
            with self.assertRaisesRegex(SoloError, "a magic trick is always ready"):
                c.prepare("spark")

    def test_preparing_an_unknown_or_a_prepared_spell_is_refused(self):
        with self.session() as c:
            with self.assertRaisesRegex(SoloError, "already prepared"):
                c.prepare("ember")
            with self.assertRaisesRegex(SoloError, "doesn't know Charm"):
                c.prepare("charm")

    def test_a_spell_takes_a_mark_for_its_school_and_a_roll_with_a_boon_from_a_teacher(self):
        with self.session() as c:
            with self.assertRaisesRegex(SoloError, "takes an advancement mark for elementalism"):
                c.learn("charm")
            c.mark("elementalism")
            event = c.learn("charm", rng=Dice(5, 12))  # INT 15 with a boon: two dice, the better counts
            self.assertEqual((event["learned"], "Charm" in c.state["pc"]["spells"], c.state["pc"]["marks"]), (True, True, []))

    def test_a_prerequisite_that_is_one_of_several_is_met_by_any_of_them(self):
        with self.session() as c:
            c.mark("elementalism")
            with self.assertRaisesRegex(SoloError, "Surge asks for hex or bolt first"):
                c.learn("surge")
            c.commit({"pc": {"spells": {"add": ["Bolt"]}}})
            event = c.learn("surge", rng=Dice(5, 12))
            self.assertTrue(event["learned"])

    def test_a_school_with_no_skill_of_its_own_is_rolled_as_the_skill_it_uses(self):
        with self.session() as c:
            c.commit({"pc": {"spells": {"add": ["Hymn"]}}})
            c.cast("hymn", grimoire=True, rng=Dice(4))  # CHA 10: PERFORMANCE untrained is 4, which a 4 makes
            self.assertEqual((c.events[-1]["type"], c.events[-1]["outcome"]["success"], c.events[-1]["outcome"]["target"]), ("check", True, 4))
            c.cast("hymn", grimoire=True, rng=Dice(5))
            self.assertEqual(c.events[-1]["outcome"]["success"], False)

    def test_learning_such_a_school_asks_for_the_skill_it_uses(self):
        with self.session() as c:
            with self.assertRaisesRegex(SoloError, "Hymn asks for chanting first|has no skill level in performance"):
                c.learn("hymn")

    def test_a_failed_lesson_still_uses_the_mark(self):
        with self.session() as c:
            c.mark("elementalism")
            event = c.learn("charm", rng=Dice(19, 18))
            self.assertEqual((event["learned"], "Charm" in c.state["pc"]["spells"], c.state["pc"]["marks"]), (False, False, []))

    def test_a_grimoire_teaches_with_languages_and_no_boon(self):
        with self.session() as c:
            c.mark("elementalism")
            event = c.learn("charm", source="grimoire", rng=Dice(9))  # LANGUAGES: base chance for INT 15: 6, so a 9 fails
            self.assertFalse(event["learned"])

    def test_a_trick_needs_no_roll_or_mark_and_takes_a_stretch(self):
        with self.session() as c:
            c.commit({"pc": {"spells": {"remove": ["Spark"]}}})
            before = c.state["time"]
            c.learn("spark")
            self.assertEqual((c.state["time"] - before, "Spark" in c.state["pc"]["spells"]), (900, True))


class Sheet(CampaignTest):
    """What state.json gives the Table of a hero's magic: the buttons need no rule of their own."""

    system, character = BEASTS, MAGE

    def view(self, c):
        return campaign.snapshot(c.system, c.state, c.adventure)["magic"]

    def test_the_spells_the_hero_knows_come_with_what_their_buttons_need_and_the_tricks_last(self):
        with self.session() as c:
            magic = self.view(c)
            self.assertEqual([s["name"] for s in magic["spells"]], ["Ember", "Gale", "Mend", "Ward", "Lash", "Spark"])
            ember, gale, mend, ward, lash, spark = magic["spells"]
            self.assertEqual((ember["prepared"], ember["cost"], ember["damage"], ember["power"]), (True, 3, True, True))
            self.assertEqual((gale["prepared"], gale["reaction"]), (False, True))
            self.assertEqual((mend["heal"], ward["power"], lash["rank"]), (True, False, 2))
            self.assertEqual((spark["trick"], spark["cost"], spark["power"]), (True, 1, False))
            self.assertEqual((magic["track"], magic["max_power"], magic["ready"], magic["limit"]), ("wp", 3, 3, 6))

    def test_the_body_offers_its_dice_only_when_the_wp_are_nearly_spent(self):
        with self.session() as c:
            self.assertEqual(self.view(c)["body"], [])
            c.commit({"pc": {"wp": 2}})
            self.assertEqual(self.view(c)["body"], ["1d4", "1d6", "1d8", "1d10", "1d12", "1d20"])

    def test_a_hero_with_no_spells_has_no_magic_to_show(self):
        with self.session() as c:
            c.commit({"pc": {"spells": {"remove": list(c.state["pc"]["spells"])}}})
            self.assertIsNone(self.view(c))
