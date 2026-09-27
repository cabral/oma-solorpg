"""Gated exits, travel time, and clocks that run only while something holds and change
the world at their stages. These are what a written dungeon needs: stairs that unfold
once a puzzle is solved, and a tower that sinks on a timer."""

import copy

from helpers import DRAGONBANE, FIXTURES, RAGNA, RED_TUSK, CampaignTest, Dice

from solo import SoloError, campaign, cli, packs

GATES = FIXTURES / "gates"


class GateTest(CampaignTest):
    adventure = GATES


class GatedExits(GateTest):
    def test_a_closed_way_refuses_until_the_story_opens_it(self):
        with self.session() as c:
            with self.assertRaisesRegex(SoloError, "isn't open yet .*fact.hall.stairs_open"):
                c.move("stairs")
            c.commit({"note": "two plates at once: stairs unfold", "facts": {"hall.stairs_open": True}})
            c.move("stairs")
            self.assertEqual(c.state["scene"], "stairs")

    def test_a_forced_move_goes_through_a_closed_way(self):
        with self.session() as c:
            c.move("stairs", force="the player climbed the outside wall")
            self.assertEqual(c.state["scene"], "stairs")

    def test_the_gm_sees_closed_ways_apart_and_the_player_never_does(self):
        with self.session() as c:
            digest = cli.scene_digest(c)
            open_part, closed_part = digest.split("## Closed for now")
            self.assertNotIn("stairs:", open_part.split("## Exits")[1])
            self.assertIn("stairs: Stairs that unfold from the ceiling; opens when fact.hall.stairs_open", closed_part)
            # The Book's map counts only ways that are open, so it can't give the stairs away.
            [hall] = campaign.route(c.adventure, c.state)
            self.assertEqual(hall["unexplored"], 1)
            self.assertNotIn("stairs", str(c.state["log"]))

    def test_a_word_of_a_label_takes_the_one_way_it_fits(self):
        with self.session() as c:
            c.move("the")  # "Down the well", or the stairs that haven't unfolded: only the well is there
            self.assertEqual(c.state["scene"], "well")
        with self.session() as c:
            c.move("hall", force="back up the rope")
            c.adventure["scenes"]["hall"]["exits"]["stairs"] = "Down the stairs"
            with self.assertRaisesRegex(SoloError, r"'down' could be stairs \(Down the stairs\), well \(Down the well\): name the exit"):
                c.move("down")
            self.assertEqual(c.state["scene"], "hall")
            c.move("Down the well")  # a whole label is never in doubt
            self.assertEqual(c.state["scene"], "well")

    def test_an_unknown_exit_lists_only_open_ways(self):
        with self.session() as c:
            with self.assertRaisesRegex(SoloError, r"exits: well \(Down the well\)$"):
                c.move("attic")

    def test_validate_reads_exit_conditions_and_time(self):
        with self.session() as c:
            adventure = copy.deepcopy(c.adventure)
            system = c.system
        adventure["scenes"]["hall"]["exits"]["stairs"] = {"label": "x", "when": "clock.nope >= 1", "time": {"fortnight": 1}}
        problems = packs.validate(system, adventure)
        self.assertIn("scene hall exit stairs: unknown clock nope", problems)
        self.assertTrue(any("unknown time unit fortnight" in p for p in problems))


class TravelTime(GateTest):
    def test_moves_take_the_adventures_time_unless_the_exit_says(self):
        with self.session() as c:
            c.move("well")
            self.assertEqual(c.state["time"], 21600)  # the well: a shift
            c.move("hall")
            self.assertEqual(c.state["time"], 21600 + 900)  # the default: a stretch

    def test_travel_time_ticks_clocks_and_the_digest_says_what_a_way_takes(self):
        with self.session() as c:
            self.assertIn("well: Down the well (takes 1 shift)", cli.scene_digest(c))
            c.move("well")
            self.assertEqual(c.state["clocks"]["hours"]["value"], 4)

    def test_a_forced_move_takes_no_time(self):
        with self.session() as c:
            c.move("well", force="swept away")
            self.assertEqual(c.state["time"], 0)

    def test_the_log_rebuilds_the_same_time(self):
        with self.session() as c:
            c.move("well")
            c.move("hall")
            self.assertEqual(campaign.fold(c.system, c.adventure, c.events), c.state)


