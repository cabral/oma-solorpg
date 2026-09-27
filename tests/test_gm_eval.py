"""The GM play-test harness (tests/gm_eval), without a model: a stand-in GM plays the
turns, so the checks, the player's view and the report are tested for what they are."""

import json
import os
import sys
import unittest.mock
from pathlib import Path

from helpers import CampaignTest, Dice, DRAGONBANE, ROOT

sys.path.insert(0, str(ROOT / "tests" / "gm_eval"))
import harness  # noqa: E402

from solo import campaign  # noqa: E402

class Checks(CampaignTest):
    def test_hygiene_flags_bookkeeping_ids_and_a_missing_question(self):
        with self.session() as c:
            c.commit({"facts": {"hall.alarm": True}})
            kinds = [k for k, _ in harness.hygiene("::: gm\nI ran solo commit and hall.alarm is set.", c)]
            self.assertEqual(kinds.count("bookkeeping"), 3)
            self.assertIn("no_question", kinds)
            self.assertEqual(harness.hygiene("Rain on the road. The drums go on. What do you do?", c), [])

    def test_spoilers_wait_for_their_condition(self):
        forbid = [{"text": "Deep Mother", "unless": "visited.final_battle"}]
        with self.session() as c:
            self.assertEqual(len(harness.spoilers("The Deep Mother stirs!", c, forbid)), 1)
            for scene in ("gate", "hall", "cellar", "final_battle"):
                c.move(scene, rng=Dice(20, 20, 20))
            self.assertEqual(harness.spoilers("The Deep Mother stirs!", c, forbid), [])

    def test_a_round_where_no_foe_struck_back_is_flagged(self):
        events = [{"seq": 1, "type": "fight"}, {"seq": 2, "type": "check", "attack": {"target": "eel"}}, {"seq": 3, "type": "round"},
                  {"seq": 4, "type": "check", "attack": {"target": "eel"}}, {"seq": 5, "type": "enemy"}, {"seq": 6, "type": "fight_end"}]
        [problem] = harness.fight_checks(events)
        self.assertIn("#1", problem[1])

    def test_an_expected_event_can_be_a_commit_key(self):
        rule = {"event": "consequence"}
        with self.session() as c:
            self.assertFalse(harness._holds(rule, c))
            c.commit({"consequence": {"text": "Grukk remembers the hero's rudeness", "npc": "orc_leader"}})
            self.assertTrue(harness._holds(rule, c))

    def test_every_scenario_loads_and_its_conditions_read(self):
        for path in sorted((ROOT / "tests" / "gm_eval" / "scenarios").glob("*.toml")):
            with self.subTest(path.name):
                scenario = harness.load(str(path))
                for rule in scenario.get("expect", []) + scenario.get("forbid", []):
                    for condition in filter(None, [rule.get("when"), rule.get("unless")]):
                        campaign.packs.compile_condition(condition)

    def test_the_players_view_holds_nothing_hidden(self):
        with self.session() as c:
            c.commit({"time": {"shift": 1}})  # the ritual clock ticks, hidden
            c.threat("The warband wakes", threat_id="warband")
            view = harness.player_view(c, {"goal": "stop the orcs"}, 1)
        self.assertIn("Warband 1/6", view)
        self.assertNotIn("The ritual below", view)
        self.assertNotIn("Deep Mother", view)
        self.assertIn("Your goal: stop the orcs", view)

    def test_the_players_own_packs_are_seen_from_the_runs_home(self):
        own = self.tmp / "own"
        (own / "systems").mkdir(parents=True)
        (own / "systems" / "dragonbane").symlink_to(DRAGONBANE, target_is_directory=True)
        harness.link_own_packs(own, self.tmp / "run" / "home")
        harness.link_own_packs(own, self.tmp / "run" / "home")  # twice is fine
        self.assertEqual((self.tmp / "run" / "home" / "systems" / "dragonbane").resolve(), DRAGONBANE.resolve())


