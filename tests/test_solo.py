"""The solo tools a system pack can carry, the way Dragonbane's solo rules have them: a fortune
chart, inspiration tables, dragon and demon effects, a treasure deck, threats, NPC templates and
roles, searching and scavenging, and the solo hero's abilities, healing and rallying. Played on
the made-up test rules (tests/fixtures/house), so every text and number here is the fixture's."""

import io
import json
from contextlib import redirect_stdout

from helpers import BUNDLED, DRAGONBANE, RED_TUSK, CampaignTest, Dice

from solo import SoloError, campaign, cli, dice, packs


class Dice_(CampaignTest):
    def test_a_multiplier_scales_the_dice(self):
        self.assertEqual(dice.roll("2d6x10", Dice(3, 4))["total"], 70)
        self.assertEqual(dice.roll("1d6*5+2", Dice(2))["total"], 12)
        self.assertEqual(sorted(dice.outcomes("2d6×10"))[:3], [20, 30, 40])


class Tables(CampaignTest):
    def test_a_treasure_card_rolls_its_own_value(self):
        with self.session() as c:
            card = c.table("treasure", rng=Dice(7, 3, 4))  # the goblet: 2D6 x 5 silver
        self.assertEqual(card["text"], "Tin goblet, worth 35 silver")
        self.assertEqual(card["value"], 35)

    def test_a_card_with_a_choice_picks_it(self):
        with self.session() as c:
            card = c.table("treasure", rng=Dice(9, 4))  # the jewel
        self.assertEqual(card["text"], "Jewel: star opal (worth 90 gold)")

    def test_a_result_can_draw_from_another_table_and_roll_again(self):
        with self.session() as c:
            first = c.table("scavenge", rng=Dice(10, 5, 3, 2))  # a card, and again: nothing of note
        rolled = [e["text"] for e in c.events if e["type"] == "table"]
        self.assertEqual(rolled, ["A find from the treasure deck, and dig again", "3 gold coins", "Dust and old straw"])
        self.assertEqual(c.events[-1]["cause"], first["seq"])

    def test_every_table_validates(self):
        with self.session() as c:
            self.assertEqual(packs.validate(c.system), [])


class Fortune(CampaignTest):
    def test_a_question_reads_a_column_of_the_chart(self):
        with self.session() as c:
            answer = c.ask("Is the passage guarded?", rng=Dice(4))
            number = c.ask("How many orcs?", kind="number", rng=Dice(6))
        self.assertEqual((answer["roll"], answer["answer"]), (4, "Yes"))
        self.assertEqual((number["answer"], number["extreme"]), ("A horde", True))
        self.assertNotIn("random_event", answer)
        self.assertEqual(campaign.describe(number), 'asked "How many orcs?" (fortune, number, rolled 6): A horde (an extreme result, or a twist)')

    def test_tilting_the_scales_keeps_the_highest_or_lowest_of_two(self):
        with self.session() as c:
            likely = c.ask("Is the door unlocked?", likely="likely", rng=Dice(1, 5))
            unlikely = c.ask("Is the troll asleep?", likely="unlikely", rng=Dice(1, 5))
        self.assertEqual((likely["roll"], likely["answer"]), (5, "Yes"))
        self.assertEqual((unlikely["roll"], unlikely["answer"]), (1, "No, and worse"))

    def test_an_npc_question_reads_their_reaction_tilted_by_attitude(self):
        with self.session() as c:
            answer = c.ask("How does Grukk take it?", npc="orc_leader", rng=Dice(2, 6))
        self.assertEqual((answer["kind"], answer["tilt"], answer["answer"]), ("reaction", "low", "Guarded"))

    def test_an_unknown_column_is_refused(self):
        with self.session() as c, self.assertRaisesRegex(SoloError, "fortune chart reads yes_no, number"):
            c.ask("Hmm?", kind="colour")

    def test_the_inspiration_table_gives_an_action_an_attribute_and_a_thing(self):
        with self.session() as c:
            event = c.meaning("What danger waits here?", rng=Dice(15, 15, 1))
        self.assertEqual(event["words"], ["Pray", "Quick", "Anchor"])

    def test_no_scene_checks_by_the_book(self):
        with self.session() as c:
            move = c.move("gate", rng=Dice(15))  # only the voice rolls
        self.assertIsNone(move.get("scene_check"))
        self.assertNotIn("Chaos factor", cli.scene_digest(c))