class Stages(GateTest):
    def test_a_stage_sets_facts_that_close_ways_and_the_player_feels_its_text(self):
        with self.session() as c:
            c.commit({"facts": {"hall.stairs_open": True}})
            c.move("stairs")  # 1 stretch: hours 1
            event = c.commit({"time": {"stretch": 1}})  # hours 2: the stage
            self.assertTrue(c.state["facts"]["hall.flooded"])
            with self.assertRaisesRegex(SoloError, "isn't open yet"):
                c.move("hall")
            stage = next(e for e in c.events if e["type"] == "stage")
            self.assertEqual(stage["cause"], next(e["seq"] for e in c.events if e["type"] == "clock" and e["value"] == 2))
            self.assertGreater(stage["seq"], event["seq"])
            self.assertIn({"seq": stage["seq"], "kind": "event", "text": "The floor shakes."}, c.state["story"])

    def test_the_gm_note_reaches_the_gm_and_never_the_player(self):
        with self.session() as c:
            c.commit({"time": {"stretch": 2}})
            note = "The hall floods: it can't be entered any more."
            self.assertNotIn(note, str(c.state["log"]) + str(c.state["story"]))
            stage = next(e for e in c.events if e["type"] == "stage")
            self.assertIn(f"[for the GM: {note}]", campaign.gm_line(stage))
            self.assertIn(f"Reached 2: {note}", cli.scene_digest(c))

    def test_a_while_clock_waits_then_counts_from_when_it_started(self):
        with self.session() as c:
            c.commit({"time": {"round": 3}})
            self.assertEqual(c.state["clocks"]["collapse"]["value"], 0)  # not sinking: rounds don't count
            self.assertIn("not running (runs while fact.tower.sinking)", cli.scene_digest(c))
            # Four stretches pass: the last one's stage sets the tower sinking. Its fact ticks the
            # collapse once, and the ninety rounds of that stretch don't count: it hadn't begun.
            c.commit({"time": {"stretch": 4}})
            self.assertTrue(c.state["facts"]["tower.sinking"])
            self.assertEqual(c.state["clocks"]["collapse"]["value"], 1)
            self.assertTrue(c.state["facts"]["hall.gone"])
            c.commit({"time": {"round": 1}})
            self.assertEqual(c.state["clocks"]["collapse"]["value"], 2)

    def test_a_hidden_clocks_silent_stage_stays_out_of_the_book(self):
        with self.session() as c:
            c.commit({"time": {"stretch": 4}})
            silent = [e for e in c.events if e["type"] == "stage" and e["clock"] == "collapse"]
            self.assertEqual(len(silent), 1)
            self.assertTrue(next(e for e in c.state["log"] if e["seq"] == silent[0]["seq"])["hidden"])

    def test_fight_rounds_pass_game_time(self):
        # The gates have no foes, so this fight is Red Tusk's.
        root = campaign.create(self.tmp / "rt", DRAGONBANE, RED_TUSK, RAGNA)
        with campaign.session(root) as c:
            c.fight(["cultist"], rng=Dice(1, 1))
            c.next_round(rng=Dice(1, 1))
            self.assertEqual(c.state["time"], 10)
            self.assertEqual(campaign.fold(c.system, c.adventure, c.events), c.state)

    def test_validate_checks_stages_and_while(self):
        with self.session() as c:
            adventure = copy.deepcopy(c.adventure)
            system = c.system
        adventure["clocks"]["hours"]["stages"].append({"at": 9, "text": "x"})
        adventure["clocks"]["hours"]["stages"].append({"at": 1})
        adventure["clocks"]["collapse"]["while"] = "clock.nope"
        problems = packs.validate(system, adventure)
        self.assertIn("clock hours: a stage needs at = a segment from 1 to 4", problems)
        self.assertIn("clock hours: stage 1 does nothing (give it text, note, facts or clock)", problems)
        self.assertIn("clock collapse while: unknown clock nope", problems)
        self.assertEqual(packs.validate(system, c.adventure), [])