class Generated(CampaignTest):
    def test_a_scenario_can_play_a_campaign_rolled_for_it(self):
        own = self.tmp / "own"
        (own / "systems").mkdir(parents=True)
        (own / "systems" / "dragonbane").symlink_to(DRAGONBANE, target_is_directory=True)
        scenario = harness.load(str(ROOT / "tests" / "gm_eval" / "scenarios" / "generated-mission.toml"))
        with unittest.mock.patch.dict(os.environ, {"SOLO_HOME": str(own), "XDG_STATE_HOME": str(self.tmp / "state")}):
            root = harness.start(scenario, self.tmp / "campaign")
            with campaign.session(root) as c:
                self.assertEqual(c.state["scene"], "hub")
                self.assertIn("m1_w1", c.adventure["scenes"])  # published: the mission is in play
                self.assertEqual(c.problems, [])
            again = harness.roll_campaign(scenario)  # a second run finds it rolled already
        self.assertEqual(again, own / "adventures" / scenario["adventure"])


class Run(CampaignTest):
    def test_a_scripted_run_with_a_stand_in_gm(self):
        def stand_in(root, text=None, agent=None):
            with campaign.session(root) as c:
                if text and "gate" in text:
                    c.move("gate")
                answer = "The gate looms, two guards above it. What do you do?" if text else "Rain on the road. Do you go on?"
                c.say(text, "player") if text else None
                c.say(answer, "gm")
            return {"status": "done", "text": answer, "usage": {"model_calls": 2, "input_tokens": 900, "output_tokens": 40, "cost_usd": 0.01}}

        scenario = {"name": "stand-in", "adventure": "red-tusk", "character": "ragna", "max_turns": 3,
                    "player": {"mode": "scripted", "lines": ["I walk up to the gate."]},
                    "expect": [{"when": "visited.gate", "by_turn": 1}], "forbid": [{"text": "Deep Mother"}]}
        out = self.tmp / "run"
        own = self.tmp / "own"  # the player's library: the rules built from their book
        (own / "systems").mkdir(parents=True)
        (own / "systems" / "dragonbane").symlink_to(DRAGONBANE, target_is_directory=True)
        with unittest.mock.patch.dict(os.environ, {"SOLO_HOME": str(own)}), unittest.mock.patch.object(harness.gm, "turn", stand_in):
            report = harness.run(scenario, out, judge=False, log=lambda *_: None)
        self.assertEqual(report["totals"]["turns"], 2)  # the opening and the one scripted line
        self.assertEqual((report["totals"]["model_calls"], report["totals"]["cost_usd"]), (4, 0.02))
        self.assertTrue(report["expect"][0]["ok"])
        self.assertEqual(report["turns"][1]["events"][0].split(" ")[1:3], ["moved", "to"])
        saved = json.loads((out / "report.json").read_text())
        self.assertEqual(saved["final"]["scene"], "gate")
        self.assertIn("**PLAYER**", (out / "transcript.md").read_text())
        self.assertIn("## Expectations", (out / "report.md").read_text())
        self.assertIn("4 model calls, $0.02", (out / "report.md").read_text())
        self.assertTrue(Path(out / "campaign" / "events.jsonl").exists())


class Voice(CampaignTest):
    def test_narration_that_never_says_you_is_flagged(self):
        third = "Ragna trudges up the muddy road. " * 12 + "What does Ragna do?"
        with self.session() as c:
            self.assertIn("third_person", [k for k, _ in harness.hygiene(third, c)])
            self.assertNotIn("third_person", [k for k, _ in harness.hygiene(third.replace("Ragna trudges", "You trudge"), c)])

    def test_a_gm_message_recorded_twice_is_flagged(self):
        with self.session() as c:
            c.say("The drums go on. What do you do?", "gm")
            c.say("The drums go on.  What do you do?", "gm")
            report = harness.summarize({"name": "x", "adventure": "red-tusk"}, c, [], {})
        self.assertEqual(len(report["totals"]["play_problems"]), 1)

    def test_dice_written_into_the_story_are_flagged(self):
        with self.session() as c:
            kinds = [k for k, _ in harness.hygiene("You slip past (Sneaking, 4 vs 5, success). What now?", c)]
        self.assertIn("bookkeeping", kinds)