class Effects(CampaignTest):
    def test_a_dragon_outside_a_fight_rolls_its_effect_and_in_a_fight_it_doesnt(self):
        with self.session() as c:
            c.check("awareness", rng=Dice(1, 6))
            self.assertEqual(c.events[-1]["text"], "It works better than it had any right to")
            c.fight(["cultist"], rng=Dice(1, 1))
            c.check("awareness", rng=Dice(1))
            self.assertEqual(c.events[-1]["type"], "check")


class Threats(CampaignTest):
    def test_a_threat_starts_at_one_advances_with_time_and_comes_to_pass_at_six(self):
        with self.session() as c:
            c.threat("A trio of goblin scouts spring an ambush", threat_id="goblins", label="Goblin scouts")
            self.assertEqual(c.state["clocks"]["goblins"]["label"], "Goblin scouts")
            self.assertEqual(c.state["clocks"]["goblins"]["value"], 1)
            c.rest("stretch", rng=Dice(1, 1))  # a stretch: the threat advances
            self.assertEqual(c.state["clocks"]["goblins"]["value"], 2)
            c.commit({"clock": {"goblins": "+2"}})  # a Demon on a task against time
            self.assertIn("goblins): 4/6, a threat: at 6 it comes to pass", cli.scene_digest(c))
            c.commit({"time": {"stretch": 2}})
            self.assertTrue(c.state["clocks"]["goblins"]["stopped"])  # it happened; it's gone
            self.assertIn("the threat comes to pass: A trio of goblin scouts spring an ambush", [s.get("text") for s in c.state["story"]])
            self.assertEqual(campaign.fold(c.system, c.adventure, c.events), c.state)

    def test_a_threat_inherent_to_the_place_starts_over(self):
        with self.session() as c:
            c.threat("Magma bursts into the scene", threat_id="magma", recurring=True)
            c.commit({"clock": {"magma": "+5"}})
            self.assertEqual(c.state["clocks"]["magma"]["value"], 1)
            self.assertFalse(c.state["clocks"]["magma"]["stopped"])

    def test_a_random_threat_and_ending_one(self):
        with self.session() as c:
            c.threat(threat_id="random", rng=Dice(2))
            self.assertIn("riddled with old shafts", c.state["clocks"]["random"]["threat"]["text"])
            self.assertEqual(c.state["clocks"]["random"]["label"], "Random")  # the table shows a short name
            c.end_threat("random")
            self.assertTrue(c.state["clocks"]["random"]["stopped"])
            with self.assertRaisesRegex(SoloError, "no threat 'random'"):
                c.end_threat("random")

    def test_advancing_takes_the_only_threat_and_never_an_adventure_clock(self):
        with self.session() as c:
            with self.assertRaisesRegex(SoloError, "which threat\\? none is looming"):
                c.advance_threat()
            c.threat("A trio of goblin scouts spring an ambush", threat_id="goblins")
            c.advance_threat(by=2)
            self.assertEqual(c.state["clocks"]["goblins"]["value"], 3)
            with self.assertRaisesRegex(SoloError, "no threat 'dark_ritual'; threats: goblins"):
                c.advance_threat("dark_ritual")  # the hidden ritual moves by its own triggers
            c.threat("Magma bursts into the scene", threat_id="magma")
            with self.assertRaisesRegex(SoloError, "which threat\\? goblins, magma"):
                c.end_threat()
            c.end_threat("magma")
            c.end_threat()
            self.assertTrue(c.state["clocks"]["goblins"]["stopped"])

    def test_a_failed_check_reminds_the_gm_of_the_threat_it_may_let_in(self):
        with self.session() as c:
            passed = c.check("awareness", rng=Dice(3))
            self.assertIsNone(cli._threat_opening(c, passed))
            c.threat("A trio of goblin scouts spring an ambush", threat_id="goblins")
            failed = c.check("sneaking", rng=Dice(19))
            self.assertEqual(cli._threat_opening(c, failed), "if the failure stands and gives it an opening: solo threat advance goblins")
            self.assertIsNone(cli._threat_opening(c, c.check("awareness", rng=Dice(3))))