class Monsters(CampaignTest):
    """Red Tusk's tentacle stands in for a monster; its stats are adjusted in memory."""

    def monster(self, c, **stats):
        c.adventure["npcs"]["tentacle"]["stats"].update(stats)

    def test_ferocity_is_how_many_initiative_cards_a_monster_draws(self):
        with self.session() as c:
            self.monster(c, ferocity=2)
            fight = c.fight(["tentacle"], rng=Dice(2, 1, 1))  # Ragna 2; the tentacle 1 and 3
            self.assertEqual([f["card"] for f in fight["order"]], [1, 2, 3])
            self.assertEqual(c.to_act(), ["Tentacle from the pool", "Ragna", "Tentacle from the pool"])
            c.enemy(rng=Dice(6))  # a result without damage: nothing incoming
            self.assertEqual(c.to_act(), ["Ragna", "Tentacle from the pool"])
            c.enemy(rng=Dice(6))
            self.assertEqual(c.to_act(), ["Ragna"])

    def test_monster_attacks_are_evaded_not_parried_unless_they_say_so(self):
        with self.session() as c:
            c.fight(["tentacle"], rng=Dice(1, 2))
            c.enemy(rng=Dice(1))
            self.assertFalse(c.state["combat"]["incoming"]["can_parry"])
            with self.assertRaisesRegex(SoloError, "can't be parried"):
                c.defend("parry")
            c.defend("evade", rng=Dice(1))
            c.adventure["tables"]["tentacle_attacks"]["results"][0]["parry"] = True
            c.enemy(rng=Dice(1))
            self.assertTrue(c.state["combat"]["incoming"]["can_parry"])

    def test_an_immune_foe_shrugs_off_weapons_and_the_gm_wounds_it_with_fire(self):
        with self.session() as c:
            self.monster(c, immune="magic and fire")
            c.fight(["tentacle"], rng=Dice(1, 2))
            c.attack(rng=Dice(3, 6, 6, 4))
            self.assertEqual(c.state["combat"]["foes"]["tentacle"]["hp"], 12)
            self.assertIn("no effect (only magic and fire can harm it)", c.state["log"][-1]["text"])
            wound = c.wound("tentacle", "2d6", why="the torch sets it alight", armor=False, rng=Dice(4, 3))
            self.assertEqual((wound["dealt"], wound["hp"]), (7, 5))
            self.assertEqual(c.state["story"][-1]["kind"], "hit")
            c.wound("tentacle", "1d6", why="burning oil", double=True, rng=Dice(2))  # 2 x2 - armor 2
            self.assertEqual(c.state["combat"]["foes"]["tentacle"]["hp"], 3)
            c.wound("tentacle", "all", why="the light turns it to stone")
            self.assertIsNone(c.state["combat"])  # the last foe down ends the fight
            self.assertEqual(campaign.fold(c.system, c.adventure, c.events), c.state)

    def test_a_wound_needs_a_reason(self):
        with self.session() as c:
            c.fight(["tentacle"], rng=Dice(1, 2))
            with self.assertRaisesRegex(SoloError, "say what does the harm"):
                c.wound("tentacle", "2", why=" ")

    def test_an_attack_that_ignores_armor(self):
        with self.session() as c:
            c.commit({"pc": {"items": {"add": ["Chainmail"]}}})
            c.adventure["tables"]["tentacle_attacks"]["results"][0]["armor"] = False
            c.fight(["tentacle"], rng=Dice(1, 2))
            c.enemy(rng=Dice(1))
            harm = c.defend("take", rng=Dice(3, 4))
            self.assertEqual((harm["armor"], harm["dealt"]), (0, 7))

    def test_a_hero_struck_down_after_attacking_rolls_against_death_next_round(self):
        with self.session() as c:
            c.fight(["tentacle"], rng=Dice(1, 2))
            c.attack(rng=Dice(19))  # a miss
            c.commit({"pc": {"hp": 0}})
            with self.assertRaisesRegex(SoloError, "already had their turn"):
                c.death_roll()
            c.next_round(rng=Dice(1, 2))
            c.death_roll(rng=Dice(5))