class Searching(CampaignTest):
    def test_a_search_takes_a_stretch_then_spot_hidden_finds_by_the_table(self):
        with self.session() as c:
            c.threat("Traps are sprung", threat_id="traps")
            c.search(rng=Dice(3, 6, 5, 2))  # success: a hidden find, one card
            self.assertEqual(c.state["time"], 900)
            self.assertEqual(c.state["clocks"]["traps"]["value"], 2)
            texts = [e.get("text") for e in c.events if e["type"] == "table"]
        self.assertEqual(texts, ["A loose stone with something behind it", "2 gold coins"])

    def test_the_gm_hears_about_the_stretch_the_search_took(self):
        with self.session() as c:
            c.threat("Traps are sprung", threat_id="traps")
        with self.session() as c:  # one command: its report says all it did, the stretch first
            event = c.search(rng=Dice(3, 6, 5, 2))
            out = io.StringIO()
            with redirect_stdout(out):
                cli._report(c, event)
        report = json.loads(out.getvalue())
        self.assertTrue(report["summary"].startswith("Spot hidden: 3 vs"))
        self.assertEqual(report["then"], ["a careful search; 15 min pass", "Traps 2/6",
                                          "Search (6): A loose stone with something behind it", "Treasure deck (5): 2 gold coins"])

    def test_a_dragon_rolls_the_table_twice_and_a_failure_finds_nothing(self):
        with self.session() as c:
            c.search(rng=Dice(1, 4, 5))  # the alcove, twice: the player picks
            self.assertEqual(len([e for e in c.events if e["type"] == "table"]), 2)
            c.search(rng=Dice(18))
            self.assertEqual(len([e for e in c.events if e["type"] == "table"]), 2)

    def test_scavenging_again_takes_a_stretch(self):
        with self.session() as c:
            c.scavenge(rng=Dice(5, 4))
            self.assertEqual(c.events[-1]["text"], "Odds and ends: a torch")
            c.scavenge(again=True, rng=Dice(3))
        self.assertEqual(c.state["time"], 900)


class NPCs(CampaignTest):
    def test_an_ad_libbed_minion_fights_from_its_template(self):
        with self.session() as c:
            c.commit({"npc": {"slime_bug": {"name": "Slime bug", "template": "minion", "attacker": "ranged"}}})
            fight = c.fight(["slime_bug"], rng=Dice(1, 2))
            self.assertEqual((fight["foes"]["slime_bug"]["hp"], fight["foes"]["slime_bug"]["armor"]), (10, 0))
            shot = c.enemy(rng=Dice(2, 7))  # a shot: skill 11, a hit
            self.assertEqual(shot["incoming"]["damage"], "2d4")
            self.assertEqual(shot["text"], "Loose! The NPC shoots at you.")

    def test_a_volley_is_two_attacks_with_a_bane_on_one_action(self):
        with self.session() as c:
            c.commit({"npc": {"archer": {"name": "Archer", "template": "boss", "attacker": "ranged"}}})
            c.fight(["archer"], rng=Dice(1, 2))
            c.enemy(rng=Dice(5, 3, 18))  # two arrows: 3 and 18 with a bane, keep 18: a miss
            self.assertEqual(c.to_act(), ["Ragna", "Archer"])  # the second shot is still to come
            second = c.enemy(rng=Dice(2, 4))  # no new table roll: the same volley
            self.assertEqual(second["text"], c.events[-2]["text"])
            self.assertEqual(c.to_act(), ["Ragna"])

    def test_effects_are_for_the_gm_to_run(self):
        with self.session() as c:
            c.commit({"npc": {"brute": {"name": "Brute", "template": "boss", "attacker": "melee"}}})
            c.fight(["brute"], rng=Dice(1, 2))
            rage = c.enemy(rng=Dice(6))
        self.assertIsNone(rage.get("incoming"))
        self.assertIn("make a WIL roll or be scared", rage["text"])

    def test_a_bad_template_or_attacker_is_refused(self):
        with self.session() as c:
            with self.assertRaisesRegex(SoloError, "template must be one of minion, boss"):
                c.commit({"npc": {"x": {"name": "X", "template": "dragon"}}})
            with self.assertRaisesRegex(SoloError, "attacker must be one of melee, ranged, sneaky, magic"):
                c.commit({"npc": {"x": {"name": "X", "attacker": "bard"}}})


class SoloHero(CampaignTest):
    """The pre-made Ragna as the pack ships the sheet: Army of One, the solo rules' extra ability."""

    character = BUNDLED / "characters" / "ragna.toml"

    def sole_survivor(self):
        sheet = packs.load_data(self.character)
        sheet["abilities"] = ["Unforgiving", "Veteran", "Sole Survivor"]
        return campaign.create(self.tmp / "sole", DRAGONBANE, RED_TUSK, sheet)

    def test_army_of_one_draws_two_cards_and_attacks_twice_a_round(self):
        with self.session() as c:
            fight = c.fight(["cultist"], rng=Dice(1, 1, 1))  # Ragna 1 and 2, the cultist 3
            self.assertEqual([f["id"] for f in fight["order"]], ["pc", "pc", "cultist"])
            c.attack(rng=Dice(18))
            c.attack(rng=Dice(19))
            with self.assertRaisesRegex(SoloError, "already attacked this round"):
                c.attack(rng=Dice(3))
            self.assertEqual(c.to_act(), ["Cultist"])

    def test_sole_survivor_pushes_for_willpower_instead_of_a_condition(self):
        root = self.sole_survivor()
        with campaign.session(root) as c:
            c.check("awareness", rng=Dice(15))
            self.assertIn("Sole Survivor: pay 3 wp instead", cli._push_options(c, c.events[-1])["or"])
            pushed = c.push(sole_survivor=True, rng=Dice(2))
            self.assertEqual((c.state["pc"]["tracks"]["wp"]["value"], c.state["pc"]["conditions"]), (8, []))
            self.assertTrue(campaign.describe(pushed).endswith("; paid 3 WP"))

    def test_without_the_ability_there_is_no_paying_willpower(self):
        with self.session() as c:
            c.check("awareness", rng=Dice(15))
            with self.assertRaisesRegex(SoloError, "Sole Survivor"):
                c.push(sole_survivor=True)

    def test_tending_your_own_wounds_at_a_stretch_rest(self):
        with self.session() as c:
            c.commit({"pc": {"hp": "-10"}})
            c.rest("stretch", tend=True, rng=Dice(3, 5, 6, 2))  # HEALING 3 vs 4: 2D8 = 11; WP 1D8
            self.assertEqual(c.state["pc"]["tracks"]["hp"]["value"], 14)
            c.commit({"time": {"shift": 1}, "pc": {"hp": "-10"}})
            c.rest("stretch", tend=True, rng=Dice(18, 2, 2))  # a failed HEALING: the rest's own D8
            self.assertEqual(c.state["pc"]["tracks"]["hp"]["value"], 6)

    def test_rallying_alone_and_saving_your_own_life(self):
        with self.session() as c:
            c.commit({"pc": {"hp": 0}})
            with self.assertRaisesRegex(SoloError, "rally \\(solo rally\\)"):
                c.check("awareness")
            rally = c.rally(rng=Dice(4))  # PERSUASION 8, no bane
            self.assertTrue(rally["rallied"])
            c.check("awareness", rng=Dice(3))  # a rallied hero acts, still dying
            self.assertIsNotNone(c.state["pc"]["dying"])
            c.save_self(rng=Dice(2, 4))  # HEALING 4: saved, with D8 HP
            self.assertEqual((c.state["pc"]["dying"], c.state["pc"]["tracks"]["hp"]["value"]), (None, 4))
            self.assertEqual(campaign.fold(c.system, c.adventure, c.events), c.state)

    def test_a_new_hero_gets_one_more_heroic_ability_for_going_alone(self):
        from solo import creation
        sheet = creation.character(packs.load_system(DRAGONBANE), "human mage", seed=4)
        self.assertEqual(len([a for a in sheet["abilities"] if a in ("Army of One", "Sole Survivor")]), 1)
